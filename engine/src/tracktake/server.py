"""Local web API for the UI (contract: apps/web/src/api/types.ts). Run with `uv run tracktake serve`."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import numpy as np
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from tracktake import keyframes, project, storyboard
from tracktake.config import REPO_ROOT
from tracktake.jobs import Conflict, Context, JobManager, clip_progress
from tracktake.models import Analysis
from tracktake.project import FORMATS, KEY_SETS, Project

ENGINE = REPO_ROOT / "engine"
WEB_DIST = REPO_ROOT / "apps" / "web" / "dist"
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
        "settings": {"workers": m.settings.workers, "gpu": m.settings.gpu, "max_dph": m.settings.max_dph},
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
    song = p.input_file("song")
    if not song:
        raise ValueError("upload a song first")
    lang = p.meta().language

    def run(ctx: Context) -> None:
        cmd = [sys.executable, "-m", "tracktake.cli", "analyze", song, "--out", p.root, "--language", lang]
        if p.lyrics().strip():
            cmd[5:5] = ["--lyrics", p.lyrics_path]
        ctx.run(cmd, cwd=ENGINE)
        (p.root / "peaks.json").unlink(missing_ok=True)

    return jobs.submit("analyze", pid, "Song analysis", run).to_dict()


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
    p = project.get(pid)
    sb = storyboard.replan(_analysis(p), p.storyboard(), p.meta().style)
    p.save_storyboard(sb)
    return sb


class WriteBody(BaseModel):
    shots: list[str] | None = None
    instructions: str = ""


@app.post("/api/projects/{pid}/storyboard/write")
def write_storyboard(pid: str, body: WriteBody) -> dict:
    p = project.get(pid)
    if not p.storyboard():
        p.save_storyboard(storyboard.replan(_analysis(p), None, p.meta().style))
    n = len(body.shots) if body.shots else len(p.storyboard()["shots"])

    def run(ctx: Context) -> None:
        sb = storyboard.write(p.storyboard(), body.shots, p.meta().style,
                              p.cover_ref if p.cover_ref.exists() else None, p.lyrics(), body.instructions, log=ctx.log)
        p.save_storyboard(sb)
        ctx.log(f"storyboard saved ({sum(1 for s in sb['shots'] if s.get('scene'))}/{len(sb['shots'])} shots written)")

    return jobs.submit("storyboard", pid, f"Director writes the storyboard ({n} shots)", run, {"shots": n}).to_dict()


# ------------------------------------------------------------------------------------------------ keyframes

@app.get("/api/projects/{pid}/keys")
def get_keys(pid: str) -> dict:
    return keyframes.listing(project.get(pid))


class CharacterBody(BaseModel):
    force: bool = False


@app.post("/api/projects/{pid}/character")
def make_character(pid: str, body: CharacterBody) -> dict:
    p = project.get(pid)

    def run(ctx: Context) -> None:
        ctx.log("Codex is drawing the character sheet")
        sec = keyframes.character_sheet(p, force=body.force)
        ctx.log(f"character sheet ready ({sec:.0f}s)" if sec else "character sheet already exists")

    return jobs.submit("character", pid, "Character sheet (Codex)", run).to_dict()


class CodexKeysBody(BaseModel):
    shots: list[str] | None = None
    force: bool = False
    workers: int = 4


@app.post("/api/projects/{pid}/keys/codex")
def make_codex_keys(pid: str, body: CodexKeysBody) -> dict:
    p = project.get(pid)
    orients = [p.meta().orientation]
    planned = keyframes.codex_jobs(p, body.shots, orients, force=False)  # validates the storyboard early

    def run(ctx: Context) -> None:
        if not p.character_sheet.exists() and any("woman" in s["scene"] for s in p.storyboard()["shots"]):
            ctx.log("no character sheet yet - drawing it first")
            keyframes.character_sheet(p)
        todo = keyframes.codex_jobs(p, body.shots, orients, force=body.force)
        ctx.progress(0, len(todo))
        done = 0

        def on_done(job, result) -> None:
            nonlocal done
            done += 1
            ctx.progress(done, len(todo))
            ctx.log(f"{job.out.name}: {result}")

        keyframes.run_codex(p, todo, max(1, min(body.workers, 8)), on_done, ctx.cancelled)
        failed = [j.out.name for j in todo if not j.out.exists()]
        if failed and not ctx.cancelled():
            raise RuntimeError(f"{len(failed)} keyframes failed: {', '.join(failed[:6])}")

    params = {"shots": len(body.shots)} if body.shots else {"missing": len(planned)}
    label = f"{len(body.shots)} shots" if body.shots else f"{len(planned)} missing"
    return jobs.submit("keys_codex", pid, f"Codex keyframes ({label})", run, params).to_dict()


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


def _settings_ns(gpu: str | None, max_dph: float | None) -> argparse.Namespace:
    return argparse.Namespace(gpu=gpu, max_dph=max_dph)


@app.get("/api/projects/{pid}/estimate")
def estimate(pid: str, set: str = "codex", workers: int = 4) -> dict:
    from tracktake import cli, vast

    p = project.get(pid)
    m = p.meta().settings
    sb = p.storyboard()
    if not sb:
        raise ValueError("no storyboard")
    orientation = p.meta().orientation
    clips = len(sb["shots"])
    models = ["wan22_i2v", "zimage"] if set == "comfy" else ["wan22_i2v"]
    s = cli._remote_settings(_settings_ns(m.gpu, m.max_dph), models)
    hours, usd = cli._estimate(s, workers, clips, formats=1)
    alternatives = []
    for n in sorted({1, 2, 4, workers}):
        h, u = (hours, usd) if n == workers else cli._estimate(s, n, clips, formats=1)
        alternatives.append({"workers": n, "minutes": round(h * 60), "usd": round(u, 2)})
    offers = vast.search_offers(s, limit=5)
    missing = 0 if set == "comfy" else sum(1 for sh in sb["shots"]
                                           if not p.key_path("codex", sh["id"], orientation).exists())
    return {"set": set, "workers": workers, "clips": clips, "minutes": round(hours * 60), "usd": round(usd, 2),
            "models_gb": round(s.download_gb), "missing_keys": missing, "alternatives": alternatives,
            "offers": [{"id": o.id, "gpu": o.gpu, "dph": round(o.dph, 3), "download_usd": round(o.setup_cost(s.download_gb), 2),
                        "inet_down": round(o.inet_down), "location": o.location} for o in offers]}


class RenderBody(BaseModel):
    set: str
    workers: int = 4
    gpu: str | None = None
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
    song = p.input_file("song")
    if not (song and p.analysis_path.exists() and p.storyboard()):
        raise ValueError("song, analysis and storyboard are required")
    m = p.meta().settings
    cmd = [sys.executable, "-m", "tracktake.cli", "remote", "run", "--full", p.full, "--set", body.set, "--song", song,
           "--analysis", p.analysis_path, "--workers", str(max(1, min(body.workers, 8))), "--gpu", body.gpu or m.gpu,
           "--max-dph", str(body.max_dph or m.max_dph), "--orient", p.meta().orientation, "--yes"]
    if not body.masters:
        cmd.append("--no-masters")

    def run(ctx: Context) -> None:
        ctx.run(cmd, cwd=ENGINE, parse=clip_progress(ctx))

    name = "Codex" if body.set == "codex" else "ComfyUI"
    return jobs.submit("render", pid, f"Vast render ({name}, {body.workers} cards)", run,
                       {"set": body.set, "workers": body.workers}).to_dict()


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
            out["instances"].append({"id": i["id"], "name": names.get(i["id"], i.get("label") or ""),
                                     "gpu": i.get("gpu_name", ""), "status": i.get("actual_status") or "",
                                     "dph": round(float(i.get("dph_total") or 0), 3)})
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
    return vast_status()


@app.post("/api/vast/down")
def vast_down() -> dict:
    from tracktake import vast

    states = vast.all_states()
    usd = sum(vast.destroy(st) for st in states)
    return {"freed": len(states), "usd": round(usd, 2)}


# ------------------------------------------------------------------------------------------------ jobs & files

@app.get("/api/jobs")
def list_jobs(project: str | None = None) -> list[dict]:
    return [j.to_dict() for j in jobs.list(project)]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    return jobs.jobs[job_id].to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    return jobs.cancel(job_id).to_dict()


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
