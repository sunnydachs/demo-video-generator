"""Offline tests for .srt / .vtt subtitle generation."""

from demo_video_generator.subtitles import (
    build_srt,
    build_vtt,
    format_srt_cue,
    format_vtt_cue,
)


def test_format_srt_cue():
    assert format_srt_cue(0.0, 1.25) == "00:00:00,000 --> 00:00:01,250"
    assert format_srt_cue(2.5, 5.0) == "00:00:02,500 --> 00:00:05,000"


def test_format_vtt_cue():
    assert format_vtt_cue(0.0, 1.25) == "00:00:00.000 --> 00:00:01.250"


def test_build_srt_single():
    srt = build_srt([(0.0, 2.0, "Hello")])
    assert "1\n00:00:00,000 --> 00:00:02,000\nHello\n" in srt
    assert "WEBVTT" not in srt


def test_build_srt_sequences_numbers():
    srt = build_srt([(0.0, 1.0, "a"), (1.0, 2.0, "b")])
    assert srt.startswith("1\n00:00:00,000 --> 00:00:01,000\na\n")
    assert "2\n00:00:01,000 --> 00:00:02,000\nb\n" in srt


def test_build_vtt_header_and_cues():
    vtt = build_vtt([(0.0, 1.0, "Hello")])
    assert vtt.startswith("WEBVTT\n")
    assert "00:00:00.000 --> 00:00:01.000\nHello" in vtt


def test_build_vtt_multiple():
    vtt = build_vtt([(0.0, 1.0, "a"), (1.5, 2.0, "b")])
    assert vtt.count("-->") == 2