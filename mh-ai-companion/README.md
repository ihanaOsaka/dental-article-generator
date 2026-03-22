# mh-ai-companion

モンスターハンターワイルズで一緒に狩りを楽しむAI相棒「アイル」

## コンセプト

ゲーム初心者の歯科医師（41歳）が、AI相棒「アイル」と一緒にモンハンワイルズに挑む配信チャンネル。

- AIがリアルタイムで声の掛け合いをする（Gemini Live API）
- 3Dアバターが画面上で口パクしながら喋る（VRM + VSeeFace）
- ゲーム画面を見てアドバイスもできる（画面共有機能）

## アーキテクチャ

```
マイク → Gemini Live API（STT + LLM + TTS一体型）→ 音声出力
              ↑ 画面キャプチャ（Phase 3）            ↓
              │                          VB-Audio Virtual Cable
              │                                ↓
         ゲーム画面 ←────────────────── VSeeFace（リップシンク）
              │                                ↓
              └──────── OBS Studio ←───────────┘
                            ↓
                     YouTube Live 配信
```

## フェーズ

| Phase | 内容 | 状態 |
|-------|------|------|
| Phase 0 | 環境構築 | 未着手 |
| Phase 1 | 声だけの相棒（音声会話） | 未着手 |
| Phase 2 | 姿を持つ相棒（3Dアバター追加） | 未着手 |
| Phase 3 | 目を持つ相棒（画面認識追加） | 未着手 |
| Phase 4 | 記憶を持つ相棒（長期記憶） | 未着手 |

## 技術スタック

| コンポーネント | 技術 | コスト |
|---------------|------|--------|
| AI基盤 | Google Gemini 2.5 Flash（Live API） | ~¥3,200/月 |
| 音声会話 | Gemini Live API（STT+LLM+TTS一体型） | 上記に含む |
| 3Dアバター | VRoid Studio + VSeeFace | 無料 |
| オーディオ | VB-Audio Virtual Cable + VoiceMeeter Banana | 無料 |
| 配信 | OBS Studio | 無料 |
| 言語 | Python 3.10+ | — |

## セットアップ

[セットアップガイド](docs/setup-guide.md) を参照。

## ドキュメント

- [技術設計書](docs/technical-design.md) — アーキテクチャ・API・コスト分析
- [システムプロンプト設計](docs/system-prompt.md) — 「アイル」のキャラクター設定
- [セットアップガイド](docs/setup-guide.md) — Phase 1 の環境構築手順

## ライセンス

Private project.
