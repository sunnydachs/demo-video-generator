"""Manifest loading, validation, and scene timeline computation.

A manifest is a JSON or YAML file with a top-level ``scenes`` array. Each scene
has an ``id``, ``image`` and ``narration``; ``title``, ``subtitle`` and
``post_pad_sec`` are optional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .config import DEFAULT_POST_PAD_SEC


class ManifestError(Exception):
    """Raised when a manifest file is malformed or fails validation."""


@dataclass
class Scene:
    id: str
    image: str
    narration: str
    title: str | None = None
    subtitle: str | None = None
    post_pad_sec: float = DEFAULT_POST_PAD_SEC

    def __post_init__(self) -> None:
        self.post_pad_sec = float(self.post_pad_sec)
        if self.subtitle is None:
            self.subtitle = self.narration
        if self.title == "":
            self.title = None


@dataclass
class Manifest:
    scenes: list = field(default_factory=list)


@dataclass
class SceneTiming:
    """Audio-first timing for one scene: [start, end) seconds on the global axis."""

    id: str
    narration: str
    subtitle: str
    start: float
    end: float
    narration_duration: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def load_manifest(path: str | Path) -> Manifest:
    p = Path(path)
    if not p.exists():
        raise ManifestError(f"manifest not found: {path}")
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:  # pragma: no cover - IO edge
        raise ManifestError(f"cannot read manifest: {path}: {exc}") from exc
    try:
        if p.suffix.lower() in (".yaml", ".yml"):
            data = yaml.safe_load(text)
        else:
            data = json.loads(text)
    except Exception as exc:
        raise ManifestError(f"cannot parse manifest {path}: {exc}") from exc

    if not isinstance(data, dict) or "scenes" not in data:
        raise ManifestError("manifest must have a top-level 'scenes' array")
    scenes = data["scenes"]
    if not isinstance(scenes, list) or len(scenes) == 0:
        raise ManifestError("'scenes' must be a non-empty array")

    model = _validate_scenes(scenes, source=str(p))
    return Manifest(scenes=model)


def json_load(text: str, path: Any = None) -> Any:
    """Backwards-compatible JSON parse helper (kept for external callers)."""
    return json.loads(text)


def _validate_scenes(raw: list, source: str) -> list[Scene]:
    seen: set[str] = set()
    out: list[Scene] = []
    for idx, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ManifestError(f"scene #{idx} in {source} is not an object")
        sid = item.get("id")
        if not isinstance(sid, str) or not sid.strip():
            raise ManifestError(f"scene #{idx} in {source}: missing non-empty 'id'")
        if sid in seen:
            raise ManifestError(f"scene #{idx} in {source}: duplicate id '{sid}'")
        seen.add(sid)

        image = item.get("image")
        if not isinstance(image, str) or not image.strip():
            raise ManifestError(f"scene '{sid}': missing 'image'")
        narration = item.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            raise ManifestError(f"scene '{sid}': missing non-empty 'narration'")

        pad = item.get("post_pad_sec", DEFAULT_POST_PAD_SEC)
        if not isinstance(pad, (int, float)) or isinstance(pad, bool) or pad < 0:
            raise ManifestError(f"scene '{sid}': 'post_pad_sec' must be a number >= 0")

        title = item.get("title")
        if title is not None and not isinstance(title, str):
            raise ManifestError(f"scene '{sid}': 'title' must be a string")
        subtitle = item.get("subtitle")
        if subtitle is not None and not isinstance(subtitle, str):
            raise ManifestError(f"scene '{sid}': 'subtitle' must be a string")
        if subtitle is None or subtitle == "":
            subtitle = narration
        out.append(
            Scene(
                id=sid,
                image=image,
                narration=narration,
                title=title,
                subtitle=subtitle,
                post_pad_sec=float(pad),
            )
        )
    return out


def build_timeline(scenes: list[Scene], durations: dict[str, float]) -> list[SceneTiming]:
    """Map narration durations (dict id -> seconds) to global scene timing blocks.

    Each scene occupies [cumulative_start, cumulative_start + narr + post_pad).
    Missing durations are treated as 0 (audio-first design: voice pass fills these).
    """
    timeline: list[SceneTiming] = []
    cursor = 0.0
    for scene in scenes:
        dur = durations.get(scene.id, 0.0)
        end = cursor + dur + scene.post_pad_sec
        timeline.append(
            SceneTiming(
                id=scene.id,
                narration=scene.narration,
                subtitle=scene.subtitle,
                start=cursor,
                end=end,
                narration_duration=dur,
            )
        )
        cursor = end
    return timeline