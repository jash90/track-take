"""Projects on disk: data/projects/<id>/ with inputs, analysis, storyboard, keyframes and videos.

Layout (the `full/` part is what the full-video scripts and the Vast remote job already use):
  project.json                 name, style, language, render settings
  input/song.<ext> cover.<ext> lyrics.txt
  analysis.json  peaks.json  work/ (analysis caches)
  full/storyboard.json  full/codex/{cover.jpeg,character_sheet.png,keys/}  full/comfy/keys/
  full/<set>/teledysk_<set>_<fmt>[_preview].mp4   thumbs/<set>_<shot>_<orientation>.jpg
"""

from __future__ import annotations

import json
import re
import shutil
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tracktake.config import REPO_ROOT

PROJECTS = REPO_ROOT / "data" / "projects"
KEY_SETS = ("codex", "comfy")
FORMATS = ("16x9", "9x16")
ORIENTATIONS = ("landscape", "portrait")
FORMAT_OF = {"landscape": "16x9", "portrait": "9x16"}
AUDIO_EXT = {".mp3", ".wav", ".flac", ".m4a", ".ogg", ".aac"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass
class Settings:
    workers: int = 4
    gpu: str = "RTX_4090"
    gpus: int = 1  # GPUs per host (one ComfyUI each, one model download)
    max_dph: float = 0.5  # USD per hour per GPU
    region: str = "US"  # rent here first (faster model downloads); "any" = anywhere, or e.g. "US,CA"
    captions: bool = True  # karaoke lyrics in the video
    beat_motion: bool = True  # camera pump on downbeats and shake on snares
    animation: str = "stopmotion"  # how the video moves: stopmotion | tableau (see animation.py)


@dataclass
class Meta:
    id: str
    name: str
    created: str
    style: str = ""
    language: str = "en"
    orientation: str = "landscape"  # one per project: landscape = 16:9 video, portrait = 9:16
    settings: Settings = field(default_factory=Settings)
    storyboard_approved: bool = False  # the autopilot waits for this when review is on
    autopilot: dict = field(default_factory=dict)  # state of the "make the video" job, see autopilot.py


def slug(name: str) -> str:
    s = unicodedata.normalize("NFKD", name.translate(str.maketrans("łŁøØđĐß", "lLoOdDs"))).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:40] or "projekt"


class Project:
    def __init__(self, root: Path):
        self.root = root
        self.id = root.name

    # -------------------------------------------------------------- paths
    @property
    def full(self) -> Path:
        return self.root / "full"

    @property
    def analysis_path(self) -> Path:
        return self.root / "analysis.json"

    @property
    def storyboard_path(self) -> Path:
        return self.full / "storyboard.json"

    def keys_dir(self, kind: str) -> Path:
        return self.full / kind / "keys"

    @property
    def character_sheet(self) -> Path:
        return self.full / "codex" / "character_sheet.png"

    @property
    def cover_ref(self) -> Path:
        """Cover copy next to the Codex keyframes (Codex is given it as a style reference)."""
        return self.full / "codex" / "cover.jpeg"

    def input_file(self, kind: str) -> Path | None:
        exts = AUDIO_EXT if kind == "song" else IMAGE_EXT
        for p in sorted((self.root / "input").glob(f"{kind}.*")):
            if p.suffix.lower() in exts:
                return p
        return None

    @property
    def lyrics_path(self) -> Path:
        return self.root / "input" / "lyrics.txt"

    # -------------------------------------------------------------- meta
    def meta(self) -> Meta:
        raw = json.loads((self.root / "project.json").read_text())
        raw["settings"] = Settings(**raw.get("settings", {}))
        return Meta(**raw)

    def save_meta(self, meta: Meta) -> None:
        (self.root / "project.json").write_text(json.dumps(asdict(meta), indent=1, ensure_ascii=False))

    def update(self, **changes) -> Meta:
        meta = self.meta()
        for k, v in changes.items():
            if v is None:
                continue
            if k == "settings":
                meta.settings = Settings(**(asdict(meta.settings) | v))
            elif k == "orientation":
                if v not in ORIENTATIONS:
                    raise ValueError(f"orientation must be one of {ORIENTATIONS}")
                meta.orientation = v
            elif k in ("name", "style", "language", "storyboard_approved", "autopilot"):
                setattr(meta, k, v)
        self.save_meta(meta)
        return meta

    # -------------------------------------------------------------- inputs
    def save_input(self, kind: str, filename: str, data: bytes) -> Path:
        ext = Path(filename).suffix.lower()
        allowed = AUDIO_EXT if kind == "song" else IMAGE_EXT
        if ext not in allowed:
            raise ValueError(f"{kind}: unsupported file type {ext}")
        folder = self.root / "input"
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob(f"{kind}.*"):
            old.unlink()
        out = folder / f"{kind}{ext}"
        out.write_bytes(data)
        if kind == "cover":  # Codex reference copy (JPEG keeps the prompt attachment small)
            from PIL import Image

            self.cover_ref.parent.mkdir(parents=True, exist_ok=True)
            Image.open(out).convert("RGB").save(self.cover_ref, quality=92)
        if kind == "song":  # new audio invalidates everything derived from it
            for p in (self.analysis_path, self.root / "peaks.json"):
                p.unlink(missing_ok=True)
        return out

    def lyrics(self) -> str:
        return self.lyrics_path.read_text(encoding="utf-8") if self.lyrics_path.exists() else ""

    def save_lyrics(self, text: str) -> None:
        self.lyrics_path.parent.mkdir(parents=True, exist_ok=True)
        self.lyrics_path.write_text(text, encoding="utf-8")

    # -------------------------------------------------------------- derived state
    def storyboard(self) -> dict | None:
        return json.loads(self.storyboard_path.read_text()) if self.storyboard_path.exists() else None

    def save_storyboard(self, sb: dict) -> None:
        self.full.mkdir(parents=True, exist_ok=True)
        self.storyboard_path.write_text(json.dumps(sb, indent=1, ensure_ascii=False))

    def key_path(self, kind: str, shot: str, orientation: str) -> Path:
        return self.keys_dir(kind) / f"{shot}_{orientation}.png"

    def video_paths(self, kind: str, fmt: str) -> tuple[Path, Path]:
        base = self.full / kind / f"teledysk_{kind}_{fmt}"
        return base.with_suffix(".mp4"), Path(f"{base}_preview.mp4")

    def url(self, path: Path) -> str:
        return f"/files/{self.id}/{path.relative_to(self.root).as_posix()}"


def all_projects() -> list[Project]:
    PROJECTS.mkdir(parents=True, exist_ok=True)
    found = [Project(p) for p in PROJECTS.iterdir() if (p / "project.json").exists()]
    return sorted(found, key=lambda p: p.meta().created, reverse=True)


def get(project_id: str) -> Project:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", project_id):
        raise KeyError(project_id)
    root = PROJECTS / project_id
    if not (root / "project.json").exists():
        raise KeyError(project_id)
    return Project(root)


def create(name: str, style: str = "", language: str = "en", orientation: str = "landscape") -> Project:
    if orientation not in ORIENTATIONS:
        raise ValueError(f"orientation must be one of {ORIENTATIONS}")
    base = slug(name)
    pid, n = base, 2
    while (PROJECTS / pid).exists():
        pid, n = f"{base}-{n}", n + 1
    root = PROJECTS / pid
    (root / "input").mkdir(parents=True)
    p = Project(root)
    p.save_meta(Meta(pid, name, datetime.now(UTC).isoformat(timespec="seconds"), style, language, orientation))
    return p


def delete(project_id: str) -> None:
    shutil.rmtree(get(project_id).root)


def import_existing(project_id: str, name: str, song: Path, lyrics: Path | None, cover: Path | None,
                    analysis: Path | None, full: Path | None, style: str = "") -> Project:
    """Make earlier CLI work visible in the UI. `full` is linked, not copied (clips are gigabytes)."""
    root = PROJECTS / project_id
    (root / "input").mkdir(parents=True, exist_ok=True)
    p = Project(root)
    if not (root / "project.json").exists():
        p.save_meta(Meta(project_id, name, datetime.now(UTC).isoformat(timespec="seconds"), style, "en"))
    shutil.copy(song, root / "input" / f"song{song.suffix.lower()}")
    if lyrics:
        shutil.copy(lyrics, p.lyrics_path)
    if cover:
        shutil.copy(cover, root / "input" / f"cover{cover.suffix.lower()}")
    if analysis:
        shutil.copy(analysis, p.analysis_path)
    if full and not p.full.exists():
        p.full.symlink_to(full.resolve(), target_is_directory=True)
    return p
