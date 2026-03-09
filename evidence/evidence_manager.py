"""エビデンス収集の統合マネージャー"""

import json
import logging
import os
from pathlib import Path

from .models import Evidence, EvidenceCollection, EvidenceLevel
from .pubmed import PubMedSearcher
from .web_evidence import WebEvidenceSearcher

logger = logging.getLogger(__name__)


class EvidenceManager:
    """複数のエビデンスソースを統合管理"""

    def __init__(
        self,
        pubmed_api_key: str = "",
        max_results: int = 20,
        date_range_years: int = 10,
        cache_dir: str = "data/evidence_cache",
    ):
        # .env の NCBI_API_KEY を優先、なければ引数を使用
        api_key = pubmed_api_key or os.environ.get("NCBI_API_KEY", "")
        self.pubmed = PubMedSearcher(
            api_key=api_key,
            max_results=max_results,
            date_range_years=date_range_years,
        )
        self.web = WebEvidenceSearcher()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def collect_evidence(self, topic: dict) -> EvidenceCollection:
        """トピックに対するエビデンスを全ソースから収集

        Args:
            topic: topics.yamlのトピック定義（dict）

        Returns:
            EvidenceCollection: 収集されたエビデンス
        """
        topic_id = topic["id"]
        logger.info(f"Collecting evidence for: {topic_id} - {topic['title']}")

        collection = EvidenceCollection(topic_id=topic_id)

        # キャッシュ確認
        cached = self._load_cache(topic_id)
        if cached:
            logger.info(f"Using cached evidence for {topic_id}")
            return cached

        # 1. 公的機関のエビデンス（Tier 1）
        keywords = topic.get("keywords", [])
        web_evidences = self.web.search_all(keywords)
        collection.evidences.extend(web_evidences)
        logger.info(f"  Web sources: {len(web_evidences)} found")

        # 2. PubMed検索（Tier 2-3）
        search_terms = topic.get("search_terms", {})
        en_terms = search_terms.get("en", [])

        if en_terms:
            # まずSR/メタアナリシスを検索
            sr_filters = ["Systematic Review", "Meta-Analysis"]
            sr_evidences = self.pubmed.search_for_topic(en_terms, filters=sr_filters)
            collection.evidences.extend(sr_evidences)
            logger.info(f"  PubMed SR/MA: {len(sr_evidences)} found")

            # SR/MAが少なければ、ガイドラインとRCTも検索
            if len(sr_evidences) < 3:
                broader_filters = [
                    "Systematic Review",
                    "Meta-Analysis",
                    "Randomized Controlled Trial",
                    "Practice Guideline",
                ]
                broader_evidences = self.pubmed.search_for_topic(
                    en_terms, filters=broader_filters
                )
                # 重複除去
                existing_pmids = {e.pmid for e in collection.evidences if e.pmid}
                for ev in broader_evidences:
                    if ev.pmid and ev.pmid not in existing_pmids:
                        collection.evidences.append(ev)
                        existing_pmids.add(ev.pmid)
                logger.info(f"  PubMed broader: {len(broader_evidences)} found (after dedup)")

        # キャッシュ保存
        self._save_cache(topic_id, collection)

        logger.info(
            f"  Total evidence for {topic_id}: {len(collection.evidences)} "
            f"(High quality: {collection.has_high_quality()})"
        )
        return collection

    def _cache_path(self, topic_id: str) -> Path:
        return self.cache_dir / f"{topic_id}.json"

    def _save_cache(self, topic_id: str, collection: EvidenceCollection) -> None:
        """エビデンスをJSON形式でキャッシュ保存"""
        cache_data = {
            "topic_id": collection.topic_id,
            "evidences": [
                {
                    "title": e.title,
                    "authors": e.authors,
                    "year": e.year,
                    "journal": e.journal,
                    "doi": e.doi,
                    "pmid": e.pmid,
                    "abstract": e.abstract,
                    "evidence_level": e.evidence_level.value,
                    "source_type": e.source_type.value,
                    "url": e.url,
                    "key_findings": e.key_findings,
                    "summary_ja": e.summary_ja,
                }
                for e in collection.evidences
            ],
        }
        self._cache_path(topic_id).write_text(
            json.dumps(cache_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_cache(self, topic_id: str) -> EvidenceCollection | None:
        """キャッシュからエビデンスを読み込み"""
        cache_file = self._cache_path(topic_id)
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            collection = EvidenceCollection(topic_id=data["topic_id"])
            for ev_data in data["evidences"]:
                collection.evidences.append(
                    Evidence(
                        title=ev_data["title"],
                        authors=ev_data["authors"],
                        year=ev_data["year"],
                        journal=ev_data["journal"],
                        doi=ev_data["doi"],
                        pmid=ev_data["pmid"],
                        abstract=ev_data["abstract"],
                        evidence_level=EvidenceLevel(ev_data["evidence_level"]),
                        source_type=_parse_source_type(ev_data["source_type"]),
                        url=ev_data["url"],
                        key_findings=ev_data["key_findings"],
                        summary_ja=ev_data["summary_ja"],
                    )
                )
            return collection
        except Exception as e:
            logger.warning(f"Cache load failed for {topic_id}: {e}")
            return None

    def clear_cache(self, topic_id: str | None = None) -> None:
        """キャッシュをクリア"""
        if topic_id:
            cache_file = self._cache_path(topic_id)
            if cache_file.exists():
                cache_file.unlink()
        else:
            for f in self.cache_dir.glob("*.json"):
                f.unlink()

    def close(self):
        self.pubmed.close()
        self.web.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def _parse_source_type(value: str):
    """文字列からSourceTypeを安全にパース"""
    from .models import SourceType

    for st in SourceType:
        if st.value == value:
            return st
    return SourceType.OTHER
