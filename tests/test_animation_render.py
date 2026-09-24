"""TDD tests for Ken Burns / camera-work rendering in frames.py."""
import pytest
from PIL import Image

from demo_video_generator.frames import camera_rect, camera_scale, render_scene_frames
from demo_video_generator.manifest import Scene


def _make_image(path, w=800, h=600):
    img = Image.new("RGB", (w, h), (200, 30, 30))
    img.save(path)


def _make_gradient(path, w=800, h=600):
    """Non-uniform image: a solid color cannot show camera movement."""
    img = Image.new("RGB", (w, h))
    for x in range(w):
        for y in range(0, h, 4):
            img.putpixel((x, y), (x * 255 // w, y * 255 // h, 128))
    img.save(path)


# --- camera_rect: pure camera-window math (content coordinates) -----------------


def test_camera_rect_static_is_identity():
    rect = camera_rect("static", 0.5, 800, 600)
    assert (rect.left, rect.top, rect.width, rect.height) == (0, 0, 800, 600)


def test_camera_rect_zoom_in_shrinks_toward_center():
    start = camera_rect("zoom_in", 0.0, 800, 600)
    end = camera_rect("zoom_in", 1.0, 800, 600)
    assert end.width < start.width
    assert end.height < start.height
    # centered
    assert end.left == pytest.approx((800 - end.width) / 2, abs=1)
    assert end.top == pytest.approx((600 - end.height) / 2, abs=1)


def test_camera_rect_zoom_out_grows():
    start = camera_rect("zoom_out", 0.0, 800, 600)
    end = camera_rect("zoom_out", 1.0, 800, 600)
    assert end.width > start.width


def test_camera_rect_pan_left_moves_window_left():
    start = camera_rect("pan_left", 0.0, 800, 600)
    end = camera_rect("pan_left", 1.0, 800, 600)
    assert end.left < start.left
    # constant zoom: window size unchanged
    assert end.width == start.width


def test_camera_rect_pan_right_moves_window_right():
    start = camera_rect("pan_right", 0.0, 800, 600)
    end = camera_rect("pan_right", 1.0, 800, 600)
    assert end.left > start.left


def test_camera_rect_pan_up_moves_window_up():
    start = camera_rect("pan_up", 0.0, 800, 600)
    end = camera_rect("pan_up", 1.0, 800, 600)
    assert end.top < start.top
    assert end.height == start.height


def test_camera_rect_pan_down_moves_window_down():
    start = camera_rect("pan_down", 0.0, 800, 600)
    end = camera_rect("pan_down", 1.0, 800, 600)
    assert end.top > start.top


def test_camera_rect_invalid_mode_raises():
    with pytest.raises(ValueError):
        camera_rect("wiggle_360", 0.5, 800, 600)


def test_camera_rect_pan_has_travel_headroom():
    # pan travel must be non-zero: window is strictly smaller than content
    rect = camera_rect("pan_left", 0.0, 800, 600)
    assert rect.width < 800


def test_camera_scale_pan_uses_zoom_headroom():
    assert camera_scale("static") == 1.0
    assert camera_scale("pan_left") > 1.0
    assert camera_scale("zoom_in") > 1.0


# --- frame sequence: animated frames differ, static frames don't -----------------


def test_render_scene_frames_animation_produces_distinct_frames(tmp_path):
    img = tmp_path / "i.png"
    _make_gradient(img)
    scene = Scene(id="a", image=str(img), narration="hello", animation="zoom_in")
    tick = render_scene_frames(scene, tmp_path, start_frame=1, duration=0.2, fps=30)
    assert tick == 7  # 6 frames
    first = (tmp_path / "frame_00001.png").read_bytes()
    last = (tmp_path / "frame_00006.png").read_bytes()
    assert first != last


def test_render_scene_frames_static_produces_identical_frames(tmp_path):
    img = tmp_path / "i.png"
    _make_image(img)
    scene = Scene(id="a", image=str(img), narration="hello")
    tick = render_scene_frames(scene, tmp_path, start_frame=1, duration=0.2, fps=30)
    assert tick == 7
    first = (tmp_path / "frame_00001.png").read_bytes()
    last = (tmp_path / "frame_00006.png").read_bytes()
    assert first == last


def test_render_scene_frames_animation_dimensions(tmp_path):
    img = tmp_path / "i.png"
    _make_image(img)
    scene = Scene(id="a", image=str(img), narration="hello", title="Demo", animation="pan_right")
    render_scene_frames(scene, tmp_path, start_frame=1, duration=0.1, fps=10)
    with Image.open(tmp_path / "frame_00001.png") as im:
        assert im.size == (1280, 720)
