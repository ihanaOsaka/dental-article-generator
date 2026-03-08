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

logger = logging.getLogger(__name__)


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

    def generate_from_topic(
        self,
        topic: dict,
        category_name: str = "",
        age_range: str = "",
        progress_callback=None,
    ) -> GenerationResult:
        """フルパイプライン: エビデンス収集 → 記事生成 → 公開版 → 検証"""

        def progress(msg):
            if progress_callback:
                progress_callback(msg)

        topic_id = topic["id"]

        # 1. エビデンス収集
        progress("エビデンスを収集中...")
        collection = self.manager.collect_evidence(topic)
        progress(f"エビデンス {len(collection.evidences)} 件収集完了")

        # 2. 専門版記事生成
        progress("専門版記事を生成中...")
        professional = self.writer.generate_article(
            topic=topic,
            evidence=collection,
            category_name=category_name,
            age_range=age_range,
        )

        # 3. 一般公開版生成
        progress("一般公開版を生成中...")
        public = self.writer.generate_public_version(
            original_article=professional,
            evidence=collection,
        )

        # 4. 品質チェック
        progress("品質チェック中...")
        report = self.checker.check(professional, topic_id)

        # 5. 参考文献リンク検証
        progress("参考文献リンクを検証中...")
        verification = self.verifier.verify_article(professional)

        progress("完了")

        return GenerationResult(
            topic_id=topic_id,
            professional=professional,
            public=public,
            quality_score=report.score,
            verification_results=verification,
        )

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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
