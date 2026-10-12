"""Model-free unit tests for the analysis helpers (no demucs/whisper/beat_this needed)."""

import itertools

import numpy as np
import pytest

from sunomv.analysis.beats import beats_per_bar_of, bpm_of, regularize_downbeats
from sunomv.analysis.features import HOP, SR, normalise, pool_to_frames
from sunomv.analysis.sections import build_sections, raw_boundaries, snap_boundaries
from sunomv.lyrics import parse_lyrics
from sunomv.models import LyricLine, Word


def _line(text: str, start: float, end: float) -> LyricLine:
    return LyricLine(text=text, start=start, end=end, words=[Word(text=text, start=start, end=end)])


def test_bpm_and_bar_length():
    beats = np.arange(0, 60, 0.5)  # 120 BPM
    assert bpm_of(beats) == pytest.approx(120.0)
    assert beats_per_bar_of(beats, beats[::4]) == 4
    assert beats_per_bar_of(beats, beats[::3]) == 3


def test_regularize_drops_half_bar_downbeats_but_keeps_phase():
    beats = np.arange(40) * 0.5
    downbeats = np.concatenate([beats[0:16:4], beats[16:32:2], beats[32::4]])
    fixed = regularize_downbeats(beats, downbeats, 4)
    assert np.allclose(fixed, beats[::4])


def test_raw_boundaries_fill_gaps_with_instrumental_blocks():
    # intro, verse (10..20), build, chorus (25..40), break, outro (50..58)
    spans = [None, (10.0, 20.0), None, (25.0, 40.0), None, (50.0, 58.0)]
    b = raw_boundaries(spans, [1, 1, 1, 1, 1, 1], duration=60.0)
    assert b == [0.0, 10.0, 20.0, 25.0, 40.0, 50.0, 60.0]


def test_raw_boundaries_split_run_and_clamp_overlap():
    spans = [(5.0, 10.0), None, None, (20.0, 30.0), None, (29.0, 35.0)]
    b = raw_boundaries(spans, [1] * 6, duration=40.0)
    assert b[:4] == [0.0, 10.0, 15.0, 20.0]
    assert b[4] == b[5] == 29.0  # overlapping alignment gives the gap block zero length, never negative
    assert b == sorted(b)


def test_snap_boundaries_only_within_distance_and_in_order():
    bounds = [0.0, 10.3, 20.9, 21.0, 30.0]
    snapped = snap_boundaries(bounds, downbeats=[0.0, 10.0, 21.2, 30.0], max_distance=0.6)
    assert snapped[1] == 10.0
    assert snapped[2] == 20.9  # snapping to 21.2 would pass the next boundary
    assert snapped[0] == 0.0 and snapped[-1] == 30.0


def test_build_sections_cover_song():
    blocks = parse_lyrics("[Intro]\n[Verse 1: Soft]\na\nb\n[Build-Up]\n[Chorus]\nc\n[Outro]\n")
    lines = [[], [_line("a", 8.1, 9.0), _line("b", 9.5, 12.0)], [], [_line("c", 14.0, 20.0)], []]
    secs = build_sections(blocks, lines, duration=30.0, downbeats=[0.0, 8.0, 12.2, 16.0, 20.4, 24.0])
    assert [s.kind for s in secs] == ["intro", "verse", "build", "chorus", "outro"]
    assert secs[0].start == 0.0 and secs[-1].end == 30.0
    assert all(a.end == b.start for a, b in itertools.pairwise(secs))
    assert secs[1].start == 8.0 and secs[2].start == 12.2 and secs[4].start == 20.4
    assert secs[1].tag_details == "Soft" and len(secs[1].lines) == 2
    assert secs[4].lines == [] and secs[4].start < secs[4].end


def test_pool_to_frames_and_normalise():
    fps = 24
    n_analysis = int(2.0 * SR / HOP)
    x = np.ones(n_analysis)
    x[n_analysis // 2 :] = 3.0
    frames = pool_to_frames(x, 48, fps)
    assert frames.shape == (48,)
    assert frames[5] == pytest.approx(1.0) and frames[40] == pytest.approx(3.0)
    norm = normalise(frames)
    assert norm.max() == pytest.approx(1.0) and norm.min() == pytest.approx(1 / 3)
    assert not normalise(np.zeros(10)).any()
