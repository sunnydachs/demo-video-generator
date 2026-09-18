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
    for name in ("manifest-check", "voice", "frames", "join", "build"):
        assert name in result.output