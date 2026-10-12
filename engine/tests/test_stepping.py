import itertools

import pytest

from sunomv.render.stepping import active_drawing, drawing_frames, pulse_track


def test_on_twos_without_forced():
    assert drawing_frames(0, 9, 2) == [0, 2, 4, 6, 8]


def test_forced_beat_restarts_cadence():
    # beat at frame 5 interrupts the twos and the cadence continues from it
    assert drawing_frames(0, 10, 2, forced=[5]) == [0, 2, 4, 5, 7, 9]


def test_forced_too_close_is_skipped():
    assert drawing_frames(0, 8, 3, forced=[1], min_hold=2) == [0, 3, 6]


def test_forced_outside_range_ignored():
    assert drawing_frames(10, 14, 2, forced=[3, 99]) == [10, 12]


def test_bad_cadence():
    with pytest.raises(ValueError):
        drawing_frames(0, 5, 0)


def test_active_drawing():
    starts = [0, 2, 4, 5]
    assert [active_drawing(f, starts) for f in range(7)] == [0, 0, 1, 1, 2, 3, 3]


def test_pulse_decays_and_retriggers():
    track = pulse_track(20, 24, [(0.0, 1.0), (10 / 24, 0.5)], decay_frames=4)
    assert track[0] == 1.0
    assert track[2] == pytest.approx(0.5)  # half-life of 2 frames
    assert track[10] == 0.5  # retrigger takes the max of decayed level and new hit
    assert all(a >= b for a, b in itertools.pairwise(track[:10]))  # decays until the retrigger
