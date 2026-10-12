"""Keyframes for a project: the Codex character sheet, Codex shot keyframes (whole scenes) and gallery thumbnails."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PIL import Image

from tracktake.codex_images import ImageJob, generate, generate_all
from tracktake.project import KEY_SETS, ORIENTATIONS, Project
from tracktake.storyboard import is_cut

FRAMING = {
    "landscape": "Cinematic horizontal composition; keep the main subject and action inside the central 16:9 area.",
    "portrait": "Vertical composition for a phone screen; the main subject is centered and fills the frame.",
}


def shot_prompt(sb: dict, shot: dict, orientation: str) -> str:
    who = f" The woman is {sb['heroine']}." if sb.get("heroine") and "woman" in shot["scene"] else ""
    return f"Scene: {shot['scene']}{who} {FRAMING[orientation]} Style: {sb['style']}."


def character_sheet(p: Project, force: bool = False) -> float:
    sb = p.storyboard() or {}
    if not sb.get("heroine"):
        raise ValueError("storyboard has no `heroine` description yet - write the storyboard first")
    if force:
        p.character_sheet.unlink(missing_ok=True)
    refs = [p.cover_ref] if p.cover_ref.exists() else []
    job = ImageJob(p.character_sheet,
                   "It is a character reference sheet for a music video: the SAME person shown three times side by "
                   "side on a plain dark paper background - full body front view, full body three-quarter view, and a "
                   f"head-and-shoulders close-up. The character: {sb['heroine']}. Style: {sb.get('style', '')}.",
                   "landscape", refs)
    return generate(job)


def codex_jobs(p: Project, shots: list[str] | None = None, orientations: list[str] | None = None,
               force: bool = False) -> list[ImageJob]:
    sb = p.storyboard()
    if not sb:
        raise ValueError("no storyboard")
    empty = [s["id"] for s in sb["shots"] if not s.get("scene") and (not shots or s["id"] in shots)]
    if empty:
        raise ValueError(f"shots without a scene: {', '.join(empty[:8])}")
    jobs = []
    for i, shot in enumerate(sb["shots"]):
        if shots and shot["id"] not in shots:
            continue
        has_woman = "woman" in shot["scene"]
        refs = [r for r in (p.cover_ref, p.character_sheet if has_woman else None) if r and r.exists()]
        for o in orientations or ORIENTATIONS:
            out = p.key_path("codex", shot["id"], o)
            if force:
                out.unlink(missing_ok=True)
                thumb(p, "codex", shot["id"], o, drop=True)
            if not out.exists():
                previous = None if is_cut(sb["shots"], i) else p.key_path("codex", sb["shots"][i - 1]["id"], o)
                jobs.append(ImageJob(out, shot_prompt(sb, shot, o), o, refs, previous))
    return jobs


def run_codex(p: Project, jobs: list[ImageJob], workers: int, on_done: Callable, should_stop: Callable) -> dict:
    return generate_all(jobs, workers=workers, on_done=on_done, should_stop=should_stop)


def thumb_path(p: Project, kind: str, shot: str, orientation: str) -> Path:
    return p.root / "thumbs" / f"{kind}_{shot}_{orientation}.jpg"


def thumb(p: Project, kind: str, shot: str, orientation: str, drop: bool = False) -> Path | None:
    """Small JPEG for grids, made on demand from the keyframe and refreshed when the keyframe is newer."""
    src, out = p.key_path(kind, shot, orientation), thumb_path(p, kind, shot, orientation)
    if drop:
        out.unlink(missing_ok=True)
        return None
    if not src.exists():
        return None
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        out.parent.mkdir(parents=True, exist_ok=True)
        im = Image.open(src).convert("RGB")
        im.thumbnail((480, 480))
        im.save(out, quality=80)
    return out


def listing(p: Project) -> dict:
    sb = p.storyboard() or {"shots": []}
    sets: dict = {}
    for kind in KEY_SETS:
        sets[kind] = {}
        for shot in sb["shots"]:
            entry = {}
            for o in ORIENTATIONS:
                full = p.key_path(kind, shot["id"], o)
                t = thumb(p, kind, shot["id"], o)
                entry[o] = p.url(full) if full.exists() else None
                entry[f"{o}_thumb"] = p.url(t) if t else None
            sets[kind][shot["id"]] = entry
    sheet = p.character_sheet
    return {"character_sheet": p.url(sheet) if sheet.exists() else None, "sets": sets}
