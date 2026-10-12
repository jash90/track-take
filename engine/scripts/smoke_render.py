"""Smoke test of the renderer without AI: one background, one cut-out subject, synthetic 120 BPM beats, captions.

Usage: uv run python scripts/smoke_render.py <background.png> <out_dir>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
import numpy as np

from sunomv.models import LyricLine, Word
from sunomv.render.captions import line_at, overlay, render_caption
from sunomv.render.compositor import LANDSCAPE, PORTRAIT, Camera, Layer, Shot, compose, to_rgba
from sunomv.render.encode import VideoWriter
from sunomv.render.stepping import active_drawing, drawing_frames, pulse_track
from sunomv.timegrid import frames_of

FPS = 24
SECONDS = 6.0


def main() -> None:
    bg_path, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    bg = to_rgba(cv2.cvtColor(cv2.imread(str(bg_path)), cv2.COLOR_BGR2RGB))
    # the cut-out: the right half of the image inside a feathered ellipse stands in for a masked character
    h, w = bg.shape[:2]
    mask = np.zeros((h, w), np.uint8)
    cv2.ellipse(mask, (int(w * 0.72), int(h * 0.6)), (int(w * 0.13), int(h * 0.36)), 0, 0, 360, 255, -1)
    mask = cv2.GaussianBlur(mask, (31, 31), 0)
    subject = bg.copy()
    subject[:, :, 3] = mask

    n = int(SECONDS * FPS)
    beats = [k * 0.5 for k in range(int(SECONDS / 0.5) + 1)]
    kicks = [(t, 1.0) for t in beats[::2]]
    snares = [(t, 0.8) for t in beats[1::2]]
    kick, snare, beat = pulse_track(n, FPS, kicks), pulse_track(n, FPS, snares, 4), pulse_track(n, FPS, [(t, 1) for t in beats], 5)
    starts = drawing_frames(0, n, 2, forced=frames_of(beats, FPS))
    shot = Shot(0, n, [Layer([bg], width=1.0, parallax=0.6, jitter=0.002),
                       Layer([subject], width=1.0, parallax=1.0, bounce=0.012, jitter=0.004)],
                cam_from=Camera((0.5, 0.5), 1.05), cam_to=Camera((0.56, 0.48), 1.18), focus=(0.72, 0.6), seed=7)
    words = ["Your", "coat", "still", "hangs", "by", "the", "door"]
    line = LyricLine(text=" ".join(words), start=1.0, end=4.0,
                     words=[Word(text=x, start=1.0 + i * 0.4, end=1.3 + i * 0.4) for i, x in enumerate(words)])

    for fmt in (LANDSCAPE, PORTRAIT):
        t0 = time.monotonic()
        cache: dict[int, np.ndarray] = {}
        with VideoWriter(out / f"smoke_{fmt.name}.mp4", fmt.width, fmt.height, FPS) as vw:
            for f in range(n):
                d = active_drawing(f, starts)
                if d not in cache:
                    sf = starts[d]  # stop-motion: the scene is evaluated when the drawing is shot, then held
                    cache = {d: compose(shot, fmt, sf, d, kick[sf], snare[sf], beat[sf])}
                frame = cache[d]
                t = f / FPS
                ln = line_at([line], t)
                vw.write(overlay(frame, render_caption(ln, t, fmt)) if ln else frame)
        print(f"{fmt.name}: {n} frames, {len(starts)} drawings, {time.monotonic() - t0:.1f}s")


if __name__ == "__main__":
    main()
