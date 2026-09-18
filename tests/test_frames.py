"""Offline tests for Pillow frame rendering (letterbox + title band)."""
import pytest
from PIL import Image

from demo_video_generator.config import HEIGHT, WIDTH
from demo_video_generator.frames import (
    frame_count,
    letterbox_draw,
    load_font,
    render_scene,
)
from demo_video_generator.manifest import Scene


def _make_image(path, w=800, h=600):
    img = Image.new("RGB", (w, h), (200, 30, 30))
    img.save(path)


def test_frame_count_rounds_up():
    assert frame_count(1.0, 30) == 30
    assert frame_count(1.0 + 1 / 60, 30) == 31
    assert frame_count(0.0, 30) == 0


def test_render_scene_dimensions(tmp_path):
    img = tmp_path / "i.png"
    _make_image(img)
    out = tmp_path / "frame.png"
    scene = Scene(id="a", image=str(img), narration="hello", title="My Demo")
    render_scene(scene, out)
    with Image.open(out) as im:
        assert im.size == (WIDTH, HEIGHT)
        assert im.mode == "RGB"


def test_render_scene_no_title(tmp_path):
    img = tmp_path / "i.png"
    _make_image(img)
    out = tmp_path / "frame.png"
    scene = Scene(id="a", image=str(img), narration="hello")
    render_scene(scene, out)
    assert out.exists()


def test_letterbox_draw_keeps_aspect_ratio():
    # landscape image into portrait-ish container
    draw_rect = letterbox_draw(1620, 1080, WIDTH, HEIGHT)  # 3:2 landscape
    assert draw_rect.width > 0 and draw_rect.height > 0
    ratio = draw_rect.width / draw_rect.height
    assert ratio == pytest.approx(1620 / 1080, rel=1e-2)
    assert draw_rect.left >= 0 and draw_rect.top >= 0
    assert draw_rect.right <= WIDTH


def test_load_font_returns_font():
    font = load_font(40)
    assert font is not None