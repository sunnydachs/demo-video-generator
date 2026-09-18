"""demo-video-generator: deterministic, manifest-driven demo videos.

Pipeline: manifest -> VOICEVOX narration + timing -> Pillow frames -> ffmpeg mux.
"""

__version__ = "0.1.0"

from .config import (
    FFMPEG_JOIN_OUTPUT_FLAGS,
    FPS,
    HEIGHT,
    VOICEVOX_SPEAKER,
    VOICEVOX_URL,
    WIDTH,
)
from .ffmpegjoin import build_ffmpeg_command, join
from .frames import render_scene, render_scene_frames
from .manifest import Manifest, ManifestError, Scene, SceneTiming, build_timeline, load_manifest
from .subtitles import build_srt, build_vtt
from .voice import (
    cache_path_for,
    get_scene_durations,
    get_wav,
    synth_wav,
    text_hash,
    wav_duration,
)

__all__ = [
    "FFMPEG_JOIN_OUTPUT_FLAGS",
    "FPS",
    "HEIGHT",
    "VOICEVOX_SPEAKER",
    "VOICEVOX_URL",
    "WIDTH",
    "Manifest",
    "ManifestError",
    "Scene",
    "SceneTiming",
    "__version__",
    "build_ffmpeg_command",
    "build_srt",
    "build_timeline",
    "build_vtt",
    "cache_path_for",
    "get_scene_durations",
    "get_wav",
    "join",
    "load_manifest",
    "render_scene",
    "render_scene_frames",
    "synth_wav",
    "text_hash",
    "wav_duration",
]