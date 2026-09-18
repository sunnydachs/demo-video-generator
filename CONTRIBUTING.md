# Contributing to demo-video-generator

Thanks for your interest in contributing.

## Development setup

```bash
git clone https://github.com/sunnydachs/demo-video-generator.git
cd demo-video-generator
uv sync                     # creates .venv and installs all groups
```

## Workflow

1. Fork / create a branch: `git checkout -b feature/your-feature`
2. Make your change with tests (TDD: write the failing test first when fixing logic)
3. Verify:

   ```bash
   uv run pytest -m "not integration"   # offline unit tests
   uv run ruff check src tests          # lint (line-length 100, py311)
   ```

4. Open a PR with a short description of the change

## Ground rules

- **Determinism**: a given manifest must always produce the same video. Do not add
  seeds, timestamps, locale-dependent output, or other nondeterminism to the pipeline.
- **3-pass separation**: AI/network-touching steps stay confined to `voice.py`.
  `manifest.py`, `frames.py`, `subtitles.py` are pure and offline-testable.
- **Tests**: new logic needs tests. Integration-only behavior (real VOICEVOX / ffmpeg)
  goes under the `integration` marker.
- **Canonical ffmpeg profile** lives only in `config.py` (`FFMPEG_JOIN_OUTPUT_FLAGS`).
  Do not add ad-hoc ffmpeg flags elsewhere.
- **No secrets in git**: credentials come from environment variables only. Never commit
  API keys, tokens, or `.env` files, and never bypass the gitleaks pre-commit hook
  with `--no-verify`.

## Code style

- Python 3.11+, `from __future__ import annotations`
- ruff with `line-length = 100` (see `[tool.ruff]` in `pyproject.toml`)
- Match the existing style of neighbouring modules

## Commit messages

Small, atomic commits with concise messages, e.g. `voice: pad silence by sample count`.
