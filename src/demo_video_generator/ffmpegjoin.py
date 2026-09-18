"""ffmpeg join step: mux a frame sequence + narration wav into an mp4.

Command construction is pure and offline-testable; executing ffmpeg requires a
local `ffmpeg` binary and is therefore integration-only.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from .config import FFMPEG_JOIN_OUTPUT_FLAGS, FPS

log = logging.getLogger("demo-video-generator.ffmpegjoin")


class FfmpegError(Exception):
    """Raised when the ffmpeg join step fails."""


FRAME_PATTERN = "frame_%05d.png"


def build_ffmpeg_command(
    *,
    frame_dir: str | Path,
    audio_path: str | Path,
    out_path: str | Path,
    fps: int = FPS,
    start_number: int = 1,
) -> list[str]:
    """Build the canonical ffmpeg argv to join frames from ``frame_dir`` + wav.

    Output uses the standard profile: x264, yuv420p, +faststart, bt709 colorspace.
    ``-shortest`` trims the longer stream so the video and audio tracks align
    exactly (audio-first design: frame count already spans narration + pad).
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-start_number",
        str(start_number),
        "-i",
        str(Path(frame_dir) / FRAME_PATTERN),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        *FFMPEG_JOIN_OUTPUT_FLAGS,
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(out_path),
    ]
    return cmd


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def join(
    *,
    frame_dir: str | Path,
    audio_path: str | Path,
    out_path: str | Path,
    fps: int = FPS,
    cmd_factory=build_ffmpeg_command,
) -> Path:
    """Run the ffmpeg join. Requires an ffmpeg binary (integration)."""
    if not ffmpeg_available():
        raise FfmpegError("ffmpeg binary not found on PATH")
    cmd = cmd_factory(frame_dir=frame_dir, audio_path=audio_path, out_path=out_path, fps=fps)
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise FfmpegError(f"ffmpeg failed ({proc.returncode}):\n{proc.stderr[-2000:]}")
    out = Path(out_path)
    if not out.exists():
        raise FfmpegError(f"ffmpeg did not produce output: {out_path}")
    return out