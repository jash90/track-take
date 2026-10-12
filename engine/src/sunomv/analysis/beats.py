"""Beats, downbeats and BPM. CPJKU beat_this first, librosa as fallback."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from ..devices import torch_devices

log = logging.getLogger(__name__)


@dataclass
class BeatGrid:
    beats: list[float]
    downbeats: list[float]
    bpm: float
    beats_per_bar: int
    method: str


def bpm_of(beats: np.ndarray) -> float:
    """Tempo from the median inter-beat interval (robust to a few missed/extra beats)."""
    if len(beats) < 2:
        return 0.0
    return float(60.0 / np.median(np.diff(beats)))


def beats_per_bar_of(beats: np.ndarray, downbeats: np.ndarray, default: int = 4) -> int:
    """Most common number of beats between consecutive downbeats."""
    if len(downbeats) < 2:
        return default
    counts = np.diff(np.searchsorted(beats, downbeats))
    counts = counts[counts > 0]
    if not len(counts):
        return default
    vals, freq = np.unique(counts, return_counts=True)
    return int(vals[np.argmax(freq)])


def regularize_downbeats(beats: np.ndarray, downbeats: np.ndarray, beats_per_bar: int) -> np.ndarray:
    """Drop downbeats that come at most half a bar after the previous kept one.

    beat_this sometimes flips to half-bars (a downbeat every 2 beats) in sparse passages; keeping the
    original phase gives a consistent bar grid. Short bars after a real pause (3 of 4 beats) are kept.
    """
    if len(downbeats) < 2 or len(beats) < 2:
        return downbeats
    idx = np.searchsorted(beats, downbeats - 1e-3)
    kept = [0]
    for k in range(1, len(downbeats)):
        if idx[k] - idx[kept[-1]] > beats_per_bar // 2:
            kept.append(k)
    return downbeats[kept]


def _beat_this(mono: np.ndarray, sr: int, device: str) -> tuple[np.ndarray, np.ndarray]:
    from beat_this.inference import Audio2Beats

    tracker = Audio2Beats(checkpoint_path="final0", device=device, dbn=False)
    beats, downbeats = tracker(mono.astype(np.float64), sr)
    return np.asarray(beats, dtype=float), np.asarray(downbeats, dtype=float)


def _librosa(mono: np.ndarray, sr: int, beats_per_bar: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """librosa beat tracking; downbeat phase = the one with the strongest low-band onsets."""
    import librosa

    hop = 512
    env = librosa.onset.onset_strength(y=mono, sr=sr, hop_length=hop)
    _, frames = librosa.beat.beat_track(onset_envelope=env, sr=sr, hop_length=hop)
    beats = librosa.frames_to_time(frames, sr=sr, hop_length=hop)
    mel = librosa.feature.melspectrogram(y=mono, sr=sr, hop_length=hop, n_mels=64, fmax=sr / 2)
    low_bins = librosa.mel_frequencies(n_mels=64, fmax=sr / 2) < 200
    low_env = librosa.onset.onset_strength(S=librosa.power_to_db(mel[low_bins]), sr=sr, hop_length=hop)
    idx = np.clip(frames, 0, len(low_env) - 1)
    phase_strength = [
        low_env[idx[p::beats_per_bar]].mean() if len(idx[p::beats_per_bar]) else 0.0
        for p in range(beats_per_bar)
    ]
    phase = int(np.argmax(phase_strength))
    return beats, beats[phase::beats_per_bar]


def track(mono: np.ndarray, sr: int, prefer: str = "beat_this") -> BeatGrid:
    """Beat grid of a mono mix. Falls back from beat_this (CUDA or MPS, then CPU) to librosa."""
    attempts: list[str] = []
    if prefer == "beat_this":

        attempts = torch_devices()
    for dev in attempts:
        try:
            beats, downbeats = _beat_this(mono, sr, dev)
            if len(beats) >= 8:
                return _grid(beats, downbeats, f"beat_this final0 ({dev}, minimal postprocessing)")
            log.warning("beat_this on %s found only %d beats", dev, len(beats))
        except Exception as e:  # noqa: BLE001 - any failure falls through to the next backend
            log.warning("beat_this on %s failed: %s", dev, e)
    beats, downbeats = _librosa(mono, sr)
    return _grid(beats, downbeats, "librosa beat_track + low-band downbeat phase")


def _grid(beats: np.ndarray, downbeats: np.ndarray, method: str) -> BeatGrid:
    bpb = beats_per_bar_of(beats, downbeats)
    fixed = regularize_downbeats(beats, downbeats, bpb)
    if len(fixed) < len(downbeats):
        method += f"; dropped {len(downbeats) - len(fixed)} half-bar downbeats"
    return BeatGrid(
        beats=[round(float(t), 4) for t in beats],
        downbeats=[round(float(t), 4) for t in fixed],
        bpm=round(bpm_of(beats), 2),
        beats_per_bar=bpb,
        method=method,
    )
