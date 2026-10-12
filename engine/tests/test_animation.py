import sys
from pathlib import Path

import numpy as np

from tracktake import animation, storyboard
from tracktake.render.compositor import Shot, whip

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from full_render import Blended, whips, zoom_span
from test_server import analysis


def test_stopmotion_stays_the_default_plan():
    a = analysis()
    assert storyboard.plan_shots(a) == storyboard.plan_shots(a, "stopmotion")
    assert storyboard.replan(a, None, "")["animation"] == "stopmotion"
    assert zoom_span([{"cut": True}, {"cut": False}], 1, animation.get(None)["zoom"]) == (1.02, 1.04)


def test_tableau_cuts_every_shot_on_the_bar():
    a = analysis()
    shots = storyboard.plan_shots(a, "tableau")
    assert all(s["cut"] for s in shots) and not any("role" in s for s in shots)
    assert min(s["end"] - s["start"] for s in shots[:-1]) >= 4.0 - 0.01
    sb = storyboard.replan(a, None, "", "tableau")
    prompt = storyboard.director_prompt(sb, [shots[0]["id"]], "", None, "")
    assert animation.ANIMATIONS["tableau"]["motion"] in prompt and "role:" not in prompt


def test_journey_follows_the_song_parts():
    a = analysis()  # bar 3 s: verse 0-24, a 1 s build-up blip, chorus 25-60
    shots = storyboard.plan_shots(a, "journey")
    assert all(s["cut"] for s in shots)
    verse = [s for s in shots if s["kind"] == "verse"]
    chorus = [s for s in shots if s["kind"] == "chorus"]
    assert [s["transition"] for s in verse] == ["cut", "whip", "whip", "whip"]  # whip pans chain a verse
    assert {s["role"] for s in verse} == {"tableau"} and verse[-1]["end"] == 25.0  # the blip joined the verse
    assert all(s["transition"] == "cut" for s in chorus)  # hard cuts in a chorus
    assert [s["role"] for s in chorus][:4] == ["insert", "wide", "insert", "wide"]
    assert chorus[0]["start"] == 25.0 and chorus[0]["end"] - chorus[0]["start"] >= 3.0  # partial bar joined
    sb = storyboard.replan(a, None, "", "journey")
    prompt = storyboard.director_prompt(sb, [shots[0]["id"]], "", None, "")
    assert animation.ANIMATIONS["journey"]["motion"] in prompt and "| role: insert" in prompt
    plain = storyboard.replan(a, None, "")
    assert "living illustration" not in storyboard.director_prompt(plain, [shots[0]["id"]], "", None, "")


def test_planned_transitions_decide_the_whips():
    shots = [{"transition": "cut"}, {"transition": "whip"}, {"transition": "cut"}]
    assert [whips(shots, i, 5) for i in range(3)] == [(0, 5), (5, 0), (0, 0)]


def test_whips_join_a_section_and_hard_cut_into_the_next():
    shots = [{"section": "Verse 1"}, {"section": "Verse 1"}, {"section": "Chorus+Build-Up"}, {"section": "Chorus"}]
    assert [whips(shots, i, 5) for i in range(4)] == [(0, 5), (5, 0), (0, 5), (5, 0)]
    assert whips(shots, 1, 0) == (0, 0)


def test_whip_moves_only_the_frames_around_the_cut():
    frame = np.zeros((20, 40, 3), np.uint8)
    frame[:, :20] = 255
    shot = Shot(0, 24, [], whip_in=5, whip_out=5)
    assert whip(frame, shot, 12) is frame  # the middle of the shot is untouched
    assert not np.array_equal(whip(frame, shot, 0), frame) and not np.array_equal(whip(frame, shot, 23), frame)
    assert np.abs(whip(frame, shot, 0).astype(int) - frame).sum() > np.abs(whip(frame, shot, 4).astype(int) - frame).sum()


def test_blended_frames_mix_neighbours():
    frames = [np.full((2, 2, 4), 0, np.uint8), np.full((2, 2, 4), 200, np.uint8)]
    b = Blended(frames, [0.0, 0.5, 1.0])
    assert len(b) == 3 and b[0][0, 0, 0] == 0 and b[1][0, 0, 0] == 100 and b[2][0, 0, 0] == 200
