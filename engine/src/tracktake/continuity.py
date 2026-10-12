"""Continuity supervisor: a second pass over the whole storyboard that catches contradictions between shots.

The director writes shot by shot; small drifts creep in (a bed that is single in one shot and holds two people's
imprint in the next, a coat back on its hook after she took it, two cups turning into one, day in a night run).
This pass reads every scene together with the world bible and the cut/continue structure, and rewrites only the
shots that contradict the bible or the shots around them. The issues found are kept in the storyboard
(`continuity`) so the UI can show what was changed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from tracktake.storyboard import ask, bible_text, is_cut

SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {"type": "array", "items": {
            "type": "object",
            "properties": {"shot": {"type": "string"}, "problem": {"type": "string"},
                           "scene": {"type": "string"}, "motion": {"type": "string"}},
            "required": ["shot", "problem", "scene", "motion"]}},
    },
    "required": ["issues"],
}
SHAPE = '{"issues": [{"shot", "problem", "scene", "motion"}]}'

RULES = """You are the continuity supervisor of a music video. Below are the world bible (fixed looks of places and
objects) and every shot in order: CUT starts a new scene, CONTINUES is the same camera take a few seconds later.
Find real continuity errors and fix them:
- an object or place that contradicts the bible: different kind, size, count or colour (a single bed described or
  implied as double - e.g. "the empty other side of the bed"; three cups instead of two; a window on the wrong wall);
- a contradiction with earlier shots in the same location, also across cuts (the coat she took is back on the hook
  without a reason; a broken window is whole again; furniture appears or vanishes);
- inside a CONTINUES run: changed time of day, weather, clothes, hair, what she holds, or where she is, without the
  previous shot's motion causing it;
- the character's look contradicting the main character description;
- screen directions: when a side matters (who drives, where the lamps or the window are) the scene must state it in
  frame terms that fit the camera angle and the world's fixed layout (seen from the front, the driver of a
  left-hand-drive car is on the RIGHT of the frame; from behind on the left). Fix scenes that leave it ambiguous after
  the camera turns around, or that put it on the wrong side.
Do NOT report style choices, intentional story changes that the scenes make explicit, or dream/memory scenes that
say so. For every real error return the shot id, the problem in one sentence, and the corrected `scene` and `motion`
(change as little as possible, keep the same shot idea). Return an empty list when everything is consistent."""


def prompt(sb: dict) -> str:
    lines = []
    for i, s in enumerate(sb["shots"]):
        tag = "CUT" if is_cut(sb["shots"], i) else "CONTINUES"
        where = f" @{s['location']}" if s.get("location") else ""
        props = f" props={','.join(s['props'])}" if s.get("props") else ""
        lines.append(f"{s['id']} {tag}{where}{props} [{s['section']}]\n  scene: {s.get('scene', '')}\n"
                     f"  motion: {s.get('motion', '')}")
    return (f"{RULES}\n\nMain character: {sb.get('heroine', '')}\n\nWorld bible:\n{bible_text(sb) or '(none)'}\n\n"
            "Shots:\n" + "\n".join(lines))


def check(sb: dict, timeout: float = 900, log=print, cover: Path | None = None) -> tuple[dict, list[dict]]:
    """Review the written storyboard, apply the fixes, record them; returns (storyboard, issues)."""
    written = [s for s in sb["shots"] if s.get("scene")]
    if len(written) < 2:
        return sb, []
    result = ask(prompt(sb), cover, timeout, log, SCHEMA, "issues", "continuity", SHAPE)
    by_id = {s["id"]: s for s in sb["shots"]}
    applied = []
    for issue in result.get("issues") or []:
        shot = by_id.get(issue.get("shot", ""))
        if not shot or not issue.get("scene", "").strip():
            continue
        before = shot["scene"]
        shot["scene"], shot["motion"] = issue["scene"].strip(), (issue.get("motion") or shot["motion"]).strip()
        applied.append({"shot": shot["id"], "problem": issue.get("problem", "").strip(), "before": before})
    sb["continuity"] = {"checked": datetime.now(UTC).isoformat(timespec="seconds"), "issues": applied}
    log(f"continuity: {len(applied)} fix(es)" + "".join(f"\n  {a['shot']}: {a['problem']}" for a in applied))
    return sb, applied
