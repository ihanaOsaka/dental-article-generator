"""記事生成エンジン - Claude Code CLIを使用"""

import logging
import os
import subprocess
import sys
from pathlib import Path

try:
    from ..evidence.models import EvidenceCollection
    from .prompts.article_prompt import (
        ARTICLE_PROMPT_TEMPLATE,
        PUBLIC_VERSION_PROMPT_TEMPLATE,
        PUBLIC_VERSION_SYSTEM_PROMPT,
        SYSTEM_PROMPT,
        format_evidence_for_prompt,
    )
except ImportError:
    from evidence.models import EvidenceCollection
    from generator.prompts.article_prompt import (
        ARTICLE_PROMPT_TEMPLATE,
        PUBLIC_VERSION_PROMPT_TEMPLATE,
        PUBLIC_VERSION_SYSTEM_PROMPT,
        SYSTEM_PROMPT,
        format_evidence_for_prompt,
    )

logger = logging.getLogger(__name__)


def _find_claude_cmd() -> str:
    """Claude Code CLI の実行パスを取得"""
    import shutil

    # Windows: claude.cmd を優先
    if sys.platform == "win32":
        # npm グローバルインストール先
        npm_path = Path(os.environ.get("APPDATA", "")) / "npm" / "claude.cmd"
        if npm_path.exists():
            return str(npm_path)

    # PATH上のclaude
    found = shutil.which("claude")
    if found:
        return found

    raise FileNotFoundError("Claude Code CLI (claude) が見つかりません。npm install -g @anthropic-ai/claude-code でインストールしてください。")


def _call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
    """Claude Code CLIを呼び出してテキストを生成"""
    full_prompt = f"""以下のシステム指示に従って、ユーザーの依頼に応えてください。

## システム指示
{system_prompt}

## ユーザーの依頼
{user_prompt}"""

    claude_cmd = _find_claude_cmd()

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)  # ネスト実行を許可
    env["PYTHONIOENCODING"] = "utf-8"

    # Windows: stdinのエンコーディング問題を回避するためファイル経由で渡す
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.txt', delete=False, encoding='utf-8'
    ) as f:
        f.write(full_prompt)
        prompt_file = f.name

    try:
        # ファイルからstdinにパイプ
        with open(prompt_file, 'r', encoding='utf-8') as pf:
            result = subprocess.run(
                [claude_cmd, "-p", "--output-format", "text"],
                stdin=pf,
                capture_output=True,
                text=True,
                timeout=300,  # 5分タイムアウト
                env=env,
                encoding='utf-8',
            )
    finally:
        os.unlink(prompt_file)

    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown error"
        raise RuntimeError(f"Claude CLI error (exit {result.returncode}): {error_msg}")

    output = result.stdout.strip()
    if not output:
        raise RuntimeError("Claude CLI returned empty output")

    return output


class ArticleWriter:
    """Claude Code CLIを使用した記事生成"""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        clinic_info: dict | None = None,
    ):
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
        """トピックとエビデンスから記事を生成"""
        sorted_evidence = evidence.sorted_by_priority()
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

        article_text = _call_claude(SYSTEM_PROMPT, prompt, self.max_tokens)
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

    def generate_public_version(
        self,
        original_article: str,
        evidence: EvidenceCollection,
    ) -> str:
        """専門版記事から一般公開版を生成"""
        sorted_evidence = evidence.sorted_by_priority()
        evidence_text = format_evidence_for_prompt(sorted_evidence)
        clinic_text = self._format_clinic_info()

        prompt = PUBLIC_VERSION_PROMPT_TEMPLATE.format(
            original_article=original_article,
            evidence_section=evidence_text,
            clinic_info=clinic_text,
        )

        logger.info("Generating public version...")

        public_text = _call_claude(
            PUBLIC_VERSION_SYSTEM_PROMPT, prompt, self.max_tokens * 2
        )
        logger.info(f"  Public version generated: {len(public_text)} chars")

        return public_text

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
