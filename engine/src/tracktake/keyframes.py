"""Keyframes for a project: the Codex character sheet, Codex shot keyframes (whole scenes) and gallery thumbnails."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from PIL import Image

from tracktake import keycheck
from tracktake.codex_images import ImageJob, fingerprint_path, generate, generate_all
from tracktake.keycheck import note_path
from tracktake.project import KEY_SETS, ORIENTATIONS, Project
from tracktake.storyboard import is_cut

FRAMING = {
    "landscape": "Cinematic horizontal composition; keep the main subject and action inside the central 16:9 area.",
    "portrait": "Vertical composition for a phone screen; the main subject is centered and fills the frame.",
}


def shot_prompt(sb: dict, shot: dict, orientation: str) -> str:
    who = f" The woman is {sb['heroine']}." if sb.get("heroine") and "woman" in shot["scene"] else ""
    places = {e["id"]: e["look"] for e in sb.get("locations", [])}
    things = {e["id"]: e["look"] for e in sb.get("props", [])}
    where = f" Setting (keep exactly as described): {places[shot['location']]}." if shot.get("location") in places else ""
    props = [things[x] for x in shot.get("props", []) if x in things]
    objects = f" Objects (keep exactly as described): {'; '.join(props)}." if props else ""
    return f"Scene: {shot['scene']}{who}{where}{objects} {FRAMING[orientation]} Style: {sb['style']}."


def _sources(shots: list[dict]) -> dict[str, tuple[str | None, str | None]]:
    """shot id -> (the shot it continues, the first shot of its location): the keyframes it is drawn after."""
    first_at: dict[str, str] = {}
    for shot in shots:
        if shot.get("location"):
            first_at.setdefault(shot["location"], shot["id"])
    out = {}
    for i, shot in enumerate(shots):
        prev = None if is_cut(shots, i) else shots[i - 1]["id"]
        first = first_at.get(shot.get("location", ""))
        out[shot["id"]] = (prev, first if first and first != shot["id"] else None)
    return out


def fingerprints(sb: dict, orientation: str) -> dict[str, str]:
    """shot id -> what its keyframe is drawn from: its prompt (scene, the world bible's looks, the character, style)
    and the fingerprints of the keyframes it is drawn after (the previous moment of its take, the first frame of its
    location). An edit upstream therefore marks every keyframe drawn from it stale, down the whole take."""
    out: dict[str, str] = {}
    for shot_id, (prev, anchor) in _sources(sb.get("shots", [])).items():
        shot = next(s for s in sb["shots"] if s["id"] == shot_id)
        text = shot_prompt(sb, shot, orientation) if shot.get("scene") else ""
        up = f"{out.get(prev, '') if prev else ''}|{out.get(anchor, '') if anchor else ''}"
        out[shot_id] = hashlib.sha1(f"{text}|{up}".encode()).hexdigest()[:16]
    return out


def key_statuses(p: Project, sb: dict, orientation: str) -> dict[str, str]:
    """shot id -> missing | stale | ok for the Codex keyframes. Stale: drawn before its scene, the world bible or a
    keyframe it is drawn after changed. A keyframe made before fingerprints existed is stale only if the continuity
    check rewrote its scene after it was drawn (or a keyframe it follows is stale); otherwise it is taken as current
    and gets its fingerprint now, so later edits are caught. Staleness flows down a take and to a location's later
    shots, except for a keyframe the keyframe check flagged: its redraw is a local correction (redrawing every frame
    after it would replace good pictures and bring new errors)."""
    prints = fingerprints(sb, orientation)
    cont = sb.get("continuity") or {}
    fixed = {i["shot"] for i in cont.get("issues", [])}
    checked = datetime.fromisoformat(cont["checked"]).timestamp() if cont.get("checked") else 0.0
    out: dict[str, str] = {}
    local: set[str] = set()  # flagged by the keyframe check only
    for shot_id, sources in _sources(sb.get("shots", [])).items():
        path = p.key_path("codex", shot_id, orientation)
        saved = fingerprint_path(path)
        if not path.exists():
            out[shot_id] = "missing"
        elif any(out.get(x) == "stale" and x not in local for x in sources if x):
            out[shot_id] = "stale"
        elif note_path(path).exists() and (not saved.exists() or saved.read_text().strip() in (prints[shot_id],
                                                                                              "flagged")):
            out[shot_id] = "stale"  # the keyframe check found an error in the picture
            local.add(shot_id)
        elif saved.exists():
            out[shot_id] = "ok" if saved.read_text().strip() == prints[shot_id] else "stale"
        elif shot_id in fixed and path.stat().st_mtime < checked:
            saved.write_text("stale")  # remembered: the next continuity check replaces the list of fixes
            out[shot_id] = "stale"
        else:
            saved.write_text(prints[shot_id])
            out[shot_id] = "ok"
    return out


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
    sources = _sources(sb["shots"])
    prints = {o: fingerprints(sb, o) for o in orientations or ORIENTATIONS}
    statuses = {o: key_statuses(p, sb, o) for o in orientations or ORIENTATIONS}
    for shot in sb["shots"]:
        if shots and shot["id"] not in shots:
            continue
        has_woman = "woman" in shot["scene"]
        refs = [r for r in (p.cover_ref, p.character_sheet if has_woman else None) if r and r.exists()]
        for o in orientations or ORIENTATIONS:
            out = p.key_path("codex", shot["id"], o)
            if force:
                out.unlink(missing_ok=True)
                thumb(p, "codex", shot["id"], o, drop=True)
            status = "missing" if force else statuses[o][shot["id"]]  # forced: just deleted above
            if status != "ok":
                prev, first = sources[shot["id"]]
                previous = p.key_path("codex", prev, o) if prev else None
                anchor = p.key_path("codex", first, o) if first else None
                # the previous frame / the location's first frame already carry the palette: the cover is one image
                # less to read (each attachment makes Codex slower)
                own = [r for r in refs if r != p.cover_ref] if (previous or anchor) else refs
                note = note_path(out)
                fix = f" Correct this error of the earlier version: {note.read_text().strip()}" if note.exists() else ""
                jobs.append(ImageJob(out, shot_prompt(sb, shot, o) + fix, o, own, previous, anchor,
                                     fingerprint=prints[o][shot["id"]], replace=status == "stale",
                                     fix_note=note if fix else None))
                if status == "stale":
                    thumb(p, "codex", shot["id"], o, drop=True)
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
    statuses = {o: key_statuses(p, sb, o) for o in ORIENTATIONS}
    for kind in KEY_SETS:
        sets[kind] = {}
        for shot in sb["shots"]:
            entry = {}
            for o in ORIENTATIONS:
                full = p.key_path(kind, shot["id"], o)
                t = thumb(p, kind, shot["id"], o)
                entry[o] = p.url(full) if full.exists() else None
                entry[f"{o}_thumb"] = p.url(t) if t else None
                if kind == "codex":
                    entry[f"{o}_stale"] = statuses[o][shot["id"]] == "stale"
                    note = note_path(full)
                    entry[f"{o}_issue"] = note.read_text().strip() if note.exists() else None
                    entry[f"{o}_flipped"] = full.with_suffix(".orig.png").exists()
            sets[kind][shot["id"]] = entry
    sheet = p.character_sheet
    return {"character_sheet": p.url(sheet) if sheet.exists() else None, "sets": sets, "check": keycheck.report(p)}
