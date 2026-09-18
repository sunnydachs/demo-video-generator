"""Offline tests for timeline-accurate audio concat + mux wiring (review fixes)."""
import json
import wave

import pytest
from click.testing import CliRunner

from demo_video_generator.cli import _read_durations
from demo_video_generator.manifest import Manifest, Scene, build_timeline
from demo_video_generator.voice import (
    VoiceError,
    cache_path_for,
    concat_timeline_wavs,
    wav_duration,
)


def _make_wav(path, seconds=1.0, rate=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


def test_concat_timeline_wavs_spans_all_scenes_plus_pad(tmp_path):
    wavs = {}
    for sid, text, secs in (("a", "first line", 1.0), ("b", "second line", 2.0)):
        p = cache_path_for(text, tmp_path)
        _make_wav(p, seconds=secs)
        wavs[sid] = (text, secs)
    scenes = [
        Scene(id="a", image="a.png", narration=wavs["a"][0], post_pad_sec=0.5),
        Scene(id="b", image="b.png", narration=wavs["b"][0], post_pad_sec=0.0),
    ]
    out = tmp_path / "timeline.wav"
    got = concat_timeline_wavs(scenes, tmp_path, out)
    assert got == out
    expected = 1.0 + 0.5 + 2.0
    assert wav_duration(out) == pytest.approx(expected, abs=1e-6)


def test_concat_timeline_wavs_missing_later_wav_raises(tmp_path):
    scenes = [
        Scene(id="a", image="a.png", narration="present"),
        Scene(id="b", image="b.png", narration="missing"),
    ]
    _make_wav(cache_path_for("present", tmp_path), seconds=0.5)
    with pytest.raises(VoiceError):
        concat_timeline_wavs(scenes, tmp_path, tmp_path / "out.wav")


def test_concat_timeline_wavs_empty_scenes(tmp_path):
    with pytest.raises(VoiceError, match="no scenes"):
        concat_timeline_wavs([], tmp_path, tmp_path / "out.wav")


def test_join_click_exception_when_cache_empty(tmp_path, mocker):
    """join with an empty cache is a clean ClickException, not a raw traceback."""
    from demo_video_generator.cli import main

    manifest_path = tmp_path / "m.json"
    manifest_path.write_text(json.dumps({"scenes": [{"id": "a", "image": "a.png", "narration": "hi"}]}))
    empty_cache = tmp_path / "empty-cache"
    empty_cache.mkdir()
    # ffmpeg is irrelevant: the error must fire before the mux
    mocker.patch("demo_video_generator.ffmpegjoin.ffmpeg_available", return_value=False)
    runner = CliRunner()
    result = runner.invoke(main, ["join", str(manifest_path), "--cache-dir", str(empty_cache)])
    assert result.exit_code != 0
    assert "run `voice` first" in result.output
    assert "Traceback" not in result.output


def test_read_durations_non_dict_timing_json(tmp_path):
    p = tmp_path / "timings.json"
    p.write_text("[1, 2, 3]")
    manifest = Manifest(scenes=[Scene(id="a", image="a.png", narration="hi")])
    with pytest.raises(Exception, match="expected a 'scenes' array"):
        _read_durations(str(p), str(tmp_path), manifest)


def test_read_durations_scene_without_id(tmp_path):
    p = tmp_path / "timings.json"
    p.write_text(json.dumps({"scenes": [{"narration_duration": 1.0}]}))
    manifest = Manifest(scenes=[Scene(id="a", image="a.png", narration="hi")])
    with pytest.raises(Exception, match="string 'id'"):
        _read_durations(str(p), str(tmp_path), manifest)


def test_read_durations_non_numeric_duration(tmp_path):
    p = tmp_path / "timings.json"
    p.write_text(json.dumps({"scenes": [{"id": "a", "narration_duration": "fast"}]}))
    manifest = Manifest(scenes=[Scene(id="a", image="a.png", narration="hi")])
    with pytest.raises(Exception, match="non-numeric duration"):
        _read_durations(str(p), str(tmp_path), manifest)


def test_concat_timeline_wavs_mixed_formats_raise(tmp_path):
    """Wavs with differing rate/channels/sampwidth are rejected, not concatenated."""
    scenes = [
        Scene(id="a", image="a.png", narration="first"),
        Scene(id="b", image="b.png", narration="second"),
    ]
    _make_wav(cache_path_for("first", tmp_path), seconds=1.0, rate=24000)
    _make_wav(cache_path_for("second", tmp_path), seconds=1.0, rate=16000)
    with pytest.raises(VoiceError, match="format mismatch"):
        concat_timeline_wavs(scenes, tmp_path, tmp_path / "out.wav")


def test_read_durations_from_timing_file(tmp_path):
    p = tmp_path / "timings.json"
    p.write_text(json.dumps({"scenes": [{"id": "a", "narration_duration": 2.5}]}))
    scenes = [Scene(id="a", image="a.png", narration="hi")]
    got = _read_durations(str(p), str(tmp_path), scenes)
    assert got == {"a": 2.5}


def test_read_durations_bad_timing_file_click_exception(tmp_path):
    p = tmp_path / "timings.json"
    p.write_text("{not json")
    scenes = [Scene(id="a", image="a.png", narration="hi")]
    with pytest.raises(Exception, match="cannot read timing file"):
        _read_durations(str(p), str(tmp_path), scenes)


def test_read_durations_from_cache_glob(tmp_path):
    _make_wav(cache_path_for("hello", tmp_path), seconds=1.5)
    manifest = Manifest(scenes=[Scene(id="a", image="a.png", narration="hello")])
    got = _read_durations(None, str(tmp_path), manifest)
    assert got["a"] == pytest.approx(1.5)


def test_read_durations_invalid_wav_raises_click_exception(tmp_path):
    wav_path = cache_path_for("hello", tmp_path)
    wav_path.write_bytes(b"not a wav")
    manifest = Manifest(scenes=[Scene(id="a", image="a.png", narration="hello")])
    with pytest.raises(Exception, match="invalid wav"):
        _read_durations(None, str(tmp_path), manifest)


def test_numeric_title_rejected_by_validation(tmp_path):
    from demo_video_generator.manifest import ManifestError, load_manifest

    p = tmp_path / "m.yaml"
    p.write_text("scenes:\n  - id: a\n    image: i.png\n    narration: hi\n    title: 2024\n")
    with pytest.raises(ManifestError, match="title"):
        load_manifest(str(p))


def test_numeric_subtitle_rejected_by_validation(tmp_path):
    from demo_video_generator.manifest import ManifestError, load_manifest

    p = tmp_path / "m.json"
    p.write_text(json.dumps({"scenes": [{"id": "a", "image": "i.png", "narration": "hi", "subtitle": 7}]}))
    with pytest.raises(ManifestError, match="subtitle"):
        load_manifest(str(p))


def test_timeline_matches_frame_and_audio_duration(tmp_path):
    """End-to-end alignment: frames rendered from the timeline span narration + pad."""
    from demo_video_generator.frames import frame_count

    scenes = [
        Scene(id="a", image="a.png", narration="alpha narration", post_pad_sec=0.4),
        Scene(id="b", image="b.png", narration="beta narration", post_pad_sec=0.0),
    ]
    durations = {"a": 2.2, "b": 1.7}
    tl = build_timeline(scenes, durations)
    total = tl[-1].end

    wavs = {}
    for scene in scenes:
        p = cache_path_for(scene.narration, tmp_path)
        _make_wav(p, seconds=durations[scene.id])
        wavs[scene.id] = p
    out = tmp_path / "timeline.wav"
    concat_timeline_wavs(scenes, tmp_path, out)

    audio_dur = wav_duration(out)
    video_frames = sum(frame_count(t.duration, 30) for t in tl)
    video_dur = video_frames / 30.0
    # audio-first design: frame count covers narration + pad, so video >= audio
    assert video_dur >= audio_dur - 1e-6
    assert video_dur <= total + 1e-6
