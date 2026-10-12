"""Measure Wan clip speed on one rented Vast GPU: rent, provision, generate a few clips of a project, report, free.

Usage: uv run python scripts/bench_vast.py <full_dir> <song> <analysis.json> --gpu RTX_5090 [--shots s01,...]
         [--orient landscape] [--max-dph 0.7]
The first clip includes loading the models into VRAM; the rest are the steady-state speed used by the estimates.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from tracktake import cli, remote, vast


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("full")
    ap.add_argument("song")
    ap.add_argument("analysis")
    ap.add_argument("--gpu", default="RTX_5090")
    ap.add_argument("--gpus", type=int, default=1, help="GPUs per host: one ComfyUI each, one model download")
    ap.add_argument("--max-dph", type=float, default=0.7)
    ap.add_argument("--shots", default="s01,s02,s03,s04,s05,s06")
    ap.add_argument("--orient", default="landscape")
    args = ap.parse_args()
    log = lambda m: print(time.strftime("%H:%M:%S"), m, flush=True)

    s = cli._remote_settings(argparse.Namespace(gpu=args.gpu, max_dph=args.max_dph, gpus=args.gpus), ["wan22_i2v"])
    t0 = time.monotonic()
    workers = vast.rent_fleet(1, s, log=log, spares=3, prefix="bench-", tunnel=False)
    if not workers:
        raise SystemExit("no worker came up")
    st = workers[0]
    try:
        setup = time.monotonic() - t0
        log(f"{st.name} ready after {setup / 60:.1f} min")
        full = Path(args.full)
        remote.prepare(st, s, full, "codex", Path(args.song), Path(args.analysis))
        cmd = (f"{remote.PY} scripts/full_clips.py {remote.FULL} codex {remote.comfy_urls(st)} "
               f"--shots {args.shots} --orient {args.orient}")
        t1 = time.monotonic()
        pid = remote.start(st, s, "bench", cmd)
        while remote.alive(st, s, pid):
            time.sleep(15)
        wall = time.monotonic() - t1
        out = remote.ssh(st, s, f"cat {remote.REMOTE}/logs/bench.log; for f in {remote.FULL}/codex/clips/*.json; "
                                f"do echo \"META $(basename $f) $(cat $f)\"; done", check=False)
        clips = {}
        for line in out.splitlines():
            if line.startswith("META "):
                _, name, meta = line.split(" ", 2)
                m = json.loads(meta)
                clips[name[:-5]] = {"seconds": m["seconds"], "gpu_seconds": m.get("gpu_seconds"),
                                    "frames": m["key"]["frames"], "end_frame": "end" in m["key"]}
            elif line.startswith("["):
                log(line)
        report = {"gpu": args.gpu, "dph": st.dph, "setup_min": round(setup / 60, 1), "clips_wall_s": round(wall),
                  "clips": clips}
        print("REPORT " + json.dumps(report), flush=True)
    finally:
        log(f"freed (~${vast.destroy(st):.2f} by local estimate)")


if __name__ == "__main__":
    main()
