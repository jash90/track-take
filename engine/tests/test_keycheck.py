from PIL import Image

from tracktake import codex_images, keycheck, keyframes
from tracktake.project import Project


def storyboard():
    return {"style": "paper", "heroine": "a woman",
            "locations": [{"id": "road", "name": "Road", "look": "a highway, lamps on the right"}],
            "props": [{"id": "car", "name": "Car", "look": "a red convertible; the man drives on the left"}],
            "shots": [{"id": "s01", "scene": "a bar", "motion": ""},
                      {"id": "s02", "scene": "the bar later", "motion": "", "cut": False},
                      {"id": "s03", "scene": "the car seen from the front", "motion": "", "location": "road",
                       "props": ["car"], "cut": True},
                      {"id": "s04", "scene": "the car from behind", "motion": "", "location": "road", "cut": False},
                      {"id": "s05", "scene": "a park", "motion": "", "cut": True}]}


def project(tmp_path):
    p = Project(tmp_path)
    sb = storyboard()
    p.save_storyboard(sb)
    prints = keyframes.fingerprints(sb, "landscape")
    for s in sb["shots"]:
        out = p.key_path("codex", s["id"], "landscape")
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.new("RGB", (4, 2))
        im.putpixel((0, 0), (255, 0, 0))  # red top-left: shows a flip
        im.save(out)
        codex_images.fingerprint_path(out).write_text(prints[s["id"]])
    return p


def test_groups_follow_locations_and_takes():
    sb = storyboard()
    assert keycheck.groups(sb) == [["s03", "s04"], ["s01", "s02"], ["s05"]]
    long = {"shots": [{"id": f"s{i:02d}", "location": "road"} for i in range(1, 12)]}
    chunks = keycheck.groups(long)
    assert [len(c) for c in chunks] == [8, 4] and chunks[0][-1] == chunks[1][0]  # one image of overlap


def test_check_asks_with_images_and_keeps_only_known_shots(tmp_path, monkeypatch):
    p = project(tmp_path)
    seen = []

    def fake_ask(prompt, cover, timeout, log, schema, key, who, shape, images=None):
        seen.append([i.name for i in images])
        if "s03" in prompt:
            return {"issues": [{"shot": "s03", "kind": "mirrored", "problem": "driver on the wrong side", "fix": "x"},
                               {"shot": "s99", "kind": "object", "problem": "?", "fix": "?"}]}
        return {"issues": []}

    monkeypatch.setattr(keycheck, "ask", fake_ask)
    issues = keycheck.check(p, "landscape", log=lambda *_: None)
    assert [i["shot"] for i in issues] == ["s03"]
    assert ["s03_landscape.png", "s04_landscape.png"] in seen
    assert keycheck.report(p)["issues"][0]["kind"] == "mirrored"


def test_apply_flips_mirrored_and_flags_the_rest(tmp_path):
    p = project(tmp_path)
    issues = [{"shot": "s03", "kind": "mirrored", "problem": "mirrored", "fix": "flip"},
              {"shot": "s05", "kind": "object", "problem": "The fountain has three tiers.", "fix": "Draw two tiers."}]
    done = keycheck.apply(p, issues, "landscape", log=lambda *_: None)
    assert done == {"flipped": ["s03"], "redraw": ["s05"]}
    flipped = p.key_path("codex", "s03", "landscape")
    assert Image.open(flipped).getpixel((3, 0)) == (255, 0, 0)
    assert flipped.with_suffix(".orig.png").exists()
    jobs = keyframes.codex_jobs(p, orientations=["landscape"])
    assert [j.out.stem for j in jobs] == ["s05_landscape"]  # the flipped one is fine, the flagged one is redrawn
    assert jobs[0].replace and "Draw two tiers." in jobs[0].prompt and jobs[0].fix_note
    entry = keyframes.listing(p)["sets"]["codex"]
    assert entry["s05"]["landscape_issue"].startswith("The fountain") and entry["s03"]["landscape_flipped"]


def test_redraw_clears_the_note(tmp_path, monkeypatch):
    p = project(tmp_path)
    keycheck.apply(p, [{"shot": "s05", "kind": "count", "problem": "two lamps", "fix": "one lamp"}], "landscape",
                   log=lambda *_: None)

    def ok(job, timeout, retries):
        Image.new("RGB", (4, 2)).save(job.out)
        return 1.0

    monkeypatch.setattr(codex_images, "_generate", ok)
    for job in keyframes.codex_jobs(p, orientations=["landscape"]):
        codex_images.generate(job)
    assert keyframes.codex_jobs(p, orientations=["landscape"]) == []
    assert not keycheck.note_path(p.key_path("codex", "s05", "landscape")).exists()


def test_a_flagged_frame_is_redrawn_alone(tmp_path):
    p = project(tmp_path)  # s03 -> s04 is one take at the road
    keycheck.apply(p, [{"shot": "s03", "kind": "object", "problem": "a blue car", "fix": "a red car"}], "landscape",
                   log=lambda *_: None)
    assert [j.out.stem for j in keyframes.codex_jobs(p, orientations=["landscape"])] == ["s03_landscape"]


def test_a_vetoed_flip_leaves_the_picture(tmp_path):
    p = project(tmp_path)
    issue = {"shot": "s03", "kind": "mirrored", "problem": "mirrored?", "fix": ""}
    done = keycheck.apply(p, [issue], "landscape", log=lambda *_: None, confirm_flip=lambda i, image: False)
    image = p.key_path("codex", "s03", "landscape")
    assert done == {"flipped": [], "redraw": []} and Image.open(image).getpixel((0, 0)) == (255, 0, 0)
