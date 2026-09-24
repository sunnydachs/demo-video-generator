"""Export a HyperFrames project from the manifest + timeline.

Pure generation (offline-testable): build_index_html produces the HTML string;
write_project copies media assets (images, narration wavs) into the trivial
``assets/`` layout a HyperFrames scaffold expects. Deterministic: same manifest
+ timings in, same project out.
"""

from __future__ import annotations

import html
import json
import os
import shutil
from pathlib import Path

from .config import HEIGHT, WIDTH
from .manifest import Scene, SceneTiming

_PACKAGE_JSON = """{
  "name": "%s",
  "private": true,
  "type": "module",
  "scripts": {
    "preview": "npx --yes hyperframes@latest preview",
    "check": "npx --yes hyperframes@latest check",
    "render": "npx --yes hyperframes@latest render"
  }
}
"""

# Per-mode GSAP motion (from/to pairs) applied to the scene's bg wrapper.
# Gentle magnitudes matching the Ken Burns renderer (config.py).
_MOTION: dict = {
    "zoom_in": ('{ scale: 1.0 }', '{ scale: 1.12 }'),
    "zoom_out": ('{ scale: 1.12 }', '{ scale: 1.0 }'),
    "pan_left": ('{ scale: 1.1, x: "3%" }', '{ scale: 1.1, x: "-3%" }'),
    "pan_right": ('{ scale: 1.1, x: "-3%" }', '{ scale: 1.1, x: "3%" }'),
    "pan_up": ('{ scale: 1.1, y: "3%" }', '{ scale: 1.1, y: "-3%" }'),
    "pan_down": ('{ scale: 1.1, y: "-3%" }', '{ scale: 1.1, y: "3%" }'),
}


def _dest_basename(workspace: list, path: Path) -> str:
    """Unique asset basename in ``workspace``, de-duplicating same-name files."""
    name = path.name
    if name not in workspace:
        workspace.append(name)
        return name
    stem, suffix = os.path.splitext(name)
    i = 2
    while f"{stem}-{i}{suffix}" in workspace:
        i += 1
    unique = f"{stem}-{i}{suffix}"
    workspace.append(unique)
    return unique


def build_index_html(
    scenes: list[Scene],
    *,
    canvas_w: int = WIDTH,
    canvas_h: int = HEIGHT,
    fps: int | None = None,
    total_duration: float | None = None,
    timeline: list[SceneTiming] | None = None,
    include_audio: bool = True,
) -> str:
    """Build the HyperFrames index.html as a string (pure, offline-testable).

    Scenes become timed clips; narrations become <audio> elements with ids.
    When ``timeline`` (or no explicit ``total_duration``) is absent the root
    duration falls back to the sum of each scene's ``post_pad_sec``.
    ``include_audio=False`` emits no <audio> elements at all.
    """
    if timeline is None:
        timeline = []
    timeline_by_id = {t.id: t for t in timeline}
    if total_duration is None:
        if timeline:
            total_duration = max(t.end for t in timeline)
        else:
            total_duration = sum(s.post_pad_sec for s in scenes) or 10.0
    total_duration = float(total_duration)

    scene_clips: list[str] = []
    audio_elems: list[str] = []
    gsap_inits: list[str] = []

    for scene, idx in zip(scenes, range(len(scenes))):
        sid = scene.id
        esc_title = html.escape(scene.title or scene.narration.splitlines()[0][:80])
        timing = timeline_by_id.get(sid)
        start = 0.0 if timing is None else float(timing.start)
        duration = scene.post_pad_sec if timing is None else float(timing.duration)
        img_rel = f"assets/images/{Path(scene.image).name}"
        clips = f'''
      <section id="sc-{sid}" class="clip" data-start="{start:.3f}" data-duration="{duration:.3f}" data-track-index="{idx}">
        <div
          id="bg-{sid}"
          class="scene-bg"
          style="background-image: url('{img_rel}');"
        ></div>
        <div id="title-{sid}" class="scene-title">{esc_title}</div>
      </section>'''
        scene_clips.append(clips)
        if include_audio:
            audio_elems.append(
                f'<audio id="audio-{sid}" src="assets/audio/{sid}.wav" data-start="{start:.3f}" data-duration="{duration:.3f}">'
            )
        gsap_inits.append(
            f'      tl.fromTo("#sc-{sid}", '
            f'{{ opacity: 0, y: 36 }}, '
            f'{{ opacity: 1, y: 0, duration: 0.6, ease: "power2.out" }}, {start:.3f});'
        )
        # Ken Burns camera work: animate the INNER bg wrapper (a child of the
        # clip), never the .clip element itself (lint: gsap_animates_clip_element).
        motion = _MOTION.get(scene.animation)
        if motion is not None and duration > 0:
            # e.g. from: { scale: 1.0 }  to: scale: 1.12 (props only)
            to_props = motion[1].strip()[1:-1].strip()  # "{ scale: 1.12 }" -> "scale: 1.12"
            gsap_inits.append(
                f'      tl.fromTo("#bg-{sid}", {motion[0]}, '
                f'{{ {to_props}, duration: {duration:.3f}, ease: "none" }}, {start:.3f});'
            )

    scenes_block = "".join(scene_clips)
    audio_block = "".join(audio_elems)
    gsap_block = "\n".join(gsap_inits)

    return f'''<!doctype html>
<html lang="ja">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={canvas_w}, height={canvas_h}" />
    <title>demo-video-generator export</title>
    <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
    <style>
      html, body {{
        margin: 0;
        width: {canvas_w}px;
        height: {canvas_h}px;
        overflow: hidden;
        background: #0b0f14;
        font-family: Inter, ui-sans-serif, system-ui, sans-serif;
      }}
      #root {{
        position: relative;
        width: 100%;
        height: 100%;
        overflow: hidden;
      }}
      .clip {{
        position: absolute;
        inset: 0;
      }}
      .scene-bg {{
        position: absolute;
        inset: 0;
        background-size: contain;
        background-repeat: no-repeat;
        background-position: center;
        background-color: #0b0f14;
      }}
      .scene-title {{
        position: absolute;
        left: 5%;
        right: 5%;
        bottom: 6%;
        color: #f4f4f5;
        font-size: 56px;
        font-weight: 600;
        letter-spacing: -0.02em;
        text-shadow: 0 2px 20px rgba(0,0,0,0.75);
        line-height: 1.25;
      }}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-width="{canvas_w}"
      data-height="{canvas_h}"
      data-duration="{total_duration}"
    >{scenes_block}
{audio_block}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
{gsap_block}
      window.__timelines["main"] = tl;
      tl.seek(0);
    </script>
  </body>
</html>
'''


def write_project(
    out_dir: Path,
    index_html: str,
    scenes: list[Scene],
    *,
    base_dir: Path,
    wavs: dict | None = None,
) -> dict:
    """Write the generated project: index.html, package.json, copied assets.

    ``wavs`` maps scene id -> source wav path; each is copied under
    ``assets/audio/<id>.wav``. Returns a per-scene mapping of emitted asset paths.
    Copies are content-overwritten only when the source is newer/different.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "index.html").write_text(index_html, encoding="utf-8")
    (out_dir / "package.json").write_text(_PACKAGE_JSON % out_dir.name, encoding="utf-8")

    (out_dir / "assets" / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "assets" / "audio").mkdir(parents=True, exist_ok=True)

    mapping: dict = {}
    # images: preserve basename but de-dupe on collision via a copy index
    used: list = []
    for scene in scenes:
        src = Path(base_dir) / scene.image
        if not src.is_absolute():
            src = (base_dir / src).resolve()
        if not src.exists():
            raise FileNotFoundError(f"image not found: {src}")
        base_name = src.name
        # de-dupe same-basename different sources
        candidate = base_name
        i = 2
        while candidate in used:
            candidate = f"{src.stem}-{i}{src.suffix}"
            i += 1
        used.append(candidate)
        dest = out_dir / "assets" / "images" / candidate
        shutil.copy2(src, dest)
        mapping[scene.id] = {"image": f"assets/images/{candidate}"}
    # narration wavs
    for scene in scenes:
        entry = mapping.get(scene.id, {})
        wav = (wavs or {}).get(scene.id)
        if wav is None:
            mapping[scene.id] = entry
            continue
        wav = Path(base_dir) / wav
        if not wav.is_absolute():
            wav = (base_dir / wav).resolve()
        if not (wav.exists() and wav.is_file()):
            mapping[scene.id] = entry
            continue
        dest = out_dir / "assets" / "audio" / f"{scene.id}.wav"
        shutil.copy2(wav, dest)
        entry["audio"] = f"assets/audio/{scene.id}.wav"
        mapping[scene.id] = entry
    # hyperframes.json marker
    (out_dir / "hyperframes.json").write_text(
        json.dumps(
            {
                "name": out_dir.name,
                "version": "1.0.0",
                "composition": "index.html",
                "canvas": {"width": WIDTH, "height": HEIGHT},
                "annotation": "generated by demo-video-generator export-hyperframes",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return mapping
