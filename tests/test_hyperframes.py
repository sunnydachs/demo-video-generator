"""TDD tests for the export-hyperframes project generator."""
from demo_video_generator import hyperframes as hf
from demo_video_generator.manifest import Scene, SceneTiming


def _scene(**kw):
    base = {"id": "s1", "image": "shots/intro.png", "narration": "こんにちは。", "title": "イントロ", "post_pad_sec": 4.0}
    base.update(kw)
    return Scene(**base)


def _timing(id, start, end, narr):
    return SceneTiming(id=id, narration="", subtitle="", start=start, end=end, narration_duration=narr)


# --- pure generation: index.html from scene info --------------------------------


def test_build_index_html_structure():
    scenes = [_scene(), _scene(id="s2", image="shots/outro.png", narration="おわり。", title=None)]
    html = hf.build_index_html(scenes, canvas_w=1920, canvas_h=1080, fps=30)
    assert 'data-composition-id="main"' in html
    assert 'data-width="1920"' in html
    assert 'data-height="1080"' in html
    assert "gsap.min.js" in html
    # title present for s1
    assert "sc-s1" in html and "イントロ" in html
    # s2 has no title -> no h2 for it
    assert "sc-s2" in html


def test_build_index_html_escapes_special_chars():
    s = _scene(title='<script>alert("x")</script> & Co.')
    html = hf.build_index_html([s])
    # the injected title must be HTML-escaped, not executable: every angle
    # bracket and quote lands as an entity (built via chr() to survive
    # tool-layer entity decoding)
    lt = chr(38) + "lt;"
    gt = chr(38) + "gt;"
    amp = chr(38) + "amp;"
    assert "<script>alert" not in html
    assert lt + "script" + gt + "alert" in html
    assert amp + " Co." in html
    # gsap CDN script is legitimately present
    assert "gsap.min.js" in html

def test_build_index_html_has_gsap_timeline_and_registry():
    html = hf.build_index_html([_scene()])
    assert "gsap.timeline({ paused: true })" in html
    assert 'window.__timelines["main"]' in html


def test_build_index_html_total_duration_is_last_end():
    scenes = [_scene(), _scene(id="s2")]
    html = hf.build_index_html(scenes, total_duration=12.5)
    assert 'data-duration="12.5"' in html


# --- audio wiring: one <audio id src data-start> per scene; escaped file name ----


def test_build_index_html_audio_elements():
    """An <audio> per scene with id + src (assets/audio/.wav) at the scene's global start."""
    scenes = [_scene(), _scene(id="s2", image="shots/outro.png", narration="おわり。")]
    timeline = [_timing("s1", 0.0, 5.0, 4.7), _timing("s2", 5.0, 8.5, 3.2)]
    html = hf.build_index_html(scenes, timeline=timeline)
    assert '<audio id="audio-s1" src="assets/audio/s1.wav" data-start="0.000"' in html
    assert '<audio id="audio-s2" src="assets/audio/s2.wav" data-start="5.000"' in html
    # every audio has an id (mixer's media_missing_id rule) and no crossorigin
    assert "crossorigin" not in html


def test_build_index_html_scene_timing_windows():
    """Each scene clip carries its [start, start+duration) window from the timeline."""
    scenes = [_scene(), _scene(id="s2", image="shots/outro.png", narration="おわり。")]
    timeline = [_timing("s1", 0.0, 5.0, 4.7), _timing("s2", 5.0, 8.5, 3.2)]
    html = hf.build_index_html(scenes, timeline=timeline)
    assert 'id="sc-s1" class="clip" data-start="0.000" data-duration="5.000"' in html
    assert 'id="sc-s2" class="clip" data-start="5.000" data-duration="3.500"' in html


# --- images: copied/escaped asset path -------------------------------------------


def test_build_index_html_background_image_uses_copied_asset_path():
    """Images live under assets/images/ (the generated project copies them)."""
    s = _scene(image="shots/intro.png")
    html = hf.build_index_html([s])
    assert "assets/images/" in html
    assert "intro.png" in html
    assert "shots/" not in html  # external path must not leak into the composition


# --- file layout: write_project emits index.html + assets -------------------------


def test_write_project_layout(tmp_path):
    img = tmp_path / "shots" / "intro.png"
    img.parent.mkdir()
    img.write_bytes(b"\x89PNG\r\n\x1a\n")  # minimal png marker
    scenes = [_scene()]
    html = hf.build_index_html(scenes)
    out = tmp_path / "proj"
    mapping = hf.write_project(out, html, scenes, base_dir=tmp_path)
    assert (out / "index.html").exists()
    assert (out / "package.json").exists()
    # copied image under assets/images/
    assert (out / "assets" / "images" / "intro.png").exists()
    assert mapping["s1"]["image"] == "assets/images/intro.png"


def test_write_project_unique_image_names_on_collision(tmp_path):
    """Two scenes referencing different files with the same basename get distinct names."""
    a = tmp_path / "a" / "intro.png"
    b = tmp_path / "b" / "intro.png"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(b"AAAAAAAA")
    b.write_bytes(b"BBBBBBBB")
    scenes = [_scene(image=str(a)), _scene(id="s2", image=str(b))]
    out = tmp_path / "proj"
    html = "<html>placeholder</html>"
    mapping = hf.write_project(out, html, scenes, base_dir=tmp_path)
    assert mapping["s1"]["image"] != mapping["s2"]["image"]
    assert (out / mapping["s1"]["image"]).exists()
    assert (out / mapping["s2"]["image"]).exists()


def test_write_project_copies_wavs(tmp_path):
    """Narration wavs land under assets/audio/<id>.wav when provided."""
    img = tmp_path / "intro.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    wav = tmp_path / "wav-cache" / "abc.wav"
    wav.parent.mkdir()
    wav.write_bytes(b"RIFF....")
    scenes = [_scene(image="intro.png")]
    html = hf.build_index_html([_scene(image="intro.png")])
    out = tmp_path / "proj"
    mapping = hf.write_project(out, html, scenes, base_dir=tmp_path, wavs={"s1": wav})
    assert (out / "assets" / "audio" / "s1.wav").exists()
    assert mapping["s1"]["audio"] == "assets/audio/s1.wav"

# --- camera work export: manifest `animation` -> GSAP motion on the scene bg ----


def test_build_index_html_zoom_in_animates_scale():
    s = _scene(animation="zoom_in")
    html = hf.build_index_html([s])
    # animated inner wrapper (bg element), not the .clip
    assert "bg-s1" in html
    assert "scale" in html
    # entering from 1.0 to >1.0 over the scene window
    assert "1.12" in html or "1.1" in html


def test_build_index_html_static_scene_has_no_motion():
    # default (no animation) -> only the entrance fade, no scale/pan tween on bg
    s = _scene()
    html = hf.build_index_html([s])
    assert "bg-s1" in html  # wrapper exists for CSS background
    # but no scale/x/y motion tween on the bg wrapper (only opacity)
    motion = [l for l in html.splitlines() if "#bg-s1" in l and "scale" in l]
    assert motion == [], f"static scene must not animate the bg: {motion}"


def test_build_index_html_pan_right_animates_x():
    s = _scene(animation="pan_right")
    html = hf.build_index_html([s])
    assert "bg-s1" in html
    assert "x:" in html or "x :" in html


def test_build_index_html_scene_animation_uses_scene_start_time():
    # motion tweens are anchored at the scene's global start on the main timeline
    scenes = [_scene(animation="zoom_in"), _scene(id="s2", image="shots/outro.png", narration="おわり。", animation="pan_right")]
    timeline = [_timing("s1", 0.0, 5.0, 4.7), _timing("s2", 5.0, 8.5, 3.2)]
    html = hf.build_index_html(scenes, timeline=timeline)
    # s2's motion tween is scheduled at 5.000 on the main timeline
    s2_motion = [l for l in html.splitlines() if "#bg-s2" in l and ("scale" in l or "x:" in l)]
    assert s2_motion, "expected a motion tween for s2"
    assert any("5.000" in l for l in s2_motion), f"motion not anchored at scene start: {s2_motion}"

