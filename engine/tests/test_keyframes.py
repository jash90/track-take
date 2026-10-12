from PIL import Image

from tracktake import codex_images, keyframes
from tracktake.project import Project


def storyboard():
    return {"style": "paper", "heroine": "a woman in a red coat",
            "locations": [{"id": "room", "name": "Room", "look": "a small room with a single bed"}],
            "props": [{"id": "bed", "name": "Bed", "look": "a narrow single bed"}],
            "shots": [{"id": "s01", "scene": "the woman wakes up", "motion": "", "location": "room", "props": ["bed"]},
                      {"id": "s02", "scene": "she sits up", "motion": "", "location": "room", "cut": False},
                      {"id": "s03", "scene": "a street at night", "motion": "", "cut": True}]}


def project(tmp_path, sb):
    p = Project(tmp_path)
    p.save_storyboard(sb)
    return p


def draw(p, sb, shots):
    prints = keyframes.fingerprints(sb, "landscape")
    for s in shots:
        out = p.key_path("codex", s, "landscape")
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8)).save(out)
        codex_images.fingerprint_path(out).write_text(prints[s])


def jobs(p):
    return {j.out.stem: j.replace for j in keyframes.codex_jobs(p, orientations=["landscape"])}


def test_fresh_keyframes_need_nothing(tmp_path):
    sb = storyboard()
    p = project(tmp_path, sb)
    assert jobs(p) == {"s01_landscape": False, "s02_landscape": False, "s03_landscape": False}
    draw(p, sb, ["s01", "s02", "s03"])
    assert jobs(p) == {}


def test_bible_edit_makes_the_location_and_its_take_stale(tmp_path):
    sb = storyboard()
    p = project(tmp_path, sb)
    draw(p, sb, ["s01", "s02", "s03"])
    sb["props"][0]["look"] = "a wide double bed"  # s01 shows the bed; s02 continues s01's take
    p.save_storyboard(sb)
    assert jobs(p) == {"s01_landscape": True, "s02_landscape": True}
    assert keyframes.listing(p)["sets"]["codex"]["s03"]["landscape_stale"] is False
    assert keyframes.listing(p)["sets"]["codex"]["s02"]["landscape_stale"] is True


def test_scene_edit_later_in_a_take_leaves_earlier_frames(tmp_path):
    sb = storyboard()
    p = project(tmp_path, sb)
    draw(p, sb, ["s01", "s02", "s03"])
    sb["shots"][1]["scene"] = "she stands by the window"
    p.save_storyboard(sb)
    assert jobs(p) == {"s02_landscape": True}


def test_keyframes_without_a_fingerprint_are_adopted(tmp_path):
    sb = storyboard()
    p = project(tmp_path, sb)
    for s in ("s01", "s02", "s03"):
        out = p.key_path("codex", s, "landscape")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"png")
    assert jobs(p) == {}  # made before fingerprints existed: taken as current
    sb["shots"][2]["scene"] = "a street in the rain"
    p.save_storyboard(sb)
    assert jobs(p) == {"s03_landscape": True}  # later edits are caught


def test_failed_redraw_keeps_the_old_image(tmp_path, monkeypatch):
    out = tmp_path / "s01_landscape.png"
    out.write_bytes(b"old")
    codex_images.fingerprint_path(out).write_text("before")

    def fail(job, timeout, retries):
        raise RuntimeError("codex down")

    monkeypatch.setattr(codex_images, "_generate", fail)
    job = codex_images.ImageJob(out, "x", "landscape", fingerprint="after", replace=True)
    try:
        codex_images.generate(job)
    except RuntimeError:
        pass
    assert out.read_bytes() == b"old" and codex_images.fingerprint_path(out).read_text() == "before"

    def ok(job, timeout, retries):
        assert out.read_bytes() == b"old"  # the old image stays visible while the new one is drawn
        job.out.write_bytes(b"new")
        return 1.0

    monkeypatch.setattr(codex_images, "_generate", ok)
    codex_images.generate(job)
    assert out.read_bytes() == b"new" and codex_images.fingerprint_path(out).read_text() == "after"
    assert not out.with_name("s01_landscape.new.png").exists()


def test_old_keyframes_rewritten_by_continuity_are_stale(tmp_path):
    import os

    sb = storyboard()
    p = project(tmp_path, sb)
    for s in ("s01", "s02", "s03"):
        out = p.key_path("codex", s, "landscape")
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (8, 8)).save(out)
        os.utime(out, (1_000_000_000, 1_000_000_000))  # drawn in 2001, before the check below
    sb["continuity"] = {"checked": "2026-10-12T14:26:22+00:00",
                        "issues": [{"shot": "s01", "problem": "double bed", "before": "..."}]}
    p.save_storyboard(sb)
    assert jobs(p) == {"s01_landscape": True, "s02_landscape": True}  # s02 continues s01's take
    sb["continuity"] = {"checked": "2026-10-12T15:00:00+00:00", "issues": []}  # a later check, other fixes
    p.save_storyboard(sb)
    assert jobs(p) == {"s01_landscape": True, "s02_landscape": True}  # still stale


def test_forced_regeneration_redraws_a_current_keyframe(tmp_path):
    sb = storyboard()
    p = project(tmp_path, sb)
    draw(p, sb, ["s01", "s02", "s03"])
    got = keyframes.codex_jobs(p, shots=["s02"], orientations=["landscape"], force=True)
    assert [j.out.stem for j in got] == ["s02_landscape"] and not got[0].replace
