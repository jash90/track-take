"""Accelerator choice shared by the analysis steps: CUDA (Vast/NVIDIA), then MPS (Apple Silicon), then CPU."""

from __future__ import annotations


def torch_devices() -> list[str]:
    """Devices to try in order; CPU is always the last fallback."""
    import torch

    if torch.cuda.is_available():
        return ["cuda", "cpu"]
    if torch.backends.mps.is_available():
        return ["mps", "cpu"]
    return ["cpu"]
