"""Offline tests for VOICEVOX synthesis client + content-addressed wav cache."""
import hashlib
import wave

import pytest

from demo_video_generator.voice import (
    cache_path_for,
    get_wav,
    text_hash,
    wav_duration,
)


def test_text_hash_is_sha256_hex():
    h = text_hash("hello")
    assert h == hashlib.sha256(b"hello").hexdigest()
    assert len(h) == 64


def test_text_hash_distinguishes_text():
    assert text_hash("a") != text_hash("b")


def _make_wav(path, seconds=1.0, rate=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        nframes = int(seconds * rate)
        w.writeframes(b"\x00\x00" * nframes)


def test_wav_duration(tmp_path):
    p = tmp_path / "a.wav"
    _make_wav(p, seconds=2.0, rate=16000)
    assert wav_duration(p) == pytest.approx(2.0)


def test_cache_path_for_uses_hash_and_wav_suffix(tmp_path):
    p = cache_path_for("text", tmp_path)
    assert p.name == text_hash("text") + ".wav"
    assert p.parent == tmp_path


def test_get_wav_returns_cached_without_synth(tmp_path, mocker):
    p = cache_path_for("cached text", tmp_path)
    _make_wav(p, seconds=1.0, rate=24000)
    synth = mocker.patch("demo_video_generator.voice.synth_wav")
    got = get_wav("cached text", cache_dir=tmp_path)
    assert got == p
    synth.assert_not_called()


def test_get_wav_synthesizes_when_missing(tmp_path, mocker):
    synth = mocker.patch(
        "demo_video_generator.voice.synth_wav",
        side_effect=lambda text, **kw: _make_wav_bytes("ignored"),
    )
    got = get_wav("new text", cache_dir=tmp_path)
    assert got.exists()
    assert synth.call_count == 1
    # second call hits cache, no re-synth
    get_wav("new text", cache_dir=tmp_path)
    assert synth.call_count == 1


def _make_wav_bytes(text, rate=24000):
    bio = __import__("io").BytesIO()
    with wave.open(bio, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate / 2))
    return bio.getvalue()


@pytest.mark.integration
def test_synth_wav_hits_voicevox_http():
    from demo_video_generator.voice import synth_wav

    data = synth_wav("こんにちは")
    assert len(data) > 0
    assert data[:4] == b"RIFF"