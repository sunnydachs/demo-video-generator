"""Offline tests for the CLI wiring."""
import json

from click.testing import CliRunner

from demo_video_generator.cli import main


def test_version_flag():
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0


def test_manifest_check_valid(tmp_path):
    manifest = {"scenes": [{"id": "a", "image": "i.png", "narration": "hi"}]}
    p = tmp_path / "m.json"
    p.write_text(json.dumps(manifest))
    runner = CliRunner()
    result = runner.invoke(main, ["manifest-check", str(p)])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_manifest_check_invalid(tmp_path):
    p = tmp_path / "m.json"
    p.write_text(json.dumps({"scenes": [{"id": "a"}]}))
    runner = CliRunner()
    result = runner.invoke(main, ["manifest-check", str(p)])
    assert result.exit_code != 0


def test_no_args_shows_help():
    runner = CliRunner()
    result = runner.invoke(main, [])
    assert result.exit_code == 1 or result.exit_code == 2
    assert "manifest-check" in result.output or "Usage" in result.output


def test_subcommands_registered():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    for name in ("manifest-check", "voice", "frames", "join", "build", "export-hyperframes"):
        assert name in result.output


def test_export_hyperframes_no_audio(tmp_path):
    """--no-audio emits a project with assets + no voice requirement (offline)."""
    import json as _json

    img = tmp_path / "shots" / "intro.png"
    img.parent.mkdir()
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    manifest = {"scenes": [{"id": "s1", "image": "shots/intro.png", "narration": "hi"}]}
    p = tmp_path / "m.json"
    p.write_text(_json.dumps(manifest))

    out = tmp_path / "proj"
    runner = CliRunner()
    result = runner.invoke(
        main, ["export-hyperframes", str(p), "--out", str(out), "--no-audio"]
    )
    assert result.exit_code == 0, result.output + (result.exception or "").__class__.__name__
    assert (out / "index.html").exists()
    assert (out / "package.json").exists()
    assert (out / "assets" / "images" / "intro.png").exists()
    html = (out / "index.html").read_text(encoding="utf-8")
    assert 'data-composition-id="main"' in html
    assert "<audio" not in html  # no narration wiring without voice


def test_export_hyperframes_with_audio_requires_wavs(tmp_path):
    """With audio enabled, a missing wav cache fails cleanly (run `voice` first)."""
    import json as _json

    img = tmp_path / "intro.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    manifest = {"scenes": [{"id": "s1", "image": "intro.png", "narration": "hi"}]}
    p = tmp_path / "m.json"
    p.write_text(_json.dumps(manifest))

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["export-hyperframes", str(p), "--out", str(tmp_path / "proj"), "--cache-dir", str(tmp_path / "wav-cache")],
    )
    assert result.exit_code != 0
    assert "voice" in result.output.lower() or "wav" in result.output.lower()