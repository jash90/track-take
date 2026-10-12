"""Lyric blocks + aligned lines -> timed sections covering 0..duration."""

from __future__ import annotations

from collections.abc import Sequence

from ..lyrics import LyricBlock
from ..models import LyricLine, Section
from ..timegrid import snap
from .align import line_is_timed

Span = tuple[float, float] | None


def block_spans(block_lines: Sequence[Sequence[LyricLine]]) -> list[Span]:
    """(first word start, last word end) per block; None for instrumental or unaligned blocks."""
    spans: list[Span] = []
    for lines in block_lines:
        timed = [ln for ln in lines if line_is_timed(ln)]
        spans.append((timed[0].start, timed[-1].end) if timed else None)
    return spans


def raw_boundaries(spans: Sequence[Span], weights: Sequence[float], duration: float) -> list[float]:
    """Section start times plus the final end (len(spans) + 1 values).

    A sung block starts at its first word and runs until the next block starts. Runs of untimed blocks
    share the gap between the previous sung block's last word and the next one's first word, split by
    `weights`. The first block always starts at 0 and the last one ends at `duration`.
    """
    n = len(spans)
    starts: list[float | None] = [s[0] if s else None for s in spans]
    i = 0
    while i < n:
        if starts[i] is not None:
            i += 1
            continue
        j = i
        while j < n and starts[j] is None:
            j += 1
        prev = spans[i - 1] if i > 0 else None  # runs are maximal, so i - 1 is a sung block
        lo = prev[1] if prev else 0.0
        hi = starts[j] if j < n else duration
        lo = min(lo, hi)
        total = sum(weights[i:j])
        acc = lo
        for k in range(i, j):
            starts[k] = acc
            acc += (hi - lo) * weights[k] / total
        i = j
    out = [float(s) for s in starts]  # type: ignore[arg-type]
    if out:
        out[0] = 0.0
    out.append(duration)
    return _monotonic(out)


def snap_boundaries(
    bounds: list[float], downbeats: Sequence[float], max_distance: float = 0.6
) -> list[float]:
    """Snap interior boundaries to the nearest downbeat within `max_distance`, never reordering them."""
    out = list(bounds)
    for k in range(1, len(out) - 1):
        cand = snap(out[k], downbeats, max_distance)
        if out[k - 1] < cand < out[k + 1]:
            out[k] = cand
    return out


def _monotonic(bounds: list[float]) -> list[float]:
    for k in range(1, len(bounds)):
        bounds[k] = max(bounds[k], bounds[k - 1])
    return bounds


def build_sections(
    blocks: Sequence[LyricBlock],
    block_lines: Sequence[Sequence[LyricLine]],
    duration: float,
    downbeats: Sequence[float],
    snap_distance: float = 0.6,
) -> list[Section]:
    spans = block_spans(block_lines)
    weights = [max(1.0, float(len(b.lines))) for b in blocks]
    bounds = snap_boundaries(raw_boundaries(spans, weights, duration), downbeats, snap_distance)
    return [
        Section(
            label=b.label or "Untitled",
            kind=b.kind,
            start=round(bounds[k], 4),
            end=round(bounds[k + 1], 4),
            tag_details=b.tag_details,
            lines=list(block_lines[k]),
            hints=list(b.hints),
        )
        for k, b in enumerate(blocks)
    ]
