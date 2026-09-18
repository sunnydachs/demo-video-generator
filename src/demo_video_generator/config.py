"""Shared configuration: canvas size, fates, ffmpeg policy flags, VOICEVOX endpoints.

Design note: all tunables live here so the CLI stays deterministic and the
canonical ffmpeg profile is defined in exactly one place.
"""

from __future__ import annotations

# Canvas / render
WIDTH = 1280
HEIGHT = 720
FPS = 30
BG_COLOR = (12, 12, 14)
TITLE_BAND_HEIGHT = 120
TITLE_FONT_SIZE = 44
TITLE_COLOR = (245, 245, 245)
TITLE_BAND_COLOR = (18, 18, 26)
DEFAULT_POST_PAD_SEC = 0.0

# Logging
LOG_NAME = "demo-video-generator"

# VOICEVOX HTTP API
VOICEVOX_URL = "http://127.0.0.1:50021"
VOICEVOX_SPEAKER = 1

# Canonical ffmpeg output profile (Safari color-safe + web streaming).
# Applied to the muxed output video stream.
FFMPEG_JOIN_OUTPUT_FLAGS = [
    "-pix_fmt",
    "yuv420p",
    "-movflags",
    "+faststart",
    "-colorspace",
    "bt709",
    "-color_primaries",
    "bt709",
    "-color_trc",
    "bt709",
]