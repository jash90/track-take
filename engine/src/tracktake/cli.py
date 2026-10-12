"""Command line.

  tracktake analyze <song> --lyrics <txt> --out <work_dir>
  tracktake vast setup | offers | up [--yes] | status | tunnel | down
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from pathlib import Path

from .models import Analysis


def _summary(a: Analysis) -> str:
    out = [
        f"duration {a.duration:.2f}s  bpm {a.bpm:.2f}  beats {len(a.beats)}  downbeats {len(a.downbeats)}  "
        + f"({a.beats_per_bar}/bar)",
        f"lines {len(a.lines)}  first word "
        + (f'{a.lines[0].start:.2f}s "{a.lines[0].words[0].text}"' if a.lines and a.lines[0].words else "-"),
        "drum hits " + "  ".join(f"{k} {len(v)}" for k, v in a.drum_hits.items()),
        "methods:",
        *(f"  {k}: {v}" for k, v in a.methods.items()),
        "sections:",
        *(
            f"  {s.start:7.2f} {s.end:7.2f}  {s.kind:<10} {s.label}"
            + (f"  ({len(s.lines)} lines)" if s.lines else "  (instrumental)")
            + (f"  hints={s.hints}" if s.hints else "")
            for s in a.sections
        ),
    ]
    return "\n".join(out)


def cmd_analyze(args: argparse.Namespace) -> int:
    from .analysis.pipeline import Options, analyze

    song, out = Path(args.song), Path(args.out)
    lyrics = Path(args.lyrics).read_text(encoding="utf-8") if args.lyrics else ""
    out.mkdir(parents=True, exist_ok=True)
    opts = Options(
        fps=args.fps,
        language=args.language,
        whisper_model=args.whisper_model,
        align_backend=args.align_backend,
        beat_method=args.beats,
    )
    analysis, timings = analyze(song, lyrics, out, opts)
    analysis = Analysis.model_validate(analysis.model_dump())  # round-trip validation of the contract
    path = out / "analysis.json"
    path.write_text(analysis.model_dump_json(), encoding="utf-8")
    print(_summary(analysis))
    print("timings:")
    for name, sec in timings.steps.items():
        print(f"  {name:<9} {sec:7.1f}s")
    print(f"  {'total':<9} {sum(timings.steps.values()):7.1f}s")
    print(f"wrote {path}")
    return 0


def _vast_settings(args: argparse.Namespace):
    from . import config

    s = config.load().vast
    if getattr(args, "gpu", None):
        s.gpu = args.gpu
    if getattr(args, "max_dph", None) is not None:
        s.max_dph = args.max_dph
    if getattr(args, "gpus", None):
        s.gpus = args.gpus
    region = getattr(args, "region", None)
    if region:
        s.regions = [] if region.lower() == "any" else [r.strip().upper() for r in region.split(",") if r.strip()]
    return s


def _comfy_ready(url: str) -> str:
    from .comfy.client import ComfyClient

    info = ComfyClient(url).http.get("/system_stats").raise_for_status().json()
    dev = (info.get("devices") or [{}])[0]
    return f"ComfyUI {info['system'].get('comfyui_version')} on {dev.get('name', '?')}"


def cmd_vast(args: argparse.Namespace) -> int:
    from . import vast

    s = _vast_settings(args)
    if args.all and args.action in ("status", "down"):
        states = vast.all_states()
        if not states:
            print("no tracktake instances")
        total = 0.0
        for st in states:
            if args.action == "down":
                cost = vast.destroy(st)
                total += cost
                print(f"destroyed {st.name} (instance {st.instance_id}) ~${cost:.2f}")
            else:
                hours = (time.time() - st.created_at) / 3600
                print(f"{st.name}: instance {st.instance_id} ${st.dph:.3f}/h {hours:.2f} h (~${hours * st.dph:.2f})  "
                      f"tunnel {'up' if vast.tunnel_alive(st) else 'down'} {st.url}")
        if args.action == "down" and states:
            print(f"total ~${total:.2f}")
        return 0
    state = vast.State.load(args.name)
    if args.action == "setup":
        user = json.loads(vast.run_cli(["show", "user", "--raw"]))
        print(f"account {user.get('email', '?')}  balance ${float(user.get('credit', 0)):.2f}")
        pub = Path(s.ssh_key).expanduser().with_suffix(".pub").read_text().strip()
        keys = json.loads(vast.run_cli(["show", "ssh-keys", "--raw"]))
        if any(pub.split()[1] in str(k.get("public_key", k.get("ssh_key", ""))) for k in keys):
            print("ssh key already registered")
        else:
            vast.run_cli(["create", "ssh-key", pub])
            print(f"registered {s.ssh_key}.pub")
        return 0
    if args.action == "offers":
        offers = vast.search_offers(s)
        if not offers:
            print(f"no {s.gpu} offers at or below ${s.max_dph:.2f}/h")
            return 1
        for o in offers:
            print(f"{o.id:>10}  {o.gpu:<10} ${o.dph:.3f}/h + ${o.setup_cost(s.download_gb):.2f} download  "
                  f"rel {o.reliability:.3f}  net {o.inet_down:5.0f} Mb/s  disk {o.disk_gb:4.0f} GB  {o.location}")
        return 0
    if args.action == "up":
        if state is None:
            offers = vast.search_offers(s, limit=500 if args.offer else 5)
            offer = next((o for o in offers if not args.offer or o.id == args.offer), None)
            if offer is None:
                print(f"no matching {s.gpu} offer at or below ${s.max_dph:.2f}/h")
                return 1
            print(f"cheapest: offer {offer.id} {offer.gpu} ${offer.dph:.3f}/h, {offer.location}")
            if not args.yes:
                print("not renting: run again with --yes to rent it (billing starts immediately)")
                return 1
            state = vast.create(offer, s, name=args.name, local_port=args.port or 0)
            print(f"rented instance {state.instance_id}; waiting for it to boot...")
        try:
            state = vast.wait_running(state)
            vast.wait_ssh(state, s)
            print(f"ssh root@{state.ssh_host} -p {state.ssh_port}; provisioning (models ~45 GB on first boot)...")
            vast.provision(state, s)
            state = vast.open_tunnel(state, s)
            print(f"{_comfy_ready(state.url)} at {state.url}")
            print("use it with TRACKTAKE_COMFY_BACKEND=vast (or backend = \"vast\" in config/tracktake.toml)")
        except Exception as e:  # noqa: BLE001 - any failure after renting must stop billing
            if args.keep_on_error:
                print(f"error: {e}\ninstance {state.instance_id} is still billed; `tracktake vast down` stops it")
            else:
                cost = vast.destroy(state)
                print(f"error: {e}\ndestroyed instance {state.instance_id} (~${cost:.2f})")
            return 1
        return 0
    if args.action == "fleet":
        return _vast_fleet(args, s)
    if state is None:
        print("no tracktake instance")
        return 0 if args.action != "tunnel" else 1
    if args.action == "status":
        info = json.loads(vast.run_cli(["show", "instance", str(state.instance_id), "--raw"]))
        hours = (time.time() - state.created_at) / 3600
        print(f"instance {state.instance_id}: {info.get('actual_status')}  ${state.dph:.3f}/h  "
              f"{hours:.2f} h so far (~${hours * state.dph:.2f})")
        print(f"tunnel {'up' if vast.tunnel_alive(state) else 'down'} -> {state.url}")
        return 0
    if args.action == "tunnel":
        state = vast.open_tunnel(state, s)
        print(f"{_comfy_ready(state.url)} at {state.url}")
        return 0
    if args.action == "down":
        cost = vast.destroy(state)
        print(f"destroyed instance {state.instance_id}; session cost ~${cost:.2f}")
        return 0
    return 1


def _vast_fleet(args: argparse.Namespace, s) -> int:
    """Rent `count` workers in one go and provision them in parallel (used for tunnel-based work)."""
    from . import vast

    if args.min_net:
        s.min_inet_down = args.min_net
    if not args.yes:
        for o in vast.search_offers(s, limit=args.count):
            print(f"offer {o.id} {o.gpu} ${o.dph:.3f}/h + download ${o.setup_cost(s.download_gb):.2f} {o.location}")
        print("not renting: run again with --yes")
        return 1
    ok = vast.rent_fleet(args.count, s)
    print("FLEET_READY " + " ".join(st.url for st in ok))
    return 0 if ok else 1


MODEL_GB = {"wan22_i2v": 38.0, "zimage": 21.0}


def _remote_settings(args: argparse.Namespace, models: list[str]):
    s = _vast_settings(args)
    s.models = models
    s.download_gb = sum(MODEL_GB[m] for m in models) + 3.0  # + pip packages / apt / torch hub weights
    return s


SETUP_H = 0.17  # fallback only: setup now comes from nethistory (region boot + install/models), 5-11 min measured
CLIP_S = 55.0  # Wan 2.2 14B, up to 81 frames, 832x480 on an RTX 4090 (measured: 45 clips in 2454 s, 2026-10-12)
# one format, 4:29 song: 9 min measured as one process; now chunks render in parallel while the clips are still
# generating, leaving ~3 min after the last clip (estimate, to verify on the next run)
RENDER_H = 0.03  # measured: chunks render alongside the clips, 109 s left after the last clip (H100 NVL host)
# Wan clip speed relative to an RTX 4090.
# Measured only; other cards are estimated from Vast's DLPerf (vast.gpu_catalog) until measured with bench_vast.py.
GPU_SPEED = {
    "RTX_4090": 1.0,  # 3505 frames in 2454 s = 0.70 s/frame (2026-10-12)
    "H100_NVL": 1.9,  # 3505 frames in 1290 s (2026-10-12)
    "RTX_PRO_6000_S": 1.6,  # 3635 frames in 2 x 793 GPU-seconds (2026-10-12, 2-GPU machine)
}
FRAME_S = 0.70  # Wan 2.2 14B at 832x480 on an RTX 4090, per generated frame: clip time follows the clip length


_CATALOG: dict[tuple, tuple[float, list[dict]]] = {}


def gpu_catalog(s, max_age: float = 300) -> list[dict]:
    """vast.gpu_catalog, cached for a few minutes per region choice (one search is ~2 s)."""
    from . import vast

    key = tuple(sorted(r.upper() for r in s.regions))
    hit = _CATALOG.get(key)
    if hit is None or time.monotonic() - hit[0] > max_age:
        hit = _CATALOG[key] = (time.monotonic(), vast.gpu_catalog(s, GPU_SPEED))
    return hit[1]


def gpu_speed(gpu: str) -> float:
    """Wan clip speed relative to an RTX 4090: measured, else estimated from the live catalog, else 1."""
    if gpu in GPU_SPEED:
        return GPU_SPEED[gpu]
    try:
        from . import config

        return next((g["speed"] for g in gpu_catalog(config.load().vast) if g["gpu"] == gpu and g["speed"]), 1.0)
    except Exception:  # noqa: BLE001 - no network / no API key: fall back to the 4090 speed
        return 1.0


FIXED_H = 3 / 60  # worker preparation (~0.6 min) + downloading the finished video (~2.3 min), measured
FAILED_HOST_MIN = 10  # a host that never starts holds its slot up to ~10 min before a spare offer takes over


def _estimate(s, workers: int, clips: int, render: bool = True, extra_minutes: float = 0.0,
              formats: int = 2, frames: int | None = None) -> tuple[float, float]:
    """(wall hours, USD). Every card pays setup + model download once; the clip work is the same total whatever
    the card count; followers are released after handing over their clips, each format renders on one card."""
    from . import vast

    offers = vast.search_offers(s, limit=max(workers, 1))
    if not offers:
        return 0.0, 0.0
    from . import nethistory

    dph = sum(o.dph for o in offers) / len(offers)
    dl = sum(o.setup_cost(s.download_gb) for o in offers) / len(offers)
    hist = nethistory.history()
    setup_h = sum(hist.setup_minutes(o.machine_id, o.location, s.download_gb) for o in offers) / len(offers) / 60
    gpu_s = frames * FRAME_S if frames else clips * CLIP_S  # on an RTX 4090
    work_h = gpu_s / gpu_speed(s.gpu) / 3600 / max(1, s.gpus) + extra_minutes / 60  # host-hours
    render_wall = RENDER_H * math.ceil(formats / min(workers, formats)) if render else 0.0
    wall = setup_h + work_h / workers + render_wall + FIXED_H
    usd = workers * (setup_h * dph + dl) + work_h * dph + (formats * RENDER_H * dph if render else 0.0) + FIXED_H * dph
    return wall, usd


def cmd_remote(args: argparse.Namespace) -> int:
    from . import remote, vast

    if args.action == "analyze":
        s = _remote_settings(args, [])
        hours, usd = _estimate(s, 1, 0, render=False, extra_minutes=5)
        print(f"remote analysis: 1x {s.gpu}, ~{hours * 60:.0f} min, ~${usd:.2f}")
    else:
        if not (args.full and args.set and args.song and args.analysis):
            print("remote run needs --full, --set, --song and --analysis")
            return 2
        sb = json.loads((Path(args.full) / "storyboard.json").read_text())
        orients = ("landscape", "portrait") if args.orient == "both" else (args.orient,)
        clips = len(sb["shots"]) * len(orients)
        s = _remote_settings(args, ["wan22_i2v", "zimage"] if args.set == "comfy" else ["wan22_i2v"])
        hours, usd = _estimate(s, args.workers, clips, formats=len(orients))
        if not hours:
            print(f"no {s.gpu} offer matches (max ${s.max_dph}/h, download <= ${s.max_download_cost}/GB)")
            return 1
        print(f"remote run: {clips} clips + render on {args.workers}x {s.gpu}, ~{hours * 60:.0f} min, ~${usd:.2f} "
              f"(models {s.download_gb:.0f} GB per card)")
        if args.workers != 1:
            h1, usd1 = _estimate(s, 1, clips, formats=len(orients))
            print(f"  for comparison 1x {s.gpu}: ~{h1 * 60:.0f} min, ~${usd1:.2f} (cheaper, slower)")
    if not args.yes:
        print("not renting: run again with --yes (billing starts immediately; cards are freed at the end)")
        return 1
    workers: list = []
    # this job's workers only: another job may be renting right now (the UI passes its job's id to tell them apart)
    run_id = (args.run_id or f"r{int(time.time()) % 1_000_000}").rstrip("-") + "-"
    try:
        workers = vast.rent_fleet(1 if args.action == "analyze" else args.workers, s, prefix=run_id, tunnel=False)
        if not workers:
            print("no worker came up")
            return 1
        if args.action == "analyze":
            path = remote.run_analysis(workers[0], s, Path(args.song), Path(args.lyrics) if args.lyrics else None,
                                       Path(args.out), args.language)
            print(f"wrote {path}")
        else:
            timings = remote.run_job(workers, s, Path(args.full), args.set, Path(args.song), Path(args.analysis),
                                     masters=not args.no_masters, release=vast.destroy, orients=orients,
                                     captions=not args.no_captions, beat_motion=not args.no_beat_motion)
            print(f"DONE {json.dumps(timings)}")
        return 0
    finally:
        if args.keep:
            print("--keep: workers left running; `tracktake vast down --all` stops billing")
        else:
            total, failed = 0.0, []
            for st in [st for st in vast.all_states() if st.name.startswith(run_id)]:
                try:  # one failure must not leave the other cards running
                    total += vast.destroy(st)
                except Exception as e:  # noqa: BLE001
                    failed.append(f"{st.name} ({st.instance_id}): {e}")
            if failed:
                print("COULD NOT FREE: " + "; ".join(failed) + " - run `tracktake vast down --all`")
            print(f"freed this job's workers (~${total:.2f} by local estimate; see `vastai show invoices` for the bill)")


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve

    print(f"tracktake UI: http://{args.host}:{args.port}")
    serve(args.host, args.port)
    return 0


def cmd_projects(args: argparse.Namespace) -> int:
    from . import project

    if args.action == "list":
        for p in project.all_projects():
            m = p.meta()
            print(f"{p.id:<24} {m.name}  ({m.created})")
        return 0
    p = project.import_existing(args.id, args.name or args.id, Path(args.song), Path(args.lyrics) if args.lyrics else None,
                                Path(args.cover) if args.cover else None, Path(args.analysis) if args.analysis else None,
                                Path(args.full) if args.full else None, args.style or "")
    print(f"imported {p.id} -> {p.root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tracktake")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="audio + lyrics analysis -> <out>/analysis.json")
    a.add_argument("song", help="audio file (mp3/wav/...)")
    a.add_argument("--lyrics", help="Suno lyrics .txt with [Section] tags")
    a.add_argument("--out", required=True, help="work directory (also holds the stem cache)")
    a.add_argument("--fps", type=float, default=24.0)
    a.add_argument("--language", default="en", help="lyrics language code, e.g. en, pl")
    a.add_argument("--whisper-model", default="large-v3", help="whisper size used for alignment")
    a.add_argument("--align-backend", choices=["mlx", "torch"], default=None)
    a.add_argument("--beats", choices=["beat_this", "librosa"], default="beat_this")
    a.set_defaults(func=cmd_analyze)

    v = sub.add_parser("vast", help="rent / manage a Vast.ai GPU running ComfyUI")
    v.add_argument("action", choices=["setup", "offers", "up", "fleet", "status", "tunnel", "down"])
    v.add_argument("--gpu", help="override [vast].gpu, e.g. RTX_5090")
    v.add_argument("--max-dph", type=float, help="override [vast].max_dph (USD per hour)")
    v.add_argument("--offer", type=int, help="rent this offer id instead of the cheapest")
    v.add_argument("--yes", action="store_true", help="actually rent (billing starts)")
    v.add_argument("--keep-on-error", action="store_true", help="do not destroy the instance if setup fails")
    v.add_argument("--name", default="main", help="worker name; several named instances can run at once")
    v.add_argument("--port", type=int, help="local tunnel port for this worker (default [vast].local_port)")
    v.add_argument("--all", action="store_true", help="status/down: every tracktake instance")
    v.add_argument("--count", type=int, default=4, help="fleet: number of workers")
    v.add_argument("--min-net", type=int, help="fleet: minimum download speed in Mb/s")
    v.set_defaults(func=cmd_vast)

    r = sub.add_parser("remote", help="run analysis or a whole video on Vast workers, fetch only the results")
    r.add_argument("action", choices=["run", "analyze"])
    r.add_argument("--full", help="run: full-video dir with storyboard.json (and <set>/keys for codex)")
    r.add_argument("--set", choices=["codex", "comfy"], help="run: keyframe set (comfy = made on the workers)")
    r.add_argument("--song", required=True)
    r.add_argument("--analysis", help="run: analysis.json")
    r.add_argument("--lyrics", help="analyze: Suno lyrics .txt")
    r.add_argument("--out", default=".", help="analyze: where analysis.json goes")
    r.add_argument("--language", default="en")
    r.add_argument("--workers", type=int, default=4)
    r.add_argument("--orient", choices=["landscape", "portrait", "both"], default="both",
                   help="run: which video to make (a project has one orientation)")
    r.add_argument("--gpu", help="override [vast].gpu")
    r.add_argument("--gpus", type=int, help="GPUs per host (one ComfyUI per GPU, one model download)")
    r.add_argument("--region", help="country codes to rent in first, e.g. US or US,CA; 'any' = anywhere")
    r.add_argument("--max-dph", type=float, help="override [vast].max_dph")
    r.add_argument("--no-masters", action="store_true", help="run: download only the small previews")
    r.add_argument("--no-captions", action="store_true", help="run: video without karaoke lyrics")
    r.add_argument("--no-beat-motion", action="store_true", help="run: no camera pump/shake on the beat")
    r.add_argument("--keep", action="store_true", help="do not free the workers at the end")
    r.add_argument("--run-id", help="prefix of this job's worker names (default: from the clock)")
    r.add_argument("--yes", action="store_true", help="actually rent (billing starts)")
    r.set_defaults(func=cmd_remote)

    sv = sub.add_parser("serve", help="web UI + API (open the printed URL)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8770)
    sv.set_defaults(func=cmd_serve)

    pr = sub.add_parser("projects", help="list projects, or import earlier CLI work into the UI")
    pr.add_argument("action", choices=["list", "import"])
    pr.add_argument("--id", help="import: project id (lowercase, dashes)")
    pr.add_argument("--name")
    pr.add_argument("--song")
    pr.add_argument("--lyrics")
    pr.add_argument("--cover")
    pr.add_argument("--analysis")
    pr.add_argument("--full", help="import: an existing full-video dir (linked, not copied)")
    pr.add_argument("--style")
    pr.set_defaults(func=cmd_projects)
    return p


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    sys.stdout.reconfigure(line_buffering=True)  # progress shows up live when logged to a file
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except RuntimeError as e:  # VastError, ComfyError: print the message, not a traceback
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
