"""Settings from config/tracktake.toml, with TRACKTAKE_* environment overrides.

Overrides use TRACKTAKE_<SECTION>_<KEY>, e.g. TRACKTAKE_COMFY_BACKEND=vast or TRACKTAKE_VAST_MAX_DPH=0.8.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import get_origin

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_PATH = REPO_ROOT / "config" / "tracktake.toml"
STATE_DIR = Path.home() / ".config" / "tracktake"


class ComfySettings(BaseModel):
    backend: str = "local"
    local_url: str = "http://127.0.0.1:8188"


class VideoSettings(BaseModel):
    local: str = "mlx"
    vast: str = "wan"


class VastSettings(BaseModel):
    gpu: str = "RTX_4090"
    gpus: int = 1  # GPUs per host; >1 runs one ComfyUI per GPU on a shared model download
    max_dph: float = 0.6  # USD per hour per GPU (a host with N GPUs may cost N times this)
    min_reliability: float = 0.98
    min_inet_down: int = 500
    max_download_cost: float = 0.006  # USD per GB downloaded; some hosts charge 10x more and models are ~60 GB
    download_gb: float = 60.0  # what provisioning downloads per instance, priced into each offer
    # country codes to rent in first; [] = anywhere. US hosts pulled the models 2-6x faster than European/Asian ones
    # (measured 147-493 MB/s vs 14-92 MB/s). With no matching offer there, the search falls back to anywhere.
    regions: list[str] = ["US"]
    # measured Hugging Face speed below this (MB/s) -> drop the host, take the next; under 70 MB/s the ~41 GB of models
    # take over 10 paid minutes
    min_download_mbs: float = 70.0
    disk_gb: int = 120
    image: str = "pytorch/pytorch:2.14.1-cuda13.0-cudnn9-runtime"
    comfy_repo: str = "https://github.com/comfyanonymous/ComfyUI"
    comfy_commit: str = "0df64eb"
    remote_port: int = 18188
    local_port: int = 8189
    models: list[str] = ["wan22_i2v", "zimage"]
    ssh_key: str = "~/.ssh/id_ed25519"


class Settings(BaseModel):
    comfy: ComfySettings = ComfySettings()
    video: VideoSettings = VideoSettings()
    vast: VastSettings = VastSettings()

    @property
    def comfy_url(self) -> str:
        if self.comfy.backend == "vast":
            return f"http://127.0.0.1:{self.vast.local_port}"
        return self.comfy.local_url

    @property
    def video_engine(self) -> str:
        return self.video.vast if self.comfy.backend == "vast" else self.video.local


def _apply_env(data: dict) -> dict:
    for section, fields in Settings.model_fields.items():
        model = fields.annotation
        for key, field in model.model_fields.items():
            raw = os.environ.get(f"TRACKTAKE_{section.upper()}_{key.upper()}")
            if raw is None:
                continue
            if get_origin(field.annotation) is list:
                value: object = [x.strip() for x in raw.split(",") if x.strip()]
            else:
                value = raw
            data.setdefault(section, {})[key] = value
    return data


def load(path: Path | None = None) -> Settings:
    path = path or CONFIG_PATH
    data = tomllib.loads(path.read_text()) if path.exists() else {}
    return Settings.model_validate(_apply_env(data))
