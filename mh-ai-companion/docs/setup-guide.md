# セットアップガイド — Phase 1（声だけの相棒）

Phase 1 のゴール: **モンハンをプレイしながら、アイルと声で会話できる状態にする。**

---

## 前提条件

- Windows 10/11（64bit）
- Python 3.10 以上
- マイク（USB推奨）
- ヘッドフォン（スピーカーだとAI音声がマイクに回り込む）

---

## Step 1: Google Cloud / Gemini API キー取得

### 1-1. Google AI Studio でAPIキーを作成

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. Googleアカウントでログイン
3. 左メニュー「Get API key」→「Create API key」
4. 表示されたAPIキーをコピーして安全な場所に保存

### 1-2. 無料枠の確認

| 項目 | 無料枠 |
|------|--------|
| リクエスト数 | 1日100回（Free tier） |
| RPM | 5 |

Phase 1のテスト・開発には十分。本番利用（配信）は Tier 1（課金設定のみで自動昇格）で RPM 150 に上がる。

---

## Step 2: Python 環境構築

### 2-1. リポジトリのクローン

```bash
git clone https://github.com/ihanaOsaka/mh-ai-companion.git
cd mh-ai-companion
```

### 2-2. 仮想環境の作成

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux
```

### 2-3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 2-4. 環境変数の設定

```bash
copy .env.example .env
```

`.env` ファイルを開き、APIキーを設定:

```
GEMINI_API_KEY=your_api_key_here
```

---

## Step 3: 動作確認

### 3-1. 最小テスト（テキストのみ）

```bash
python src/main.py --mode text
```

テキスト入力で会話ができることを確認。

### 3-2. 音声テスト

```bash
python src/main.py --mode voice
```

マイクに向かって話しかけ、アイルが音声で返答することを確認。

### 3-3. モンハンと同時起動テスト

1. モンスターハンターワイルズを起動（ウィンドウモードまたはボーダーレス推奨）
2. 別ウィンドウで `python src/main.py --mode voice` を実行
3. ゲームをプレイしながらアイルと会話できるか確認

---

## トラブルシューティング

### マイクが認識されない

```bash
python -c "import pyaudio; p = pyaudio.PyAudio(); [print(f'{i}: {p.get_device_info_by_index(i)[\"name\"]}') for i in range(p.get_device_count())]"
```

使用するマイクのデバイスインデックスを確認し、`.env` に設定:

```
AUDIO_INPUT_DEVICE=1  # マイクのインデックス番号
```

### PyAudio のインストールに失敗する（Windows）

```bash
pip install pipwin
pipwin install pyaudio
```

または、非公式ビルド済みwheelを使用:

```bash
pip install PyAudio-0.2.14-cp310-cp310-win_amd64.whl
```

### API接続エラー

1. APIキーが正しいか確認
2. インターネット接続を確認
3. 無料枠の上限に達していないか確認（1日100回）

### 音声が聞こえない

1. Pythonの出力デバイスが正しいか確認
2. ヘッドフォン/スピーカーの音量を確認
3. Windows のサウンド設定でデフォルトの出力デバイスを確認

---

## 次のステップ

Phase 1 が動いたら [Phase 2: 3Dアバター追加](technical-design.md) へ進む。

Phase 2 で追加するソフトウェア:
- VRoid Studio（モデル作成）
- VSeeFace（アバター表示）
- VB-Audio Virtual Cable（オーディオルーティング）
- VoiceMeeter Banana（オーディオミキシング）
- OBS Studio（配信合成）
