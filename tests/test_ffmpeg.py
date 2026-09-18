"""Offline tests for ffmpeg join command construction."""
from demo_video_generator.config import FFMPEG_JOIN_OUTPUT_FLAGS
from demo_video_generator.ffmpegjoin import build_ffmpeg_command


def test_build_command_contains_standard_flags():
    cmd = build_ffmpeg_command(
        frame_dir="frames",
        audio_path="voice.wav",
        out_path="out.mp4",
        fps=30,
    )
    joined = " ".join(cmd)
    # frame + audio inputs
    assert "-framerate" in cmd and "30" in cmd
    assert "-i" in cmd
    # all canonical output flags present
    for flag in FFMPEG_JOIN_OUTPUT_FLAGS:
        assert flag in joined


def test_build_command_input_order_frame_then_audio():
    cmd = build_ffmpeg_command(frame_dir="f", audio_path="a.wav", out_path="o.mp4", fps=24)
    i_positions = [i for i, x in enumerate(cmd) if x == "-i"]
    assert len(i_positions) == 2
    # frames first, then audio
    assert "frame_" in cmd[i_positions[0] + 1]
    assert cmd[i_positions[1] + 1].endswith(".wav")


def test_build_command_shortest_flag():
    cmd = build_ffmpeg_command(frame_dir="f", audio_path="a.wav", out_path="o.mp4", fps=30)
    assert "-shortest" in cmd


def test_build_command_standard_video_codec():
    cmd = build_ffmpeg_command(frame_dir="f", audio_path="a.wav", out_path="o.mp4", fps=30)
    assert "libx264" in cmd