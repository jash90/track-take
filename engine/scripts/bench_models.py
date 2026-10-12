"""Phase 0: measure image generation speed on this Mac for the models already installed in ComfyUI.

Usage: uv run python scripts/bench_models.py <cover.jpg> <out_dir> [--only zimage|qwen]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from sunomv.comfy.client import ComfyClient
from sunomv.comfy.graphs import qwen_edit, zimage

STYLE = (
    "paper cut-out stop-motion animation, layered construction paper, visible paper texture and soft shadows "
    "between layers, cold teal and blue palette with a purple light accent, dark moody night, rain on the window"
)
SCENE = "a white wool coat hanging by an old wooden door in a dim hallway, a lonely woman's silhouette in the doorway"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("cover")
    p.add_argument("out")
    p.add_argument("--only", choices=["zimage", "qwen"])
    args = p.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    c = ComfyClient()
    cover = c.upload_image(args.cover, "sunomv_cover.jpg")
    runs: list[tuple[str, dict]] = []
    if args.only in (None, "zimage"):
        runs += [
            ("zimage_t2i_cold", zimage(f"{SCENE}. {STYLE}", seed=1)),
            ("zimage_t2i_warm", zimage(f"{SCENE}. {STYLE}", seed=2)),
            ("zimage_i2i_cover_d055", zimage(f"{SCENE}. {STYLE}", seed=3, init_image=cover, denoise=0.55)),
            ("zimage_t2i_768", zimage(f"{SCENE}. {STYLE}", seed=4, width=768, height=768)),
        ]
    if args.only in (None, "qwen"):
        prompt = f"Using the style, palette and mood of the reference image, create a new scene: {SCENE}. {STYLE}"
        runs += [
            ("qwen_ref_cover_25", qwen_edit(prompt, [cover], seed=5)),
            ("qwen_ref_cover_12", qwen_edit(prompt, [cover], seed=6, steps=12)),
        ]

    report = {}
    for name, graph in runs:
        r = c.run(graph)
        (out / f"{name}.png").write_bytes(r.images[0])
        report[name] = round(r.seconds, 1)
        print(f"{name}: {r.seconds:.1f}s", flush=True)
    (out / "timings.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
