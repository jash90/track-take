"""Pick the video encoder for this machine: VideoToolbox on a Mac, NVENC on an NVIDIA box (Vast), else x264/x265.

TRACKTAKE_ENCODER=videotoolbox|nvenc|cpu forces a family (e.g. cpu when a host's NVENC sessions are exhausted).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from functools import cache

FAMILIES = {
    "videotoolbox": {"h264": "h264_videotoolbox", "hevc": "hevc_videotoolbox"},
    "nvenc": {"h264": "h264_nvenc", "hevc": "hevc_nvenc"},
    "cpu": {"h264": "libx264", "hevc": "libx265"},
}


@cache
def _available() -> frozenset[str]:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, check=False).stdout
    return frozenset(line.split()[1] for line in out.splitlines() if line.startswith(" V") and len(line.split()) > 1)


def family() -> str:
    forced = os.environ.get("TRACKTAKE_ENCODER")
    if forced:
        if forced not in FAMILIES:
            raise ValueError(f"TRACKTAKE_ENCODER must be one of {sorted(FAMILIES)}")
        return forced
    have = _available()
    if platform.system() == "Darwin" and "h264_videotoolbox" in have:
        return "videotoolbox"
    if "h264_nvenc" in have and shutil.which("nvidia-smi") and _encodes("h264_nvenc"):
        return "nvenc"
    return "cpu"


@cache
def _encodes(encoder: str) -> bool:
    """Listed is not enough: a container without the driver's encode library lists NVENC but cannot use it."""
    probe = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
             "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"]
    return subprocess.run(probe, capture_output=True, check=False).returncode == 0


def video_args(codec: str, bitrate: str) -> list[str]:
    """ffmpeg output args for `codec` (h264|hevc) at a target `bitrate` like "14M" or "1300k"."""
    fam = family()
    enc = FAMILIES[fam][codec]
    args = ["-c:v", enc, "-b:v", bitrate]
    if fam == "nvenc":
        args += ["-preset", "p5", "-rc", "vbr"]
    elif fam == "cpu":
        args += ["-preset", "medium"]
    if codec == "h264":
        args += ["-profile:v", "high"]
    else:
        args += ["-tag:v", "hvc1"]  # plays in QuickTime / iOS
    return [*args, "-pix_fmt", "yuv420p"]
