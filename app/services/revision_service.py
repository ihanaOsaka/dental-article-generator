"""記事修正サービス

修正フローは新規作成フロー (article_service.py) のアーキテクチャに準拠:
  1. 修正指示を分析し、追加エビデンスが必要か判定
  2. 必要なら EvidenceManager で追加収集 → 既存キャッシュとマージ
  3. エビデンス付きプロンプトで記事を修正
  4. リンク検証・修復
  5. 一般公開版を再生成
"""

import json
import logging
import re
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from evidence.evidence_manager import EvidenceManager
from evidence.models import EvidenceCollection
from generator.writer import ArticleWriter, _call_claude
from generator.prompts.article_prompt import format_evidence_for_prompt
from app.services.link_validator import LinkValidator

logger = logging.getLogger(__name__)

# --- プロンプト定義 ---

ANALYSIS_SYSTEM_PROMPT = """\
あなたは小児歯科の専門家です。
記事の修正指示を分析し、追加のエビデンス検索が必要かどうかを判定してください。
JSON以外のテキストは出力しないでください。
"""

ANALYSIS_PROMPT_TEMPLATE = """\
以下の修正指示について、PubMed等での追加エビデンス検索が必要かどうかを判定してください。

## 現在の記事タイトル
{article_title}

## 修正指示
{instructions}

## 判定基準
- エビデンスの追加・補強・最新化を求める指示 → 検索が必要
- 文体・構成・表現の変更、セクション削除、CTA変更など → 検索は不要

## 出力形式（厳密にこのJSON構造を守ってください）
```json
{{
  "needs_evidence": true または false,
  "reason": "判定理由（日本語、1文）",
  "search_terms": {{
    "en": ["English search term 1", "English search term 2"],
    "ja": ["日本語検索語1"]
  }},
  "keywords": ["キーワード1", "キーワード2"]
}}
```

検索が不要な場合、search_terms と keywords は空配列にしてください。
"""

REVISION_SYSTEM_PROMPT = """\
あなたは小児歯科の専門知識を持つ医療ライターです。
既存の歯科記事に対するユーザーの修正指示を受け、記事を修正します。

## 修正ルール
1. ユーザーの修正指示に従って記事を変更してください
2. 指示されていない部分は原文をそのまま維持してください
3. 医学的正確さを維持してください
4. エビデンスの引用は変更・削除しないでください（追加は可）
5. 全体の構成と参考文献セクションは維持してください
6. です・ます調を維持してください
7. 既存のMarkdownリンク [テキスト](URL) はすべて維持してください
8. エビデンスの追加が必要な場合は「参考エビデンス」セクションから引用してください
9. URLを推測・創作しないでください。提供されたURLのみを使用してください

## 出力形式
- 修正後の記事全文をMarkdown形式で出力してください
- 記事本文のみを出力してください。作業説明・方針・前置き・あとがき等は一切含めないでください
- 最初の出力文字は記事の見出し（#）で始めてください
"""

REVISION_PROMPT_TEMPLATE = """\
## 現在の記事

{current_article}

## 参考エビデンス

{evidence_section}

## 修正指示

{instructions}

上記の修正指示に従って、記事全文を修正して出力してください。
エビデンスの追加が必要な場合は「参考エビデンス」セクションの情報とURLを使用してください。
"""

REVISION_PROMPT_TEMPLATE_NO_EVIDENCE = """\
## 現在の記事

{current_article}

## 修正指示

{instructions}

上記の修正指示に従って、記事全文を修正して出力してください。
"""


def _strip_preamble(text: str) -> str:
    """記事本文の前に付いた説明文を除去する

    Claude が「〜リライトします。」等の前置きを付けた場合、
    最初の見出し（#）より前のテキストを除去する。
    """
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("#"):
            return "\n".join(lines[i:])
    # 見出しがない場合はそのまま返す
    return text


def _validate_article_output(revised: str, original: str) -> None:
    """修正結果が記事の体裁であることを検証"""
    if len(revised) < len(original) * 0.3:
        raise RuntimeError(
            f"修正結果が短すぎます（{len(revised)}文字 / 元記事{len(original)}文字）。"
            "記事ではない出力が返された可能性があります。元の記事は変更されていません。"
        )

    if "#" not in revised:
        raise RuntimeError(
            "修正結果にMarkdown見出しが含まれていません。"
            "記事ではない出力が返された可能性があります。元の記事は変更されていません。"
        )

    permission_keywords = ["許可をお願い", "許可をいただ", "許可が必要", "not permitted"]
    if any(kw in revised for kw in permission_keywords) and len(revised) < len(original) * 0.5:
        raise RuntimeError(
            "記事ではない出力が返されました。元の記事は変更されていません。"
        )


class RevisionService:
    """記事の修正と一般公開版の自動再生成

    新規作成フローと同じく、エビデンスはPython側で収集し
    プロンプトに埋め込む。Claude のWeb検索ツールには依存しない。
    """

    def __init__(self, writer: ArticleWriter, evidence_manager: EvidenceManager,
                 link_validator: LinkValidator):
        self.writer = writer
        self.evidence_manager = evidence_manager
        self.link_validator = link_validator

    def analyze_instructions(self, article_title: str, instructions: str) -> dict:
        """修正指示を分析し、追加エビデンス検索が必要かを判定

        Returns:
            dict: {"needs_evidence": bool, "reason": str,
                   "search_terms": {"en": [...], "ja": [...]}, "keywords": [...]}
        """
        prompt = ANALYSIS_PROMPT_TEMPLATE.format(
            article_title=article_title,
            instructions=instructions,
        )

        response = _call_claude(ANALYSIS_SYSTEM_PROMPT, prompt)

        json_match = re.search(r'\{[\s\S]*\}', response)
        if not json_match:
            logger.warning("修正指示の分析でJSONを取得できませんでした。エビデンス不要として続行。")
            return {"needs_evidence": False, "reason": "分析失敗", "search_terms": {"en": [], "ja": []}, "keywords": []}

        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            logger.warning("修正指示の分析JSONパースに失敗。エビデンス不要として続行。")
            return {"needs_evidence": False, "reason": "パース失敗", "search_terms": {"en": [], "ja": []}, "keywords": []}

    def collect_additional_evidence(
        self,
        analysis: dict,
        existing_evidence: EvidenceCollection,
    ) -> EvidenceCollection:
        """追加エビデンスを収集し、既存エビデンスとマージ

        Args:
            analysis: analyze_instructions の戻り値
            existing_evidence: 既存のエビデンスキャッシュ

        Returns:
            マージ済みの EvidenceCollection
        """
        # 分析結果からダミーの topic dict を構築して EvidenceManager に渡す
        topic_for_search = {
            "id": f"{existing_evidence.topic_id}_revision",
            "title": "",
            "keywords": analysis.get("keywords", []),
            "search_terms": analysis.get("search_terms", {"en": [], "ja": []}),
        }

        # 一時的にキャッシュを使わず新規収集する
        self.evidence_manager.clear_cache(topic_for_search["id"])
        new_collection = self.evidence_manager.collect_evidence(topic_for_search)

        # 既存エビデンスとマージ（重複はPMIDで除去）
        merged = EvidenceCollection(topic_id=existing_evidence.topic_id)
        existing_pmids = set()

        for ev in existing_evidence.evidences:
            merged.evidences.append(ev)
            if ev.pmid:
                existing_pmids.add(ev.pmid)

        for ev in new_collection.evidences:
            if ev.pmid and ev.pmid in existing_pmids:
                continue
            merged.evidences.append(ev)
            if ev.pmid:
                existing_pmids.add(ev.pmid)

        logger.info(
            f"Evidence merged: {len(existing_evidence.evidences)} existing + "
            f"{len(new_collection.evidences)} new → {len(merged.evidences)} total"
        )

        # 一時キャッシュを掃除
        self.evidence_manager.clear_cache(topic_for_search["id"])

        return merged

    def revise_professional(
        self,
        article: str,
        instructions: str,
        evidence: EvidenceCollection | None = None,
    ) -> str:
        """専門版記事をエビデンス付きで修正

        Args:
            article: 現在の記事テキスト
            instructions: ユーザーの修正指示
            evidence: マージ済みエビデンス（Noneの場合エビデンスなしで修正）
        """
        if evidence and evidence.evidences:
            evidence_text = format_evidence_for_prompt(evidence.sorted_by_priority())
            prompt = REVISION_PROMPT_TEMPLATE.format(
                current_article=article,
                evidence_section=evidence_text,
                instructions=instructions,
            )
        else:
            prompt = REVISION_PROMPT_TEMPLATE_NO_EVIDENCE.format(
                current_article=article,
                instructions=instructions,
            )

        revised = _call_claude(REVISION_SYSTEM_PROMPT, prompt)
        revised = _strip_preamble(revised)
        logger.info(f"Article revised: {len(revised)} chars")

        _validate_article_output(revised, article)

        return revised

    def validate_links(self, article: str):
        """修正後の記事のリンクを検証・修復

        Returns:
            tuple: (fixed_article, link_report)
        """
        report = self.link_validator.validate_and_fix(article)
        return report.fixed_article, report

    def regenerate_public(self, revised_professional: str,
                         evidence: EvidenceCollection) -> str:
        """修正後の専門版から一般公開版を再生成"""
        return self.writer.generate_public_version(
            original_article=revised_professional,
            evidence=evidence,
        )
