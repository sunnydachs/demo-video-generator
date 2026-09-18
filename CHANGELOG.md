# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-09-19

### Added

- 3-pass pipeline: `manifest` (load/validate) → `voice` (VOICEVOX + SHA256 wav
  cache) → `frames` (Pillow rendering) → `join` (ffmpeg mux)
- CLI with `manifest-check` / `voice` / `frames` / `join` / `build` subcommands
- Scene manifests in JSON or YAML (`examples/scenes.example.json`)
- Deterministic output: same manifest → same video (no seeds, no timing drift)
- Canonical ffmpeg profile (`yuv420p` / `+faststart` / `bt709`) for Safari-safe color
- `.srt` / `.vtt` subtitle output generated from audio timing
- Offline unit test suite (52 tests) + integration marker for real VOICEVOX/ffmpeg

### Fixed

- `join` / `build` now mux a timeline-accurate concatenated track
  (`<cache>/timeline.wav`, narration + pad for every scene) instead of the first
  cached wav, so the MP4 audio always spans the subtitle timeline
- Manifest validation rejects non-string `title` / `subtitle` with `ManifestError`
  instead of crashing mid-render
- `join` / `build` with an empty wav cache exit with a clean `ClickException`
  (`... run \`voice\` first`) instead of a raw traceback
- Malformed timing JSON (non-dict, missing `scenes`, missing `id`,
  non-numeric duration) exits with a clean `ClickException`
- `concat_timeline_wavs` validates wav format (channels/sampwidth/rate) across
  all scenes and raises `VoiceError` on mismatch instead of producing corrupt audio

[Unreleased]: https://github.com/sunnydachs/demo-video-generator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sunnydachs/demo-video-generator/releases/tag/v0.1.0
