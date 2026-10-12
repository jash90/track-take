"""Asset library: background plates and character cut-outs, generated once in ComfyUI and reused by many shots.

Like a real cut-out animation, shots are combinations of a background, a puppet pose and a camera move. This keeps
the number of AI images small (a few dozen per song on an M1 Pro) and the character consistent.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image

from tracktake.comfy.client import ComfyClient
from tracktake.comfy.graphs import zimage


@dataclass(frozen=True)
class AssetSpec:
    id: str
    kind: Literal["background", "cutout"]
    prompt: str
    seed: int = 0
    size: int = 1024


class AssetLibrary:
    def __init__(self, root: str | Path, client: ComfyClient | None = None):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.client = client
        self._rembg = None

    def path(self, spec: AssetSpec) -> Path:
        return self.root / f"{spec.id}.png"

    def ensure(self, spec: AssetSpec) -> tuple[Path, float]:
        """Generate the asset unless an image made from the same spec is cached. Returns (path, seconds spent)."""
        out, meta = self.path(spec), self.root / f"{spec.id}.json"
        if out.exists() and meta.exists() and json.loads(meta.read_text()) == asdict(spec):
            return out, 0.0
        if self.client is None:
            raise RuntimeError(f"asset {spec.id} is missing and no ComfyUI client was given")
        result = self.client.run(zimage(spec.prompt, seed=spec.seed, width=spec.size, height=spec.size,
                                        prefix=f"tracktake/assets/{spec.id}"))
        img = Image.open(io.BytesIO(result.images[0])).convert("RGB")
        seconds = result.seconds
        if spec.kind == "cutout":
            img = self._cut(img)
        img.save(out)
        meta.write_text(json.dumps(asdict(spec), indent=2))
        return out, seconds

    def load(self, spec: AssetSpec) -> np.ndarray:
        """RGBA uint8 array; cut-outs are cropped to their opaque bounding box."""
        img = np.asarray(Image.open(self.path(spec)).convert("RGBA"))
        if spec.kind == "cutout":
            ys, xs = np.nonzero(img[:, :, 3] > 8)
            if len(xs):
                img = img[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]
        return img

    def _cut(self, img: Image.Image) -> Image.Image:
        from rembg import new_session, remove  # imported lazily: the model download is ~1 GB on first use

        if self._rembg is None:
            self._rembg = new_session("birefnet-general")
        return remove(img, session=self._rembg)
