"""記事修正サービス"""

import logging
import sys
from pathlib import Path

_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from evidence.models import EvidenceCollection
from generator.writer import ArticleWriter, _call_claude

logger = logging.getLogger(__name__)

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

修正後の記事全文をMarkdown形式で出力してください。
"""

REVISION_PROMPT_TEMPLATE = """\
## 現在の記事

{current_article}

## 修正指示

{instructions}

上記の修正指示に従って、記事全文を修正して出力してください。
"""


class RevisionService:
    """記事の修正と一般公開版の自動再生成"""

    def __init__(self, writer: ArticleWriter):
        self.writer = writer

    def revise_professional(self, article: str, instructions: str) -> str:
        """専門版記事を修正指示に基づいて修正"""
        prompt = REVISION_PROMPT_TEMPLATE.format(
            current_article=article,
            instructions=instructions,
        )

        revised = _call_claude(REVISION_SYSTEM_PROMPT, prompt)
        logger.info(f"Article revised: {len(revised)} chars")
        return revised

    def regenerate_public(self, revised_professional: str,
                         evidence: EvidenceCollection) -> str:
        """修正後の専門版から一般公開版を再生成"""
        return self.writer.generate_public_version(
            original_article=revised_professional,
            evidence=evidence,
        )
