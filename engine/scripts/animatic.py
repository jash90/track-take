"""Animatic: the whole song cut from the Codex keyframes, without a GPU - to judge rhythm and transitions before a paid
render.

Every keyframe stands in for its Wan clip: a slow sideways drift across the picture (an `insert` stays still), then
the real montage runs on it (scripts/full_render.py: the storyboard's animation, its cuts and whip pans, the song).
Writes <project>/full/animatic_<format>.mp4.

Usage: uv run python scripts/animatic.py <project_dir> [--format 16x9|9x16] [--jobs 8]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

from tracktake.shards import split_args

FRAMES = 33  # the shortest Wan clip; the montage stretches it over the shot like a real one
SIZE = {"16x9": (832, 480), "9x16": (480, 832)}
ORIENT = {"16x9": "landscape", "9x16": "portrait"}


def fake_clip(key: Path, out: Path, size: tuple[int, int], still: bool) -> None:
    """Frames that pan slowly left to right across the keyframe (zoomed in a little to have room to move)."""
    out.mkdir(parents=True, exist_ok=True)
    w, h = size
    img = Image.open(key).convert("RGB")
    big = img.resize((int(w * 1.1), int(h * 1.1)))
    room = big.width - w
    for i in range(FRAMES):
        x = room // 2 if still else round(room * i / (FRAMES - 1))
        big.crop((x, (big.height - h) // 2, x + w, (big.height - h) // 2 + h)).save(out / f"{i:04d}.png")


def main() -> None:
    pos, opts = split_args(sys.argv[1:])
    project = Path(pos[0])
    fmt = opts.get("format", "16x9")
    full = project / "full"
    sb = json.loads((full / "storyboard.json").read_text())
    song = next((project / "input").glob("song.*"))
    with tempfile.TemporaryDirectory(prefix="animatic_") as tmp:
        work = Path(tmp) / "full"
        clips = work / "codex" / "clips"
        clips.mkdir(parents=True)
        (work / "storyboard.json").write_text(json.dumps(sb))
        for sh in sb["shots"]:
            key = full / "codex" / "keys" / f"{sh['id']}_{ORIENT[fmt]}.png"
            if not key.exists():
                raise SystemExit(f"missing keyframe {key.name}: draw the keyframes first")
            name = f"{sh['id']}_{ORIENT[fmt]}"
            fake_clip(key, clips / name, SIZE[fmt], still=sh.get("role") == "insert")
            (clips / f"{name}.json").write_text("{}")
        subprocess.run([sys.executable, str(Path(__file__).with_name("full_render.py")), str(work),
                        str(project / "analysis.json"), str(song), "codex", "--format", fmt, "--captions", "off",
                        "--jobs", opts.get("jobs", "8")], check=True)
        out = full / f"animatic_{fmt}.mp4"
        shutil.copy2(work / "codex" / f"teledysk_codex_{fmt}_preview.mp4", out)
        print(out)


if __name__ == "__main__":
    main()
