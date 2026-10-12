"""Stop-motion timing: on which frames a new drawing appears, and audio-driven pulses.

In stop-motion everything (pose, camera, jitter) only changes when a new drawing is shot, so the renderer
evaluates the scene at drawing frames and holds it in between.
"""

from __future__ import annotations

from collections.abc import Sequence

from tracktake.timegrid import frame_at


def drawing_frames(
    start_frame: int,
    end_frame: int,
    cadence: int,
    forced: Sequence[int] = (),
    min_hold: int = 1,
) -> list[int]:
    """Frames in [start_frame, end_frame) where a new drawing starts.

    A drawing is held for `cadence` frames ("on twos" = 2). Frames in `forced` (beats, hits) always start a
    new drawing; the regular cadence restarts from each forced frame so holds stay even.
    A forced frame closer than `min_hold` to the previous drawing is skipped to avoid 1-frame flashes.
    """
    if cadence < 1:
        raise ValueError("cadence must be >= 1")
    forced_set = sorted({f for f in forced if start_frame <= f < end_frame})
    out: list[int] = []
    f = start_frame
    fi = 0
    while f < end_frame:
        out.append(f)
        nxt = f + cadence
        while fi < len(forced_set) and forced_set[fi] <= f:
            fi += 1
        if fi < len(forced_set) and forced_set[fi] < nxt:
            nxt = forced_set[fi]
            if nxt - f < min_hold:
                fi += 1
                nxt = f + cadence
        f = nxt
    return out


def active_drawing(frame: int, starts: Sequence[int]) -> int:
    """Index of the drawing visible at `frame` (starts sorted)."""
    lo, hi = 0, len(starts) - 1
    if frame < starts[0]:
        return 0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if starts[mid] <= frame:
            lo = mid
        else:
            hi = mid - 1
    return lo


def pulse_track(
    n_frames: int,
    fps: float,
    hits: Sequence[tuple[float, float]],
    decay_frames: float = 6.0,
) -> list[float]:
    """Per-frame 0..1 envelope: each (time, strength) hit jumps to `strength` and decays exponentially."""
    track = [0.0] * n_frames
    k = 0.5 ** (1.0 / max(decay_frames / 2.0, 1e-6))  # half-life = decay_frames / 2
    starts = sorted((frame_at(t, fps), s) for t, s in hits)
    level = 0.0
    j = 0
    for f in range(n_frames):
        level *= k
        while j < len(starts) and starts[j][0] <= f:
            level = max(level, starts[j][1])
            j += 1
        track[f] = level
    return track
