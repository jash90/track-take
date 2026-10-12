"""Karaoke captions drawn per frame: the current lyric line, with already-sung words highlighted.

Layout per format: 16:9 bottom centre; 9:16 above the bottom ~22% and away from the right edge, where
TikTok / Reels / Shorts put their buttons.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from tracktake.models import LyricLine
from tracktake.render.compositor import Format

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux (Vast): fonts-dejavu-core, covers Polish
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


@lru_cache(maxsize=8)
def _font(size: int) -> ImageFont.FreeTypeFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


@dataclass(frozen=True)
class CaptionStyle:
    sung: tuple[int, int, int] = (255, 255, 255)
    unsung: tuple[int, int, int] = (150, 170, 185)
    outline: tuple[int, int, int] = (0, 0, 0)


def _layout(fmt: Format) -> tuple[int, float, float, float]:
    """Font size, centre x (0..1), baseline y (0..1) and max text width (0..1) for a format."""
    if fmt.width >= fmt.height:
        return round(fmt.height * 0.052), 0.5, 0.88, 0.8
    return round(fmt.width * 0.062), 0.46, 0.70, 0.78


def _wrap(words: list[str], font: ImageFont.FreeTypeFont, max_px: float) -> list[list[int]]:
    rows: list[list[int]] = [[]]
    for i, w in enumerate(words):
        trial = " ".join(words[j] for j in rows[-1] + [i])
        if rows[-1] and font.getlength(trial) > max_px:
            rows.append([i])
        else:
            rows[-1].append(i)
    return rows


def line_at(lines: list[LyricLine], t: float, lead: float = 0.15, tail: float = 0.6) -> LyricLine | None:
    """The line to show at time `t`: shown slightly before it starts and briefly after it ends."""
    for line in lines:
        if line.start - lead <= t <= line.end + tail:
            return line
    return None


def render_caption(line: LyricLine, t: float, fmt: Format, style: CaptionStyle | None = None) -> np.ndarray:
    """Transparent RGBA overlay (fmt size) with `line`, highlighting words whose start time has passed."""
    style = style or CaptionStyle()
    size, cx, base_y, max_w = _layout(fmt)
    font = _font(size)
    words = [w.text for w in line.words] or line.text.split()
    sung = [w.start <= t for w in line.words] if line.words else [line.start <= t] * len(words)
    rows = _wrap(words, font, max_w * fmt.width)
    img = Image.new("RGBA", (fmt.width, fmt.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    space = font.getlength(" ")
    line_h = round(size * 1.25)
    y = round(base_y * fmt.height) - line_h * (len(rows) - 1)
    for row in rows:
        row_w = sum(font.getlength(words[i]) for i in row) + space * (len(row) - 1)
        x = cx * fmt.width - row_w / 2
        for i in row:
            color = style.sung if sung[i] else style.unsung
            draw.text((x, y), words[i], font=font, fill=color + (255,), anchor="ls",
                      stroke_width=max(2, size // 14), stroke_fill=style.outline + (230,))
            x += font.getlength(words[i]) + space
        y += line_h
    return np.asarray(img)


def overlay(frame: np.ndarray, rgba: np.ndarray) -> np.ndarray:
    alpha = rgba[:, :, 3:4].astype(np.float32) / 255.0
    out = frame.astype(np.float32) * (1 - alpha) + rgba[:, :, :3].astype(np.float32) * alpha
    return out.astype(np.uint8)
