"""Full video, step 2: Wan 2.2 image-to-video for every shot keyframe, spread over several Vast workers.

Clip length follows the shot (16 fps, at most 81 frames = 5 s); longer shots are stretched at render time, which
the stop-motion stepping hides. A shot that flows into the next one (no hard cut) is animated first-to-last frame:
its clip ends exactly on the next shot's keyframe. Clips are cached per set, so an interrupted run resumes.

Usage: uv run python scripts/full_clips.py <full_dir> <set: codex|comfy> <comfy_url> [<comfy_url> ...]
         [--shots s01,s02] [--orient landscape|portrait]   (a Vast worker takes a slice)
         [--order reverse]   (a helper card joining late works from the end towards a busy one)
"""

from __future__ import annotations

import json
import math
import queue
import sys
import threading
import time
from pathlib import Path

import cv2
from PIL import Image

from sunomv.comfy.client import ComfyClient
from sunomv.ltx import ClipSpec, fit_cover
from sunomv.shards import split_args, wanted
from sunomv.storyboard import continues_into
from sunomv.video import PROFILES, ComfyWanBackend

PROFILE = PROFILES["wan"]
SUFFIX = "Stop-motion paper cut-out animation, layered construction paper, visible paper texture."


def revive_tunnel(url: str) -> None:
    """Reopen the SSH tunnel of the Vast worker behind `url` if it died (e.g. under memory pressure)."""
    from sunomv import config, vast

    port = int(url.rsplit(":", 1)[1])
    for state in vast.all_states():
        if state.local_port == port and not vast.tunnel_alive(state):
            try:
                vast.open_tunnel(state, config.load().vast)
                print(f"reopened tunnel {url} ({state.name})", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"could not reopen {url}: {e}", flush=True)


def clip_frames(duration: float) -> int:
    """4k+1 frames covering the shot at 16 fps, between 33 and 81."""
    return max(33, min(81, 4 * math.ceil(duration * PROFILE.fps / 4) + 1))


def prepare(key: Path, prepared: Path, w: int, h: int) -> Path:
    small = prepared / key.name
    if not small.exists() or small.stat().st_mtime < key.stat().st_mtime:
        img = cv2.cvtColor(cv2.imread(str(key)), cv2.COLOR_BGR2RGB)
        Image.fromarray(fit_cover(img, w, h)).save(small)
    return small


def main() -> None:
    pos, opts = split_args(sys.argv[1:])
    full, kind, urls = Path(pos[0]), pos[1], pos[2:]
    only, orients = wanted(opts)
    sb = json.loads((full / "storyboard.json").read_text())
    keys, prepared, clips = full / kind / "keys", full / kind / "keys_wan", full / kind / "clips"
    prepared.mkdir(parents=True, exist_ok=True)
    jobs: queue.Queue = queue.Queue()
    order = list(enumerate(sb["shots"]))
    for i, shot in reversed(order) if opts.get("order") == "reverse" else order:
        if only and shot["id"] not in only:
            continue
        for orientation, (w, h) in (("landscape", PROFILE.landscape), ("portrait", PROFILE.portrait)):
            if orientation not in orients:
                continue
            key = keys / f"{shot['id']}_{orientation}.png"
            if not key.exists():
                print(f"skip {key.name}: no keyframe", flush=True)
                continue
            small = prepare(key, prepared, w, h)
            nxt = continues_into(sb["shots"], i)
            end_key = keys / f"{nxt['id']}_{orientation}.png" if nxt else None
            end = prepare(end_key, prepared, w, h) if end_key and end_key.exists() else None
            motion = shot["motion"] + (f" The shot ends exactly on this picture: {nxt['scene']}" if end else "")
            spec = ClipSpec(f"{shot['id']}_{orientation}", f"{motion} {SUFFIX}", w, h,
                            clip_frames(shot["end"] - shot["start"]), PROFILE.fps, seed=7 + i)
            jobs.put((spec, small, end))
    total, started, lock, report = jobs.qsize(), time.monotonic(), threading.Lock(), {}

    def worker(url: str) -> None:
        backend = ComfyWanBackend(ComfyClient(url))
        while True:
            try:
                spec, small, end = jobs.get_nowait()
            except queue.Empty:
                return
            msg = ""
            for attempt in range(3):
                try:
                    frames, seconds = backend.generate(spec, small, clips, end)
                    msg = f"{seconds:.0f}s, {len(frames)} frames" + (f" (retry {attempt})" if attempt else "")
                    break
                except Exception as e:  # noqa: BLE001 - a dropped tunnel is reopened and the clip retried
                    msg = f"ERROR {e}"
                    revive_tunnel(url)
                    time.sleep(10 * (attempt + 1))
            with lock:
                report[spec.id] = msg
                print(f"[{len(report)}/{total}] {kind} {spec.id}: {msg} on {url} "
                      f"({time.monotonic() - started:.0f}s elapsed)", flush=True)

    threads = [threading.Thread(target=worker, args=(u,)) for u in urls]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    (full / kind / "clips_report.json").write_text(json.dumps(report, indent=1))
    print(f"done {kind}: {len(report)}/{total} in {time.monotonic() - started:.0f}s", flush=True)


if __name__ == "__main__":
    main()
