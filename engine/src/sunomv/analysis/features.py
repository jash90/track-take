"""Per-stem envelopes at the video fps, onsets with strength, and kick/snare/hat hits from the drums stem."""

from __future__ import annotations

import math

import numpy as np

from ..models import Envelope, Onset, StemFeatures

SR = 22050
HOP = 256  # ~11.6 ms analysis hop; envelopes are then pooled into video frames
N_FFT = 2048
BANDS = {"low": (20.0, 250.0), "mid": (250.0, 4000.0), "high": (4000.0, 11025.0)}
DRUM_BANDS = {"kick": (30.0, 150.0), "snare": (1000.0, 5000.0), "hat": (7000.0, 11025.0)}
MIN_STRENGTH = 0.08  # onsets weaker than this (after 0..1 normalisation) are dropped
GATE_DB = -24.0  # onsets where the signal is this far below its loud level are bleed/noise, not hits


def _spectrum(y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    import librosa

    power = np.abs(librosa.stft(y, n_fft=N_FFT, hop_length=HOP)) ** 2
    return power, librosa.fft_frequencies(sr=SR, n_fft=N_FFT)


def _band(power: np.ndarray, freqs: np.ndarray, lo: float, hi: float) -> np.ndarray:
    sel = (freqs >= lo) & (freqs < hi)
    return power[sel].sum(axis=0)


def normalise(x: np.ndarray, pct: float = 99.0) -> np.ndarray:
    """Scale to 0..1 by a high percentile (robust to single spikes); silent input stays 0."""
    ref = float(np.percentile(x, pct)) if len(x) else 0.0
    if ref <= 1e-9:
        return np.zeros_like(x, dtype=float)
    return np.clip(x / ref, 0.0, 1.0)


def pool_to_frames(x: np.ndarray, n_frames: int, fps: float) -> np.ndarray:
    """Average analysis frames into video frames; video frame k covers [(k-0.5)/fps, (k+0.5)/fps)."""
    t = np.arange(len(x)) * HOP / SR
    idx = np.clip(np.floor(t * fps + 0.5).astype(int), 0, n_frames - 1)
    sums = np.bincount(idx, weights=x, minlength=n_frames)
    counts = np.bincount(idx, minlength=n_frames)
    out = np.zeros(n_frames)
    nz = counts > 0
    out[nz] = sums[nz] / counts[nz]
    if (~nz).any() and nz.any():  # fps above the analysis rate: fill gaps by interpolation
        k = np.arange(n_frames)
        out[~nz] = np.interp(k[~nz], k[nz], out[nz])
    return out


def envelopes(power: np.ndarray, freqs: np.ndarray, duration: float, fps: float) -> dict[str, Envelope]:
    """rms + low/mid/high band amplitude, one value per video frame, each normalised to 0..1."""
    n_frames = max(1, math.ceil(duration * fps))
    raw = {"rms": np.sqrt(power.sum(axis=0) / N_FFT)}
    for name, (lo, hi) in BANDS.items():
        raw[name] = np.sqrt(_band(power, freqs, lo, hi))
    return {
        name: Envelope(
            fps=fps, values=[round(float(v), 4) for v in normalise(pool_to_frames(x, n_frames, fps))]
        )
        for name, x in raw.items()
    }


def _flux(band_energy: np.ndarray) -> np.ndarray:
    """Half-wave rectified log-energy difference: rises in a band's energy."""
    log_e = np.log1p(band_energy / (np.percentile(band_energy, 99) + 1e-12) * 100.0)
    return np.maximum(0.0, np.diff(log_e, prepend=log_e[:1]))


def _loud_enough(energy: np.ndarray, lookahead: int = 4) -> np.ndarray:
    """Per analysis frame: is the energy just after it within GATE_DB of the signal's loud (p99) level?"""
    ref = np.percentile(energy, 99)
    if ref <= 1e-12:
        return np.zeros(len(energy), dtype=bool)
    padded = np.concatenate([energy, np.zeros(lookahead)])
    ahead = np.lib.stride_tricks.sliding_window_view(padded, lookahead + 1)[: len(energy)].max(axis=1)
    return ahead >= ref * 10 ** (GATE_DB / 10)


def _pick(env: np.ndarray, energy: np.ndarray, wait_s: float = 0.05) -> list[Onset]:
    """Peak-pick an onset envelope, dropping weak peaks and peaks over near-silence (`energy` gate)."""
    import librosa

    if env.max() <= 1e-9:
        return []
    frames = librosa.onset.onset_detect(
        onset_envelope=env, sr=SR, hop_length=HOP, units="frames", wait=max(1, int(wait_s * SR / HOP))
    )
    loud = _loud_enough(energy[: len(env)])
    strength = env / env.max()
    return [
        Onset(time=round(float(f * HOP / SR), 4), strength=round(float(strength[f]), 4))
        for f in frames
        if f < len(loud) and loud[f] and strength[f] >= MIN_STRENGTH
    ]


def onsets(y: np.ndarray, power: np.ndarray | None = None) -> list[Onset]:
    import librosa

    power = _spectrum(y)[0] if power is None else power
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    return _pick(env, power.sum(axis=0))


def drum_hits(drums: np.ndarray, coincide_s: float = 0.03) -> dict[str, list[Onset]]:
    """Kick/snare/hat by band-split onset detection; a hat that coincides with a snare is the snare's
    own high-frequency noise and is dropped."""
    power, freqs = _spectrum(drums)
    hits = {}
    for name, (lo, hi) in DRUM_BANDS.items():
        energy = _band(power, freqs, lo, hi)
        hits[name] = _pick(_flux(energy), energy)
    snare_t = np.array([o.time for o in hits["snare"]])
    if len(snare_t):
        hits["hat"] = [o for o in hits["hat"] if np.min(np.abs(snare_t - o.time)) > coincide_s]
    return hits


def stem_features(y: np.ndarray, duration: float, fps: float) -> StemFeatures:
    power, freqs = _spectrum(y)
    return StemFeatures(onsets=onsets(y, power), envelopes=envelopes(power, freqs, duration, fps))
