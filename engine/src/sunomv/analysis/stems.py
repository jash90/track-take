"""Source separation with demucs htdemucs (MPS when available, CPU fallback), cached as WAVs."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from ..devices import torch_devices

STEM_NAMES = ("vocals", "drums", "bass", "other")
log = logging.getLogger(__name__)


def stem_paths(stem_dir: Path) -> dict[str, Path]:
    return {name: stem_dir / f"{name}.wav" for name in STEM_NAMES}


def _run_demucs(mix: np.ndarray, sr: int, device: str, model_name: str) -> dict[str, np.ndarray]:
    import torch
    from demucs.apply import apply_model
    from demucs.pretrained import get_model

    model = get_model(model_name)
    model.eval()
    if sr != model.samplerate:
        raise ValueError(f"demucs expects {model.samplerate} Hz, got {sr}")
    wav = torch.from_numpy(mix.T.copy())  # (channels, samples)
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std() + 1e-8
    wav = (wav - mean) / std
    with torch.no_grad():
        out = apply_model(model, wav[None], device=device, split=True, overlap=0.25, progress=False)[0]
    out = out * std + mean
    return {name: out[i].cpu().numpy().T for i, name in enumerate(model.sources)}


def separate(
    mix: np.ndarray, sr: int, stem_dir: Path, model_name: str = "htdemucs", device: str | None = None
) -> tuple[dict[str, Path], str]:
    """Write vocals/drums/bass/other WAVs into `stem_dir`; returns (paths, device used or "cache")."""
    import soundfile as sf

    paths = stem_paths(stem_dir)
    if all(p.exists() for p in paths.values()):
        return paths, "cache"
    stem_dir.mkdir(parents=True, exist_ok=True)

    import torch

    devices = [device] if device else torch_devices()
    last_err: Exception | None = None
    for dev in devices:
        try:
            stems = _run_demucs(mix, sr, dev, model_name)
            break
        except Exception as e:  # noqa: BLE001 - MPS can miss ops or run out of memory; retry on CPU
            log.warning("demucs on %s failed: %s", dev, e)
            last_err = e
    else:
        raise RuntimeError("demucs failed on all devices") from last_err

    for name, p in paths.items():
        sf.write(p, stems[name], sr, subtype="FLOAT")
    if dev == "mps":
        torch.mps.empty_cache()
    return paths, dev
