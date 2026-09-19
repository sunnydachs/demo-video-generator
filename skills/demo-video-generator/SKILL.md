---
name: demo-video-generator
description: Generate deterministic demo videos from still frames + VOICEVOX narration via a manifest. Use when producing product demo videos, screen-recording slideshows, or narrated walkthroughs.
license: MIT
compatibility: Requires Python 3.11+, uv, ffmpeg on PATH, and a local VOICEVOX engine (default http://127.0.0.1:50021)
metadata:
  author: sunnydachs
  version: "0.1.0"
  repository: https://github.com/sunnydachs/demo-video-generator
  pypi: https://pypi.org/project/demo-video-generator/
---

# demo-video-generator Skill

Generate a finished MP4 from a scene manifest (JSON/YAML): each scene is a still
screenshot held on screen while VOICEVOX narrates over it, with burned-in
subtitles and a canonical ffmpeg profile. Same manifest in, same video out —
deterministic, no seeds, no timing drift. Do NOT use for live screen recording,
interactive editing, or video without narration.

## When to Use

- User wants a product demo video from existing app screenshots
- User wants a narrated slideshow / walkthrough with subtitles (.srt/.vtt)
- User asks to regenerate a video deterministically from a changed manifest
- User mentions VOICEVOX, demo videos, manifest-driven video, or 一点止め

Don't use for: real-time screen capture, trimming/editing existing videos,
non-narrated video (use ffmpeg directly), or audio-only synthesis (the
`voice` subcommand is one pass of the full pipeline).

## Prerequisites

- `uv` on PATH (`pip install uv` or the official installer)
- `ffmpeg` on PATH (mux step only)
- A running [VOICEVOX engine](https://voicevox.hiroshiba.jp/) (default
  `http://127.0.0.1:50021`) — check with `curl -s http://127.0.0.1:50021/version`
- Quick check without VOICEVOX: `uvx demo-video-generator --version`

## How to Run

All invocations go through the `terminal` tool. Install once, then run:

```bash
# validate the manifest (offline, no VOICEVOX needed)
uvx demo-video-generator manifest-check scenes.json

# full pipeline: voice -> frames -> subtitles -> ffmpeg mux
uvx demo-video-generator build scenes.json

# from a repo checkout instead of PyPI
uv run demo-video-generator build scenes.json
```

Useful build options: `--cache-dir` (wav cache, default `wav-cache`),
`--frames-dir` (default `frames`), `--out` (default `dist/demo.mp4`),
`--speaker` (VOICEVOX speaker id, default 1), `--voicevox-url`, `--fps`,
`--no-ffmpeg` (stop after frames + subtitles).

## Procedure

1. **Gather inputs** — a manifest file plus the still images it references.
   Checkable criterion: the manifest lists every image path and each file exists.
2. **Validate** — `manifest-check scenes.json` exits 0. If it fails, fix the
   manifest (it reports scene index and field); do not proceed to synthesis.
3. **Build** — `build scenes.json`. Checkable criterion: it prints
   `rendered N frame(s)`, `wrote …​.srt and …​.vtt`, and `wrote …​.mp4`.
4. **Verify output** — `ffprobe -v error -show_entries format=duration dist/demo.mp4`
   returns a duration >= the last scene end in `wav-cache/timings.json`; the
   audio track spans narration + pad for every scene (timeline-accurate mux).
5. **Cache behavior** — re-running `build` with an unchanged manifest does NOT
   re-hit VOICEVOX (SHA256 content-addressed wav cache). Changed narration text
   re-synthesizes only that scene.

## Manifest format

```json
{
  "scenes": [
    {
      "id": "intro",
      "image": "shots/intro.png",
      "title": "Intro",
      "narration": "こんにちは。これは製品デモ動画です。",
      "post_pad_sec": 0.4,
      "subtitle": "Optional, burned into the frame and written to .srt/.vtt"
    }
  ]
}
```

- `id`, `image`, `narration` are required strings; `title`, `subtitle`,
  `post_pad_sec` (number >= 0, default 0.0) are optional.
- Validation is strict: a non-string `title`/`subtitle` (e.g. YAML `title: 2024`
  parses as an int) is a `ManifestError`, not a silent crash later.
- YAML works too (`manifest-check` accepts either by file extension).
- Subtitles default to the narration text when `subtitle` is omitted.

## Pitfalls

- **3-pass separation**: network/AI steps live only in the `voice` module.
  `manifest`, `frames`, `subtitles` are pure and offline-testable. Errors from
  VOICEVOX are `VoiceError`; the CLI surfaces them as clean `Error:` messages.
- **Canonical ffmpeg profile** (`-pix_fmt yuv420p -movflags +faststart
  -colorspace bt709 ...`) lives only in `config.py` (`FFMPEG_JOIN_OUTPUT_FLAGS`).
  Do not add ad-hoc ffmpeg flags elsewhere — the profile is Safari color-safe.
- **Empty wav cache in `join`/`build`** exits with
  `wav files not found in cache ...; run voice first` — that is the expected
  error, not a bug. Run `voice` (or `build`, which synthesizes) first.
- **Mixed-format wav caches** (different rate/channels/sampwidth) are rejected
  with `VoiceError: wav format mismatch` instead of producing corrupt audio.
- **Timing JSON is schema-validated**: non-dict, missing `scenes`, missing
  string `id`, or non-numeric duration all exit with a clean `Error:` message.
- **VOICEVOX is a local engine** — if `curl http://127.0.0.1:50021/version`
  fails, start it first; the tool will not reach remote endpoints.

## Verification

- `uvx demo-video-generator manifest-check <manifest>` → exit 0
- `ffprobe -v error -show_entries format=duration <out.mp4>` → duration
  covering the full timeline (compare with `wav-cache/timings.json` last end)
- `.srt`/`.vtt` timestamps fit inside the video duration
- Repo development: `uv run pytest -m "not integration"` (52 offline tests),
  `uv run ruff check src tests`

See [the PyPI page](https://pypi.org/project/demo-video-generator/) and
[the repository](https://github.com/sunnydachs/demo-video-generator) for the
full README.
