"""全記事をエビデンス収集から再生成するスクリプト

プロトコル:
1. topics.yaml から全トピックを読み込み
2. 各トピックについてエビデンスを収集（PubMed + Web）→ キャッシュ保存
3. エビデンスURLを含むプロンプトで Claude Code CLI を使って記事生成
4. 専門版・一般公開版の両方を生成
5. リンクの到達確認

Usage:
    python scripts/regenerate_all.py                  # 全記事再生成
    python scripts/regenerate_all.py --topic infant_snack  # 特定トピックのみ
    python scripts/regenerate_all.py --evidence-only  # エビデンス収集のみ（記事生成なし）
    python scripts/regenerate_all.py --skip-evidence  # エビデンス収集スキップ（キャッシュ使用）
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

# .env から環境変数を読み込み
env_file = project_root / ".env"
if env_file.exists():
    for line in env_file.read_text().strip().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())

import yaml

from evidence.evidence_manager import EvidenceManager
from generator.writer import ArticleWriter
from generator.prompts.article_prompt import format_evidence_for_prompt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_topics() -> list[dict]:
    """topics.yaml から全トピックを読み込み"""
    topics_path = project_root / "topics" / "topics.yaml"
    data = yaml.safe_load(topics_path.read_text(encoding="utf-8"))

    topics = []
    for category in data["categories"]:
        for topic in category["topics"]:
            topic["_category_name"] = category["name"]
            topic["_age_range"] = category["age_range"]
            topics.append(topic)

    return topics


def collect_all_evidence(topics: list[dict], force: bool = False) -> dict:
    """全トピックのエビデンスを収集"""
    manager = EvidenceManager()

    collections = {}
    for i, topic in enumerate(topics, 1):
        topic_id = topic["id"]
        logger.info(f"[{i}/{len(topics)}] Collecting evidence for: {topic_id}")

        if force:
            manager.clear_cache(topic_id)

        collection = manager.collect_evidence(topic)
        collections[topic_id] = collection

        logger.info(
            f"  -> {len(collection.evidences)} evidences "
            f"(URLs: {sum(1 for e in collection.evidences if e.url)})"
        )

    manager.close()
    return collections


def generate_articles(
    topics: list[dict],
    collections: dict,
    config: dict,
    target_topic: str | None = None,
):
    """記事を生成"""
    clinic_config = config.get("clinic", {})
    writer = ArticleWriter(clinic_info=clinic_config)

    for i, topic in enumerate(topics, 1):
        topic_id = topic["id"]

        if target_topic and topic_id != target_topic:
            continue

        collection = collections.get(topic_id)
        if not collection:
            logger.warning(f"[{i}/{len(topics)}] No evidence for {topic_id}, skipping")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"[{i}/{len(topics)}] Generating: {topic_id} - {topic['title']}")
        logger.info(f"  Evidence: {len(collection.evidences)} items")

        # URLを持つエビデンスを表示
        for ev in collection.evidences:
            if ev.url:
                logger.info(f"    URL: {ev.url}")

        try:
            # 専門版生成
            logger.info("  Generating professional version...")
            professional = writer.generate_article(
                topic=topic,
                evidence=collection,
                category_name=topic["_category_name"],
                age_range=topic["_age_range"],
            )

            # 保存
            writer.save_article(professional, topic_id, "output/articles")
            logger.info(f"  Professional version saved ({len(professional)} chars)")

            # 一般公開版生成
            logger.info("  Generating public version...")
            public = writer.generate_public_version(
                original_article=professional,
                evidence=collection,
            )

            writer.save_article(public, topic_id, "output/articles_public")
            logger.info(f"  Public version saved ({len(public)} chars)")

            # リンク数を確認
            import re
            pro_links = len(re.findall(r'\[.+?\]\(https?://', professional))
            pub_links = len(re.findall(r'\[.+?\]\(https?://', public))
            logger.info(f"  Links: professional={pro_links}, public={pub_links}")

        except Exception as e:
            logger.error(f"  ERROR generating {topic_id}: {e}")
            continue

        # API制限を考慮して少し待つ
        time.sleep(2)


def main():
    parser = argparse.ArgumentParser(description="全記事を再生成")
    parser.add_argument("--topic", help="特定のトピックIDのみ処理")
    parser.add_argument("--evidence-only", action="store_true", help="エビデンス収集のみ")
    parser.add_argument("--skip-evidence", action="store_true", help="エビデンス収集をスキップ")
    parser.add_argument("--force-evidence", action="store_true", help="キャッシュを無視してエビデンス再収集")
    args = parser.parse_args()

    # 設定読み込み
    config_path = project_root / "config" / "settings.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}

    # トピック読み込み
    topics = load_topics()
    logger.info(f"Loaded {len(topics)} topics")

    if args.topic:
        matching = [t for t in topics if t["id"] == args.topic]
        if not matching:
            logger.error(f"Topic '{args.topic}' not found")
            sys.exit(1)
        topics = matching

    # エビデンス収集
    if not args.skip_evidence:
        logger.info("\n" + "=" * 60)
        logger.info("Phase 1: Evidence Collection")
        logger.info("=" * 60)
        collections = collect_all_evidence(topics, force=args.force_evidence)
    else:
        logger.info("Skipping evidence collection (using cache)")
        manager = EvidenceManager()
        collections = {}
        for topic in topics:
            cached = manager._load_cache(topic["id"])
            if cached:
                collections[topic["id"]] = cached
            else:
                logger.warning(f"No cache for {topic['id']}")
        manager.close()

    if args.evidence_only:
        logger.info("\nEvidence collection complete. Skipping article generation.")
        return

    # 記事生成
    logger.info("\n" + "=" * 60)
    logger.info("Phase 2: Article Generation (Claude Code CLI)")
    logger.info("=" * 60)
    generate_articles(topics, collections, config, args.topic)

    logger.info("\n" + "=" * 60)
    logger.info("All done!")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
