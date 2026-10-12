"""Forced alignment of known lyric lines to the vocals stem with stable-ts.

Backends: "mlx" (Apple Silicon, mlx-whisper weights) or "torch" (openai-whisper weights, CUDA/MPS/CPU).
The text is given, so this is alignment, not transcription.
"""

from __future__ import annotations

import gc
import logging
import platform
import re

import numpy as np

from ..devices import torch_devices
from ..models import LyricLine, Word

log = logging.getLogger(__name__)
WHISPER_SR = 16000


def default_backend() -> str:
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        try:
            import mlx_whisper  # noqa: F401

            return "mlx"
        except ImportError:
            pass
    return "torch"


def _load(model_name: str, backend: str):
    import stable_whisper

    if backend == "mlx":
        import mlx.core as mx

        return stable_whisper.load_mlx_whisper(model_name, dtype=mx.float16)
    device = torch_devices()[0]
    try:
        return stable_whisper.load_model(model_name, device=device)
    except Exception as e:  # noqa: BLE001 - sparse/unsupported ops on MPS
        log.warning("whisper on %s failed to load: %s; using CPU", device, e)
        return stable_whisper.load_model(model_name, device="cpu")


def align_lines(
    vocals_16k: np.ndarray,
    lines: list[str],
    language: str,
    model_name: str = "large-v3",
    backend: str | None = None,
) -> tuple[list[LyricLine], str]:
    """Align `lines` (in order) to mono 16 kHz vocals. Returns (aligned lines, method description)."""
    backend = backend or default_backend()
    model = _load(model_name, backend)
    result = model.align(
        vocals_16k.astype(np.float32),
        "\n".join(lines),
        language=language,
        original_split=True,
        verbose=None,
    )
    words = [w for seg in result.segments for w in seg.words]
    seg_words = [list(seg.words) for seg in result.segments]
    del model, result
    gc.collect()

    if len(seg_words) == len(lines):
        grouped = seg_words
    else:  # segment split drifted: regroup by word counts of the original lines
        log.warning(
            "aligner returned %d segments for %d lines; regrouping by word count", len(seg_words), len(lines)
        )
        grouped = _regroup(words, lines)
    out = [_to_line(text, ws) for text, ws in zip(lines, grouped)]
    return out, f"stable-ts align ({backend}, whisper {model_name})"


def _norm(s: str) -> str:
    return re.sub(r"[^\w']+", "", s.lower())


def _regroup(words: list, lines: list[str]) -> list[list]:
    groups, k = [], 0
    for line in lines:
        n = len([t for t in line.split() if _norm(t)])
        groups.append(words[k : k + n])
        k += n
    return groups


def _to_line(text: str, words: list) -> LyricLine:
    ws = [Word(text=w.word.strip(), start=float(w.start), end=float(w.end)) for w in words if w.word.strip()]
    if not ws:
        return LyricLine(text=text, start=0.0, end=0.0, words=[])
    return LyricLine(text=text, start=ws[0].start, end=ws[-1].end, words=ws)


def line_is_timed(line: LyricLine, min_dur: float = 0.05) -> bool:
    """False when the aligner gave up on a line (no words or zero length)."""
    return bool(line.words) and line.end - line.start >= min_dur
