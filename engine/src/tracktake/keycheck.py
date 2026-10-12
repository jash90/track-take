"""Visual continuity check of the drawn keyframes: a vision model looks at the pictures, not the texts.

The storyboard can be consistent while the images are not: the image model mirrors a picture (the car driven from
the passenger seat when seen from the front, the roadside lamps jumping to the other side of the road), swaps a
single bed for a double, changes his jacket, draws three cups. The keyframes of every location (and of every
continuous take without one) are shown in film order with their scene texts and the world bible; each error comes
back with a kind and a correction. A `mirrored` frame is flipped left-right on the spot (free and instant; keyframes
carry no text); any other error leaves a correction note next to the keyframe, which marks it stale - the next
"generate missing and stale" redraws it with the note added to its prompt.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps

from tracktake.project import Project
from tracktake.storyboard import ask, bible_text, is_cut

KINDS = ("mirrored", "object", "count", "character", "place", "other")
CHUNK = 8  # images per question; a long location is split with one image of overlap
SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {"type": "array", "items": {
            "type": "object",
            "properties": {"shot": {"type": "string"}, "kind": {"type": "string", "enum": list(KINDS)},
                           "problem": {"type": "string"}, "fix": {"type": "string"}},
            "required": ["shot", "kind", "problem", "fix"]}},
    },
    "required": ["issues"],
}
SHAPE = '{"issues": [{"shot", "kind": "mirrored|object|count|character|place|other", "problem", "fix"}]}'

RULES = """You are the continuity supervisor of a music video, checking the drawn keyframes (the start picture of each
shot) for visual continuity errors. Below are the world bible (fixed looks of places, objects and other people), the
main character, and the shots in film order: CUT starts a new scene, CONTINUES is the same camera take a few seconds
later. Open EVERY image file listed (use the Read tool) and compare the pictures with the texts and with each other.
Report only real errors, with a kind:
- mirrored: the whole picture is the left-right mirror image of what it should be. Typical: a car seen from the FRONT
  with the driver on the left of the image although the bible says he drives on the left (seen from the front the
  driver's own left is on the RIGHT of the image; seen from behind it is on the left); roadside lamps, a guardrail, a
  window or a door on the opposite side compared with the other pictures of the same place seen from the same
  direction. Use it only when flipping the WHOLE image left-right would make it correct.
- object: a place or object looks different from the bible or from the other pictures (another kind, size, colour or
  shape; missing, or appearing from nowhere inside a continuous take).
- count: a wrong number of people or things (two beds, three cups, an extra person).
- character: a person's face, hair, build or clothes differ from the description or from the other pictures.
- place: the wrong location, time of day or weather inside a continuous take.
- other: any other clear contradiction.
Do NOT report style, small drawing differences, different camera angles or framing, or changes the scene text asks
for. Do not invent problems: return an empty list when the pictures are consistent. For every error give the shot id,
the kind, the problem in one sentence, and `fix`: one concrete instruction for the image model that redraws the
picture, in screen terms (e.g. "Seen from the front: the man sits on the RIGHT of the image holding the steering
wheel, the woman on the LEFT; the street lamps line the LEFT edge of the road")."""


def report_path(p: Project) -> Path:
    return p.full / "codex" / "keycheck.json"


def note_path(image: Path) -> Path:
    """Correction for the next redraw of a keyframe; its presence marks the keyframe stale."""
    return image.with_suffix(".fix.txt")


def groups(sb: dict) -> list[list[str]]:
    """Shot ids to look at together: every location in film order (its takes and its returns after cuts), and every
    continuous take of shots without a location."""
    shots = sb.get("shots", [])
    by_place: dict[str, list[str]] = {}
    out: list[list[str]] = []
    take: list[str] = []
    for i, shot in enumerate(shots):
        if shot.get("location"):
            by_place.setdefault(shot["location"], []).append(shot["id"])
            continue
        if is_cut(shots, i) and take:
            out.append(take)
            take = []
        take.append(shot["id"])
    if take:
        out.append(take)
    out = list(by_place.values()) + out
    chunks: list[list[str]] = []
    for g in out:
        start = 0
        while True:
            chunks.append(g[start:start + CHUNK])
            if start + CHUNK >= len(g):
                break
            start += CHUNK - 1
    return [c for c in chunks if c]


def prompt(sb: dict, ids: list[str], paths: dict[str, Path]) -> str:
    index = {s["id"]: i for i, s in enumerate(sb["shots"])}
    lines = []
    for sid in ids:
        i = index[sid]
        s = sb["shots"][i]
        tag = "CUT" if is_cut(sb["shots"], i) else "CONTINUES"
        where = f" @{s['location']}" if s.get("location") else ""
        props = f" props={','.join(s['props'])}" if s.get("props") else ""
        lines.append(f"{sid} {tag}{where}{props}\n  image: {paths[sid].resolve()}\n  scene: {s.get('scene', '')}")
    return (f"{RULES}\n\nMain character (\"the woman\"): {sb.get('heroine', '')}\n\nWorld bible:\n"
            f"{bible_text(sb) or '(none)'}\n\nShots:\n" + "\n".join(lines))


def check(p: Project, orientation: str, shots: list[str] | None = None, log=print, workers: int = 4,
          timeout: float = 900) -> list[dict]:
    """Ask about every group (only groups holding `shots` when given); returns the issues and saves the report."""
    sb = p.storyboard() or {"shots": []}
    paths = {s["id"]: p.key_path("codex", s["id"], orientation) for s in sb["shots"]}
    todo = [[x for x in g if paths[x].exists()] for g in groups(sb)]
    todo = [g for g in todo if g and (not shots or set(g) & set(shots))]
    log(f"keyframe check: {len(todo)} group(s) of pictures")

    def one(g: list[str]) -> list[dict]:
        try:
            answer = ask(prompt(sb, g, paths), paths[g[0]], timeout, log, SCHEMA, "issues", "keyframe check", SHAPE,
                         images=[paths[x] for x in g])
        except Exception as e:  # noqa: BLE001 - one failed group must not lose the others
            log(f"keyframe check of {g[0]}..{g[-1]} failed: {e}")
            return []
        return [i for i in answer.get("issues") or [] if i.get("shot") in g and i.get("kind") in KINDS]

    with ThreadPoolExecutor(max(1, workers)) as pool:
        found = [i for part in pool.map(one, todo) for i in part]
    issues: dict[str, dict] = {}
    for i in found:  # a shot seen in two overlapping chunks: keep the first report
        if not shots or i["shot"] in shots:
            issues.setdefault(i["shot"], {k: str(i.get(k, "")).strip() for k in ("shot", "kind", "problem", "fix")})
    result = sorted(issues.values(), key=lambda i: [s["id"] for s in sb["shots"]].index(i["shot"]))
    report_path(p).parent.mkdir(parents=True, exist_ok=True)
    report_path(p).write_text(json.dumps({"checked": datetime.now(UTC).isoformat(timespec="seconds"),
                                          "orientation": orientation, "issues": result}, indent=1))
    log(f"keyframe check: {len(result)} issue(s)" + "".join(f"\n  {i['shot']} [{i['kind']}]: {i['problem']}"
                                                            for i in result))
    return result


def apply(p: Project, issues: list[dict], orientation: str, log=print, confirm_flip=None) -> dict[str, list[str]]:
    """Flip mirrored keyframes (the original is kept as *.orig.png the first time) and leave correction notes for the
    others, which marks them stale. `confirm_flip(issue, image)` may veto a flip. Returns {"flipped", "redraw"}."""
    done: dict[str, list[str]] = {"flipped": [], "redraw": []}
    for i in issues:
        image = p.key_path("codex", i["shot"], orientation)
        if not image.exists():
            continue
        if i["kind"] == "mirrored":
            if confirm_flip and not confirm_flip(i, image):
                log(f"{i['shot']}: the flipped picture is not better - left as it is")
                continue
            backup = image.with_suffix(".orig.png")
            if not backup.exists():
                backup.write_bytes(image.read_bytes())
            with Image.open(image) as im:
                flipped = ImageOps.mirror(im.convert("RGB"))
            flipped.save(image)
            done["flipped"].append(i["shot"])
        else:
            note_path(image).write_text(f"{i['problem']} {i['fix']}".strip())
            done["redraw"].append(i["shot"])
    log(f"flipped: {', '.join(done['flipped']) or '-'}; to redraw: {', '.join(done['redraw']) or '-'}")
    return done


CHOICE = {"type": "object", "properties": {"choice": {"type": "string", "enum": ["A", "B"]},
                                         "why": {"type": "string"}}, "required": ["choice", "why"]}

PICK = """Two versions of the same keyframe of a music video: A is the picture as drawn, B is the same picture flipped
left-right. Open both files (Read tool) and the neighbouring keyframes of the same place, and decide which version
agrees with the world bible and with the neighbours: who sits or stands on which side, which side of the road or
room things are on, seen from this camera direction (seen from the front, a person's or vehicle's own left is on the
RIGHT of the picture; from behind, on the left). Answer B only if B is clearly right and A clearly wrong."""


def flip_checker(p: Project, orientation: str, timeout: float = 600, log=print):
    """A second opinion before a flip: the model sees the picture and its mirror image side by side (a direct choice is
    steadier than judging one picture: three-quarter views of a car were called mirrored and then not)."""
    sb = p.storyboard() or {"shots": []}
    order = [s["id"] for s in sb["shots"]]

    def confirm(issue: dict, image: Path) -> bool:
        flipped = image.with_name(f"{image.stem}.flipped-candidate.png")
        with Image.open(image) as im:
            ImageOps.mirror(im.convert("RGB")).save(flipped)
        try:
            i = order.index(issue["shot"])
            near = [p.key_path("codex", x, orientation) for x in order[max(0, i - 2):i + 3] if x != issue["shot"]]
            near = [x for x in near if x.exists()]
            shot = sb["shots"][i]
            text = (f"{PICK}\n\nWorld bible:\n{bible_text(sb)}\n\nThis shot ({issue['shot']}): {shot.get('scene', '')}\n"
                    f"Reported problem: {issue['problem']}\n\nA: {image.resolve()}\nB: {flipped.resolve()}\n"
                    "Neighbouring keyframes:\n" + "\n".join(str(x.resolve()) for x in near))
            answer = ask(text, image, timeout, log, CHOICE, "choice", "flip check", '{"choice": "A|B", "why"}',
                         images=[image, flipped, *near])
            return answer.get("choice") == "B"
        except Exception as e:  # noqa: BLE001 - no second opinion, no flip
            log(f"flip check of {issue['shot']} failed: {e}")
            return False
        finally:
            flipped.unlink(missing_ok=True)

    return confirm


def report(p: Project) -> dict | None:
    path = report_path(p)
    return json.loads(path.read_text()) if path.exists() else None
