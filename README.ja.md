# demo-video-generator

**静止画フレーム + VOICEVOXナレーションから、マニフェスト駆動・決定論的なデモ動画を生成するCLI。**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/sunnydachs/demo-video-generator/actions/workflows/ci.yml)

[English](README.md) | 日本語

`demo-video-generator` はシーンマニフェスト(JSON/YAML)をMP4に変換します。
各シーンは実アプリのスクリーンショットを一点止めで表示し、VOICEVOXナレーションを重ねます。
同一マニフェストから同一動画(LLMのseedやタイミングの気まぐれなし)。

## 仕組み(3パス分離パイプライン)

```
manifest ──▶ voice ──▶ frames ──▶ join ──▶ demo.mp4 + .srt + .vtt
             │           │
             │           └─ Pillow: タイトル帯・枠・字幕焼き込み
             └─ VOICEVOX HTTP API、SHA256コンテンツキャッシュ
```

- **pass 1 — manifest**: `scenes[]` (JSON/YAML) の読込・検証、タイムライン構築
- **pass 2 — voice / frames**: VOICEVOXでナレーション合成(ナレーションハッシュでキャッシュ、
  変更がなければ再叩きしない)、Pillowで1280x720 @ 30fpsのフレームを描画
- **pass 3 — join**: 正規ffmpegプロファイルでフレーム+音声をmux
  (`-pix_fmt yuv420p -movflags +faststart -colorspace bt709` — Safari色崩れ防止)、
  音声タイミングから `.srt` / `.vtt` を同時出力

## インストール

```bash
uv tool install demo-video-generator
# または
uvx demo-video-generator --help
```

Python 3.11+ 必須。実際の動画生成には [VOICEVOX](https://voicevox.hiroshiba.jp/) エンジン
(デフォルト `http://127.0.0.1:50021`)と PATH上の `ffmpeg` が必要です。

## クイックスタート

```bash
# 1. マニフェスト検証(オフライン、VOICEVOX不要)
demo-video-generator manifest-check examples/scenes.example.json

# 2. フルパイプライン: voice -> frames -> subtitles -> ffmpeg mux
demo-video-generator build examples/scenes.example.json
```

### マニフェスト形式

```json
{
  "scenes": [
    {
      "id": "intro",
      "image": "shots/intro.png",
      "title": "Intro",
      "narration": "こんにちは。これは製品デモ動画です。",
      "post_pad_sec": 0.4,
      "subtitle": "字幕(フレームに焼き込み、.srt/.vttにも出力)"
    }
  ]
}
```

| フィールド | 必須 | 説明 |
|---|---|---|
| `id` | ✓ | シーン識別子(タイミング出力で使用) |
| `image` | ✓ | 静止画フレームのパス |
| `title` | | フレームに描画するタイトル帯テキスト |
| `narration` | ✓ | VOICEVOXに送るテキスト |
| `post_pad_sec` | | ナレーション後の無音時間(デフォルト: `0.0`) |
| `subtitle` | | 焼き込み字幕テキスト(`.srt`/`.vtt`にも出力) |

YAMLも可 — `manifest-check` は拡張子で両方を受け付けます。

### サブコマンド

| コマンド | 内容 |
|---|---|
| `manifest-check` | マニフェストを合成・描画なしで検証 |
| `voice` | VOICEVOXで全ナレーション合成、`timings.json` 出力 |
| `frames` | マニフェスト+タイミングからフレーム連番を描画 |
| `join` | フレーム連番+音声をffmpegでmux |
| `build` | フルパイプライン: voice → frames → subtitles → join |

## 開発

```bash
git clone https://github.com/sunnydachs/demo-video-generator.git
cd demo-video-generator
uv sync
uv run pytest -m "not integration"   # オフライン単体テスト
uv run ruff check src tests          # lint
```

integration テスト(実VOICEVOX + ffmpeg)は `integration` マーカー付きで、
デフォルトで除外されます。VOICEVOXエンジン起動時に
`uv run pytest -m integration` で実行できます。

## ライセンス

[MIT](LICENSE)
