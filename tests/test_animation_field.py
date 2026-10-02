"""TDD tests for the scene-level ``animation`` field (Ken Burns / camera work)."""
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


# --- Scene dataclass defaults -------------------------------------------------


def test_scene_animation_defaults_to_static():
    s = Scene(id="a", image="a.png", narration="hi")
    assert s.animation == "static"


def test_scene_animation_coerced_to_string():
    s = Scene(id="a", image="a.png", narration="hi", animation="zoom_in")
    assert s.animation == "zoom_in"


# --- Manifest validation: allowed values ---------------------------------------


@pytest.mark.parametrize("anim", ["static", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"])
def test_load_manifest_accepts_known_animation(tmp_path, anim):
    m = {"scenes": [valid_scene(animation=anim)]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    manifest = load_manifest(str(p))
    assert manifest.scenes[0].animation == anim


def test_load_manifest_rejects_unknown_animation(tmp_path):
    m = {"scenes": [valid_scene(animation="wiggle_360")]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_load_manifest_rejects_non_string_animation(tmp_path):
    # YAML `animation: 1` parses as an int -- must be a ManifestError, not a silent crash.
    m = {"scenes": [valid_scene(animation=1)]}
    p = tmp_path / "m.yaml"
    p.write_text(yaml.safe_dump(m))
    with pytest.raises(ManifestError):
        load_manifest(str(p))


def test_load_manifest_animation_defaults_when_absent(tmp_path):
    m = {"scenes": [valid_scene()]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(m))
    manifest = load_manifest(str(p))
    assert manifest.scenes[0].animation == "static"
