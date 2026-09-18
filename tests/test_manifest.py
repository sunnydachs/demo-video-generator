"""Offline tests for manifest loading / validation."""
import json

import pytest
import yaml

from demo_video_generator.manifest import ManifestError, Scene, load_manifest


def valid_scene(**overrides):
    base = {
        "id": "s1",
        "image": "shots/s1.png",
        "narration": "Hello world.",
        "post_pad_sec": 0.5,
    }
    base.update(overrides)
    return base


def test_scene_defaults():
    s = Scene(id="a", image="a.png", narration="hi")
    assert s.post_pad_sec == 0.0
    assert s.title is None
    assert s.subtitle == "hi"


def test_load_manifest_json(tmp_path):
    m = {"scenes": [valid_scene()]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    manifest = load_manifest(str(p))
    assert len(manifest.scenes) == 1
    assert manifest.scenes[0].id == "s1"


def test_load_manifest_yaml(tmp_path):
    m = {"scenes": [valid_scene(title="Intro")]}
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(m))
    manifest = load_manifest(str(p))
    assert manifest.scenes[0].title == "Intro"


def test_missing_scenes_key(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"foo": 1}))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_empty_scenes(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"scenes": []}))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_duplicate_scene_id(tmp_path):
    m = {"scenes": [valid_scene(), valid_scene()]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_narration_required(tmp_path):
    m = {"scenes": [valid_scene(narration="")]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_negative_pad_rejected(tmp_path):
    m = {"scenes": [valid_scene(post_pad_sec=-1)]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_file_not_found():
    with pytest.raises(ManifestError):
        load_manifest("/no/such/path.json")


def test_build_timeline_uses_duration_plus_pad():
    from demo_video_generator.manifest import build_timeline

    scenes = [Scene(id="a", image="a.png", narration="hi", post_pad_sec=0.5)]
    durations = {"a": 2.0}
    tl = build_timeline(scenes, durations)
    assert len(tl) == 1
    assert tl[0].start == 0.0
    assert tl[0].end == pytest.approx(2.5)


def test_build_timeline_is_sequential():
    from demo_video_generator.manifest import build_timeline

    scenes = [
        Scene(id="a", image="a.png", narration="one", post_pad_sec=0.0),
        Scene(id="b", image="b.png", narration="two", post_pad_sec=1.0),
    ]
    durations = {"a": 1.0, "b": 1.0}
    tl = build_timeline(scenes, durations)
    assert tl[0].start == 0.0
    assert tl[1].start == pytest.approx(1.0)
    assert tl[1].end == pytest.approx(3.0)