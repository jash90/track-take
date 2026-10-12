"""Full video, step 3: assemble the whole song from the Wan clips, both formats, captions and audio.

Each shot's clip is stretched over the whole shot; stop-motion drawings (on twos, a new drawing forced on every
beat) sample the clip at their moment, the downbeat pump and snare shake come from the analysis.
Writes a master (H.264 14 Mb/s) and a small HEVC preview that fits a 50 MB chat attachment.

Usage: uv run python scripts/full_render.py <full_dir> <analysis.json> <song> <set: codex|comfy> [--format 16x9|9x16]
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from tracktake.models import Analysis
from tracktake.render.compositor import LANDSCAPE, PORTRAIT, Camera, Format, Layer, Shot
from tracktake.render.encoders import video_args
from tracktake.render.stepping import drawing_frames
from tracktake.render.timeline import render
from tracktake.shards import split_args
from tracktake.storyboard import is_cut
from tracktake.timegrid import frame_at, frames_of
from tracktake.video import _read_pngs

FPS = 24
ORIENT = {"16x9": "landscape", "9x16": "portrait"}


def preview(master: Path, out: Path, duration: float, max_mb: float = 46.0) -> None:
    """HEVC re-encode sized to fit under max_mb (hardware encoder where available, AAC 128k)."""
    video_kbps = int(max_mb * 8 * 1024 / duration - 128)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(master), *video_args("hevc", f"{video_kbps}k"),
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)], check=True)


def main() -> None:
    pos, opts = split_args(sys.argv[1:])
    full, analysis_path, song, kind = Path(pos[0]), Path(pos[1]), Path(pos[2]), pos[3]
    formats = [f for f in (LANDSCAPE, PORTRAIT) if opts.get("format") in (None, f.name)]
    sb = json.loads((full / "storyboard.json").read_text())
    analysis = Analysis.model_validate_json(analysis_path.read_text())
    beat_frames = frames_of(analysis.beats, FPS)
    out_dir = full / kind
    report = {}
    for fmt in formats:
        shots, cadence = [], []
        for i, sh in enumerate(sb["shots"]):
            start, end = frame_at(sh["start"], FPS), frame_at(sh["end"], FPS)
            frames = _read_pngs(out_dir / "clips" / f"{sh['id']}_{ORIENT[fmt.name]}")
            plan = drawing_frames(start, end, 2, forced=beat_frames, min_hold=2)
            span = max(end - start, 1)
            drawings = [frames[min(round((sf - start) / span * (len(frames) - 1)), len(frames) - 1)] for sf in plan]
            shots.append(video_shot(drawings, fmt, start, end, 100 + i, *zoom_span(sb["shots"], i)))
            cadence.append(2)
        master = out_dir / f"teledysk_{kind}_{fmt.name}.mp4"
        t0 = time.monotonic()
        r = render(shots, cadence, analysis, fmt, master, fps=FPS, t0=0.0, t1=analysis.duration, audio=song)
        small = out_dir / f"teledysk_{kind}_{fmt.name}_preview.mp4"
        preview(master, small, analysis.duration)
        r |= {"master_mb": round(master.stat().st_size / 1e6, 1), "preview_mb": round(small.stat().st_size / 1e6, 1),
              "total_s": round(time.monotonic() - t0, 1)}
        report[fmt.name] = r
        print(r, flush=True)
    tag = f"_{opts['format']}" if opts.get("format") else ""
    (out_dir / f"render_report{tag}.json").write_text(json.dumps(report, indent=1))


def zoom_span(shots: list[dict], i: int, total: float = 0.04) -> tuple[float, float]:
    """Slow push-in over a whole continuous run, so the camera does not snap back at the seam between two shots."""
    first = max(j for j in range(i + 1) if is_cut(shots, j))
    last = next((j - 1 for j in range(i + 1, len(shots)) if is_cut(shots, j)), len(shots) - 1)
    n = last - first + 1
    return 1.0 + total * (i - first) / n, 1.0 + total * (i - first + 1) / n


def video_shot(drawings, fmt: Format, start: int, end: int, seed: int, zoom_from: float = 1.0,
               zoom_to: float = 1.04) -> Shot:
    vw, vh = fmt.view
    h, w = drawings[0].shape[:2]
    width = max(vw, vh * w / h)  # cover the viewport
    return Shot(start, end, [Layer(drawings, center=(0.5, 0.5), width=width, parallax=1.0)],
                Camera((0.5, 0.5), zoom_from), Camera((0.5, 0.5), zoom_to), focus=(0.5, 0.5), seed=seed)


if __name__ == "__main__":
    main()
