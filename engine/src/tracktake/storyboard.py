"""Storyboard: shot boundaries from the analysis, and the director (an LLM) that writes each shot's scene and motion.

Shots are cut on downbeats, two bars each inside a section (a leftover bar joins the last shot of the section);
Build-Up blips shorter than 1.5 s join the previous shot. Only a few shots start with a hard cut (`cut`: the song
enters a verse, chorus, bridge, breakdown or outro); every other shot continues the previous one: its keyframe is
the next moment of the same place and the previous clip is animated to land exactly on it. The director is the local `claude` CLI (the user's own
subscription, no API key) asked for structured JSON; `codex exec` is the fallback.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from itertools import pairwise
from pathlib import Path

from tracktake.models import Analysis

CUT_KINDS = {"verse", "chorus", "bridge", "breakdown", "outro"}

DEFAULT_STYLE = ("paper cut-out stop-motion animation, everything built from layered construction paper with visible "
                 "paper texture and soft shadows between the paper layers")


MIN_SHOT_S = 5.0  # a clip needs time for its motion and for flowing into the next shot; 2 bars of a fast song
                  # (~3.7 s at 130 BPM) made the animation look rushed
TINY_SHOT_S = 3.0  # leftovers shorter than this join the previous shot


def bars_per_shot(a: Analysis) -> int:
    """2 bars per shot, doubled until a shot lasts at least MIN_SHOT_S (4 bars for fast songs, 8 for very fast)."""
    downs = sorted(a.downbeats)
    gaps = sorted(b - c for c, b in pairwise(downs) if b > c)
    bar = gaps[len(gaps) // 2] if gaps else 2.0
    step = 2
    while step * bar < MIN_SHOT_S and step < 8:
        step *= 2
    return step


def plan_shots(a: Analysis) -> list[dict]:
    step = bars_per_shot(a)
    shots: list[dict] = []
    for s in a.sections:
        if s.end - s.start < 1.5 and shots and s.kind == "build":
            shots[-1]["end"] = round(s.end, 2)
            shots[-1]["section"] += "+Build-Up"
            continue
        starts = sorted({round(s.start, 2)} | {round(d, 2) for d in a.downbeats if s.start + 0.3 < d < s.end - 0.3})
        chunk = starts[0::step]
        if len(chunk) > 1 and len(starts) - (len(chunk) - 1) * step <= step // 2:
            chunk = chunk[:-1]  # a short leftover joins the section's last shot
        for i, c in enumerate(chunk):
            end = chunk[i + 1] if i + 1 < len(chunk) else round(s.end, 2)
            shots.append({"start": c, "end": end, "section": s.label, "kind": s.kind})
    merged: list[dict] = []
    for sh in shots:  # a very short section (or leftover) would flash by: it extends the shot before it
        if merged and sh["end"] - sh["start"] < TINY_SHOT_S:
            merged[-1]["end"] = sh["end"]
            if sh["section"].split("+")[0] != merged[-1]["section"].split("+")[0]:
                merged[-1]["section"] += "+" + sh["section"]
            continue
        merged.append(sh)
    shots = merged
    for i, sh in enumerate(shots):
        sh["id"] = f"s{i + 1:02d}"
        sh["lines"] = [ln.text for ln in a.lines if sh["start"] - 0.4 <= ln.start < sh["end"] - 0.4]
        new_section = sh["section"].split("+")[0] != shots[i - 1]["section"].split("+")[0] if i else True
        sh["cut"] = i == 0 or (new_section and sh["kind"] in CUT_KINDS)
        sh["scene"] = ""
        sh["motion"] = ""
    return shots


def is_cut(shots: list[dict], i: int) -> bool:
    """Does shot i start with a hard cut? Storyboards from before continuity cut on every shot."""
    return i == 0 or shots[i].get("cut", True)


def continues_into(shots: list[dict], i: int) -> dict | None:
    """The next shot when shot i flows into it (its clip must end on the next keyframe), else None."""
    return shots[i + 1] if i + 1 < len(shots) and not is_cut(shots, i + 1) else None


def replan(a: Analysis, old: dict | None, style: str) -> dict:
    """New boundaries; scene/motion texts survive for shots whose time range did not change."""
    shots = plan_shots(a)
    previous = {(round(s["start"], 1), round(s["end"], 1)): s for s in (old or {}).get("shots", [])}
    for sh in shots:
        prev = previous.get((round(sh["start"], 1), round(sh["end"], 1)))
        if prev:
            sh["scene"], sh["motion"] = prev.get("scene", ""), prev.get("motion", "")
            sh["cut"] = prev.get("cut", sh["cut"]) or sh["id"] == "s01"
    return {"style": (old or {}).get("style") or style or DEFAULT_STYLE, "heroine": (old or {}).get("heroine", ""),
            "shots": shots}


BIBLE_ITEM = {"type": "object", "properties": {"id": {"type": "string"}, "name": {"type": "string"},
                                               "look": {"type": "string"}}, "required": ["id", "look"]}
SCHEMA = {
    "type": "object",
    "properties": {
        "heroine": {"type": "string"},
        "locations": {"type": "array", "items": BIBLE_ITEM},
        "props": {"type": "array", "items": BIBLE_ITEM},
        "shots": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "string"}, "scene": {"type": "string"}, "motion": {"type": "string"},
                           "location": {"type": "string"}, "props": {"type": "array", "items": {"type": "string"}}},
            "required": ["id", "scene", "motion", "location"]}},
    },
    "required": ["heroine", "locations", "props", "shots"],
}

RULES = """You are the director of a music video. Write, for each requested shot, two English texts:
- scene: ONE complete picture for an image model (the whole frame: place, light, the character and what she does).
  Background and characters are one scene, never separate elements. 1-3 sentences, concrete and visual.
- motion: what moves during the shot for an image-to-video model (character action, camera, light, weather). 1 sentence.
  Pace it to the shot's length (given in seconds): under ~6 s only ONE small, slow change (a gentle push-in, a head
  turn, a hand reaching); 6-10 s allow one bigger move. Never pack several actions or a long camera journey into a
  short shot - the clip would look rushed.
Rules:
- Tell the song's story through visual metaphors of the lyrics sung in that shot; instrumental shots carry mood.
- Recurring motifs and a few recurring locations make it feel like one film; vary framing (wide, medium, close-up).
- When a shot has no person, do not mention people at all (image models add people for words like "couple").
- Refer to the main character as "the woman" (or the given character) - her look is defined once in `heroine`.
- No written text, letters, signs or captions in the image.
- Screen directions: image models confuse a person's or vehicle's own left/right with the left/right of the picture.
  Whenever a side matters (who sits where, who drives, which roadside has the lamps, which wall has the window), say
  where it is IN THE FRAME for this camera angle: "seen from the front, the man at the wheel is on the right of the
  frame and the woman on the left". Seen from the front, a car's or person's own left is on the RIGHT of the frame;
  seen from behind, on the left. Keep the world's layout fixed across shots and work out the frame sides anew each
  time the camera turns around.
- Match the requested style and the cover art palette; energy follows the section (verses calmer, choruses bigger).
- Keep the shot ids exactly as given; return only the requested shots.
Continuity (most important - the video must not feel like a slideshow of separate pictures):
- Shots marked CUT start a new scene and may change place. Every other shot is marked CONTINUES: it is the same
  continuous camera take as the shot before it, picked up a few seconds later - same place, same light, same
  weather, same character in the same clothes, same palette; only the camera position/framing and the action moved on.
- `scene` describes the exact picture at the START of the shot. The clip of the previous shot is animated to arrive
  exactly at that picture, so the previous shot's `motion` must lead naturally into it (e.g. previous motion "the
  camera slowly pushes in towards her hands on the window sill" -> this scene "close-up of her hands on the sill").
- Keep the START pictures of consecutive CONTINUES shots close (similar framing, the same people in similar places):
  the clip has only the shot's length to travel from one to the next, and a big difference looks like a fast morph.
- Avoid big jumps inside a continuous run (no new location, no time-of-day change, no new costume, no new objects
  appearing from nowhere); save those for CUT shots. Gradual changes (camera travels, light slowly shifts, rain
  starts) are welcome.
- The last shot before a CUT can end anywhere.
World bible (so the same place and the same objects look identical in every shot, across cuts too):
- `locations`: every place the video uses, once, with an id (e.g. "bedroom") and a `look` that fixes what an image
  model could otherwise change: room size and layout, where the window/door are, every piece of furniture with its
  KIND, SIZE and COLOUR ("a narrow single bed with a grey wool blanket against the left wall", not "a bed"), floor,
  walls, light sources. Exterior places likewise (street width, house shape, what is across the road).
- `props`: objects that matter or recur (the coat, the two cups, the phone) with a fixed look and count. Every
  OTHER recurring person (e.g. the male partner in a duet) is also a `props` entry with id like "man" and a `look`
  that fixes face, hair, build and clothes exactly as for the main character; list that id in every shot he is in.
- Every shot names its `location` id and the `props` ids visible in it; its `scene` must agree with those looks
  exactly - never resize, recolour, double or swap an object (a single bed stays single; two cups stay two unless the
  story removes one, and then the scene says so). Story changes of an object (the coat is taken off the hook) are
  stated explicitly in the scene where they happen and kept afterwards.
- If a world bible is given below, keep it unchanged and reuse its ids; add entries only for new places or objects."""


def bible_text(sb: dict) -> str:
    rows = [f"- location {e['id']}: {e['look']}" for e in sb.get("locations", [])]
    rows += [f"- prop {e['id']}: {e['look']}" for e in sb.get("props", [])]
    return "\n".join(rows)


def director_prompt(sb: dict, shot_ids: list[str], song_style: str, cover: Path | None, lyrics: str,
                    instructions: str = "") -> str:
    shots = [s for s in sb["shots"] if s["id"] in shot_ids]
    lines = [f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s ({s['end'] - s['start']:.1f} s) [{s['section']}] "
             f"{'CUT' if is_cut(sb['shots'], i) else 'CONTINUES'} lyrics: {' / '.join(s['lines']) or '(instrumental)'}"
             + (f" | location: {s['location']}" if s.get("location") else "")
             + (f" | current scene: {s['scene']}" if s.get("scene") else "") for i, s in enumerate(sb["shots"])]
    cover_hint = f"Look at the album cover image at {cover} (use the Read tool) for palette and mood.\n" if cover else ""
    heroine = sb.get("heroine") or "(not defined yet: invent one main character that fits the cover and song, " \
                                   "and describe her look precisely in `heroine`: hair, face, clothes, shoes)"
    bible = bible_text(sb)
    return (f"{RULES}\n\nVideo style: {song_style or sb.get('style') or DEFAULT_STYLE}\nMain character: {heroine}\n"
            f"{cover_hint}{('Extra instructions from the user: ' + instructions) if instructions else ''}\n\n"
            + (f"World bible:\n{bible}\n\n" if bible else "") +
            f"Full lyrics:\n{lyrics}\n\nAll shots of the video (for context):\n" + "\n".join(lines)
            + f"\n\nWrite scene and motion for these shots: {', '.join(s['id'] for s in shots)}.")


def write(sb: dict, shot_ids: list[str] | None, song_style: str, cover: Path | None, lyrics: str,
          instructions: str = "", timeout: float = 900, log=print) -> dict:
    """Ask the director for scene+motion of `shot_ids` (all when None); returns the updated storyboard."""
    ids = shot_ids or [s["id"] for s in sb["shots"]]
    prompt = director_prompt(sb, ids, song_style, cover, lyrics, instructions)
    result = ask(prompt, cover, timeout, log)
    by_id = {s["id"]: s for s in result["shots"]}
    missing = [i for i in ids if i not in by_id]
    if missing:
        log(f"director skipped {len(missing)} shots: {', '.join(missing)}")
    for s in sb["shots"]:
        if s["id"] in by_id:
            got = by_id[s["id"]]
            s["scene"], s["motion"] = got["scene"].strip(), got["motion"].strip()
            s["location"], s["props"] = got.get("location", ""), list(got.get("props") or [])
    for kind in ("locations", "props"):  # the bible only grows: existing looks stay fixed
        known = {e["id"]: e for e in sb.get(kind, [])}
        for e in result.get(kind) or []:
            known.setdefault(e["id"], {"id": e["id"], "name": e.get("name", e["id"]), "look": e["look"].strip()})
        sb[kind] = list(known.values())
    if result.get("heroine") and not sb.get("heroine"):
        sb["heroine"] = result["heroine"].strip()
    if song_style:
        sb["style"] = song_style
    return sb


def ask(prompt: str, cover: Path | None, timeout: float, log, schema: dict | None = None, key: str = "shots",
        who: str = "director", shape: str = "", images: list[Path] | None = None) -> dict:
    """Structured answer from the local claude CLI, or codex exec when claude is not installed. `images` are files
    the prompt names by path (claude reads them, codex gets them attached)."""
    if shutil.which("claude"):
        return _ask_claude(prompt, cover, timeout, log, schema or SCHEMA, key, who, images)
    return _ask_codex(prompt, timeout, log, shape or DIRECTOR_SHAPE, who, images)


DIRECTOR_SHAPE = ('{"heroine": str, "locations": [{"id", "name", "look"}], "props": [{"id", "name", "look"}], '
                  '"shots": [{"id", "scene", "motion", "location", "props": [ids]}]}')


def _ask_claude(prompt: str, cover: Path | None, timeout: float, log, schema: dict = SCHEMA, key: str = "shots",
                who: str = "director", images: list[Path] | None = None) -> dict:
    cmd = ["claude", "-p", "--output-format", "json", "--json-schema", json.dumps(schema), "--allowedTools", "Read"]
    for folder in dict.fromkeys(f.parent.resolve() for f in [*([cover] if cover else []), *(images or [])]):
        cmd += ["--add-dir", str(folder)]
    log(f"{who}: claude -p (structured output)")
    r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"claude failed ({r.returncode}): {(r.stderr or r.stdout)[-800:]}")
    envelope = json.loads(r.stdout)
    data = envelope.get("structured_output") or envelope.get("result")
    if isinstance(data, str):
        data = json.loads(_strip_fences(data))
    if not isinstance(data, dict) or key not in data:
        raise RuntimeError(f"{who} returned no {key}: {str(envelope)[:500]}")
    return data


def _ask_codex(prompt: str, timeout: float, log, shape: str = DIRECTOR_SHAPE, who: str = "director",
               images: list[Path] | None = None) -> dict:
    log(f"{who}: codex exec (claude CLI not found)")
    full = prompt + f"\n\nAnswer with ONLY a JSON object: {shape}"
    cmd = ["codex", "exec", "--skip-git-repo-check", "-s", "read-only"]
    for image in images or []:
        cmd += ["-i", str(image.resolve())]
    r = subprocess.run(cmd, input=full, capture_output=True, text=True, timeout=timeout, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"codex failed ({r.returncode}): {r.stderr[-800:]}")
    text = r.stdout
    return json.loads(_strip_fences(text[text.find("{"): text.rfind("}") + 1]))


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return text
