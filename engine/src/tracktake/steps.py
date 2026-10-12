"""The pipeline steps as job bodies, shared by the single-step API endpoints and the autopilot.

Each `run_*` function takes the job Context and does one stage; long ones stream their log and progress.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

from tracktake import continuity, keycheck, keyframes, storyboard
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


def key_counts(p: Project) -> dict[str, int]:
    """Codex keyframes of the project's orientation: missing ones, and stale ones (drawn before their scene, the
    world bible or a keyframe they follow changed)."""
    sb = p.storyboard() or {"shots": []}
    o = p.meta().orientation
    counts = {"missing": 0, "stale": 0, "ok": 0}
    for status in keyframes.key_statuses(p, sb, o).values():
        counts[status] += 1
    return counts


def missing_keys(p: Project) -> int:
    """Keyframes to (re)draw before a render: missing + stale."""
    c = key_counts(p)
    return c["missing"] + c["stale"]


def run_codex_keys(ctx: Context, p: Project, shots: list[str] | None = None, force: bool = False,
                   workers: int = 8) -> None:
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

    # 8 parallel Codex runs: with 4, 63 keyframes took 32 min (each image ~92 s; the chains of continuous shots
    # alone would allow ~15 min)
    keyframes.run_codex(p, todo, max(1, min(workers, 12)), on_done, ctx.cancelled)
    failed = [j.out.name for j in todo if not j.out.exists()]
    if failed and not ctx.cancelled():
        raise RuntimeError(f"{len(failed)} keyframes failed: {', '.join(failed[:6])}")


def keys_need_check(p: Project) -> bool:
    """No keyframe check yet, or a keyframe drawn after the last one."""
    o = p.meta().orientation
    report = keycheck.report(p)
    sb = p.storyboard() or {"shots": []}
    keys = [p.key_path("codex", s["id"], o) for s in sb["shots"]]
    newest = max((k.stat().st_mtime for k in keys if k.exists()), default=0.0)
    if not newest:
        return False
    return not report or report.get("orientation") != o or datetime.fromisoformat(report["checked"]).timestamp() < newest


def run_keys_check(ctx: Context, p: Project, redraw: bool = True, rounds: int = 3) -> None:
    """Look at the drawn keyframes for visual continuity errors; flip mirrored ones and (with `redraw`) redraw the
    others with the correction, then look at the flipped and redrawn ones again. Errors found in the last round stay
    marked (stale, with the correction) for the next "generate missing and stale"."""
    o = p.meta().orientation
    shots: list[str] | None = None
    for round_no in range(max(1, rounds)):
        ctx.check()
        issues = keycheck.check(p, o, shots, log=ctx.log)
        done = keycheck.apply(p, issues, o, log=ctx.log, confirm_flip=keycheck.flip_checker(p, o, log=ctx.log))
        again = done["redraw"] + done["flipped"] if redraw else done["flipped"]
        if not again or round_no == rounds - 1:
            return
        if redraw and done["redraw"]:
            ctx.log(f"redrawing {len(done['redraw'])} keyframe(s) with the corrections")
            run_codex_keys(ctx, p)
        shots = again


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
           "--max-dph", str(max_dph), "--gpus", str(max(1, gpus)), "--region", m.region or "any",
           "--orient", p.meta().orientation, "--yes",
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
