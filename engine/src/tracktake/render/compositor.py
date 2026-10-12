"""2.5D cut-out compositor: layers on a square master canvas, filmed by a stop-motion camera per output format.

Coordinates are in master units: the square canvas spans 0..1 on both axes. A format's viewport at zoom 1 is the
largest crop of that aspect ratio (16:9 -> full width, 9:16 -> full height).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Layer:
    drawings: list[np.ndarray]  # RGBA uint8; the drawing changes (cycles) on every new stop-motion drawing
    center: tuple[float, float] = (0.5, 0.5)
    width: float = 1.0  # layer width in master units
    parallax: float = 1.0  # 1 = moves with the world, < 1 = farther away, drifts less when the camera pans
    bounce: float = 0.0  # hop height (master units) at full beat pulse
    jitter: float = 0.0  # boil: random offset per drawing (master units); rotation scales with it


@dataclass
class Camera:
    center: tuple[float, float] = (0.5, 0.5)
    zoom: float = 1.0


@dataclass
class Shot:
    start_frame: int
    end_frame: int
    layers: list[Layer]  # back to front
    cam_from: Camera = field(default_factory=Camera)
    cam_to: Camera = field(default_factory=Camera)
    focus: tuple[float, float] = (0.5, 0.5)  # where the subject is; narrow formats centre on it
    seed: int = 0
    whip_in: int = 0  # frames of a whip pan arriving at the start (the picture slides in from the right, blurred)
    whip_out: int = 0  # frames of a whip pan leaving at the end (the picture slides out to the left)


@dataclass(frozen=True)
class Format:
    name: str
    width: int
    height: int

    @property
    def view(self) -> tuple[float, float]:
        """Viewport size in master units at zoom 1."""
        a = self.width / self.height
        return (1.0, 1.0 / a) if a >= 1 else (a, 1.0)


LANDSCAPE = Format("16x9", 1920, 1080)
PORTRAIT = Format("9x16", 1080, 1920)


def _smoothstep(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def camera_at(shot: Shot, fmt: Format, frame: int, kick: float, snare: float, rng: random.Random) -> tuple[float, float, float]:
    """Camera centre x, y and zoom for `frame`, including beat pulses, clamped inside the master canvas."""
    span = max(shot.end_frame - shot.start_frame - 1, 1)
    u = _smoothstep((frame - shot.start_frame) / span)
    a, b = shot.cam_from, shot.cam_to
    zoom = (a.zoom + (b.zoom - a.zoom) * u) * (1.0 + 0.035 * kick)
    cx = a.center[0] + (b.center[0] - a.center[0]) * u
    cy = a.center[1] + (b.center[1] - a.center[1]) * u
    vw, vh = fmt.view
    # narrow formats lean towards the subject so it stays in frame
    if vw < 1.0:
        cx += (shot.focus[0] - 0.5) * (1.0 - vw)
    if vh < 1.0:
        cy += (shot.focus[1] - 0.5) * (1.0 - vh)
    shake = 0.006 * snare
    cx += rng.uniform(-shake, shake)
    cy += rng.uniform(-shake, shake)
    hw, hh = vw / zoom / 2, vh / zoom / 2
    cx = min(max(cx, hw), 1.0 - hw)
    cy = min(max(cy, hh), 1.0 - hh)
    return cx, cy, zoom


def _place(canvas: np.ndarray, img: np.ndarray, m: np.ndarray) -> None:
    """Warp RGBA `img` by affine `m` onto float RGB `canvas` with alpha blending (in place)."""
    h, w = canvas.shape[:2]
    warped = cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    alpha = warped[:, :, 3:4].astype(np.float32) / 255.0
    canvas *= 1.0 - alpha
    canvas += warped[:, :, :3].astype(np.float32) * alpha


def compose(
    shot: Shot,
    fmt: Format,
    frame: int,
    drawing_index: int,
    kick: float = 0.0,
    snare: float = 0.0,
    beat: float = 0.0,
) -> np.ndarray:
    """Render one RGB uint8 frame of `shot` in `fmt`, as it looks for drawing number `drawing_index`."""
    rng = random.Random(shot.seed * 1_000_003 + drawing_index)  # same shake in every format
    cx, cy, zoom = camera_at(shot, fmt, frame, kick, snare, rng)
    ref = shot.cam_from.center
    vw, vh = fmt.view
    px_per_unit = fmt.width / (vw / zoom)
    left, top = cx - vw / zoom / 2, cy - vh / zoom / 2
    canvas = np.zeros((fmt.height, fmt.width, 3), np.float32)
    for li, layer in enumerate(shot.layers):
        img = layer.drawings[drawing_index % len(layer.drawings)]
        ih, iw = img.shape[:2]
        lrng = random.Random((shot.seed * 1_000_003 + drawing_index) * 101 + li)
        jx = lrng.uniform(-layer.jitter, layer.jitter)
        jy = lrng.uniform(-layer.jitter, layer.jitter)
        rot = lrng.uniform(-1, 1) * layer.jitter * 40.0  # degrees; 0.004 jitter -> ~0.16 deg
        # far layers follow the camera partly, so they appear to move less when it pans
        lx = layer.center[0] + (1.0 - layer.parallax) * (cx - ref[0]) + jx
        ly = layer.center[1] + (1.0 - layer.parallax) * (cy - ref[1]) + jy - layer.bounce * beat
        scale = layer.width / iw * px_per_unit  # source px -> output px
        ox, oy = (lx - left) * px_per_unit, (ly - top) * px_per_unit
        m = cv2.getRotationMatrix2D((iw / 2, ih / 2), rot, scale)
        m[0, 2] += ox - iw / 2
        m[1, 2] += oy - ih / 2
        _place(canvas, img, m)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def whip(frame: np.ndarray, shot: Shot, f: int, reach: float = 0.35, smear: float = 0.22) -> np.ndarray:
    """Whip-pan transition: around a cut the camera swings sideways so fast the picture smears. Shot A slides out to
    the left, shot B slides in from the right, each within its own frames, so the cut sits in the blur."""
    k, sign = 0.0, 1.0
    if shot.whip_in and f < shot.start_frame + shot.whip_in:
        k = (shot.start_frame + shot.whip_in - f) / (shot.whip_in + 1)
    elif shot.whip_out and f >= shot.end_frame - shot.whip_out:
        k, sign = (f - (shot.end_frame - shot.whip_out) + 1) / (shot.whip_out + 1), -1.0
    if k <= 0:
        return frame
    e = k * k  # eases: slow at the shot's side, fastest at the cut
    h, w = frame.shape[:2]
    m = np.float32([[1, 0, sign * e * w * reach], [0, 1, 0]])
    moved = cv2.warpAffine(frame, m, (w, h), borderMode=cv2.BORDER_REFLECT)
    length = int(e * w * smear)
    return cv2.blur(moved, (length, 1)) if length > 1 else moved


def to_rgba(img: np.ndarray) -> np.ndarray:
    """RGB(A) uint8 -> RGBA uint8."""
    if img.shape[2] == 4:
        return img
    return np.dstack([img, np.full(img.shape[:2], 255, np.uint8)])

