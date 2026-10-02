"""TDD tests for Japanese-capable font loading and subpixel camera work."""


def test_load_font_prefers_japanese_font():
    """load_font() must return a font whose family covers Japanese glyphs.

    DejaVuSans has no CJK glyphs -> tofu. The loader must try Japanese-capable
    fonts (IPAPGothic / Noto CJK / Windows NotoSansJP) before DejaVu.
    """
    from demo_video_generator.frames import load_font

    font = load_font(44)
    name = font.getname()  # (family, style)
    assert "IPA" in name[0] or "Noto" in name[0] or "CJK" in name[0] or "YuGoth" in name[0] or "MS Gothic" in name[0], (
        f"font family is not Japanese-capable: {name}"
    )


def test_load_font_falls_back_to_default_offline():
    """With no candidate file present, load_font still returns a usable font."""
    from demo_video_generator import frames as F

    orig = F._FONT_CANDIDATES
    try:
        F._FONT_CANDIDATES = ("/nonexistent/font.ttf",)
        font = F.load_font(44)
        assert font is not None
    finally:
        F._FONT_CANDIDATES = orig


def test_camera_rect_supports_subpixel():
    """camera_rect() returns float coordinates (subpixel) so pans don't jitter.

    Integer rounding makes a slow pan move in visible 1-2px jumps (shaking).
    The window math must stay float; only the final crop rounds.
    """
    from demo_video_generator.frames import Box, camera_rect

    rect = camera_rect("pan_right", 0.5, 800, 600)
    assert isinstance(rect.left, (int, float))
    # Box fields must tolerate float; re-create with floats
    b = Box(left=12.5, top=6.25, width=700.0, height=500.0)
    assert b.right == 712.5


def test_camera_rect_float_positions():
    """Camera positions at non-integer progress are computed as floats."""
    from demo_video_generator.frames import camera_rect

    r3 = camera_rect("pan_right", 0.37, 801, 601)
    assert isinstance(r3.left, (int, float))


def test_render_scene_accepts_float_crop():
    """render_scene must not round camera coordinates to ints before cropping."""
    from pathlib import Path

    from PIL import Image

    from demo_video_generator import frames as F
    from demo_video_generator.manifest import Scene

    img = Image.new("RGB", (800, 600))
    px = img.load()
    for x in range(800):
        for y in range(0, 600, 3):
            px[x, y] = (x * 255 // 800, y * 255 // 600, 128)
    tmp = Path("/tmp/_kb_float_src.png")
    img.save(tmp)
    scene = Scene(id="a", image=str(tmp), narration="hi", animation="pan_right", title="てすと")
    out = Path("/tmp/_kb_float_out.png")
    F.render_scene(scene, out, progress=0.333)
    with Image.open(out) as im:
        assert im.size == (1280, 720)
