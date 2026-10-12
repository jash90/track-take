"""Audio decoding, hashing and the per-song cache directory."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import numpy as np


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def decode(path: Path, sr: int = 44100, channels: int = 2) -> np.ndarray:
    """Decode any ffmpeg-readable file to float32, shape (samples, channels)."""
    cmd = [
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-i",
        str(path),
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ac",
        str(channels),
        "-ar",
        str(sr),
        "-",
    ]
    raw = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).reshape(-1, channels).copy()


def to_mono(audio: np.ndarray) -> np.ndarray:
    return audio.mean(axis=1) if audio.ndim == 2 else audio


def cache_dir(work_dir: Path, audio_sha256: str) -> Path:
    """Per-song cache, keyed by the audio hash so a re-run never recomputes."""
    d = work_dir / "cache" / audio_sha256[:16]
    d.mkdir(parents=True, exist_ok=True)
    return d
