import sys
from itertools import pairwise
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from full_render import chunks


def test_chunks_cover_every_shot_once_with_similar_durations():
    shots = [{"start": i * 6.0, "end": i * 6.0 + (3.0 if i % 4 == 0 else 6.0)} for i in range(45)]
    parts = chunks(shots, 8)
    assert len(parts) == 8 and parts[0][0] == 0 and parts[-1][1] == 45
    assert all(a[1] == b[0] for a, b in pairwise(parts))
    sizes = [sum(shots[i]["end"] - shots[i]["start"] for i in range(a, b)) for a, b in parts]
    assert max(sizes) - min(sizes) <= 12.0


def test_fewer_shots_than_jobs():
    shots = [{"start": i, "end": i + 1.0} for i in range(3)]
    assert chunks(shots, 8) == [(0, 1), (1, 2), (2, 3)]
