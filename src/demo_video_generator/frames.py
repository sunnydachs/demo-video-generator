"""Pillow frame rendering: letterbox image + title band + camera work.

Each scene is rendered as a 1280x720 RGB frame with the reference app
screenshot letterboxed to fit, an optional bottom title band, and the
narration duration mapped onto an ffmpeg frame sequence. A scene-level
``animation`` mode moves a camera window over the still image (Ken Burns)
so the frame sequence gains zoom/pan motion while staying deterministic.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import (
    ANIMATION_MODES,
    ANIMATION_STATIC,
    BG_COLOR,
    HEIGHT,
    TITLE_BAND_COLOR,
    TITLE_BAND_HEIGHT,
    TITLE_COLOR,
    TITLE_FONT_SIZE,
    WIDTH,
)
from .manifest import Scene

# Camera-work tunables (Ken Burns): magnitudes are frame-progress fractions.
# Gentle speeds by design -- strong zoom/sway reads as unnatural motion.
ZOOM_MAG = 0.12  # zoom_in/zoom_out: window scales by up to 1 + ZOOM_MAG
PAN_MAG = 0.10  # pan_*: constant zoom > 1 creates the travel margin

# Font candidates in priority order. Japanese-capable fonts FIRST: DejaVu has
# no CJK glyphs and renders titles as tofu. Falls back to Pillow's default
# (headless CI without fonts) which is acceptable for non-CJK text.
_FONT_CANDIDATES = (
    # Linux (apt install fonts-ipafont-gothic / fonts-noto-cjk)
    "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf",
    "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
    # Windows drives mounted under WSL
    "/mnt/c/Windows/Fonts/NotoSansJP-VF.ttf",
    "/mnt/c/Windows/Fonts/YuGothR.ttc",
    "/mnt/c/Windows/Fonts/msgothic.ttc",
    # Classic Linux names
    "DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
)


def frame_count(duration_sec: float, fps: int) -> int:
    """Number of frames covering ``duration_sec`` at ``fps`` (ceil)."""
    return int(math.ceil(max(0.0, duration_sec) * fps))  # noqa: RUF046 - keep int for clarity


def camera_scale(mode: str) -> float:
    """Peak camera zoom for ``mode`` (1.0 = no zoom; pans keep it constant)."""
    if mode == ANIMATION_STATIC:
        return 1.0
    if mode in ("pan_left", "pan_right", "pan_up", "pan_down"):
        return 1.0 + PAN_MAG
    if mode in ("zoom_in", "zoom_out"):
        return 1.0 + ZOOM_MAG
    raise ValueError(f"unknown animation mode: {mode}")


@dataclass
class Box:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width


def camera_rect(mode: str, t: float, content_w: int, content_h: int) -> Box:
    """Camera window over the content image at progress ``t`` in [0, 1].

    Pure math, offline-testable. ``static`` returns the full content box;
    zooms interpolate the window size toward/away from the center; pans keep
    a constant (zoomed) window and travel across the free axis margin.
    Coordinates stay FLOAT (subpixel): integer rounding makes slow camera
    moves jitter in visible 1-2px steps.
    """
    if mode not in ANIMATION_MODES:
        raise ValueError(f"unknown animation mode: {mode}")
    t = min(max(float(t), 0.0), 1.0)
    if mode == ANIMATION_STATIC:
        return Box(left=0.0, top=0.0, width=float(content_w), height=float(content_h))

    peak = camera_scale(mode)
    if mode == "zoom_in":
        scale = 1.0 + (peak - 1.0) * t
    elif mode == "zoom_out":
        scale = peak - (peak - 1.0) * t
    else:  # pans: constant zoom
        scale = peak

    w = max(1.0, content_w / scale)
    h = max(1.0, content_h / scale)
    free_w = content_w - w
    free_h = content_h - h

    if mode == "zoom_in" or mode == "zoom_out":
        left = free_w / 2
        top = free_h / 2
    elif mode == "pan_left":
        left, top = free_w * (1.0 - t), free_h / 2
    elif mode == "pan_right":
        left, top = free_w * t, free_h / 2
    elif mode == "pan_up":
        left, top = free_w / 2, free_h * (1.0 - t)
    else:  # pan_down
        left, top = free_w / 2, free_h * t
    return Box(left=left, top=top, width=w, height=h)


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
    """Load a Japanese-capable TrueType font if available, else Pillow's default.

    Tries each candidate path in order (CJK fonts first -- DejaVu renders
    Japanese titles as tofu). Offline-safe: falls back to Pillow's default
    font on hosts with no fonts installed (e.g. minimal CI).
    """
    for path in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
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
    progress: float = 0.0,
) -> Path:
    """Render one scene (image letterboxed + optional title band) to ``out_path``.

    ``progress`` in [0, 1] drives the scene's camera work (Ken Burns); the
    default 0.0 with ``animation: static`` reproduces the classic still frame.
    """
    canvas = Image.new("RGB", (width, height), BG_COLOR)

    src_img = Image.open(scene.image)
    src_img = src_img.convert("RGB")
    content_h = height - (TITLE_BAND_HEIGHT if scene.title else 0)
    x, y, w, h = _scale(*src_img.size, width, content_h)
    if scene.animation != ANIMATION_STATIC:
        # Camera window in SOURCE coordinates (float/subpixel: rounding here
        # is what made pans jitter). Pillow crop accepts a float box and does
        # the subpixel resample in one pass via transform+resize.
        cam = camera_rect(scene.animation, progress, src_img.width, src_img.height)
        crop = src_img.crop(
            (cam.left, cam.top, cam.left + cam.width, cam.top + cam.height)
        )
        crop = crop.resize((w, h), Image.Resampling.LANCZOS)
        canvas.paste(crop, (x, y))
    else:
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
    if scene.animation == ANIMATION_STATIC:
        # Static fast path: one render, byte-copied per frame (deterministic).
        single = render_scene(scene, out_dir / ".scene_single.png", width=width, height=height)
        data = single.read_bytes()
        for i in range(n):
            (out_dir / f"frame_{start_frame + i:05d}.png").write_bytes(data)
        return start_frame + n
    for i in range(n):
        progress = i / n if n > 1 else 0.0
        render_scene(
            scene,
            out_dir / f"frame_{start_frame + i:05d}.png",
            width=width,
            height=height,
            progress=progress,
        )
    return start_frame + n
