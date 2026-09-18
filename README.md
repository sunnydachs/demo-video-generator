# demo-video-generator

**Deterministic, manifest-driven demo videos from still frames + VOICEVOX narration.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/sunnydachs/demo-video-generator/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

English | [日本語](README.ja.md)

`demo-video-generator` turns a scene manifest (JSON/YAML) into a finished MP4:
each scene is a still screenshot held on screen while VOICEVOX narrates over it.
Same manifest in, same video out — no LLM seeds, no timing drift.

## How it works (3-pass pipeline)

```
manifest ──▶ voice ──▶ frames ──▶ join ──▶ demo.mp4 + .srt + .vtt
             │           │
             │           └─ Pillow: title band, border, burned-in subtitles
             └─ VOICEVOX HTTP API, SHA256 content-addressed wav cache
```

- **pass 1 — manifest**: load + validate `scenes[]` (JSON or YAML), build the timeline
- **pass 2 — voice / frames**: synthesize narration via VOICEVOX (cached by narration
  hash, never re-hit for unchanged text) and render 1280x720 @ 30fps frames with Pillow
- **pass 3 — join**: mux frames + audio with a canonical ffmpeg profile
  (`-pix_fmt yuv420p -movflags +faststart -colorspace bt709` — Safari color-safe),
  emitting `.srt` / `.vtt` subtitles from the audio timing

## Install

```bash
uv tool install demo-video-generator
# or
uvx demo-video-generator --help
```

Requires Python 3.11+. For actual video generation you need a running
[VOICEVOX](https://voicevox.hiroshiba.jp/) engine (default `http://127.0.0.1:50021`)
and `ffmpeg` on PATH.

## Quick start

```bash
# 1. Validate the manifest (offline, no VOICEVOX needed)
demo-video-generator manifest-check examples/scenes.example.json

# 2. Full pipeline: voice -> frames -> subtitles -> ffmpeg mux
demo-video-generator build examples/scenes.example.json
```

### Manifest format

```json
{
  "scenes": [
    {
      "id": "intro",
      "image": "shots/intro.png",
      "title": "Intro",
      "narration": "こんにちは。これは製品デモ動画です。",
      "post_pad_sec": 0.4,
      "subtitle": "Optional English subtitle, burned into the frame and written to .srt/.vtt"
    }
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `id` | yes | Scene identifier (used in timing output) |
| `image` | yes | Path to the still frame image |
| `title` | no | Title band text drawn on the frame |
| `narration` | yes | Text sent to VOICEVOX |
| `post_pad_sec` | no | Silence appended after narration (default: `0.0`) |
| `subtitle` | no | Burned-in subtitle text (also goes to `.srt`/`.vtt`) |

YAML works too — `manifest-check` accepts either by file extension.

### Subcommands

| Command | What it does |
|---|---|
| `manifest-check` | Validate a scene manifest without synthesizing or rendering |
| `voice` | Synthesize all narrations via VOICEVOX, write `timings.json` |
| `frames` | Render the frame sequence from manifest + timings |
| `join` | Mux the frame sequence + audio with ffmpeg |
| `build` | Full pipeline: voice → frames → subtitles → join |

## Development

```bash
git clone https://github.com/sunnydachs/demo-video-generator.git
cd demo-video-generator
uv sync
uv run pytest -m "not integration"   # offline unit tests
uv run ruff check src tests          # lint
```

Integration tests (real VOICEVOX + ffmpeg) are marked `integration` and deselected
by default; run them with `uv run pytest -m integration` when a VOICEVOX engine
is up.

## License

[MIT](LICENSE)
