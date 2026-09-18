"""VOICEVOX narration synthesis + SHA256 content-addressed wav cache.

The HTTP calls to VOICEVOX are integration-only; cache lookup and wav duration
measurement are pure and offline-testable.
"""

from __future__ import annotations

import hashlib
import logging
import wave
from pathlib import Path
from urllib.parse import urlencode

from .config import (
    VOICEVOX_SPEAKER,
    VOICEVOX_URL,
)

log = logging.getLogger("demo-video-generator.voice")


class VoiceError(Exception):
    """Raised when VOICEVOX synthesis fails."""


def text_hash(text: str) -> str:
    """SHA256 hex digest of the narration text (deterministic cache key)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def cache_path_for(text: str, cache_dir: str | Path) -> Path:
    """Content-addressed wav path for a narration, without touching the network."""
    return Path(cache_dir) / f"{text_hash(text)}.wav"


def wav_duration(path: str | Path) -> float:
    """Audio duration in seconds read from the wav header (offline)."""
    try:
        with wave.open(str(path), "rb") as w:
            if w.getframerate() <= 0:
                raise VoiceError(f"invalid wav (bad rate): {path}")
            return w.getnframes() / float(w.getframerate())
    except wave.Error as exc:
        raise VoiceError(f"invalid wav file: {path}: {exc}") from exc


def concat_timeline_wavs(scenes, cache_dir: str | Path, out_path: str | Path) -> Path:
    """Concatenate narration wavs with exact post_pad silence for each scene."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not scenes:
        raise VoiceError("no scenes provided")

    wav_paths = [cache_path_for(s.narration, cache_dir) for s in scenes]
    missing = [str(p) for p in wav_paths if not Path(p).exists()]
    if missing:
        raise VoiceError(f"wav files not found in cache {cache_dir}: {missing}")

    with wave.open(str(wav_paths[0]), "rb") as first:
        params = first.getparams()
        nchannels, sampwidth, framerate, _, _comptype, _compname = params

    for wp in wav_paths[1:]:
        with wave.open(str(wp), "rb") as w:
            p = w.getparams()
        if (p.nchannels, p.sampwidth, p.framerate) != (nchannels, sampwidth, framerate):
            raise VoiceError(
                f"wav format mismatch in cache {cache_dir}: {wp} is "
                f"({p.nchannels}ch/{p.sampwidth}B/{p.framerate}Hz), expected "
                f"({nchannels}ch/{sampwidth}B/{framerate}Hz)"
            )

    with wave.open(str(out_path), "wb") as out:
        out.setparams(params)
        for scene, wp in zip(scenes, wav_paths):
            with wave.open(str(wp), "rb") as w:
                out.writeframes(w.readframes(w.getnframes()))
            if scene.post_pad_sec > 0:
                silence_frames = int(scene.post_pad_sec * framerate)
                silence_bytes = b"\x00" * (silence_frames * nchannels * sampwidth)
                out.writeframes(silence_bytes)
    return out_path


def synth_wav(
    text: str,
    *,
    speaker: int = VOICEVOX_SPEAKER,
    base_url: str = VOICEVOX_URL,
    timeout: float = 60.0,
    session=None,
) -> bytes:
    """Synthesize narration via VOICEVOX /audio_query + /synthesis.

    Returns raw wav bytes. Requires a running VOICEVOX server (integration).
    """
    import urllib.request

    query_url = f"{base_url.rstrip('/')}/audio_query?{urlencode({'text': text, 'speaker': speaker})}"
    synth_url = f"{base_url.rstrip('/')}/synthesis?{urlencode({'speaker': speaker})}"

    def _post(url: str, data: bytes, ctype: str):
        req = urllib.request.Request(url, data=data, headers={"Content-Type": ctype}, method="POST")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()

    try:
        query_json = _post(query_url, b"{}", "application/json")
        return _post(synth_url, query_json, "application/json")
    except Exception as exc:
        raise VoiceError(f"VOICEVOX synthesis failed for text hash {text_hash(text)}: {exc}") from exc


def get_wav(
    text: str,
    *,
    cache_dir: str | Path,
    speaker: int = VOICEVOX_SPEAKER,
    base_url: str = VOICEVOX_URL,
) -> Path:
    """Return a wav file for ``text``, reusing the cache when available.

    If the content-addressed wav already exists it is returned without hitting
    VOICEVOX. Otherwise the narration is synthesized and cached.
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_path_for(text, cache_dir)
    if target.exists() and target.stat().st_size > 0:
        log.debug("cache hit: %s", target)
        return target
    data = synth_wav(text, speaker=speaker, base_url=base_url)
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(target)
    log.info("synthesized -> %s", target)
    return target


def get_scene_durations(
    scenes,
    *,
    cache_dir: str | Path,
    speaker: int = VOICEVOX_SPEAKER,
    base_url: str = VOICEVOX_URL,
) -> dict[str, float]:
    """Synthesize every scene narration and return id -> duration seconds.

    ``scenes`` is a manifest Scene list. Integration-requiring when any narration
    is missing from the cache.
    """
    durations: dict[str, float] = {}
    for scene in scenes:
        wav = get_wav(scene.narration, cache_dir=cache_dir, speaker=speaker, base_url=base_url)
        durations[scene.id] = wav_duration(wav)
    return durations