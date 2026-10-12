"""Render a list of shots against the song analysis into one video per format."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from tracktake.models import Analysis
from tracktake.render.captions import line_at, overlay, render_caption
from tracktake.render.compositor import Format, Shot, compose, whip
from tracktake.render.encode import VideoWriter
from tracktake.render.stepping import active_drawing, drawing_frames, pulse_track
from tracktake.timegrid import frame_at, frames_of


@dataclass
class Pulses:
    kick: list[float]
    snare: list[float]
    beat: list[float]


def pulses(analysis: Analysis, n_frames: int, fps: float) -> Pulses:
    """Audio-driven 0..1 tracks. The beat grid drives the "kick" pump, because kick onsets from the drums stem are
    noisy on sustained low end; snare hits are reliable enough to use directly."""
    downs = {round(t, 3) for t in analysis.downbeats}
    kick_hits = [(t, 1.0 if round(t, 3) in downs else 0.45) for t in analysis.beats]
    snare_hits = [(h.time, h.strength) for h in analysis.drum_hits.get("snare", []) if h.strength > 0.3]
    return Pulses(
        kick=pulse_track(n_frames, fps, kick_hits, decay_frames=7),
        snare=pulse_track(n_frames, fps, snare_hits, decay_frames=4),
        beat=pulse_track(n_frames, fps, [(t, 1.0) for t in analysis.beats], decay_frames=5),
    )


def still(n_frames: int) -> Pulses:
    """No beat-driven camera motion: every pulse track stays at 0."""
    return Pulses(kick=[0.0] * n_frames, snare=[0.0] * n_frames, beat=[0.0] * n_frames)


def render(
    shots: list[Shot],
    cadence: list[int],
    analysis: Analysis,
    fmt: Format,
    out: str | Path,
    *,
    fps: float,
    t0: float,
    t1: float,
    audio: str | Path | None = None,
    captions: bool = True,
    beat_motion: bool = True,
) -> dict:
    """Render frames [t0, t1) of the song. Shot frames are absolute song frames; `cadence[i]` is shot i's hold.
    `captions=False` leaves out the karaoke lyrics; `beat_motion=False` keeps the camera still on the beat
    (no downbeat pump, no snare shake)."""
    f0, f1 = frame_at(t0, fps), frame_at(t1, fps)
    total = frame_at(analysis.duration, fps) + 1
    p = pulses(analysis, total, fps) if beat_motion else still(total)
    beat_frames = frames_of(analysis.beats, fps)
    plans = [drawing_frames(s.start_frame, s.end_frame, c, forced=beat_frames, min_hold=2) for s, c in zip(shots, cadence, strict=True)]
    started = time.monotonic()
    drawings = 0
    shot_i = 0
    frame_cache: tuple[tuple[int, int], np.ndarray] | None = None
    cap_cache: tuple[tuple, np.ndarray | None] | None = None
    with VideoWriter(out, fmt.width, fmt.height, fps, audio=audio, audio_start=t0, duration=(f1 - f0) / fps) as vw:
        for f in range(f0, f1):
            while shot_i < len(shots) - 1 and f >= shots[shot_i].end_frame:
                shot_i += 1
            shot, plan = shots[shot_i], plans[shot_i]
            d = active_drawing(f, plan)
            if frame_cache is None or frame_cache[0] != (shot_i, d):
                sf = plan[d]  # stop-motion: evaluate the scene when the drawing is shot, then hold it
                frame_cache = ((shot_i, d), compose(shot, fmt, sf, d, p.kick[sf], p.snare[sf], p.beat[sf]))
                drawings += 1
            frame = whip(frame_cache[1], shot, f) if shot.whip_in or shot.whip_out else frame_cache[1]
            if captions:
                t = f / fps
                line = line_at(analysis.lines, t)
                key = (id(line), sum(w.start <= t for w in line.words) if line else 0)
                if cap_cache is None or cap_cache[0] != key:
                    cap_cache = (key, render_caption(line, t, fmt) if line else None)
                if cap_cache[1] is not None:
                    frame = overlay(frame, cap_cache[1])
            vw.write(frame)
    return {"format": fmt.name, "frames": f1 - f0, "drawings": drawings, "seconds": round(time.monotonic() - started, 1)}
