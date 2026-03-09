"""記事生成パイプラインのオーケストレーション"""

import logging
import sys
from pathlib import Path

import yaml

# プロジェクトルートをパスに追加
_project_root = Path(__file__).parent.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

from evidence.evidence_manager import EvidenceManager
from evidence.models import EvidenceCollection
from generator.writer import ArticleWriter
from quality.checker import QualityChecker
from app.state import GenerationResult
from app.services.reference_verifier import ReferenceVerifier
from app.services.link_validator import LinkValidator

logger = logging.getLogger(__name__)

MAX_LINK_FIX_RETRIES = 2  # リンク修復の最大リトライ回数


def load_config() -> dict:
    """設定ファイルを読み込み"""
    config_path = _project_root / "config" / "settings.yaml"
    if config_path.exists():
        return yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return {}


class ArticleService:
    """Streamlitアプリ用の記事生成パイプライン"""

    def __init__(self, config: dict | None = None):
        self.config = config or load_config()

        ev_config = self.config.get("evidence", {}).get("pubmed", {})
        self.manager = EvidenceManager(
            pubmed_api_key=ev_config.get("api_key", ""),
            max_results=ev_config.get("max_results", 20),
            date_range_years=ev_config.get("date_range_years", 10),
        )

        article_config = self.config.get("article", {}).get("llm", {})
        clinic_config = self.config.get("clinic", {})

        self.writer = ArticleWriter(
            model=article_config.get("model", "claude-sonnet-4-20250514"),
            max_tokens=article_config.get("max_tokens", 4096),
            temperature=article_config.get("temperature", 0.7),
            clinic_info=clinic_config,
        )

        self.checker = QualityChecker()
        self.verifier = ReferenceVerifier()
        self.link_validator = LinkValidator()

    def generate_from_topic(
        self,
        topic: dict,
        category_name: str = "",
        age_range: str = "",
        progress_callback=None,
    ) -> GenerationResult:
        """フルパイプライン:
        エビデンス収集 → 記事生成 → リンク検証・修復 → 一般公開版 → 品質チェック

        リンク検証で整合性エラーがあれば、エビデンス再収集から最大2回リトライ。
        """

        def progress(msg):
            if progress_callback:
                progress_callback(msg)

        topic_id = topic["id"]

        for attempt in range(1, MAX_LINK_FIX_RETRIES + 2):
            retry_label = f"（試行 {attempt}/{MAX_LINK_FIX_RETRIES + 1}）" if attempt > 1 else ""

            # 1. エビデンス収集
            progress(f"エビデンスを収集中...{retry_label}")
            if attempt > 1:
                self.manager.clear_cache(topic_id)
            collection = self.manager.collect_evidence(topic)
            progress(f"エビデンス {len(collection.evidences)} 件収集完了")

            # 2. 専門版記事生成
            progress(f"専門版記事を生成中...{retry_label}")
            professional = self.writer.generate_article(
                topic=topic,
                evidence=collection,
                category_name=category_name,
                age_range=age_range,
            )

            # 3. リンク検証・修復
            progress("参考文献リンクを検証・修復中...")
            link_report = self.link_validator.validate_and_fix(professional)

            valid = sum(1 for r in link_report.results if r.status == "valid")
            fixed = link_report.fixed_count
            invalid = link_report.invalid_count
            total = len(link_report.results)

            progress(
                f"リンク検証: {total}件中 "
                f"有効{valid} / 修復{fixed} / 問題{invalid}"
            )

            # 修復済みの記事を使用
            professional = link_report.fixed_article

            # 整合性エラーでリトライが必要か判断
            if link_report.needs_re_research and attempt <= MAX_LINK_FIX_RETRIES:
                progress(
                    f"整合性エラーを検出。エビデンス再収集からリトライします "
                    f"({attempt}/{MAX_LINK_FIX_RETRIES})"
                )
                continue
            else:
                break

        # 4. 一般公開版生成（検証済みの専門版から）
        progress("一般公開版を生成中...")
        public = self.writer.generate_public_version(
            original_article=professional,
            evidence=collection,
        )

        # 5. 一般公開版のリンクも検証
        progress("一般公開版のリンクを検証中...")
        public_link_report = self.link_validator.validate_and_fix(public)
        public = public_link_report.fixed_article

        # 6. 品質チェック
        progress("品質チェック中...")
        report = self.checker.check(professional, topic_id)

        # 7. 参考文献の詳細検証（既存の verifier も実行）
        verification = self.verifier.verify_article(professional)

        progress("完了")

        return GenerationResult(
            topic_id=topic_id,
            professional=professional,
            public=public,
            quality_score=report.score,
            verification_results=verification,
        )

    def validate_existing_article(self, article_text: str,
                                  progress_callback=None):
        """既存記事のリンクを検証・修復

        Returns:
            tuple: (fixed_article, link_report)
        """
        def progress(msg):
            if progress_callback:
                progress_callback(msg)

        progress("リンクを検証中...")
        report = self.link_validator.validate_and_fix(article_text)

        valid = sum(1 for r in report.results if r.status == "valid")
        fixed = report.fixed_count
        total = len(report.results)

        progress(f"検証完了: {total}件中 有効{valid} / 修復{fixed}")
        return report.fixed_article, report

    def save_result(self, result: GenerationResult,
                    articles_dir: str = "output/articles",
                    public_dir: str = "output/articles_public"):
        """生成結果をファイルに保存"""
        self.writer.save_article(result.professional, result.topic_id, articles_dir)
        self.writer.save_article(result.public, result.topic_id, public_dir)

    def load_evidence_cache(self, topic_id: str) -> EvidenceCollection | None:
        """エビデンスキャッシュを読み込み"""
        return self.manager._load_cache(topic_id)

    def close(self):
        self.manager.close()
        self.verifier.close()
        self.link_validator.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
