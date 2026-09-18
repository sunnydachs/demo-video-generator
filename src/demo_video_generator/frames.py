"""Pillow frame rendering: letterbox image + title band.

Each scene is rendered as a 1280x720 RGB frame with the reference app
screenshot letterboxed to fit, an optional bottom title band, and the
narration duration mapped onto an ffmpeg frame sequence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import (
    BG_COLOR,
    HEIGHT,
    TITLE_BAND_COLOR,
    TITLE_BAND_HEIGHT,
    TITLE_COLOR,
    TITLE_FONT_SIZE,
    WIDTH,
)
from .manifest import Scene


def frame_count(duration_sec: float, fps: int) -> int:
    """Number of frames covering ``duration_sec`` at ``fps`` (ceil)."""
    return int(math.ceil(max(0.0, duration_sec) * fps))  # noqa: RUF046 - keep int for clarity


@dataclass
class Box:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width


def _scale(sw: float, sh: float, tw: float, th: float) -> tuple[int, int, int, int]:
    scale = min(tw / sw, th / sh)
    w = int(sw * scale)
    h = int(sh * scale)
    x = int((tw - w) // 2)
    y = int((th - h) // 2)
    return x, y, w, h


def letterbox_draw(img_w: int, img_h: int, canvas_w: int = WIDTH, canvas_h: int = HEIGHT) -> Box:
    """Box describing where ``img_w x img_h`` lands on the canvas (letterboxed)."""
    x, y, w, h = _scale(img_w, img_h, canvas_w, canvas_h)
    return Box(left=x, top=y, width=w, height=h)


def load_font(size: int = TITLE_FONT_SIZE):
    """Load a TrueType font if available, else Pillow's default font (offline-safe)."""
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size=size)
        except OSError:
            continue
    try:
        # Pillow >= 10 supports a scalable default font.
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_scene(
    scene: Scene,
    out_path: str | Path,
    *,
    width: int = WIDTH,
    height: int = HEIGHT,
    title_font_size: int = TITLE_FONT_SIZE,
) -> Path:
    """Render one scene (image letterboxed + optional title band) to ``out_path``."""
    canvas = Image.new("RGB", (width, height), BG_COLOR)

    src_img = Image.open(scene.image)
    src_img = src_img.convert("RGB")
    content_h = height - (TITLE_BAND_HEIGHT if scene.title else 0)
    x, y, w, h = _scale(*src_img.size, width, content_h)
    src_img = src_img.resize((w, h), Image.Resampling.BILINEAR)
    canvas.paste(src_img, (x, y))

    if scene.title:
        band_top = height - TITLE_BAND_HEIGHT
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([0, band_top, width, height], fill=TITLE_BAND_COLOR)
        font = load_font(title_font_size)
        text = str(scene.title)
        # truncate to fit the band
        while text and draw.textlength(text, font=font) > width - 40:
            text = text[:-1]
        draw.text((20, band_top + (TITLE_BAND_HEIGHT - title_font_size) // 2), text, fill=TITLE_COLOR, font=font)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)
    return out


def render_scene_frames(
    scene: Scene,
    out_dir: str | Path,
    *,
    start_frame: int,
    duration: float,
    fps: int = 30,
    width: int = WIDTH,
    height: int = HEIGHT,
) -> int:
    """Write ``frame_%05d.png`` files for this scene's duration.

    Returns the next free frame index (start_frame + nframes).
    Mirrors the scene to one file per frame so ffmpeg gets a 1:1 video track.
    """
    out_dir = Path(out_dir)
    n = frame_count(duration, fps)
    if n == 0:
        return start_frame
    single = render_scene(scene, out_dir / ".scene_single.png", width=width, height=height)
    data = single.read_bytes()
    for i in range(n):
        (out_dir / f"frame_{start_frame + i:05d}.png").write_bytes(data)
    return start_frame + n
