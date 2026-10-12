"""Local web API for the UI (contract: apps/web/src/api/types.ts). Run with `uv run tracktake serve`."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from tracktake import autopilot, keyframes, project, setup_check, steps
from tracktake.config import REPO_ROOT
from tracktake.jobs import Conflict, JobManager
from tracktake.models import Analysis
from tracktake.project import FORMATS, KEY_SETS, Project

ENGINE = REPO_ROOT / "engine"
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"
log = logging.getLogger("tracktake.server")

app = FastAPI(title="tracktake")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])
jobs = JobManager()


@app.exception_handler(KeyError)
async def _not_found(_request: Request, exc: KeyError):
    return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)


@app.exception_handler(Conflict)
async def _conflict(_request: Request, exc: Conflict):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(ValueError)
async def _bad(_request: Request, exc: ValueError):
    return JSONResponse({"detail": str(exc)}, status_code=400)


# ------------------------------------------------------------------------------------------------ projects

def project_json(p: Project) -> dict:
    m = p.meta()
    sb = p.storyboard()
    shots = sb["shots"] if sb else []
    o, fmt = m.orientation, project.FORMAT_OF[m.orientation]
    keys = {k: sum(1 for s in shots if p.key_path(k, s["id"], o).exists()) for k in KEY_SETS}
    videos = {k: [f for f in FORMATS if f == fmt and any(x.exists() for x in p.video_paths(k, f))] for k in KEY_SETS}
    song, cover = p.input_file("song"), p.input_file("cover")
    return {
        "id": p.id, "name": m.name, "created": m.created, "style": m.style, "language": m.language,
        "orientation": o, "format": fmt,
        "inputs": {"song": p.url(song) if song else None, "cover": p.url(cover) if cover else None,
                   "lyrics": bool(p.lyrics().strip())},
        "stage": {"analysis": p.analysis_path.exists(), "storyboard": bool(sb),
                  "storyboard_written": sum(1 for s in shots if s.get("scene")), "shots": len(shots),
                  "character_sheet": p.url(p.character_sheet) if p.character_sheet.exists() else None,
                  "keys": keys, "videos": videos},
        "settings": asdict(m.settings),
        "storyboard_approved": m.storyboard_approved, "autopilot": m.autopilot,
    }


class NewProject(BaseModel):
    name: str
    orientation: str = "landscape"
    style: str = ""
    language: str = "en"


class ProjectPatch(BaseModel):
    name: str | None = None
    orientation: str | None = None
    style: str | None = None
    language: str | None = None
    settings: dict | None = None


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return [project_json(p) for p in project.all_projects()]


@app.post("/api/projects")
def new_project(body: NewProject) -> dict:
    if not body.name.strip():
        raise ValueError("name is required")
    return project_json(project.create(body.name.strip(), body.style, body.language, body.orientation))


@app.get("/api/projects/{pid}")
def get_project(pid: str) -> dict:
    return project_json(project.get(pid))


@app.patch("/api/projects/{pid}")
def patch_project(pid: str, body: ProjectPatch) -> dict:
    p = project.get(pid)
    p.update(**body.model_dump())
    return project_json(p)


@app.delete("/api/projects/{pid}")
def delete_project(pid: str) -> dict:
    project.delete(pid)
    return {"ok": True}


@app.post("/api/projects/{pid}/inputs")
async def upload_inputs(pid: str, song: Annotated[UploadFile | None, File()] = None,
                        cover: Annotated[UploadFile | None, File()] = None,
                        lyrics: Annotated[str | None, Form()] = None) -> dict:
    p = project.get(pid)
    if song is not None:
        p.save_input("song", song.filename or "song.mp3", await song.read())
    if cover is not None:
        p.save_input("cover", cover.filename or "cover.jpg", await cover.read())
    if lyrics is not None:
        p.save_lyrics(lyrics)
    return project_json(p)


@app.get("/api/projects/{pid}/lyrics")
def get_lyrics(pid: str) -> dict:
    return {"text": project.get(pid).lyrics()}


# ------------------------------------------------------------------------------------------------ analysis

@app.post("/api/projects/{pid}/analyze")
def analyze(pid: str) -> dict:
    p = project.get(pid)
    if not p.input_file("song"):
        raise ValueError("upload a song first")
    return jobs.view(jobs.submit("analyze", pid, "Song analysis", "tracktake.steps:run_analyze"))


@app.get("/api/projects/{pid}/analysis")
def get_analysis(pid: str) -> dict:
    p = project.get(pid)
    if not p.analysis_path.exists():
        raise KeyError("analysis")
    a = Analysis.model_validate_json(p.analysis_path.read_text())
    return {"duration": a.duration, "bpm": a.bpm, "beats": a.beats, "downbeats": a.downbeats,
            "sections": [{"label": s.label, "kind": s.kind, "start": s.start, "end": s.end} for s in a.sections],
            "lines": [{"text": ln.text, "start": ln.start, "end": ln.end} for ln in a.lines]}


@app.get("/api/projects/{pid}/peaks")
def get_peaks(pid: str, n: int = 1500) -> dict:
    p = project.get(pid)
    song = p.input_file("song")
    if not song:
        raise KeyError("song")
    n = max(100, min(n, 8000))
    cache = p.root / "peaks.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        if data.get("n") == n and data.get("song") == song.name:
            return {"duration": data["duration"], "peaks": data["peaks"]}
    sr = 4000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(song), "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    x = np.abs(np.frombuffer(raw, dtype=np.float32))
    buckets = np.array_split(x, n)
    peaks = np.array([b.max() if len(b) else 0.0 for b in buckets])
    peaks = (peaks / (np.percentile(peaks, 99.5) or 1.0)).clip(0, 1)
    out = {"duration": round(len(x) / sr, 3), "peaks": [round(float(v), 3) for v in peaks]}
    cache.write_text(json.dumps(out | {"n": n, "song": song.name}))
    return out


# ------------------------------------------------------------------------------------------------ storyboard

def _analysis(p: Project) -> Analysis:
    if not p.analysis_path.exists():
        raise ValueError("analyse the song first")
    return Analysis.model_validate_json(p.analysis_path.read_text())


@app.get("/api/projects/{pid}/storyboard")
def get_storyboard(pid: str) -> dict:
    sb = project.get(pid).storyboard()
    if not sb:
        raise KeyError("storyboard")
    return sb


@app.put("/api/projects/{pid}/storyboard")
def put_storyboard(pid: str, body: dict) -> dict:
    p = project.get(pid)
    if not isinstance(body.get("shots"), list):
        raise ValueError("storyboard needs a shots list")  # noqa: TRY004 - a 400 for the client, see handler
    p.save_storyboard(body)
    return body


@app.post("/api/projects/{pid}/storyboard/plan")
def plan_storyboard(pid: str) -> dict:
    return steps.plan(project.get(pid))


class WriteBody(BaseModel):
    shots: list[str] | None = None
    instructions: str = ""


@app.post("/api/projects/{pid}/storyboard/write")
def write_storyboard(pid: str, body: WriteBody) -> dict:
    p = project.get(pid)
    if not p.storyboard():
        steps.plan(p)
    n = len(body.shots) if body.shots else len(p.storyboard()["shots"])
    return jobs.view(jobs.submit("storyboard", pid, f"Director writes the storyboard ({n} shots)",
                                 "tracktake.steps:run_write", {"shots": body.shots, "instructions": body.instructions},
                                 {"shots": n}))


@app.post("/api/projects/{pid}/storyboard/check")
def check_storyboard(pid: str) -> dict:
    """Continuity check of the whole storyboard (runs after every director pass too; this re-runs it after edits)."""
    p = project.get(pid)
    if not p.storyboard():
        raise ValueError("no storyboard")
    return jobs.view(jobs.submit("continuity", pid, "Continuity check", "tracktake.steps:run_continuity"))


# ------------------------------------------------------------------------------------------------ keyframes

@app.get("/api/projects/{pid}/keys")
def get_keys(pid: str) -> dict:
    return keyframes.listing(project.get(pid))


class CharacterBody(BaseModel):
    force: bool = False


@app.post("/api/projects/{pid}/character")
def make_character(pid: str, body: CharacterBody) -> dict:
    project.get(pid)  # 404 for an unknown project before a process is started
    return jobs.view(jobs.submit("character", pid, "Character sheet (Codex)", "tracktake.steps:run_character",
                                 {"force": body.force}))


class CodexKeysBody(BaseModel):
    shots: list[str] | None = None
    force: bool = False
    workers: int = 4


@app.post("/api/projects/{pid}/keys/codex")
def make_codex_keys(pid: str, body: CodexKeysBody) -> dict:
    p = project.get(pid)
    planned = keyframes.codex_jobs(p, body.shots, [p.meta().orientation], force=False)  # validates the storyboard early
    params = {"shots": len(body.shots)} if body.shots else {"missing": len(planned)}
    label = f"{len(body.shots)} shots" if body.shots else f"{len(planned)} missing"
    return jobs.view(jobs.submit("keys_codex", pid, f"Codex keyframes ({label})", "tracktake.steps:run_codex_keys",
                                 {"shots": body.shots, "force": body.force, "workers": body.workers}, params))


# ------------------------------------------------------------------------------------------------ videos / Vast

@app.get("/api/projects/{pid}/videos")
def get_videos(pid: str) -> dict:
    p = project.get(pid)
    out: dict = {}
    for k in KEY_SETS:
        out[k] = {}
        for f in FORMATS:
            master, preview = p.video_paths(k, f)
            if master.exists() or preview.exists():
                out[k][f] = {"preview": p.url(preview) if preview.exists() else None,
                             "master": p.url(master) if master.exists() else None,
                             "size_mb": {n: round(x.stat().st_size / 1e6, 1)
                                         for n, x in (("preview", preview), ("master", master)) if x.exists()}}
    return out


def _settings_ns(gpu: str | None, max_dph: float | None, gpus: int | None = None) -> argparse.Namespace:
    return argparse.Namespace(gpu=gpu, max_dph=max_dph, gpus=gpus)


@app.get("/api/projects/{pid}/estimate")
def estimate(pid: str, set: str = "codex", workers: int = 4, gpu: str | None = None, gpus: int | None = None,
             max_dph: float | None = None) -> dict:
    from tracktake import cli, vast

    p = project.get(pid)
    m = p.meta().settings
    sb = p.storyboard()
    if not sb:
        raise ValueError("no storyboard")
    orientation = p.meta().orientation
    clips = len(sb["shots"])
    models = ["wan22_i2v", "zimage"] if set == "comfy" else ["wan22_i2v"]
    s = cli._remote_settings(_settings_ns(gpu or m.gpu, max_dph or m.max_dph, gpus or m.gpus), models)
    available = len(vast.search_offers(s, limit=100))  # cached a minute; a render can't get more machines than this
    workers = min(workers, available) if available else workers
    hours, usd = cli._estimate(s, workers, clips, formats=1)
    alternatives = []
    for n in sorted(n for n in {1, 2, 4, workers} if not available or n <= available):
        h, u = (hours, usd) if n == workers else cli._estimate(s, n, clips, formats=1)
        alternatives.append({"workers": n, "minutes": round(h * 60), "usd": round(u, 2)})
    offers = vast.search_offers(s, limit=5)
    missing = 0 if set == "comfy" else sum(1 for sh in sb["shots"]
                                           if not p.key_path("codex", sh["id"], orientation).exists())
    return {"set": set, "workers": workers, "clips": clips, "minutes": round(hours * 60), "usd": round(usd, 2),
            "models_gb": round(s.download_gb), "missing_keys": missing, "alternatives": alternatives,
            "gpu": s.gpu, "gpus": s.gpus, "speed": cli.gpu_speed(s.gpu), "speed_measured": s.gpu in cli.GPU_SPEED,
            "no_offers": not offers, "max_dph": s.max_dph, "available_machines": available,
            "offers": [{"id": o.id, "gpu": o.gpu, "dph": round(o.dph, 3), "download_usd": round(o.setup_cost(s.download_gb), 2),
                        "inet_down": round(o.inet_down), "location": o.location} for o in offers]}


class RenderBody(BaseModel):
    set: str
    workers: int = 4
    gpu: str | None = None
    gpus: int | None = None
    max_dph: float | None = None
    masters: bool = True
    confirm: bool = False


@app.post("/api/projects/{pid}/render")
def render(pid: str, body: RenderBody) -> dict:
    p = project.get(pid)
    if not body.confirm:
        raise ValueError("rendering on Vast costs money: send confirm=true")
    if body.set not in KEY_SETS:
        raise ValueError("set must be codex or comfy")
    m = p.meta().settings
    args = {"kind": body.set, "workers": body.workers, "gpu": body.gpu or m.gpu, "gpus": body.gpus or m.gpus,
            "max_dph": body.max_dph or m.max_dph, "masters": body.masters, "run_id": steps.new_run_id()}
    steps.render_command(p, **args)  # validates the project before a process is started
    name = "Codex" if body.set == "codex" else "ComfyUI"
    return jobs.view(jobs.submit("render", pid, f"Vast render ({name}, {body.workers} cards)",
                                 "tracktake.steps:job_render", args,
                                 {"set": body.set, "workers": body.workers, "run_id": args["run_id"]}))


# ------------------------------------------------------------------------------------------------ autopilot & setup

class AutopilotBody(BaseModel):
    budget_usd: float = 1.0
    preset: str = "recommended"  # cheapest | recommended | fastest | custom (the project's saved card settings)
    review: bool = True  # stop after the director so the storyboard can be checked
    approve: bool = False  # the storyboard has been reviewed: continue past it


@app.post("/api/projects/{pid}/autopilot")
def start_autopilot(pid: str, body: AutopilotBody) -> dict:
    """Make the video: run every missing step (analysis -> storyboard -> keyframes -> render within the budget)."""
    p = project.get(pid)
    if not p.input_file("song"):
        raise ValueError("upload a song first")
    if body.preset not in ("cheapest", "recommended", "fastest", "custom"):
        raise ValueError("preset must be cheapest, recommended, fastest or custom (the project's own settings)")
    if body.approve:
        p.update(storyboard_approved=True)
    return jobs.view(jobs.submit("autopilot", pid, "Make the video", "tracktake.autopilot:run",
                                 {"budget_usd": body.budget_usd, "preset": body.preset, "review": body.review},
                                 {"budget_usd": body.budget_usd, "preset": body.preset}))


@app.get("/api/projects/{pid}/render-presets")
def render_presets(pid: str) -> dict:
    p = project.get(pid)
    return {"clips": autopilot.clip_count(p), "estimated_clips": not p.storyboard(),
            "presets": autopilot.render_presets(p)}


@app.get("/api/setup")
def setup_status() -> dict:
    return setup_check.status()


@app.post("/api/setup/ssh-key")
def setup_ssh_key() -> dict:
    """Create the SSH key if needed and add it to the Vast account (workers are reached over SSH)."""
    return setup_check.ensure_ssh_key_on_vast()


@app.get("/api/vast/gpus")
def vast_gpus() -> dict:
    """GPU models on offer now (cached ~5 min): for the card picker's autocomplete and its price/speed hints."""
    from tracktake import cli, config

    s = config.load().vast
    return {"min_vram_gb": 24, "filters": {"min_reliability": s.min_reliability, "max_download_usd_per_gb":
            s.max_download_cost, "min_inet_down_mbps": s.min_inet_down}, "gpus": cli.gpu_catalog(s)}


@app.get("/api/vast")
def vast_status() -> dict:
    from tracktake import vast

    key_file = Path.home() / ".config" / "vastai" / "vast_api_key"
    configured = key_file.exists() or bool(os.environ.get("VAST_API_KEY"))
    out: dict = {"configured": configured, "balance": None, "instances": []}
    if not configured:
        return out
    try:
        user = json.loads(vast.run_cli(["show", "user", "--raw"]))
        out["balance"] = round(float(user.get("credit", 0) or 0), 2)
        names = {st.instance_id: st.name for st in vast.all_states()}
        for i in json.loads(vast.run_cli(["show", "instances", "--raw"])):
            name = names.get(i["id"], "")
            job = _job_using(name)
            out["instances"].append({"id": i["id"], "name": name or i.get("label") or "", "known": bool(name),
                                     "gpu": i.get("gpu_name", ""), "status": i.get("actual_status") or "",
                                     "dph": round(float(i.get("dph_total") or 0), 3),
                                     "in_use": job is not None, "job": job.id if job else None,
                                     "project": job.project if job else None})
    except Exception as e:  # noqa: BLE001 - shown in the UI
        out["error"] = str(e)
    return out


class VastKey(BaseModel):
    key: str


@app.post("/api/vast/key")
def set_vast_key(body: VastKey) -> dict:
    key = body.key.strip()
    if len(key) < 20 or any(c.isspace() for c in key):
        raise ValueError("this does not look like a Vast API key")
    subprocess.run([str(Path(sys.executable).parent / "vastai"), "set", "api-key", key], capture_output=True, check=True)
    key_file = Path.home() / ".config" / "vastai" / "vast_api_key"
    if key_file.exists():
        key_file.chmod(0o600)
    try:  # workers are reached over SSH: put this machine's key on the account right away
        setup_check.ensure_ssh_key_on_vast()
    except Exception as e:  # noqa: BLE001 - the setup checklist shows what is still missing
        log.warning("could not add the SSH key to Vast: %s", e)
    return vast_status()


def _job_using(worker_name: str):
    """The running render whose Vast worker this is (worker names start with the job's run id), else None.
    A render started before run ids existed claims every worker this machine knows about, to be safe."""
    if not worker_name:
        return None
    for j in jobs.list():
        if j.kind in ("render", "autopilot") and j.status in ("queued", "running"):
            run_id = j.params.get("run_id")
            if (not run_id and j.kind == "render") or (run_id and worker_name.startswith(f"{run_id}-")):
                return j
    return None


@app.post("/api/vast/instances/{iid}/down")
def vast_instance_down(iid: int, force: bool = False) -> dict:
    """Free one card. A card a running render is using needs force=true (or cancel the render instead)."""
    from tracktake import vast

    state = next((st for st in vast.all_states() if st.instance_id == iid), None)
    job = _job_using(state.name) if state else None
    if job and not force:
        raise Conflict(f"card {iid} is used by the running render {job.id} ({job.project}); cancel the render "
                       "or send force=true")
    if state:
        usd = vast.destroy(state)
    else:  # not started from here (or its local state is gone): free it all the same
        vast.run_cli(["destroy", "instance", str(iid), "-y"])
        usd = 0.0
    return {"freed": iid, "usd": round(usd, 2)}


@app.post("/api/vast/down")
def vast_down() -> dict:
    from tracktake import vast

    states = vast.all_states()
    usd = sum(vast.destroy(st) for st in states)
    return {"freed": len(states), "usd": round(usd, 2)}


# ------------------------------------------------------------------------------------------------ jobs & files

@app.get("/api/jobs")
def list_jobs(project: str | None = None) -> list[dict]:
    return [jobs.view(j) for j in jobs.list(project)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return jobs.view(jobs.get(job_id))


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    return jobs.view(jobs.cancel(job_id))


@app.api_route("/files/{pid}/{path:path}", methods=["GET", "HEAD"])
def get_file(pid: str, path: str) -> FileResponse:
    p = project.get(pid)
    parts = Path(path).parts
    if not parts or any(x in ("..", "") or x.startswith("/") for x in parts):
        raise KeyError(path)
    f = p.root.joinpath(*parts)  # `full/` may be a symlink to earlier work; no ".." can leave the project
    if not f.is_file():
        raise KeyError(path)
    return FileResponse(f)


if WEB_DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str) -> FileResponse:
        if full_path.split("/", 1)[0] in ("api", "files"):  # unknown API/file paths stay 404, not the app shell
            raise KeyError(full_path)
        target = WEB_DIST / full_path
        if full_path and target.is_file() and WEB_DIST in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(WEB_DIST / "index.html")


def serve(host: str = "127.0.0.1", port: int = 8770) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="warning")
