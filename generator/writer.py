"""記事生成エンジン - Claude APIを使用"""

import logging
from pathlib import Path

import anthropic

from ..evidence.models import EvidenceCollection
from .prompts.article_prompt import (
    ARTICLE_PROMPT_TEMPLATE,
    SYSTEM_PROMPT,
    format_evidence_for_prompt,
)

logger = logging.getLogger(__name__)


class ArticleWriter:
    """Claude APIを使用した記事生成"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        clinic_info: dict | None = None,
    ):
        self.client = anthropic.Anthropic()
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.clinic_info = clinic_info or {}

    def generate_article(
        self,
        topic: dict,
        evidence: EvidenceCollection,
        category_name: str = "",
        age_range: str = "",
    ) -> str:
        """トピックとエビデンスから記事を生成

        Args:
            topic: topics.yamlのトピック定義
            evidence: 収集されたエビデンス
            category_name: カテゴリ名
            age_range: 対象年齢

        Returns:
            Markdown形式の記事テキスト
        """
        # エビデンスを優先度順にソート
        sorted_evidence = evidence.sorted_by_priority()

        # プロンプト構築
        evidence_text = format_evidence_for_prompt(sorted_evidence)

        pico = topic.get("pico", {})
        clinic_text = self._format_clinic_info()

        prompt = ARTICLE_PROMPT_TEMPLATE.format(
            title=topic["title"],
            age_range=age_range,
            category=category_name,
            keywords=", ".join(topic.get("keywords", [])),
            pico_p=pico.get("population", ""),
            pico_i=pico.get("intervention", ""),
            pico_c=pico.get("comparison", ""),
            pico_o=pico.get("outcome", ""),
            evidence_section=evidence_text,
            clinic_info=clinic_text,
        )

        logger.info(f"Generating article for: {topic['title']}")
        logger.info(f"  Evidence count: {len(sorted_evidence)}")
        logger.info(f"  Model: {self.model}")

        # Claude API呼び出し
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )

        article_text = message.content[0].text
        logger.info(f"  Article generated: {len(article_text)} chars")

        return article_text

    def save_article(
        self,
        article_text: str,
        topic_id: str,
        output_dir: str = "output/articles",
    ) -> Path:
        """記事をファイルに保存"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        file_path = output_path / f"{topic_id}.md"
        file_path.write_text(article_text, encoding="utf-8")
        logger.info(f"  Saved to: {file_path}")
        return file_path

    def _format_clinic_info(self) -> str:
        """クリニック情報をテキストに整形"""
        if not self.clinic_info:
            return "（クリニック情報は設定されていません。一般的なCTAを使用してください。）"

        parts = []
        if self.clinic_info.get("name"):
            parts.append(f"クリニック名: {self.clinic_info['name']}")
        if self.clinic_info.get("url"):
            parts.append(f"URL: {self.clinic_info['url']}")
        if self.clinic_info.get("cta_message"):
            parts.append(f"CTAメッセージ: {self.clinic_info['cta_message']}")
        return "\n".join(parts) if parts else "（クリニック情報未設定）"
