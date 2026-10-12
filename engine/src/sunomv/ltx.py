"""Image-to-video with LTX-2.3 running natively on Apple Silicon (dgrauet/ltx-2-mlx), driven through its CLI.

One process per clip: the pipeline frees Gemma and the DiT between stages anyway (low_memory), and a fresh process
returns all Metal memory, which matters on a 32 GB Mac.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np

LTX_DIR = Path.home() / "Projects" / "ltx-2-mlx"
LTX_PACK = LTX_DIR / "packs" / "ltx-2.3-q4-distilled"


@dataclass(frozen=True)
class ClipSpec:
    id: str
    prompt: str
    width: int
    height: int
    frames: int  # must be 8k+1
    frame_rate: float
    seed: int = 7


def generate_clip(spec: ClipSpec, start_image: Path, out_dir: Path, end_image: Path | None = None) -> tuple[Path, float]:
    """Animate `start_image` (optionally also anchoring the last frame). Cached by spec. Returns (mp4, seconds)."""
    if (spec.frames - 1) % 8:
        raise ValueError("LTX frame counts must be 8k+1")
    out_dir, start_image = out_dir.resolve(), start_image.resolve()  # the CLI runs with cwd=LTX_DIR
    end_image = end_image.resolve() if end_image else None
    out_dir.mkdir(parents=True, exist_ok=True)
    out, meta = out_dir / f"{spec.id}.mp4", out_dir / f"{spec.id}.json"
    key = asdict(spec) | {"start": start_image.name, "end": end_image.name if end_image else None}
    if out.exists() and meta.exists() and json.loads(meta.read_text()).get("key") == key:
        return out, 0.0
    cmd = ["uv", "run", "ltx-2-mlx", "generate", "--model", str(LTX_PACK), "--distilled",
           "-W", str(spec.width), "-H", str(spec.height), "-f", str(spec.frames), "--frame-rate", str(spec.frame_rate),
           "--seed", str(spec.seed), "--no-audio", "-p", spec.prompt, "-o", str(out),
           "--image", str(start_image), "0", "1.0"]
    if end_image is not None:
        cmd += ["--image", str(end_image), "last", "1.0"]
    started = time.monotonic()
    log = out_dir / f"{spec.id}.log"
    with log.open("w") as f:
        subprocess.run(cmd, cwd=LTX_DIR, stdout=f, stderr=subprocess.STDOUT, check=True)
    seconds = time.monotonic() - started
    meta.write_text(json.dumps({"key": key, "seconds": round(seconds, 1)}, indent=2))
    return out, seconds


def read_frames(path: Path) -> list[np.ndarray]:
    """All frames of a clip as RGBA uint8 arrays."""
    cap = cv2.VideoCapture(str(path))
    frames = []
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        frames.append(np.dstack([rgb, np.full(rgb.shape[:2], 255, np.uint8)]))
    cap.release()
    if not frames:
        raise RuntimeError(f"no frames decoded from {path}")
    return frames


def fit_cover(img: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize + centre-crop `img` to exactly width x height (no stretching)."""
    h, w = img.shape[:2]
    s = max(width / w, height / h)
    r = cv2.resize(img, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LANCZOS4)
    y, x = (r.shape[0] - height) // 2, (r.shape[1] - width) // 2
    return r[y: y + height, x: x + width]
