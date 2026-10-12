"""Background jobs for the web UI: one thread per job, live log + progress, cancel, history kept across restarts.

Long or memory-heavy work (analysis, Vast render) runs as a child process so the server stays responsive; a cancelled
child gets SIGINT first, which lets `tracktake remote run` reach its `finally` and free the rented GPUs.
"""

from __future__ import annotations

import json
import re
import signal
import subprocess
import threading
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tracktake.project import PROJECTS


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
    log: deque = field(default_factory=lambda: deque(maxlen=500))
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    proc: subprocess.Popen | None = field(default=None, repr=False)
    params: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "project": self.project, "status": self.status, "title": self.title,
                "params": self.params,
                "progress": self.progress, "message": self.message, "started": self.started,
                "finished": self.finished, "log_tail": list(self.log)[-40:]}


class Context:
    """What a job function gets: logging, progress, cancellation and a streaming subprocess runner."""

    def __init__(self, job: Job, manager: JobManager):
        self.job, self.manager = job, manager

    def log(self, line: str) -> None:
        for part in str(line).rstrip().splitlines():
            self.job.log.append(part)
            if part.strip():
                self.job.message = part.strip()[:300]

    def progress(self, done: int, total: int) -> None:
        self.job.progress = {"done": done, "total": total}

    def cancelled(self) -> bool:
        return self.job.cancel_event.is_set()

    def check(self) -> None:
        if self.cancelled():
            raise Cancelled("cancelled")

    def run(self, cmd: list[str], cwd: Path | None = None, parse: Callable[[str], None] | None = None) -> None:
        self.check()
        self.log("$ " + " ".join(str(c) for c in cmd[:8]) + (" ..." if len(cmd) > 8 else ""))
        proc = subprocess.Popen([str(c) for c in cmd], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, env=_child_env())
        self.job.proc = proc
        assert proc.stdout is not None
        for line in proc.stdout:
            self.log(line)
            if parse:
                parse(line)
        code = proc.wait()
        self.job.proc = None
        if self.cancelled():
            raise Cancelled("cancelled")
        if code != 0:
            raise RuntimeError(f"exit {code}: {self.job.message}")


def _child_env() -> dict:
    import os

    return os.environ | {"PYTHONUNBUFFERED": "1"}


class JobManager:
    def __init__(self, history: Path | None = None):
        self.history = history or PROJECTS / "_jobs.json"
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()
        self._load()

    def submit(self, kind: str, project: str, title: str, fn: Callable[[Context], None],
               params: dict | None = None) -> Job:
        with self.lock:
            busy = [j for j in self.jobs.values() if j.project == project and j.kind == kind
                    and j.status in ("queued", "running")]
            if busy:
                raise Conflict(f"{kind} is already running for {project}")
            job = Job(uuid.uuid4().hex[:12], kind, project, title, params=params or {})
            self.jobs[job.id] = job
        threading.Thread(target=self._run, args=(job, fn), daemon=True).start()
        return job

    def _run(self, job: Job, fn: Callable[[Context], None]) -> None:
        job.status, job.started = "running", _now()
        self._save()
        ctx = Context(job, self)
        try:
            fn(ctx)
            job.status = "cancelled" if job.cancel_event.is_set() else "done"
            if job.status == "done" and job.progress:
                job.progress["done"] = max(job.progress["done"], 0)
        except Cancelled:
            job.status = "cancelled"
            ctx.log("cancelled")
        except Exception as e:  # noqa: BLE001 - the job reports the error, the server keeps running
            job.status = "failed"
            ctx.log(f"ERROR: {e}")
        job.finished = _now()
        self._save()

    def cancel(self, job_id: str) -> Job:
        job = self.jobs[job_id]
        job.cancel_event.set()
        if job.proc and job.proc.poll() is None:
            job.proc.send_signal(signal.SIGINT)  # remote run frees its GPUs in `finally`
            threading.Timer(120, lambda p=job.proc: p.poll() is None and p.terminate()).start()
        return job

    def list(self, project: str | None = None) -> list[Job]:
        jobs = [j for j in self.jobs.values() if project is None or j.project == project]
        return sorted(jobs, key=lambda j: j.started or "~", reverse=True)

    def _save(self) -> None:
        with self.lock:
            done = [j.to_dict() | {"log_tail": list(j.log)[-200:]} for j in self.jobs.values()][-100:]
        self.history.parent.mkdir(parents=True, exist_ok=True)
        self.history.write_text(json.dumps(done, ensure_ascii=False))

    def _load(self) -> None:
        if not self.history.exists():
            return
        for d in json.loads(self.history.read_text()):
            job = Job(d["id"], d["kind"], d["project"], d["title"], d["status"], d.get("progress"), d.get("message", ""),
                      d.get("started"), d.get("finished"), params=d.get("params") or {})
            job.log.extend(d.get("log_tail", []))
            if job.status in ("queued", "running"):
                job.status, job.message = "failed", "interrupted: the server was restarted"
            self.jobs[job.id] = job


CLIP_PROGRESS = re.compile(r"(w\d+) (\d+)/(\d+)")


def clip_progress(ctx: Context) -> Callable[[str], None]:
    """Parse `clips codex: w1 10/23, w2 9/22 (...)` lines of `tracktake remote run` into one progress bar."""

    def parse(line: str) -> None:
        if line.startswith("clips "):
            parts = CLIP_PROGRESS.findall(line)
            if parts:
                ctx.progress(sum(int(d) for _, d, _ in parts), sum(int(t) for _, _, t in parts))

    return parse
