"""Run the GPU-heavy part of a music video entirely on Vast workers; the Mac only sends inputs and fetches results.

Flow for one keyframe set (codex = keyframes made on the Mac, comfy = Z-Image keyframes made on the workers):
  push code + project -> each worker generates its slice of clips against its OWN ComfyUI (no tunnel, so a dropped
  connection on the Mac cannot break it) -> followers copy their clips to the leader of their format -> leaders
  render 16:9 and 9:16 in parallel -> the Mac downloads the finished videos.
Jobs run under nohup on the workers; the Mac only polls with short ssh calls.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from tracktake.config import REPO_ROOT, VastSettings
from tracktake.vast import State, ssh_base

REMOTE = "/workspace/tracktake"
PROJECT = f"{REMOTE}/project"
FULL = f"{PROJECT}/full"
LOCAL_COMFY = "http://127.0.0.1:18188"
PY = f"{REMOTE}/py"  # wrapper written by tracktake_runtime.sh: the ComfyUI venv interpreter
FORMAT_OF = {"landscape": "16x9", "portrait": "9x16"}
ORIENTS = ("landscape", "portrait")
Log = Callable[[str], None]


@dataclass
class Assignment:
    worker: State
    orients: tuple[str, ...]  # what this worker generates
    shots: list[str]
    leader_of: str = ""  # "landscape"/"portrait" when this worker renders that format; "both" with one worker
    followers: list[State] = field(default_factory=list)


def plan(shots: list[dict], workers: list[State], orients: tuple[str, ...] = ORIENTS) -> list[Assignment]:
    """Split the job: workers divided between the orientations (all of them for a one-orientation project), shots
    spread by duration (longest first onto the least loaded worker). The first worker of each group renders."""
    if not workers:
        raise ValueError("no workers")
    if not orients or any(o not in FORMAT_OF for o in orients):
        raise ValueError(f"orientations must be some of {ORIENTS}")
    if len(workers) == 1 and len(orients) == 2:
        return [Assignment(workers[0], orients, [s["id"] for s in shots], "both")]
    groups = [(orients[0], workers)] if len(orients) == 1 else \
        [(orients[0], workers[:(len(workers) + 1) // 2]), (orients[1], workers[(len(workers) + 1) // 2:])]
    out: list[Assignment] = []
    for orient, group in groups:
        load = {w.name: 0.0 for w in group}
        slices: dict[str, list[str]] = {w.name: [] for w in group}
        for s in sorted(shots, key=lambda s: s["end"] - s["start"], reverse=True):
            name = min(load, key=load.get)
            slices[name].append(s["id"])
            load[name] += s["end"] - s["start"]
        order = [s["id"] for s in shots]
        for i, w in enumerate(group):
            out.append(Assignment(w, (orient,), sorted(slices[w.name], key=order.index),
                                  orient if i == 0 else "", group[1:] if i == 0 else []))
    return out


# ---------------------------------------------------------------- ssh helpers

def ssh(state: State, s: VastSettings, command: str, *, check: bool = True, stdin=None, timeout: float = 600) -> str:
    r = subprocess.run([*ssh_base(state, s, connect_timeout=20), command],
                       stdin=subprocess.DEVNULL if stdin is None else stdin, capture_output=True,
                       text=stdin is None, timeout=timeout, check=False)
    out = r.stdout if isinstance(r.stdout, str) else r.stdout.decode(errors="replace")
    err = r.stderr if isinstance(r.stderr, str) else r.stderr.decode(errors="replace")
    if check and r.returncode != 0:
        raise RuntimeError(f"{state.name}: `{command[:80]}` failed ({r.returncode}): {err.strip()[-600:]}")
    return out


def _rsync_ssh(state: State, s: VastSettings) -> str:
    return (f"ssh -i {Path(s.ssh_key).expanduser()} -p {state.ssh_port} -o StrictHostKeyChecking=accept-new "
            "-o ConnectTimeout=20 -o ServerAliveInterval=30")


def push(state: State, s: VastSettings, sources: list[Path], dest: str, excludes: tuple[str, ...] = ()) -> None:
    ssh(state, s, f"mkdir -p {shlex.quote(dest)}")
    cmd = ["rsync", "-az", "--partial", "-e", _rsync_ssh(state, s), *(f"--exclude={e}" for e in excludes),
           *map(str, sources), f"root@{state.ssh_host}:{dest}/"]
    subprocess.run(cmd, check=True, capture_output=True)


def pull(state: State, s: VastSettings, remote_glob: str, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    cmd = ["rsync", "-az", "--partial", "-e", _rsync_ssh(state, s), f"root@{state.ssh_host}:{remote_glob}", f"{dest}/"]
    subprocess.run(cmd, check=True, capture_output=True)


def start(state: State, s: VastSettings, name: str, command: str) -> int:
    """Run shell `command` detached on the worker (cwd = engine, PYTHONPATH = src); returns its pid.

    The job gets its own session (setsid) and its pid goes to a file: should the launching ssh session still hang,
    the pid is read back over a fresh connection instead of failing a job that is already running."""
    pidfile = f"{REMOTE}/logs/{name}.pid"
    # `;` before the job matters: `a && b && job &` would background the whole list as a subshell that keeps the
    # ssh channel open until the job ends
    cmd = (f"cd {REMOTE}/engine || exit 1; export PYTHONPATH=src PYTHONUNBUFFERED=1; rm -f {pidfile}; "
           f"setsid nohup bash -c {shlex.quote(command)} > {REMOTE}/logs/{name}.log 2>&1 < /dev/null & "
           f"echo $! > {pidfile}; cat {pidfile}")
    try:
        return int(ssh(state, s, f"bash -c {shlex.quote(cmd)}", timeout=60).strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        out = ssh(state, s, f"cat {pidfile}", timeout=60).strip()
        if not out.isdigit():
            raise RuntimeError(f"{state.name}: {name} did not start (no pid file)") from None
        return int(out)


def alive(state: State, s: VastSettings, pid: int) -> bool:
    return ssh(state, s, f"kill -0 {pid} 2>/dev/null && echo yes || echo no", check=False).strip() == "yes"


def count(state: State, s: VastSettings, folder: str, suffix: str = ".json") -> int:
    out = ssh(state, s, f"ls {folder} 2>/dev/null | grep -c '{suffix}$' || true", check=False).strip()
    return int(out or 0)


# ---------------------------------------------------------------- the job

def prepare(state: State, s: VastSettings, full: Path, kind: str, song: Path, analysis: Path,
            with_analysis: bool = False) -> None:
    """Code, runtime (ffmpeg, fonts, python deps) and project inputs on one worker."""
    push(state, s, [REPO_ROOT / "engine" / "src", REPO_ROOT / "engine" / "scripts"], f"{REMOTE}/engine",
         excludes=("__pycache__", "*.pyc"))
    push(state, s, [REPO_ROOT / "config" / "tracktake.toml"], f"{REMOTE}/config")
    with (REPO_ROOT / "comfy" / "provisioning" / "tracktake_runtime.sh").open("rb") as script:
        out = ssh(state, s, f"bash -s -- {REMOTE} {'analysis' if with_analysis else ''}", stdin=script, timeout=1800)
    if "RUNTIME_OK" not in out:
        raise RuntimeError(f"{state.name}: runtime setup did not finish: {out[-400:]}")
    push(state, s, [full / "storyboard.json"], FULL)
    keys = full / kind / "keys"
    if keys.exists():
        push(state, s, [keys], f"{FULL}/{kind}")
    push(state, s, [song, analysis], PROJECT)


def shard_command(a: Assignment, kind: str) -> str:
    shots = ",".join(a.shots)
    orient = f" --orient {a.orients[0]}" if len(a.orients) == 1 else ""
    clips = f"{PY} scripts/full_clips.py {FULL} {kind} {LOCAL_COMFY} --shots {shots}{orient}"
    if kind != "comfy":
        return clips
    keys = f"{PY} scripts/full_keys_comfy.py {FULL} {LOCAL_COMFY} --shots {shots}{orient}"
    return f"{keys} && {clips}"


def expected(a: Assignment) -> int:
    return len(a.shots) * len(a.orients)


def run_clips(assignments: list[Assignment], s: VastSettings, kind: str, log: Log, poll: float = 30,
              max_rounds: int = 3) -> None:
    """Start every slice, report progress, restart a slice whose job ended with clips missing (cache keeps done)."""
    clip_dir = f"{FULL}/{kind}/clips"
    pids = {a.worker.name: start(a.worker, s, f"clips_{kind}", shard_command(a, kind)) for a in assignments}
    rounds = dict.fromkeys(pids, 1)
    started = time.monotonic()
    while True:
        time.sleep(poll)
        done_all, parts = True, []
        for a in assignments:
            name = a.worker.name
            have, want = count(a.worker, s, clip_dir), expected(a)
            parts.append(f"{name} {have}/{want}")
            if have >= want:
                continue
            done_all = False
            if not alive(a.worker, s, pids[name]):
                if rounds[name] >= max_rounds:
                    raise RuntimeError(f"{name}: {want - have} clips still missing after {max_rounds} rounds")
                rounds[name] += 1
                log(f"{name}: job ended with {want - have} missing, restarting (round {rounds[name]})")
                pids[name] = start(a.worker, s, f"clips_{kind}_{rounds[name]}", shard_command(a, kind))
        log(f"clips {kind}: " + ", ".join(parts) + f" ({time.monotonic() - started:.0f}s)")
        if done_all:
            return


def authorize_key_command(pub: str, path: str = "~/.ssh/authorized_keys") -> str:
    """Append `pub` once. Vast writes authorized_keys without a final newline: a plain `echo >>` glued the new key
    onto the account key's line and both stopped matching."""
    q = shlex.quote(pub)
    return (f"mkdir -p ~/.ssh && touch {path} && chmod 600 {path} && {{ grep -qxF {q} {path} || "
            f"{{ [ -s {path} ] && [ -n \"$(tail -c1 {path})\" ] && echo >> {path}; echo {q} >> {path}; }}; }}")


def gather(leader: State, followers: list[State], s: VastSettings, kind: str, log: Log) -> None:
    """Followers push their clips straight to the leader (worker-to-worker, a one-off key per follower)."""
    if not followers:
        return
    clip_dir = f"{FULL}/{kind}/clips"
    for f in followers:
        pub = ssh(f, s, "test -f ~/.ssh/tracktake_gather || ssh-keygen -q -t ed25519 -N '' -f ~/.ssh/tracktake_gather; "
                        "cat ~/.ssh/tracktake_gather.pub").strip().splitlines()[-1]
        ssh(leader, s, authorize_key_command(pub))
        rsh = (f"ssh -i ~/.ssh/tracktake_gather -p {leader.ssh_port} -o StrictHostKeyChecking=accept-new "
               "-o ConnectTimeout=20")
        t0 = time.monotonic()
        ssh(f, s, f"rsync -az -e {shlex.quote(rsh)} {clip_dir}/ root@{leader.ssh_host}:{clip_dir}/", timeout=3600)
        log(f"gathered {f.name} -> {leader.name} in {time.monotonic() - t0:.0f}s")


def render(leaders: list[Assignment], s: VastSettings, kind: str, song: Path, analysis: Path, log: Log,
           poll: float = 20) -> None:
    pids = {}
    for a in leaders:
        fmt = "" if a.leader_of == "both" else f" --format {FORMAT_OF[a.leader_of]}"
        pids[a.worker.name] = start(a.worker, s, f"render_{kind}",
                                    f"{PY} scripts/full_render.py {FULL} {PROJECT}/{analysis.name} "
                                    f"{PROJECT}/{song.name} {kind}{fmt}")
    started = time.monotonic()
    while pids:
        time.sleep(poll)
        for a in leaders:
            name = a.worker.name
            if name in pids and not alive(a.worker, s, pids[name]):
                del pids[name]
                tail = ssh(a.worker, s, f"tail -3 {REMOTE}/logs/render_{kind}.log", check=False)
                if "Traceback" in tail or "Error" in tail:
                    raise RuntimeError(f"{name}: render failed: {tail[-500:]}")
                log(f"{name}: render {a.leader_of} done in {time.monotonic() - started:.0f}s")


def fetch(leaders: list[Assignment], s: VastSettings, kind: str, local: Path, masters: bool, log: Log) -> None:
    for a in leaders:
        pattern = "teledysk_*" if masters else "teledysk_*preview.mp4"
        pull(a.worker, s, f"{FULL}/{kind}/{pattern}", local / kind)
        pull(a.worker, s, f"{FULL}/{kind}/render_report*.json", local / kind)
        if kind == "comfy":  # keyframes made remotely, for the gallery / comparison
            pull(a.worker, s, f"{FULL}/{kind}/keys/", local / kind / "keys")
            for f in a.followers:
                pull(f, s, f"{FULL}/{kind}/keys/", local / kind / "keys")
        log(f"downloaded {a.leader_of} from {a.worker.name}")


def run_job(workers: list[State], s: VastSettings, full: Path, kind: str, song: Path, analysis: Path,
            masters: bool = True, log: Log = print, release: Callable[[State], None] | None = None,
            orients: tuple[str, ...] = ORIENTS) -> dict:
    """The whole remote job. Returns timings; raises on failure (the caller decides about destroying workers)."""
    sb = json.loads((full / "storyboard.json").read_text())
    assignments = plan(sb["shots"], workers, orients)
    for a in assignments:
        log(f"{a.worker.name}: {'+'.join(a.orients)} x {len(a.shots)} shots"
            + (f", renders {a.leader_of}" if a.leader_of else ""))
    t: dict[str, float] = {}
    t0 = time.monotonic()
    _parallel([lambda w=w: prepare(w, s, full, kind, song, analysis) for w in workers])
    t["prepare"] = time.monotonic() - t0
    log(f"prepared {len(workers)} workers in {t['prepare']:.0f}s")

    t0 = time.monotonic()
    run_clips(assignments, s, kind, log)
    t["clips"] = time.monotonic() - t0

    leaders = [a for a in assignments if a.leader_of]
    t0 = time.monotonic()
    _parallel([lambda a=a: gather(a.worker, a.followers, s, kind, log) for a in leaders])
    t["gather"] = time.monotonic() - t0
    if release:  # followers handed their clips over: stop paying for them during the render
        for a in leaders:
            for f in a.followers:
                release(f)
                log(f"released {f.name} (its clips are on {a.worker.name})")

    t0 = time.monotonic()
    render(leaders, s, kind, song, analysis, log)
    t["render"] = time.monotonic() - t0

    t0 = time.monotonic()
    fetch(leaders, s, kind, full, masters, log)
    t["download"] = time.monotonic() - t0
    return {k: round(v) for k, v in t.items()}


def _parallel(tasks: list[Callable[[], None]]) -> None:
    errors: list[BaseException] = []

    def wrap(fn: Callable[[], None]) -> None:
        try:
            fn()
        except BaseException as e:  # noqa: BLE001 - re-raised below
            errors.append(e)

    threads = [threading.Thread(target=wrap, args=(fn,)) for fn in tasks]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    if errors:
        raise errors[0]


def run_analysis(worker: State, s: VastSettings, song: Path, lyrics: Path | None, out_dir: Path, language: str,
                 log: Log = print, poll: float = 15) -> Path:
    """Audio + lyrics analysis on a CUDA worker (demucs, beat_this, whisper alignment); returns the local JSON."""
    t0 = time.monotonic()
    push(worker, s, [REPO_ROOT / "engine" / "src", REPO_ROOT / "engine" / "scripts"], f"{REMOTE}/engine",
         excludes=("__pycache__", "*.pyc"))
    with (REPO_ROOT / "comfy" / "provisioning" / "tracktake_runtime.sh").open("rb") as script:
        out = ssh(worker, s, f"bash -s -- {REMOTE} analysis", stdin=script, timeout=2400)
    if "RUNTIME_OK" not in out:
        raise RuntimeError(f"{worker.name}: runtime setup did not finish: {out[-400:]}")
    push(worker, s, [song, *([lyrics] if lyrics else [])], PROJECT)
    log(f"{worker.name}: ready for analysis in {time.monotonic() - t0:.0f}s")
    lyr = f" --lyrics {PROJECT}/{lyrics.name}" if lyrics else ""
    pid = start(worker, s, "analyze", f"{PY} -m tracktake.cli analyze {PROJECT}/{song.name}{lyr} "
                                      f"--out {PROJECT}/work --language {language} --align-backend torch")
    while alive(worker, s, pid):
        time.sleep(poll)
    log(ssh(worker, s, f"tail -25 {REMOTE}/logs/analyze.log", check=False))
    pull(worker, s, f"{PROJECT}/work/analysis.json", out_dir)
    log(f"analysis done in {time.monotonic() - t0:.0f}s")
    return out_dir / "analysis.json"
