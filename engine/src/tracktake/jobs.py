"""Background jobs for the web UI that survive the server: each job is its own process in its own session.

The server only starts a job, reads its state and signals it. A job is a record `<id>.json` (status, progress,
params) plus a log `<id>.log` in `data/projects/_jobs/`; the worker process (`python -m tracktake.jobs run <dir> <id>`)
imports the job's target function and writes both while it runs. Restarting or crashing the server therefore never
stops an analysis, a keyframe batch or a Vast render; the new server simply reads the records again.
Cancelling sends SIGINT to the job's whole process group (its tools included), so `tracktake remote run` still
reaches its `finally` and frees the rented GPUs; SIGTERM follows if it has not ended after 2 minutes.
"""

from __future__ import annotations

import importlib
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tracktake.project import PROJECTS

ENGINE = Path(__file__).resolve().parents[2]
ACTIVE = ("queued", "running")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Conflict(RuntimeError):
    pass


class Cancelled(RuntimeError):
    pass


@dataclass
class Job:
    id: str
    kind: str
    project: str
    title: str  # English fallback; the UI builds a localized title from `kind` + `params`
    status: str = "queued"
    progress: dict | None = None
    message: str = ""
    started: str | None = None
    finished: str | None = None
    params: dict = field(default_factory=dict)  # shown to the UI (counts, stage, run id)
    target: str = ""  # "module:function" run as function(ctx, project, **args)
    args: dict = field(default_factory=dict)
    pid: int = 0  # the worker; also its process group
    created: str = field(default_factory=_now)
    root: str = ""  # the project's folder, so the worker needs no lookup

    def to_dict(self, log_tail: list[str] | None = None) -> dict:
        return {"id": self.id, "kind": self.kind, "project": self.project, "status": self.status, "title": self.title,
                "params": self.params, "progress": self.progress, "message": self.message, "started": self.started,
                "finished": self.finished, "log_tail": log_tail or []}


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # a zombie (finished, not yet reaped by its parent) counts as gone
    r = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False)
    return not r.stdout.strip().startswith("Z")


class Store:
    """The job records on disk."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, job_id: str) -> Path:
        if not re.fullmatch(r"[0-9a-f]{12}", job_id):
            raise KeyError(job_id)
        return self.root / f"{job_id}.json"

    def log_path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.log"

    def read(self, job_id: str) -> Job:
        path = self.path(job_id)
        if not path.exists():
            raise KeyError(job_id)
        return Job(**json.loads(path.read_text()))

    def write(self, job: Job) -> None:
        tmp = self.root / f".{job.id}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(asdict(job), ensure_ascii=False))
        tmp.replace(self.path(job.id))

    def tail(self, job_id: str, n: int = 40) -> list[str]:
        path = self.log_path(job_id)
        if not path.exists():
            return []
        with path.open("rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 64 * 1024))
            lines = f.read().decode(errors="replace").splitlines()
        return [ln for ln in lines if ln.strip()][-n:]

    def all(self) -> list[Job]:
        out = []
        for path in self.root.glob("*.json"):
            try:
                out.append(Job(**json.loads(path.read_text())))
            except (OSError, ValueError, TypeError):
                continue
        return out


class JobManager:
    def __init__(self, root: Path | None = None):
        self.store = Store(root or PROJECTS / "_jobs")
        self.lock = threading.Lock()
        self._migrate_old_history()

    # -------------------------------------------------------------- server side
    def submit(self, kind: str, project: str, title: str, target: str, args: dict | None = None,
               params: dict | None = None) -> Job:
        with self.lock:
            busy = [j for j in self.list(project) if j.kind == kind and j.status in ACTIVE]
            if busy:
                raise Conflict(f"{kind} is already running for {project}")
            from tracktake import project as projects

            job = Job(uuid.uuid4().hex[:12], kind, project, title, params=params or {}, target=target,
                      args=args or {}, root=str(projects.get(project).root))
            self.store.write(job)
            with self.store.log_path(job.id).open("ab") as log:
                proc = subprocess.Popen([sys.executable, "-m", "tracktake.jobs", "run", str(self.store.root), job.id],
                                        cwd=ENGINE, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                        start_new_session=True, env=_child_env())
            threading.Thread(target=proc.wait, daemon=True).start()  # reap it when it ends, no zombie
            job.pid = proc.pid  # the worker records its own pid; this copy is only for the caller
            return job

    def get(self, job_id: str) -> Job:
        job = self.store.read(job_id)
        if job.status in ACTIVE and job.pid and not _alive(job.pid):
            job = self.store.read(job_id)  # it may have just finished and written its final state
            if job.status in ACTIVE:
                job.status, job.finished = "failed", _now()
                job.message = job.message or "the job process stopped unexpectedly"
                self.store.write(job)
        return job

    def view(self, job: Job) -> dict:
        return job.to_dict(self.store.tail(job.id))

    def list(self, project: str | None = None, limit: int = 100) -> list[Job]:
        jobs = [self.get(j.id) if j.status in ACTIVE else j for j in self.store.all()
                if project is None or j.project == project]
        return sorted(jobs, key=lambda j: j.started or j.created, reverse=True)[:limit]

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job.status in ACTIVE and job.pid:
            self.store.root.joinpath(f"{job_id}.cancel").touch()
            try:
                os.killpg(job.pid, signal.SIGINT)  # remote run frees its GPUs in `finally`
            except ProcessLookupError:
                pass
            threading.Timer(120, _terminate, args=(job.pid,)).start()
        return self.get(job_id)

    def _migrate_old_history(self) -> None:
        old = self.store.root.parent / "_jobs.json"
        if not old.exists():
            return
        for d in json.loads(old.read_text()):
            job = Job(d["id"], d["kind"], d["project"], d["title"], d["status"], d.get("progress"),
                      d.get("message", ""), d.get("started"), d.get("finished"), d.get("params") or {})
            if job.status in ACTIVE:
                job.status, job.message = "failed", "interrupted: the server was restarted"
            if not self.store.path(job.id).exists():
                self.store.write(job)
                self.store.log_path(job.id).write_text("\n".join(d.get("log_tail", [])) + "\n")
        old.rename(old.with_suffix(".json.migrated"))


def _terminate(pid: int) -> None:
    if _alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass


def _child_env() -> dict:
    return os.environ | {"PYTHONUNBUFFERED": "1"}


# ------------------------------------------------------------------ worker side

class Context:
    """What a job function gets: logging, progress, cancellation and a streaming subprocess runner."""

    def __init__(self, job: Job, store: Store):
        self.job, self.store = job, store
        self.cancel_event = threading.Event()
        self._log = store.log_path(job.id).open("a", encoding="utf-8", buffering=1)
        self._saved = 0.0
        self._lock = threading.Lock()

    def save(self, force: bool = False) -> None:
        """Write the record; log lines alone are throttled to twice a second."""
        with self._lock:
            if force or time.monotonic() - self._saved > 0.5:
                self.store.write(self.job)
                self._saved = time.monotonic()

    def log(self, line: str) -> None:
        for part in str(line).rstrip().splitlines():
            self._log.write(part + "\n")
            if part.strip():
                self.job.message = part.strip()[:300]
        self.save()

    def progress(self, done: int, total: int) -> None:
        self.job.progress = {"done": done, "total": total}
        self.save(force=True)

    def cancelled(self) -> bool:
        return self.cancel_event.is_set() or self.store.root.joinpath(f"{self.job.id}.cancel").exists()

    def check(self) -> None:
        if self.cancelled():
            raise Cancelled("cancelled")

    def run(self, cmd: list, cwd: Path | None = None, parse: Callable[[str], None] | None = None) -> None:
        self.check()
        self.log("$ " + " ".join(str(c) for c in cmd[:8]) + (" ..." if len(cmd) > 8 else ""))
        proc = subprocess.Popen([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, text=True, bufsize=1, env=_child_env())
        assert proc.stdout is not None
        for line in proc.stdout:
            self.log(line)
            if parse:
                parse(line)
        code = proc.wait()
        if self.cancelled():
            raise Cancelled("cancelled")
        if code != 0:
            raise RuntimeError(f"exit {code}: {self.job.message}")


def run_worker(root: Path, job_id: str) -> int:
    from tracktake import project

    store = Store(root)
    job = store.read(job_id)
    ctx = Context(job, store)
    # SIGINT reaches the whole group (child tools too); here it only flags the job, children handle their own
    signal.signal(signal.SIGINT, lambda *_: ctx.cancel_event.set())
    signal.signal(signal.SIGTERM, lambda *_: (ctx.cancel_event.set(), sys.exit(143)))
    job.status, job.started, job.pid = "running", _now(), os.getpid()
    ctx.save(force=True)
    try:
        module, name = job.target.split(":")
        fn = getattr(importlib.import_module(module), name)
        p = project.Project(Path(job.root)) if job.root else project.get(job.project)
        fn(ctx, p, **job.args)
        job.status = "cancelled" if ctx.cancelled() else "done"
    except Cancelled:
        job.status = "cancelled"
        ctx.log("cancelled")
    except BaseException as e:  # noqa: BLE001 - the job reports the error and ends
        job.status = "cancelled" if ctx.cancelled() else "failed"
        ctx.log(f"ERROR: {e}")
    job.finished = _now()
    ctx.save(force=True)
    store.root.joinpath(f"{job_id}.cancel").unlink(missing_ok=True)
    return 0


CLIP_PROGRESS = re.compile(r"(\S+) (\d+)/(\d+)")


def clip_progress(ctx: Context) -> Callable[[str], None]:
    """Parse `clips codex: w1 10/23, w2 9/22 (...)` lines of `tracktake remote run` into one progress bar."""

    def parse(line: str) -> None:
        if line.startswith("clips "):
            parts = CLIP_PROGRESS.findall(line.split(":", 1)[1])
            if parts:
                ctx.progress(sum(int(d) for _, d, _ in parts), sum(int(t) for _, _, t in parts))

    return parse


def selftest(ctx: Context, p, seconds: float = 0.2, fail: bool = False) -> None:
    """A tiny job for tests: progress, a log line, an optional error; stops early when cancelled."""
    ctx.log("selftest started")
    steps = max(1, int(seconds / 0.05))
    for i in range(steps):
        ctx.check()
        ctx.progress(i + 1, steps)
        time.sleep(0.05)
    if fail:
        raise RuntimeError("selftest failure")


if __name__ == "__main__" and len(sys.argv) == 4 and sys.argv[1] == "run":
    sys.exit(run_worker(Path(sys.argv[2]), sys.argv[3]))
