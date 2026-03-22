# CLAUDE.md

## プロジェクト概要

モンスターハンターワイルズのAI相棒「アイル」を実装するプロジェクト。
Gemini Live API + VRM 3Dアバター + OBS配信の構成。

## 技術スタック

- Python 3.10+
- Google Gemini 2.5 Flash（Live API / Multimodal Live API）
- google-genai SDK
- PyAudio（音声入出力）
- VRM + VSeeFace（3Dアバター表示）

## ディレクトリ構成

```
mh-ai-companion/
├── README.md
├── CLAUDE.md
├── .gitignore
├── requirements.txt
├── src/
│   ├── main.py              # エントリーポイント
│   ├── gemini_client.py      # Gemini Live API接続
│   ├── audio.py              # 音声入出力管理
│   ├── screen_capture.py     # 画面キャプチャ（Phase 3）
│   └── config.py             # 設定管理
├── prompts/
│   └── airu.txt              # アイルのシステムプロンプト
└── docs/
    ├── technical-design.md   # 技術設計書
    ├── system-prompt.md      # キャラクター設計
    └── setup-guide.md        # セットアップ手順
```

## 開発ルール

- コードもコメントも日本語OKだが、変数名・関数名は英語
- APIキーは `.env` に格納、絶対にコミットしない
- 音声ファイル（.wav, .mp3）、VRMモデル（.vrm）はコミットしない
- Phase番号をコミットメッセージに含める（例: `[Phase1] 音声ループ実装`）

## コマンド

```bash
# 依存関係インストール
pip install -r requirements.txt

# 実行
python src/main.py

# 環境変数
cp .env.example .env
# GEMINI_API_KEY を設定
```

## Gemini Live API について

- WebSocket接続でリアルタイム音声会話を行う
- `google-genai` SDK の `client.aio.live.connect()` を使用
- モデル: `gemini-2.5-flash` (Live API対応)
- 音声入出力フォーマット: PCM 16bit, 16kHz or 24kHz
- 公式デモ: Google の gaming-assistant-demo-app を参考にする
