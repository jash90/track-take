"""Time -> frame math. The single source of truth for sync.

Events live in seconds; each one is rounded to a frame independently, so rounding error never accumulates
(at 128 BPM and 24 fps a beat is 11.25 frames, and adding 11 or 12 per beat would drift).
"""

from __future__ import annotations

import bisect
import itertools
from collections.abc import Sequence


def frame_at(t: float, fps: float) -> int:
    """Frame index whose start is closest to time `t`."""
    return round(t * fps)


def time_of(frame: int, fps: float) -> float:
    return frame / fps


def frames_of(times: Sequence[float], fps: float) -> list[int]:
    return [frame_at(t, fps) for t in times]


def nearest(times: Sequence[float], t: float) -> float:
    """Nearest event time to `t`; `times` must be sorted and non-empty."""
    i = bisect.bisect_left(times, t)
    if i == 0:
        return times[0]
    if i == len(times):
        return times[-1]
    before, after = times[i - 1], times[i]
    return before if t - before <= after - t else after


def snap(t: float, grid: Sequence[float], max_distance: float | None = None) -> float:
    """Snap `t` to the nearest grid time, unless it is farther than `max_distance` seconds."""
    if not grid:
        return t
    n = nearest(grid, t)
    if max_distance is not None and abs(n - t) > max_distance:
        return t
    return n


def subdivide(beats: Sequence[float], parts: int) -> list[float]:
    """Split each beat interval into `parts` equal steps (1/2 = eighths, 1/4 = sixteenths in 4/4)."""
    if parts < 1:
        raise ValueError("parts must be >= 1")
    out: list[float] = []
    for a, b in itertools.pairwise(beats):
        step = (b - a) / parts
        out.extend(a + k * step for k in range(parts))
    if beats:
        out.append(beats[-1])
    return out


def between(times: Sequence[float], start: float, end: float) -> list[float]:
    """Events with start <= t < end."""
    lo = bisect.bisect_left(times, start)
    hi = bisect.bisect_left(times, end)
    return list(times[lo:hi])
