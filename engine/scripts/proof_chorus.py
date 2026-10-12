"""Phase 0 proof: build-up + first chorus of "Where the Silence Hurts" as paper cut-out stop-motion, 16:9 and 9:16.

Usage: uv run python scripts/proof_chorus.py <fixture_dir> <work_dir>
The shot list is hand-written here; in the product the director (LLM) writes it from lyrics, sections and style.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from tracktake.assets import AssetLibrary, AssetSpec
from tracktake.comfy.client import ComfyClient
from tracktake.models import Analysis
from tracktake.render.compositor import LANDSCAPE, PORTRAIT, Camera, Layer, Shot, to_rgba
from tracktake.render.timeline import render
from tracktake.timegrid import frame_at, nearest

FPS = 24
STYLE = (
    "paper cut-out stop-motion animation, layered construction paper, visible paper texture and soft shadows "
    "between layers, cold teal and blue palette with a purple light accent, dark moody night"
)
HEROINE = (
    "a young woman with a short black bob haircut and pale face, wearing a long charcoal grey knitted cardigan "
    "over a dark navy dress and black boots"
)
CUTOUT = (
    "full body from head to boots, centered, isolated on a plain flat light grey background, "
    "paper cut-out puppet made of layered construction paper, visible paper texture, soft even lighting"
)


def bg(id_: str, scene: str, seed: int) -> AssetSpec:
    return AssetSpec(id_, "background", f"{scene}, empty room, no people. {STYLE}", seed)


def pose(id_: str, action: str, seed: int) -> AssetSpec:
    return AssetSpec(id_, "cutout", f"{HEROINE}, {action}. {CUTOUT}. {STYLE}", seed)


ASSETS = {
    "room": bg("room", "a small dark apartment living room with a big window, rain streaking down the glass, "
               "a single dim floor lamp", 11),
    "dance": bg("dance", "a bare wooden-floored room with an old record player on a low cabinet, moonlight "
                "through the window, dust floating in the light, nobody in the room", 12),
    "street": bg("street", "a narrow wet street at night lit by a single purple street lamp, long shadows "
                 "on the cobblestones", 13),
    "kitchen": bg("kitchen", "a cold kitchen table with two empty white coffee cups, rain on the window behind", 14),
    "hallway": bg("hallway", "a white wool coat hanging on a hook by an old wooden front door in a dim hallway", 15),
    "standing": pose("standing", "standing still with her head down and arms hanging", 21),
    "dancing": pose("dancing", "slowly dancing alone with her arms wrapped around herself, eyes closed", 22),
    "reaching": pose("reaching", "reaching one arm forward into the darkness, in profile", 23),
    "hands": pose("hands", "looking down at her open empty hands", 24),
    "kneeling": pose("kneeling", "kneeling on the floor, curled forward, falling apart", 25),
    "heart": pose("heart", "standing with one hand pressed over her heart, looking up", 26),
}

# (start downbeat time, background, pose or None, camera from, camera to, cadence)
SHOTS = [
    (47.06, "cover", None, Camera((0.5, 0.5), 1.0), Camera((0.5, 0.52), 1.6), 2),
    (50.00, "room", "standing", Camera((0.5, 0.5), 1.05), Camera((0.52, 0.52), 1.2), 2),
    (52.92, "dance", "dancing", Camera((0.45, 0.5), 1.1), Camera((0.55, 0.5), 1.15), 2),
    (55.84, "street", "reaching", Camera((0.5, 0.55), 1.25), Camera((0.5, 0.5), 1.05), 2),
    (58.78, "kitchen", "hands", Camera((0.5, 0.5), 1.0), Camera((0.5, 0.55), 1.25), 2),
    (61.70, "hallway", "standing", Camera((0.55, 0.5), 1.15), Camera((0.45, 0.5), 1.15), 2),
    (64.62, "dance", "kneeling", Camera((0.5, 0.5), 1.3), Camera((0.5, 0.55), 1.05), 2),
    (67.56, "street", "reaching", Camera((0.45, 0.5), 1.05), Camera((0.55, 0.5), 1.2), 2),
    (70.48, "room", "heart", Camera((0.5, 0.55), 1.0), Camera((0.5, 0.45), 1.3), 2),
    (73.40, "hallway", None, Camera((0.5, 0.5), 1.0), Camera((0.48, 0.45), 1.35), 3),
]
END = 76.34
POSE_LAYOUT = {  # width in master units, centre x, feet y; sized to fit the 16:9 view (0.56 units tall)
    "standing": (0.15, 0.62, 0.86), "dancing": (0.18, 0.5, 0.86), "reaching": (0.25, 0.42, 0.86),
    "hands": (0.16, 0.6, 0.87), "kneeling": (0.22, 0.5, 0.88), "heart": (0.15, 0.4, 0.86),
}


def puppet(img: np.ndarray, name: str) -> Layer:
    width, x, feet = POSE_LAYOUT[name]
    height = width * img.shape[0] / img.shape[1]
    return Layer([img], center=(x, feet - height / 2), width=width, parallax=1.0, bounce=0.008, jitter=0.0035)


def main() -> None:
    fixture, work = Path(sys.argv[1]), Path(sys.argv[2])
    analysis = Analysis.model_validate_json((work / "analysis.json").read_text())
    lib = AssetLibrary(work / "assets", ComfyClient())
    report: dict = {"assets": {}, "render": []}
    for spec in ASSETS.values():
        _path, seconds = lib.ensure(spec)
        report["assets"][spec.id] = round(seconds, 1)
        print(f"asset {spec.id}: {seconds:.0f}s", flush=True)

    cover = cv2.cvtColor(cv2.imread(str(fixture / "cover.jpeg")), cv2.COLOR_BGR2RGB)
    cover = to_rgba(cv2.resize(cover, (1024, 1024), interpolation=cv2.INTER_LANCZOS4))
    shots, cadence = [], []
    for i, (t, bg_id, pose_id, cam_a, cam_b, cad) in enumerate(SHOTS):
        t_end = SHOTS[i + 1][0] if i + 1 < len(SHOTS) else END
        start, end = frame_at(nearest(analysis.downbeats, t), FPS), frame_at(nearest(analysis.downbeats, t_end), FPS)
        back = cover if bg_id == "cover" else lib.load(ASSETS[bg_id])
        layers = [Layer([back], width=1.0, parallax=0.55, jitter=0.0015)]
        focus = (0.5, 0.5)
        if pose_id:
            layers.append(puppet(lib.load(ASSETS[pose_id]), pose_id))
            focus = layers[-1].center
        shots.append(Shot(start, end, layers, cam_a, cam_b, focus=focus, seed=100 + i))
        cadence.append(cad)

    out = work / "proof"
    out.mkdir(exist_ok=True)
    t0, t1 = SHOTS[0][0], END
    for fmt in (LANDSCAPE, PORTRAIT):
        r = render(shots, cadence, analysis, fmt, out / f"proof_{fmt.name}.mp4", fps=FPS, t0=t0, t1=t1,
                   audio=fixture / "song.mp3")
        report["render"].append(r)
        print(r, flush=True)
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (out / "report.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
