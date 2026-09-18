"""Subtitle (.srt / .vtt) generation from timing blocks.

Timing blocks are ``(start_sec, end_sec, text)`` tuples aligned to the global
timeline computed by manifest.build_timeline.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

TimingBlock = tuple[float, float, str]


def _hms_millis(seconds: float) -> tuple[int, int, int, int]:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return h, m, s, ms


def format_srt_cue(start: float, end: float) -> str:
    h, m, s, ms = _hms_millis(start)
    eh, em, es, ems = _hms_millis(end)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d} --> {eh:02d}:{em:02d}:{es:02d},{ems:03d}"


def format_vtt_cue(start: float, end: float) -> str:
    h, m, s, ms = _hms_millis(start)
    eh, em, es, ems = _hms_millis(end)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d} --> {eh:02d}:{em:02d}:{es:02d}.{ems:03d}"


def build_srt(blocks: Iterable[TimingBlock], start_index: int = 1) -> str:
    lines: list[str] = []
    for i, (start, end, text) in enumerate(blocks, start=start_index):
        lines.append(str(i))
        lines.append(format_srt_cue(start, end))
        lines.append(str(text))
        lines.append("")
    return "\n".join(lines)


def build_vtt(blocks: Iterable[TimingBlock]) -> str:
    out = ["WEBVTT", ""]
    for start, end, text in blocks:
        out.append(format_vtt_cue(start, end))
        out.append(str(text))
        out.append("")
    return "\n".join(out)


def blocks_from_timeline(timeline) -> Sequence[TimingBlock]:
    """Convert manifest SceneTiming list into (start, end, subtitle) blocks."""
    return [(t.start, t.end, t.subtitle) for t in timeline]