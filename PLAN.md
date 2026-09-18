# demo-video-generator — ビルド計画

## 目的
静止画フレーム方式（実アプリのスクリーンショットを一点止めで並べ、VOICEVOXナレーションに合わせる）で
製品デモ動画を生成する。マニフェスト駆動・3パス分離・決定論で、公開GitHubリポジトリまで持っていく（公開はしない）。

## 設計原則（ベストプラクティス: GhostMoviePlay / Argo を参照）
1. **3パス分離・AIを扱う段を閉じ込める**
   - pass1 `manifest` 読込・検証
   - pass2 `voice` VOICEVOX 音声生成 + SHA256 コンテンツキャッシュ
   - pass2 `frames` Pillow でタイトル帯・枠・字幕を画像に焼く
   - pass3 `ffmpeg` 画像連番+音声を結合、字幕 srt/vtt も出力
2. **決定論**: 同一 manifest から同一動画（seed/依存の気まぐれを入れない）
3. **マニフェスト形式**: scenes[] を JSON/YAML で定義
   - image / title / narration / post_pad_sec / subtitle
4. **音声キャッシュ**: narration の SHA256 をキーに wav 保存。変更がなければ VOICEVOX を再叩きしない
5. **字幕出力**: 音声タイミングから .srt / .vtt を同時生成
6. **ffmpeg 標準フラグ**: `-pix_fmt yuv420p` / `-movflags +faststart` / `-colorspace bt709` 系（Safari色崩れ防止）
7. **TDD**: pytest でロジック検証。オフライン（VOICEVOX 必須のものは integration に分離）

## リポジトリ構成
```
projects/demo-video-generator/
  pyproject.toml        # uv 管理
  README.md
  AGENTS.md             # repo-template 流用
  .github/              # CI + gitleaks (repo-template 習わし)
  .gitignore
  src/demo_video_generator/
    __init__.py
    cli.py              # click/argparse CLI
    manifest.py         # マニフェスト読込・検証
    voice.py            # VOICEVOX 合成 + キャッシュ
    frames.py           # Pillow フレーム合成
    subtitles.py        # srt/vtt 出力
    config.py           # ffmpeg 標準フラグ集約
    ffmpegjoin.py       # 結合・mux
  tests/
    test_manifest.py
    test_voice.py
    test_frames.py
    test_subtitles.py
    test_ffmpeg.py
  examples/
    scenes.example.json
```

## タスク
1. repo スケルトン作成 (git init, テンプレ基盤, pyproject)
2. manifest 読込・検証 (TDD)
3. voice: VOICEVOX + キャッシュ (TDD)
4. frames: Pillow 合成 (TDD)
5. ffmpeg: 結合 + 字幕 (TDD, integration)
6. CLI 配線
7. README / AGENTS / CI / gitleaks
8. サンプル実走（finance-ai-assistant の周りで動作確認）
9. Hermes Skill として包装