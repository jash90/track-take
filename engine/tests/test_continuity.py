from pathlib import Path

from tracktake import codex_images, continuity, keyframes
from tracktake.codex_images import ImageJob


def storyboard():
    return {
        "style": "paper", "heroine": "a woman with a black bob",
        "locations": [{"id": "bedroom", "name": "bedroom", "look": "a narrow single bed with a grey blanket"}],
        "props": [{"id": "phone", "name": "phone", "look": "a small black phone"}],
        "shots": [
            {"id": "s01", "cut": True, "section": "Verse", "scene": "the woman lies on the bed", "motion": "m",
             "location": "bedroom", "props": ["phone"]},
            {"id": "s02", "cut": False, "section": "Verse", "scene": "the empty other side of the bed", "motion": "m",
             "location": "bedroom", "props": []},
        ],
    }


def test_keyframe_prompt_carries_the_fixed_looks():
    text = keyframes.shot_prompt(storyboard(), storyboard()["shots"][0], "landscape")
    assert "narrow single bed with a grey blanket" in text and "small black phone" in text


def test_check_applies_fixes_and_records_them(monkeypatch):
    def fake_ask(prompt, cover, timeout, log, schema, key, who, shape):
        assert "narrow single bed" in prompt and "s02 CONTINUES @bedroom" in prompt
        return {"issues": [{"shot": "s02", "problem": "implies a double bed",
                            "scene": "the woman alone on the narrow single bed", "motion": "m2"},
                           {"shot": "nope", "problem": "unknown shot", "scene": "x", "motion": "y"}]}

    monkeypatch.setattr(continuity, "ask", fake_ask)
    sb, issues = continuity.check(storyboard(), log=lambda *_: None)
    assert [i["shot"] for i in issues] == ["s02"] and issues[0]["before"] == "the empty other side of the bed"
    assert sb["shots"][1]["scene"] == "the woman alone on the narrow single bed" and sb["shots"][1]["motion"] == "m2"
    assert sb["continuity"]["issues"] == issues


def test_scheduler_waits_for_previous_and_location_anchor(monkeypatch, tmp_path):
    order = []

    def fake_generate(job, timeout=900, retries=1):
        order.append(job.out.name)
        job.out.write_bytes(b"x")
        return 0.0

    monkeypatch.setattr(codex_images, "generate", fake_generate)
    a, b, c, d = (tmp_path / f"{n}.png" for n in "abcd")
    jobs = [ImageJob(d, "", "landscape", anchor=a),  # same place as a, after a cut
            ImageJob(b, "", "landscape", previous=a), ImageJob(a, "", "landscape"), ImageJob(c, "", "landscape")]
    codex_images.generate_all(jobs, workers=3)
    assert order.index("a.png") < order.index("b.png") and order.index("a.png") < order.index("d.png")
    assert ImageJob(d, "", "landscape", anchor=a).attachments() == [a]


def test_anchor_not_waited_for_when_outside_the_batch(monkeypatch, tmp_path):
    monkeypatch.setattr(codex_images, "generate", lambda job, **_: (job.out.write_bytes(b"x"), 0.0)[1])
    out = tmp_path / "x.png"
    res = codex_images.generate_all([ImageJob(out, "", "landscape", anchor=Path(tmp_path / "old.png"))], workers=1)
    assert res == {"x.png": 0.0}
