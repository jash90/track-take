"""Image-to-video backends behind one interface: LTX-2.3 on this Mac (MLX) or Wan 2.2 in ComfyUI (local or Vast).

Both return the clip as RGBA frames plus the seconds spent, and both cache by clip spec, so re-running a project
only generates what changed.
"""

from __future__ import annotations

import io
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from PIL import Image

from tracktake import ltx
from tracktake.comfy.client import ComfyClient
from tracktake.comfy.graphs import wan_i2v
from tracktake.config import Settings


@dataclass(frozen=True)
class EngineProfile:
    """Generation size and timing an engine is good at; the renderer resamples to the project fps."""

    landscape: tuple[int, int]
    portrait: tuple[int, int]
    fps: float
    frames: int


PROFILES = {
    "mlx": EngineProfile((768, 448), (448, 768), 12, 41),  # 3.4 s, 8k+1 frames
    "wan": EngineProfile((832, 480), (480, 832), 16, 49),  # 3.1 s, 4k+1 frames
    "wan_hd": EngineProfile((1280, 720), (720, 1280), 16, 49),  # 720p, for 32 GB+ cards
}


class I2VBackend(Protocol):
    name: str
    profile: EngineProfile

    def generate(self, spec: ltx.ClipSpec, start_image: Path, out_dir: Path) -> tuple[list[np.ndarray], float]: ...


class MlxLtxBackend:
    name = "mlx"
    profile = PROFILES["mlx"]

    def generate(self, spec: ltx.ClipSpec, start_image: Path, out_dir: Path) -> tuple[list[np.ndarray], float]:
        clip, seconds = ltx.generate_clip(spec, start_image, out_dir)
        return ltx.read_frames(clip), seconds


class ComfyWanBackend:
    def __init__(self, client: ComfyClient, hd: bool = False):
        self.client = client
        self.name = "wan_hd" if hd else "wan"
        self.profile = PROFILES[self.name]

    def generate(self, spec: ltx.ClipSpec, start_image: Path, out_dir: Path,
                 end_image: Path | None = None) -> tuple[list[np.ndarray], float]:
        """`end_image` anchors the last frame (a continuous shot lands on the next shot's keyframe)."""
        frames_dir = out_dir / spec.id
        meta = out_dir / f"{spec.id}.json"
        key = asdict(spec) | {"start": start_image.name, "engine": self.name}
        if end_image:
            key["end"] = end_image.name
        if meta.exists() and json.loads(meta.read_text()).get("key") == key:
            return _read_pngs(frames_dir), 0.0
        started = time.monotonic()
        name = self.client.upload_image(start_image, f"tracktake_{spec.id}.png")
        end = self.client.upload_image(end_image, f"tracktake_{spec.id}_end.png") if end_image else None
        graph = wan_i2v(spec.prompt, name, seed=spec.seed, width=spec.width, height=spec.height,
                        length=spec.frames, prefix=f"tracktake/clips/{spec.id}", end_image=end)
        result = self.client.run(graph)
        frames_dir.mkdir(parents=True, exist_ok=True)
        for old in frames_dir.glob("*.png"):
            old.unlink()
        for i, data in enumerate(result.images):
            (frames_dir / f"{i:05d}.png").write_bytes(data)
        seconds = time.monotonic() - started
        meta.write_text(json.dumps({"key": key, "seconds": round(seconds, 1), "gpu_seconds": round(result.seconds, 1)}))
        return _read_pngs(frames_dir), seconds


def _read_pngs(folder: Path) -> list[np.ndarray]:
    files = sorted(folder.glob("*.png"))
    if not files:
        raise RuntimeError(f"no frames in {folder}")
    return [np.asarray(Image.open(io.BytesIO(f.read_bytes())).convert("RGBA")) for f in files]


def backend_for(settings: Settings, hd: bool = False) -> I2VBackend:
    engine = settings.video_engine
    if engine == "mlx":
        return MlxLtxBackend()
    if engine == "wan":
        return ComfyWanBackend(ComfyClient(settings.comfy_url), hd=hd)
    raise ValueError(f"unknown video engine {engine!r} (expected mlx or wan)")
