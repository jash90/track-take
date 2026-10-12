""""Make the video": one job that walks every step still missing, so a project needs only the song and one click.

Stops on its own in two places, both by the user's choice when starting:
- `awaiting_storyboard`: the director's scenes are ready to review (when `review` is on) - resumed by approving;
- `awaiting_budget`: the render would cost more than the budget - resumed with a higher budget.
State lives in project.json (`autopilot`), so the UI can show it after a restart.
"""

from __future__ import annotations

import math
import subprocess
from datetime import UTC, datetime

from tracktake import cli, nethistory, presets, steps
from tracktake.jobs import Context
from tracktake.project import Project

STAGES = ("analyze", "plan", "write", "review", "character", "keys", "check", "render")


def clip_count(p: Project) -> int:
    """Clips of the project's video; before the storyboard exists, guessed from the song (~6 s per shot)."""
    sb = p.storyboard()
    if sb:
        return len(sb["shots"])
    song = p.input_file("song")
    if not song:
        return 0
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(song)],
                       capture_output=True, text=True, check=False)
    try:
        return max(1, round(float(r.stdout.strip()) / 6.0))
    except ValueError:
        return 0


def clip_frames(p: Project) -> int:
    """Frames the clips of this video will have in total (each shot: 16 fps, 33..81 frames, as scripts/full_clips.py);
    the clip time follows it. Before the storyboard exists: ~72 frames per guessed shot."""
    sb = p.storyboard()
    if not sb:
        return clip_count(p) * 72
    return sum(max(33, min(81, 4 * math.ceil((s["end"] - s["start"]) * 16 / 4) + 1)) for s in sb["shots"])


def render_presets(p: Project) -> list[dict]:
    import argparse

    region = p.meta().settings.region
    s = cli._vast_settings(argparse.Namespace(region=region))
    s.models = ["wan22_i2v"]
    s.download_gb = sum(cli.MODEL_GB[m] for m in s.models) + 3.0
    setup_h = nethistory.history().typical_setup_minutes(s.regions, s.download_gb) / 60
    out = presets.presets(cli.gpu_catalog(s), clip_frames(p), cli.FRAME_S, setup_h, cli.RENDER_H + cli.FIXED_H)
    return [o | {"minutes_max": o["minutes"] + cli.FAILED_HOST_MIN} for o in out]


def custom_choice(p: Project) -> dict | None:
    """The project's own card settings (the UI's "Custom" option), priced like the estimate endpoint."""
    import argparse

    from tracktake import vast

    m = p.meta().settings
    s = cli._remote_settings(argparse.Namespace(gpu=m.gpu, max_dph=m.max_dph, gpus=m.gpus, region=m.region),
                             ["wan22_i2v"])
    available = len(vast.search_offers(s, limit=100))
    if not available:
        return None
    workers = min(max(1, m.workers), available)
    hours, usd = cli._estimate(s, workers, clip_count(p), formats=1, frames=clip_frames(p))
    return {"id": "custom", "gpu": m.gpu, "label": m.gpu.replace("_", " "), "gpus": m.gpus, "workers": workers,
            "max_dph": m.max_dph, "minutes": round(hours * 60), "minutes_max": round(hours * 60) + cli.FAILED_HOST_MIN,
            "usd": round(usd, 2)}


def _state(p: Project, **changes) -> None:
    p.update(autopilot=changes | {"updated": datetime.now(UTC).isoformat(timespec="seconds")})


def run(ctx: Context, p: Project, budget_usd: float, preset: str, review: bool) -> None:
    def stage(name: str) -> None:
        ctx.check()
        ctx.job.params["stage"] = name
        ctx.job.progress = None
        _state(p, state="running", stage=name, job=ctx.job.id, budget_usd=budget_usd, preset=preset, review=review)
        ctx.log(f"== {name}")

    try:
        if not p.analysis_path.exists():
            stage("analyze")
            steps.run_analyze(ctx, p)
        if not p.storyboard():
            stage("plan")
            steps.plan(p)
        if any(not s.get("scene") for s in p.storyboard()["shots"]):
            stage("write")
            steps.run_write(ctx, p)
        if review and not p.meta().storyboard_approved:
            _state(p, state="awaiting_storyboard", stage="review", job=ctx.job.id, budget_usd=budget_usd,
                   preset=preset, review=review)
            ctx.log("storyboard ready - waiting for approval")
            return
        if steps.needs_character(p) and not p.character_sheet.exists():
            stage("character")
            steps.run_character(ctx, p)
        if steps.missing_keys(p):
            stage("keys")
            steps.run_codex_keys(ctx, p)
        if steps.keys_need_check(p):
            stage("check")
            steps.run_keys_check(ctx, p)
            if steps.key_counts(p)["missing"]:  # a redraw failed and lost its keyframe: the render needs one
                steps.run_codex_keys(ctx, p)
        stage("render")
        if preset == "custom":
            choice = custom_choice(p)
        else:
            choice = next((o for o in render_presets(p) if o["id"] == preset), None)
        if choice is None:
            raise RuntimeError("no GPU offers match the chosen card right now - pick another or try again later")
        if choice["usd"] > budget_usd:
            _state(p, state="awaiting_budget", stage="render", job=ctx.job.id, budget_usd=budget_usd, preset=preset,
                   review=review, estimate_usd=choice["usd"], estimate_minutes=choice["minutes"],
                   estimate_minutes_max=choice.get("minutes_max"))
            ctx.log(f"render would cost ~${choice['usd']:.2f}, over the ${budget_usd:.2f} budget - waiting")
            return
        if preset != "custom":
            p.update(settings={k: choice[k] for k in ("gpu", "gpus", "workers", "max_dph")})
        cmd, run_id = steps.render_command(p, "codex", choice["workers"], choice["gpu"], choice["gpus"],
                                           choice["max_dph"])
        ctx.job.params["run_id"] = run_id
        ctx.log(f"render: {choice['workers']}x {choice['gpus']}x {choice['label']}, ~{choice['minutes']} min, "
                f"~${choice['usd']:.2f}")
        steps.run_render(ctx, cmd)
        _state(p, state="done", stage="done", job=ctx.job.id)
    except Exception as e:
        _state(p, state="cancelled" if ctx.cancelled() else "failed", stage=ctx.job.params.get("stage"),
               job=ctx.job.id, error=str(e)[:300])
        raise
