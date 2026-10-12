"""The pipeline steps as job bodies, shared by the single-step API endpoints and the autopilot.

Each `run_*` function takes the job Context and does one stage; long ones stream their log and progress.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

from tracktake import continuity, keyframes, storyboard
from tracktake.jobs import Context, clip_progress
from tracktake.models import Analysis
from tracktake.project import Project

ENGINE = Path(__file__).resolve().parents[2]


def analysis(p: Project) -> Analysis:
    if not p.analysis_path.exists():
        raise ValueError("analyse the song first")
    return Analysis.model_validate_json(p.analysis_path.read_text())


def run_analyze(ctx: Context, p: Project) -> None:
    song = p.input_file("song")
    if not song:
        raise ValueError("upload a song first")
    cmd = [sys.executable, "-m", "tracktake.cli", "analyze", song, "--out", p.root, "--language", p.meta().language]
    if p.lyrics().strip():
        cmd[5:5] = ["--lyrics", p.lyrics_path]
    ctx.run(cmd, cwd=ENGINE)
    (p.root / "peaks.json").unlink(missing_ok=True)


def plan(p: Project) -> dict:
    sb = storyboard.replan(analysis(p), p.storyboard(), p.meta().style)
    p.save_storyboard(sb)
    p.update(storyboard_approved=False)
    return sb


def run_write(ctx: Context, p: Project, shots: list[str] | None = None, instructions: str = "") -> None:
    if not p.storyboard():
        plan(p)
    sb = storyboard.write(p.storyboard(), shots, p.meta().style, p.cover_ref if p.cover_ref.exists() else None,
                          p.lyrics(), instructions, log=ctx.log)
    p.save_storyboard(sb)
    p.update(storyboard_approved=False)
    ctx.log(f"storyboard saved ({sum(1 for s in sb['shots'] if s.get('scene'))}/{len(sb['shots'])} shots written)")
    run_continuity(ctx, p)


def run_continuity(ctx: Context, p: Project) -> None:
    """Second pass over the whole storyboard: fix contradictions between shots (also its own job)."""
    ctx.check()
    sb, issues = continuity.check(p.storyboard(), log=ctx.log, cover=p.cover_ref if p.cover_ref.exists() else None)
    p.save_storyboard(sb)
    if issues:
        p.update(storyboard_approved=False)


def needs_character(p: Project) -> bool:
    sb = p.storyboard() or {"shots": []}
    return bool(sb.get("heroine")) and any("woman" in s.get("scene", "") for s in sb["shots"])


def run_character(ctx: Context, p: Project, force: bool = False) -> None:
    ctx.log("Codex is drawing the character sheet")
    sec = keyframes.character_sheet(p, force=force)
    ctx.log(f"character sheet ready ({sec:.0f}s)" if sec else "character sheet already exists")


def missing_keys(p: Project) -> int:
    sb = p.storyboard() or {"shots": []}
    o = p.meta().orientation
    return sum(1 for s in sb["shots"] if not p.key_path("codex", s["id"], o).exists())


def run_codex_keys(ctx: Context, p: Project, shots: list[str] | None = None, force: bool = False,
                   workers: int = 4) -> None:
    orients = [p.meta().orientation]
    if not p.character_sheet.exists() and needs_character(p):
        ctx.log("no character sheet yet - drawing it first")
        keyframes.character_sheet(p)
    todo = keyframes.codex_jobs(p, shots, orients, force=force)
    ctx.progress(0, len(todo))
    done = 0

    def on_done(job, result) -> None:
        nonlocal done
        done += 1
        ctx.progress(done, len(todo))
        ctx.log(f"{job.out.name}: {result}")

    keyframes.run_codex(p, todo, max(1, min(workers, 8)), on_done, ctx.cancelled)
    failed = [j.out.name for j in todo if not j.out.exists()]
    if failed and not ctx.cancelled():
        raise RuntimeError(f"{len(failed)} keyframes failed: {', '.join(failed[:6])}")


def new_run_id() -> str:
    """Prefix of a render's Vast worker names, so the UI can tell which cards a running job uses."""
    return f"j{uuid.uuid4().hex[:6]}"


def render_command(p: Project, kind: str, workers: int, gpu: str, gpus: int, max_dph: float,
                   masters: bool = True, run_id: str | None = None) -> tuple[list, str]:
    """The `tracktake remote run` command for this project and its run id (prefix of the workers' names)."""
    song = p.input_file("song")
    if not (song and p.analysis_path.exists() and p.storyboard()):
        raise ValueError("song, analysis and storyboard are required")
    m = p.meta().settings
    run_id = run_id or new_run_id()
    cmd = [sys.executable, "-m", "tracktake.cli", "remote", "run", "--full", p.full, "--set", kind, "--song", song,
           "--analysis", p.analysis_path, "--workers", str(max(1, min(workers, 8))), "--gpu", gpu,
           "--max-dph", str(max_dph), "--gpus", str(max(1, gpus)), "--orient", p.meta().orientation, "--yes",
           "--run-id", run_id]
    if not masters:
        cmd.append("--no-masters")
    if not m.captions:
        cmd.append("--no-captions")
    if not m.beat_motion:
        cmd.append("--no-beat-motion")
    return cmd, run_id


def run_render(ctx: Context, cmd: list) -> None:
    ctx.run(cmd, cwd=ENGINE, parse=clip_progress(ctx))


def job_render(ctx: Context, p: Project, kind: str, workers: int, gpu: str, gpus: int, max_dph: float,
               masters: bool, run_id: str) -> None:
    """The render job (runs in its own process: built from plain arguments, not a prepared command)."""
    cmd, _ = render_command(p, kind, workers, gpu, gpus, max_dph, masters, run_id)
    run_render(ctx, cmd)
