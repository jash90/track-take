"""Phase 0b: the same build-up + first chorus, but every shot is animated with LTX-2.3 image-to-video (MLX).

Keyframes are the composed cut-out scenes from proof_chorus.py; LTX animates them from the lyric line's action,
generated at 12 fps so each generated frame is held for two output frames (stop-motion "on twos"), and the renderer
locks drawing changes to beats and adds the beat pump, captions and audio.

Usage: uv run python scripts/proof_chorus_i2v.py <fixture_dir> <work_dir> [--backend local|vast] [--hd]
  local = LTX-2.3 on this Mac (MLX); vast = Wan 2.2 14B in ComfyUI on the rented GPU (`tracktake vast up --yes` first)
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import cv2

from tracktake import config
from tracktake.assets import AssetLibrary
from tracktake.ltx import ClipSpec, fit_cover
from tracktake.models import Analysis
from tracktake.render.compositor import LANDSCAPE, PORTRAIT, Camera, Format, Layer, Shot, compose, to_rgba
from tracktake.render.stepping import drawing_frames
from tracktake.render.timeline import render
from tracktake.timegrid import frame_at, frames_of, nearest
from tracktake.video import backend_for

FPS = 24
SUFFIX = ("Stop-motion paper cut-out animation, layered construction paper, visible paper texture, "
          "slow gentle camera push-in.")
ACTIONS = [  # one per shot of proof_chorus.SHOTS; None = keep the cut-out camera move (cover intro)
    None,
    "She slowly lifts her head and looks toward the rainy window, rain streaks run down the glass, the lamp light flickers softly.",
    "She slowly dances alone, arms wrapped around herself, swaying and turning gently, dust floating in the moonlight.",
    "She slowly reaches her arm forward into the darkness under the purple street lamp, her cardigan flutters in the wind.",
    "She looks down at her open empty hands and slowly closes them, rain runs down the kitchen window.",
    "She turns her head toward the white coat hanging by the door and lowers her gaze sadly.",
    "She sinks down to her knees and curls forward, her shoulders trembling, dust drifting in the moonlight.",
    "She takes a step forward and stretches her hand toward the purple light, then lets it fall.",
    "She presses her hand to her heart and looks up as rain streams down the window, her hair moves slightly.",
    "The white coat sways gently on its hook, shadows slide across the wooden door, light flickers.",
]


def load_proof():
    spec = importlib.util.spec_from_file_location("proof_chorus", Path(__file__).with_name("proof_chorus.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def video_shot(frames, fmt: Format, start: int, end: int, seed: int) -> Shot:
    """A full-frame layer whose drawings are the clip's frames, sampled at each stop-motion drawing's time."""
    vw, vh = fmt.view
    h, w = frames[0].shape[:2]
    width = max(vw, vh * w / h)  # cover the viewport
    return Shot(start, end, [Layer(frames, center=(0.5, 0.5), width=width, parallax=1.0)],
                Camera((0.5, 0.5), 1.0), Camera((0.5, 0.5), 1.04), focus=(0.5, 0.5), seed=seed)


def main() -> None:
    fixture, work = Path(sys.argv[1]), Path(sys.argv[2])
    settings = config.load()
    if "--backend" in sys.argv:
        settings.comfy.backend = sys.argv[sys.argv.index("--backend") + 1]
    backend = backend_for(settings, hd="--hd" in sys.argv)
    prof = backend.profile
    print(f"backend {settings.comfy.backend}, engine {backend.name}: {prof}", flush=True)
    p = load_proof()
    analysis = Analysis.model_validate_json((work / "analysis.json").read_text())
    lib = AssetLibrary(work / "assets")
    cover = cv2.cvtColor(cv2.imread(str(fixture / "cover.jpeg")), cv2.COLOR_BGR2RGB)
    cover = to_rgba(cv2.resize(cover, (1024, 1024), interpolation=cv2.INTER_LANCZOS4))
    tag = "" if backend.name == "mlx" else f"_{backend.name}"  # keep the MLX cache paths of earlier runs
    clips_dir, keys_dir = work / "i2v" / f"clips{tag}", work / "i2v" / f"keyframes{tag}"
    keys_dir.mkdir(parents=True, exist_ok=True)
    beat_frames = frames_of(analysis.beats, FPS)
    report: dict = {"clips": {}, "render": []}

    for fmt in (LANDSCAPE, PORTRAIT):
        shots, cadence = [], []
        for i, (t, bg_id, pose_id, cam_a, cam_b, _cad) in enumerate(p.SHOTS):
            t_end = p.SHOTS[i + 1][0] if i + 1 < len(p.SHOTS) else p.END
            start = frame_at(nearest(analysis.downbeats, t), FPS)
            end = frame_at(nearest(analysis.downbeats, t_end), FPS)
            back = cover if bg_id == "cover" else lib.load(p.ASSETS[bg_id])
            layers = [Layer([back], width=1.0, parallax=0.55, jitter=0.0015)]
            focus = (0.5, 0.5)
            if pose_id:
                layers.append(p.puppet(lib.load(p.ASSETS[pose_id]), pose_id))
                focus = layers[-1].center
            cut = Shot(start, end, layers, cam_a, cam_b, focus=focus, seed=100 + i)
            if ACTIONS[i] is None:
                shots.append(cut)
                cadence.append(2)
                continue
            gw, gh = prof.landscape if fmt.width >= fmt.height else prof.portrait
            key = keys_dir / f"{i:02d}_{fmt.name}.png"
            still = compose(cut, fmt, start, 0)
            cv2.imwrite(str(key), cv2.cvtColor(fit_cover(still, gw, gh), cv2.COLOR_RGB2BGR))
            spec = ClipSpec(f"{i:02d}_{fmt.name}", f"{ACTIONS[i]} {SUFFIX}", gw, gh, prof.frames, prof.fps, seed=7 + i)
            frames, seconds = backend.generate(spec, key, clips_dir)
            report["clips"][spec.id] = round(seconds, 1)
            print(f"clip {spec.id}: {seconds:.0f}s", flush=True)
            # one drawing per stop-motion drawing start, taken from the clip at that moment
            plan = drawing_frames(start, end, 2, forced=beat_frames, min_hold=2)
            drawings = [frames[min(round((sf - start) / FPS * prof.fps), len(frames) - 1)] for sf in plan]
            shots.append(video_shot(drawings, fmt, start, end, seed=100 + i))
            cadence.append(2)
        out = work / "i2v"
        r = render(shots, cadence, analysis, fmt, out / f"proof_i2v{tag}_{fmt.name}.mp4", fps=FPS,
                   t0=p.SHOTS[0][0], t1=p.END, audio=fixture / "song.mp3")
        report["render"].append(r)
        print(r, flush=True)
    report["finished"] = time.strftime("%Y-%m-%d %H:%M:%S")
    (work / "i2v" / f"report{tag}.json").write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
