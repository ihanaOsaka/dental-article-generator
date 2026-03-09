"""自由入力トピックから構造化メタデータを生成"""

import json
import logging
import re
import time

import anthropic

logger = logging.getLogger(__name__)

TOPIC_GENERATION_PROMPT = """\
あなたは小児歯科・歯科全般の専門家です。
以下の自由入力トピックから、エビデンス検索と記事生成に必要な構造化メタデータをJSON形式で生成してください。

## 自由入力トピック
{user_input}

## 出力形式（厳密にこのJSON構造を守ってください）
```json
{{
  "id": "custom_{slug}",
  "title": "記事タイトル（日本語、40文字以内）",
  "keywords": ["キーワード1", "キーワード2", "キーワード3"],
  "search_terms": {{
    "en": ["English search term 1", "English search term 2"],
    "ja": ["日本語検索語1", "日本語検索語2"]
  }},
  "pico": {{
    "population": "対象（例: 6-12歳の小児）",
    "intervention": "介入・テーマ（例: シーラント処置）",
    "comparison": "比較対照（例: 未処置）",
    "outcome": "アウトカム（例: う蝕発生率）"
  }},
  "category_name": "カテゴリ名（例: 乳児期、幼児期、学童期、中高生、妊娠期、矯正、一般）",
  "age_range": "対象年齢（例: 6〜12歳）"
}}
```

## 注意
- idの{slug}部分は英語のスネークケースで、トピックの内容を端的に表す名前にしてください
- search_termsのenは、PubMed検索に使える英語の医学用語にしてください
- PICOの各フィールドは、トピックに応じて適切に設定してください
- JSON以外のテキストは出力しないでください
"""


class TopicGenerator:
    """自由入力テキストから構造化されたトピックメタデータを生成"""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic()
        self.model = model

    def generate(self, user_input: str) -> dict:
        """自由入力からトピックメタデータを生成

        Args:
            user_input: ユーザーが入力したトピックの自由記述

        Returns:
            topics.yamlと同じ構造のdict + category_name, age_range
        """
        prompt = TOPIC_GENERATION_PROMPT.format(
            user_input=user_input,
            slug="xxx",
        )

        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = message.content[0].text

        # JSONを抽出
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            raise ValueError("Claude APIからJSONを取得できませんでした")

        topic_data = json.loads(json_match.group())

        # ID にタイムスタンプ付加して一意にする
        base_id = topic_data.get("id", f"custom_{int(time.time())}")
        if not base_id.startswith("custom_"):
            base_id = f"custom_{base_id}"
        topic_data["id"] = base_id

        logger.info(f"Generated topic metadata: {topic_data['id']} - {topic_data['title']}")
        return topic_data
