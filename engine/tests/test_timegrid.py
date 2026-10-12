import pytest

from tracktake.timegrid import between, frame_at, frames_of, nearest, snap, subdivide


@pytest.mark.parametrize("bpm", [90, 120, 128, 174])
@pytest.mark.parametrize("fps", [12, 24, 25, 30])
def test_no_drift_over_four_minutes(bpm, fps):
    period = 60.0 / bpm
    beats = [k * period for k in range(int(240 / period) + 1)]
    for t, f in zip(beats, frames_of(beats, fps)):
        assert abs(f / fps - t) <= 0.5 / fps + 1e-9  # within half a frame, i.e. well inside the +-1 frame target


def test_frame_at_rounds_to_nearest():
    assert frame_at(0.0, 24) == 0
    assert frame_at(1 / 48 - 1e-6, 24) == 0
    assert frame_at(1 / 48 + 1e-6, 24) == 1


def test_nearest_and_snap():
    grid = [0.0, 0.5, 1.0, 1.5]
    assert nearest(grid, 0.74) == 0.5
    assert nearest(grid, 0.76) == 1.0
    assert nearest(grid, -3) == 0.0
    assert nearest(grid, 9) == 1.5
    assert snap(0.6, grid) == 0.5
    assert snap(0.7, grid, max_distance=0.1) == 0.7


def test_subdivide_three_four_bar():
    beats = [0.0, 1.0, 2.0, 3.0]
    assert subdivide(beats, 2) == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    with pytest.raises(ValueError):
        subdivide(beats, 0)


def test_between_is_half_open():
    assert between([0, 1, 2, 3], 1, 3) == [1, 2]
