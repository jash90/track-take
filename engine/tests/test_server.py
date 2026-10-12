import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tracktake import project, storyboard
from tracktake.models import Analysis, LyricLine, Section


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(project, "PROJECTS", tmp_path / "projects")
    from tracktake import jobs, server

    monkeypatch.setattr(server, "jobs", jobs.JobManager(tmp_path / "jobs"))
    return TestClient(server.app)


def analysis() -> Analysis:
    downs = [round(i * 3.0, 2) for i in range(20)]
    beats = [round(i * 0.75, 2) for i in range(80)]
    return Analysis(audio_sha256="x", duration=60.0, sample_rate=44100, bpm=80, beats=beats, downbeats=downs,
                    sections=[Section(label="Verse 1", kind="verse", start=0.0, end=24.0),
                              Section(label="Build-Up", kind="build", start=24.0, end=25.0),
                              Section(label="Chorus", kind="chorus", start=25.0, end=60.0)],
                    lines=[LyricLine(text="first line", start=1.0, end=3.0), LyricLine(text="chorus", start=27.0, end=29.0)])


def test_plan_shots_two_bars_and_build_merge():
    shots = storyboard.plan_shots(analysis())
    assert shots[0]["start"] == 0.0 and shots[0]["end"] == 6.0
    assert all(s["end"] > s["start"] for s in shots)
    verse = [s for s in shots if s["section"].startswith("Verse")]
    assert verse[-1]["end"] == 25.0 and verse[-1]["section"] == "Verse 1+Build-Up"  # build blip joined
    assert shots[0]["lines"] == ["first line"]
    assert [s["id"] for s in shots] == [f"s{i + 1:02d}" for i in range(len(shots))]


def test_replan_keeps_texts_of_unchanged_shots():
    first = storyboard.replan(analysis(), None, "paper")
    first["shots"][0]["scene"], first["shots"][0]["motion"] = "a door", "it opens"
    again = storyboard.replan(analysis(), first, "paper")
    assert again["shots"][0]["scene"] == "a door" and again["style"] == "paper"


def test_project_crud_and_inputs(client):
    r = client.post("/api/projects", json={"name": "Moja Piosenka!"})
    assert r.status_code == 200
    pid = r.json()["id"]
    assert pid == "moja-piosenka"
    assert client.post("/api/projects", json={"name": "Moja Piosenka!"}).json()["id"] == "moja-piosenka-2"
    assert r.json()["orientation"] == "landscape" and r.json()["format"] == "16x9"
    pion = client.post("/api/projects", json={"name": "Pion", "orientation": "portrait"}).json()
    assert pion["orientation"] == "portrait" and pion["format"] == "9x16"
    assert client.post("/api/projects", json={"name": "x", "orientation": "square"}).status_code == 400
    r2 = client.patch(f"/api/projects/{pion['id']}", json={"orientation": "landscape"})
    assert r2.json()["format"] == "16x9"
    assert client.patch(f"/api/projects/{pion['id']}", json={"orientation": "both"}).status_code == 400
    r = client.patch(f"/api/projects/{pid}", json={"style": "noir", "settings": {"workers": 2}})
    assert r.json()["style"] == "noir" and r.json()["settings"]["workers"] == 2
    img = io.BytesIO()
    Image.new("RGB", (8, 8), "purple").save(img, "PNG")
    r = client.post(f"/api/projects/{pid}/inputs", files={"cover": ("c.png", img.getvalue(), "image/png")},
                    data={"lyrics": "[Verse]\nhello"})
    body = r.json()
    assert body["inputs"]["cover"].endswith("input/cover.png") and body["inputs"]["lyrics"] is True
    assert client.get(f"/api/projects/{pid}/lyrics").json()["text"].startswith("[Verse]")
    bad = client.post(f"/api/projects/{pid}/inputs", files={"song": ("x.exe", b"x", "application/octet-stream")})
    assert bad.status_code == 400
    assert client.get(f"/files/{pid}/input/cover.png").status_code == 200
    for evil in (f"/files/{pid}/%2E%2E/project.json", f"/files/{pid}/..%2Fproject.json", "/files/project.json"):
        r = client.get(evil)
        assert r.status_code == 404 and '"created"' not in r.text, evil
    assert client.get("/api/nope").status_code == 404
    assert client.delete(f"/api/projects/{pid}").json() == {"ok": True}
    assert client.get(f"/api/projects/{pid}").status_code == 404


def test_storyboard_roundtrip_and_guards(client):
    pid = client.post("/api/projects", json={"name": "x"}).json()["id"]
    assert client.get(f"/api/projects/{pid}/storyboard").status_code == 404
    assert client.get(f"/api/projects/{pid}/analysis").status_code == 404
    assert client.post(f"/api/projects/{pid}/storyboard/plan").status_code == 400  # needs analysis
    sb = {"style": "paper", "heroine": "", "shots": [{"id": "s01", "start": 0, "end": 3, "section": "Intro",
                                                       "kind": "intro", "lines": [], "scene": "", "motion": ""}]}
    assert client.put(f"/api/projects/{pid}/storyboard", json=sb).status_code == 200
    assert client.get(f"/api/projects/{pid}").json()["stage"]["shots"] == 1
    assert client.post(f"/api/projects/{pid}/keys/codex", json={}).status_code == 400  # shots without scenes
    r = client.post(f"/api/projects/{pid}/render", json={"set": "codex", "workers": 1})
    assert r.status_code == 400 and "confirm" in r.json()["detail"]
    assert client.get("/api/projects/bad..id").status_code == 404


def test_cuts_only_on_big_sections_and_continuity_helpers():
    shots = storyboard.plan_shots(analysis())
    assert shots[0]["cut"] and storyboard.is_cut(shots, 0)
    chorus = next(i for i, s in enumerate(shots) if s["section"] == "Chorus")
    assert shots[chorus]["cut"] and not any(s["cut"] for s in shots[1:chorus])
    assert storyboard.continues_into(shots, 0) is shots[1]
    assert storyboard.continues_into(shots, chorus - 1) is None and storyboard.continues_into(shots, len(shots) - 1) is None
    legacy = [{k: v for k, v in s.items() if k != "cut"} for s in shots]
    assert all(storyboard.is_cut(legacy, i) for i in range(len(legacy)))  # old storyboards keep cutting every shot


def test_codex_chains_follow_continuity(tmp_path):
    from tracktake.codex_images import ImageJob, chains

    a, b, c, d = (tmp_path / f"{n}.png" for n in "abcd")
    jobs = [ImageJob(a, "", "landscape"), ImageJob(b, "", "landscape", previous=a),
            ImageJob(c, "", "landscape"), ImageJob(d, "", "landscape", previous=c)]
    assert [[j.out.stem for j in ch] for ch in chains(jobs)] == [["a", "b"], ["c", "d"]]
    lone = ImageJob(b, "", "landscape", previous=a)  # previous made earlier: attached if it exists, no chain needed
    assert chains([lone]) == [[lone]] and lone.attachments() == []
    a.write_bytes(b"x")
    assert lone.attachments() == [a]


def test_render_options_are_project_settings(client):
    pid = client.post("/api/projects", json={"name": "opts"}).json()["id"]
    s = client.get(f"/api/projects/{pid}").json()["settings"]
    assert s["captions"] is True and s["beat_motion"] is True
    s = client.patch(f"/api/projects/{pid}", json={"settings": {"captions": False, "beat_motion": False}}).json()["settings"]
    assert s["captions"] is False and s["beat_motion"] is False and s["workers"] == 4


def test_still_camera_has_no_pulses():
    from tracktake.render.timeline import still

    p = still(5)
    assert p.kick == p.snare == p.beat == [0.0] * 5


def test_release_one_card_respects_running_render(client, monkeypatch):
    from tracktake import jobs as jobs_mod
    from tracktake import server, vast
    from tracktake.vast import State

    busy, idle = State(1, 0.5, name="jabc123-w1"), State(2, 0.5, name="bench-w1")
    freed = []
    monkeypatch.setattr(vast, "all_states", lambda: [busy, idle])
    monkeypatch.setattr(vast, "destroy", lambda st, run=None: freed.append(st.instance_id) or 0.1)
    import os

    job = jobs_mod.Job("0123456789ab", "render", "p", "Vast render", status="running", params={"run_id": "jabc123"},
                       pid=os.getpid())
    server.jobs.store.write(job)
    r = client.post("/api/vast/instances/1/down")
    assert r.status_code == 409 and "0123456789ab" in r.json()["detail"] and freed == []
    assert client.post("/api/vast/instances/2/down").json()["freed"] == 2 and freed == [2]
    assert client.post("/api/vast/instances/1/down?force=true").status_code == 200 and freed == [2, 1]


def test_fast_songs_get_longer_shots():
    downs = [round(i * 1.85, 2) for i in range(40)]  # ~130 BPM: two bars would be 3.7 s
    a = Analysis(audio_sha256="x", duration=74.0, sample_rate=44100, bpm=130,
                 beats=[round(i * 0.4625, 3) for i in range(160)], downbeats=downs,
                 sections=[Section(label="Verse 1", kind="verse", start=0.0, end=37.0),
                           Section(label="Chorus", kind="chorus", start=37.0, end=74.0)], lines=[])
    assert storyboard.bars_per_shot(a) == 4
    shots = storyboard.plan_shots(a)
    assert all(s["end"] - s["start"] >= storyboard.MIN_SHOT_S for s in shots)
    assert storyboard.bars_per_shot(analysis()) == 2  # 3 s bars: two bars already last 6 s
