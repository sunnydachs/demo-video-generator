"""CLI for demo-video-generator.

Audio-first 3-pass design as subcommands:
  manifest-check  validate the scene manifest
  voice           synthesize narrations + write timing JSON
  frames          render Pillow frames from manifest + timings
  join            mux frames + audio with ffmpeg
  build           run voice -> frames -> join, plus subtitles
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import click

from . import __version__
from . import ffmpegjoin as ffjoin
from .config import FPS, VOICEVOX_SPEAKER, VOICEVOX_URL
from .frames import render_scene_frames
from .manifest import ManifestError, build_timeline, load_manifest
from .subtitles import blocks_from_timeline, build_srt, build_vtt
from .voice import (
    VoiceError,
    cache_path_for,
    concat_timeline_wavs,
    get_scene_durations,
    wav_duration,
)

log = logging.getLogger("demo-video-generator.cli")

_DEFAULT_OUT = "dist"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


def _load(scene_path: str):
    try:
        return load_manifest(scene_path)
    except ManifestError as exc:
        raise click.ClickException(f"manifest error: {exc}") from exc


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


@click.group()
@click.version_option(__version__)
def main() -> None:
    """Generate deterministic demo videos from a manifest + VOICEVOX narration."""


@main.command("manifest-check")
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
@click.option("--verbose", "-v", is_flag=True, help="Explain per-scene validation.")
def manifest_check(manifest: str, verbose: bool) -> None:
    """Validate a scene manifest without synthesizing or rendering."""
    _setup_logging(verbose)
    try:
        loaded = load_manifest(manifest)
    except ManifestError as exc:
        raise click.ClickException(str(exc)) from exc
    if verbose:
        for s in loaded.scenes:
            click.echo(f"  [{s.id}] title={s.title!r} pad={s.post_pad_sec} narration={len(s.narration)} chars")
    click.echo(f"OK: {len(loaded.scenes)} scene(s) valid in {manifest}")


@main.command()
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
@click.option("--cache-dir", default="wav-cache", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--timing-out", default=None, help="Write timing JSON to this path (default: wav-cache/timings.json).")
@click.option("--speaker", default=VOICEVOX_SPEAKER, type=int)
@click.option("--voicevox-url", default=VOICEVOX_URL)
@click.option("--verbose", "-v", is_flag=True)
def voice(
    manifest: str,
    cache_dir: str,
    timing_out: str | None,
    speaker: int,
    voicevox_url: str,
    verbose: bool,
) -> None:
    """Synthesize all narrations via VOICEVOX and record durations (pass 2a)."""
    _setup_logging(verbose)
    loaded = _load(manifest)
    cache = Path(cache_dir)
    try:
        durations = get_scene_durations(
            loaded.scenes, cache_dir=cache, speaker=speaker, base_url=voicevox_url
        )
    except VoiceError as exc:
        raise click.ClickException(str(exc)) from exc
    timeline = build_timeline(loaded.scenes, durations)
    timing_path = Path(timing_out if timing_out else cache / "timings.json")
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_path.write_text(
        json.dumps(
            {
                "fps": FPS,
                "scenes": [
                    {
                        "id": t.id,
                        "start": t.start,
                        "end": t.end,
                        "narration_duration": t.narration_duration,
                        "post_pad": t.end - t.start - t.narration_duration,
                    }
                    for t in timeline
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    for t in timeline:
        click.echo(f"  [{t.id}] {t.start:7.3f} -> {t.end:7.3f}  ({t.narration_duration:.3f}s narr)")
    click.echo(f"wrote {timing_path}")


@main.command()
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
@click.option("--timing", type=click.Path(exists=True, dir_okay=False), default=None)
@click.option("--cache-dir", default="wav-cache", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--frames-dir", default="frames", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--fps", default=FPS, type=int)
@click.option("--verbose", "-v", is_flag=True)
def frames(
    manifest: str,
    timing: str | None,
    cache_dir: str,
    frames_dir: str,
    fps: int,
    verbose: bool,
) -> None:
    """Render the frame sequence from manifest + timings (pass 2b)."""
    _setup_logging(verbose)
    loaded = _load(manifest)
    durations = _read_durations(timing, cache_dir, loaded)
    timeline = build_timeline(loaded.scenes, durations)
    out = Path(frames_dir)
    out.mkdir(parents=True, exist_ok=True)
    tick = 1
    for scene, t in zip(loaded.scenes, timeline):
        tick = render_scene_frames(scene, out, start_frame=tick, duration=t.duration, fps=fps)
        log.info("scene %s -> %d frames", scene.id, t.duration * fps)
    click.echo(f"wrote {tick - 1} frame(s) to {out}/frame_*.png")


def _read_durations(timing: str | None, cache_dir: str, loaded):
    """Narration durations per scene id, from a timing JSON or the wav cache."""
    if timing:
        try:
            data = json.loads(Path(timing).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise click.ClickException(f"cannot read timing file {timing}: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("scenes"), list):
            raise click.ClickException(f"invalid timing file {timing}: expected a 'scenes' array")
        durations: dict = {}
        for idx, entry in enumerate(data["scenes"]):
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
                raise click.ClickException(
                    f"invalid timing file {timing}: scene #{idx} needs a string 'id'"
                )
            raw = entry.get("narration_duration", entry.get("duration", 0.0))
            try:
                durations[entry["id"]] = float(raw)
            except (TypeError, ValueError) as exc:
                raise click.ClickException(
                    f"invalid timing file {timing}: scene '{entry['id']}' has a non-numeric duration"
                ) from exc
        return durations
    wavs = Path(cache_dir).glob("*.wav")
    by_hash: dict = {}
    for w in wavs:
        by_hash[w.stem] = w
    out: dict = {}
    for scene in loaded.scenes:
        cand = cache_path_for(scene.narration, cache_dir)
        if cand.exists():
            try:
                out[scene.id] = wav_duration(cand)
            except VoiceError as exc:
                raise click.ClickException(str(exc)) from exc
    return out


@main.command()
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
@click.option("--cache-dir", default="wav-cache", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--frames-dir", default="frames", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--out", "out_path", default="dist/demo.mp4", type=click.Path(dir_okay=False))
@click.option("--fps", default=FPS, type=int)
@click.option("--verbose", "-v", is_flag=True)
def join(
    manifest: str,
    cache_dir: str,
    frames_dir: str,
    out_path: str,
    fps: int,
    verbose: bool,
) -> None:
    """Mux the frame sequence + a concatenated audio track with ffmpeg (pass 3)."""
    _setup_logging(verbose)
    loaded = _load(manifest)
    try:
        audio = _timeline_audio(loaded, cache_dir, Path(cache_dir) / "timeline.wav")
    except VoiceError as exc:
        raise click.ClickException(f"{exc}; run `voice` first") from exc
    try:
        ffjoin.join(frame_dir=frames_dir, audio_path=audio, out_path=out_path, fps=fps)
    except ffjoin.FfmpegError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"wrote {out_path}")


def _timeline_audio(loaded, cache_dir: str, out_path: str | Path) -> str:
    """Build a timeline-accurate concatenated audio track (narration + pad silence)."""
    audio = concat_timeline_wavs(loaded.scenes, cache_dir, Path(out_path))
    return str(audio)


@main.command()
@click.argument("manifest", type=click.Path(exists=True, dir_okay=False))
@click.option("--cache-dir", default="wav-cache", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--frames-dir", default="frames", type=click.Path(file_okay=False, dir_okay=True))
@click.option("--out", "out_path", default="dist/demo.mp4", type=click.Path(dir_okay=False))
@click.option("--out-srt", "out_srt", default=None, type=click.Path(dir_okay=False))
@click.option("--out-vtt", "out_vtt", default=None, type=click.Path(dir_okay=False))
@click.option("--fps", default=FPS, type=int)
@click.option("--speaker", default=VOICEVOX_SPEAKER, type=int)
@click.option("--voicevox-url", default=VOICEVOX_URL)
@click.option("--verbose", "-v", is_flag=True)
@click.option("--no-ffmpeg", is_flag=True, help="Stop after frames + subtitles; skip the ffmpeg mux.")
def build(
    manifest: str,
    cache_dir: str,
    frames_dir: str,
    out_path: str,
    out_srt: str | None,
    out_vtt: str | None,
    fps: int,
    speaker: int,
    voicevox_url: str,
    verbose: bool,
    no_ffmpeg: bool,
) -> None:
    """Full pipeline: synthesize -> frames -> subtitles -> ffmpeg join."""
    _setup_logging(verbose)
    loaded = _load(manifest)
    cache = Path(cache_dir)
    try:
        durations = get_scene_durations(loaded.scenes, cache_dir=cache, speaker=speaker, base_url=voicevox_url)
    except VoiceError as exc:
        raise click.ClickException(str(exc)) from exc
    timeline = build_timeline(loaded.scenes, durations)

    # frames
    out_f = Path(frames_dir)
    out_f.mkdir(parents=True, exist_ok=True)
    tick = 1
    for scene, t in zip(loaded.scenes, timeline):
        tick = render_scene_frames(scene, out_f, start_frame=tick, duration=t.duration, fps=fps)
    click.echo(f"rendered {tick - 1} frame(s)")

    # subtitles
    blocks = blocks_from_timeline(timeline)
    srt = Path(out_srt if out_srt else Path(out_path).with_suffix(".srt"))
    vtt = Path(out_vtt if out_vtt else Path(out_path).with_suffix(".vtt"))
    srt.parent.mkdir(parents=True, exist_ok=True)
    srt.write_text(build_srt(blocks), encoding="utf-8")
    vtt.write_text(build_vtt(blocks), encoding="utf-8")
    click.echo(f"wrote {srt} and {vtt}")

    if no_ffmpeg:
        click.echo("skipping ffmpeg mux (--no-ffmpeg)")
        return
    try:
        audio = _timeline_audio(loaded, cache_dir, cache / "timeline.wav")
    except VoiceError as exc:
        raise click.ClickException(f"{exc}; run `voice` first") from exc
    try:
        ffjoin.join(frame_dir=frames_dir, audio_path=audio, out_path=out_path, fps=fps)
    except ffjoin.FfmpegError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"wrote {out_path}")


if __name__ == "__main__":
    main()