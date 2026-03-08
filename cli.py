"""CLI インターフェース"""

import logging
import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .topics.loader import TopicLoader
from .evidence.evidence_manager import EvidenceManager
from .generator.writer import ArticleWriter
from .quality.checker import QualityChecker

console = Console()

# 設定ファイルのデフォルトパス
DEFAULT_CONFIG = Path(__file__).parent / "config" / "settings.yaml"


def load_config(config_path: str | None = None) -> dict:
    """設定ファイルを読み込む"""
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return {}


@click.group()
@click.option("--config", "-c", default=None, help="設定ファイルパス")
@click.option("--verbose", "-v", is_flag=True, help="詳細ログ出力")
@click.pass_context
def main(ctx, config, verbose):
    """歯科記事自動生成ツール - エビデンスベースの小児歯科記事を生成"""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)

    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


@main.command()
@click.pass_context
def topics(ctx):
    """トピック一覧を表示"""
    loader = TopicLoader()

    table = Table(title="記事トピック一覧")
    table.add_column("ID", style="cyan")
    table.add_column("カテゴリ", style="green")
    table.add_column("対象年齢", style="yellow")
    table.add_column("タイトル", style="white")

    for category, topic in loader.get_all_topics():
        table.add_row(
            topic["id"],
            category["name"],
            category.get("age_range", ""),
            topic["title"],
        )

    console.print(table)
    console.print(f"\n合計: {loader.get_topic_count()} トピック")


@main.command()
@click.argument("topic_id")
@click.option("--no-cache", is_flag=True, help="キャッシュを使わず再検索")
@click.pass_context
def evidence(ctx, topic_id, no_cache):
    """特定トピックのエビデンスを収集・表示"""
    config = ctx.obj["config"]
    loader = TopicLoader()

    result = loader.get_topic_by_id(topic_id)
    if not result:
        console.print(f"[red]Topic not found: {topic_id}[/red]")
        sys.exit(1)

    category, topic = result

    ev_config = config.get("evidence", {}).get("pubmed", {})
    manager = EvidenceManager(
        pubmed_api_key=ev_config.get("api_key", ""),
        max_results=ev_config.get("max_results", 20),
        date_range_years=ev_config.get("date_range_years", 10),
    )

    if no_cache:
        manager.clear_cache(topic_id)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task(f"エビデンス収集中: {topic['title']}", total=None)
        collection = manager.collect_evidence(topic)

    # 結果表示
    table = Table(title=f"エビデンス: {topic['title']}")
    table.add_column("#", style="dim")
    table.add_column("レベル", style="cyan")
    table.add_column("出典", style="green")
    table.add_column("タイトル", style="white", max_width=60)
    table.add_column("年", style="yellow")

    for i, ev in enumerate(collection.sorted_by_priority(), 1):
        table.add_row(
            str(i),
            ev.evidence_level.value,
            ev.source_type.value,
            ev.title[:60],
            str(ev.year or ""),
        )

    console.print(table)
    console.print(f"\n合計: {len(collection.evidences)} 件")
    console.print(f"高品質エビデンス: {'あり' if collection.has_high_quality() else 'なし'}")

    manager.close()


@main.command()
@click.argument("topic_id")
@click.option("--output-dir", "-o", default="output/articles", help="出力ディレクトリ")
@click.option("--no-cache", is_flag=True, help="エビデンスキャッシュを使わない")
@click.option("--skip-quality", is_flag=True, help="品質チェックをスキップ")
@click.option("--skip-public", is_flag=True, help="一般公開版の生成をスキップ")
@click.pass_context
def generate(ctx, topic_id, output_dir, no_cache, skip_quality, skip_public):
    """指定トピックの記事を生成"""
    config = ctx.obj["config"]
    loader = TopicLoader()

    result = loader.get_topic_by_id(topic_id)
    if not result:
        console.print(f"[red]Topic not found: {topic_id}[/red]")
        sys.exit(1)

    category, topic = result

    # 1. エビデンス収集
    ev_config = config.get("evidence", {}).get("pubmed", {})
    manager = EvidenceManager(
        pubmed_api_key=ev_config.get("api_key", ""),
        max_results=ev_config.get("max_results", 20),
        date_range_years=ev_config.get("date_range_years", 10),
    )

    if no_cache:
        manager.clear_cache(topic_id)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("エビデンス収集中...", total=None)
        collection = manager.collect_evidence(topic)
        progress.update(task, description="エビデンス収集完了")

    console.print(
        f"[green]エビデンス {len(collection.evidences)} 件収集[/green]"
    )

    # 2. 記事生成
    article_config = config.get("article", {}).get("llm", {})
    clinic_config = config.get("clinic", {})

    writer = ArticleWriter(
        model=article_config.get("model", "claude-sonnet-4-20250514"),
        max_tokens=article_config.get("max_tokens", 4096),
        temperature=article_config.get("temperature", 0.7),
        clinic_info=clinic_config,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("記事生成中...", total=None)
        article = writer.generate_article(
            topic=topic,
            evidence=collection,
            category_name=category["name"],
            age_range=category.get("age_range", ""),
        )
        progress.update(task, description="記事生成完了")

    # 3. 保存（専門版）
    file_path = writer.save_article(article, topic_id, output_dir)
    console.print(f"[green]専門版保存: {file_path}[/green]")

    # 4. 品質チェック（専門版）
    if not skip_quality:
        checker = QualityChecker()
        report = checker.check(article, topic_id)
        console.print(f"\n{report.summary()}")

        if not report.passed:
            console.print(
                "[yellow]品質チェックに問題があります。記事を確認してください。[/yellow]"
            )

    # 5. 一般公開版の生成
    if not skip_public:
        public_output_dir = output_dir.replace("/articles", "/articles_public")
        if public_output_dir == output_dir:
            public_output_dir = output_dir + "_public"

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("一般公開版を生成中...", total=None)
            public_article = writer.generate_public_version(
                original_article=article,
                evidence=collection,
            )
            progress.update(task, description="一般公開版の生成完了")

        public_path = writer.save_article(
            public_article, topic_id, public_output_dir
        )
        console.print(f"[green]一般公開版保存: {public_path}[/green]")

        # 品質チェック（公開版）
        if not skip_quality:
            public_report = checker.check(
                public_article, f"{topic_id}_public"
            )
            console.print(f"\n[公開版] {public_report.summary()}")

    manager.close()


@main.command()
@click.option("--output-dir", "-o", default="output/articles", help="出力ディレクトリ")
@click.option("--no-cache", is_flag=True, help="エビデンスキャッシュを使わない")
@click.option("--category", "-cat", default=None, help="カテゴリIDで絞り込み")
@click.option("--skip-public", is_flag=True, help="一般公開版の生成をスキップ")
@click.pass_context
def generate_all(ctx, output_dir, no_cache, category, skip_public):
    """全トピック（またはカテゴリ内）の記事を一括生成"""
    config = ctx.obj["config"]
    loader = TopicLoader()

    all_topics = loader.get_all_topics()
    if category:
        all_topics = [(c, t) for c, t in all_topics if c["id"] == category]

    if not all_topics:
        console.print("[red]対象トピックが見つかりません[/red]")
        sys.exit(1)

    mode = "専門版 + 一般公開版" if not skip_public else "専門版のみ"
    console.print(
        f"[bold]全 {len(all_topics)} トピックの記事を生成します（{mode}）[/bold]\n"
    )

    ev_config = config.get("evidence", {}).get("pubmed", {})
    manager = EvidenceManager(
        pubmed_api_key=ev_config.get("api_key", ""),
        max_results=ev_config.get("max_results", 20),
        date_range_years=ev_config.get("date_range_years", 10),
    )

    article_config = config.get("article", {}).get("llm", {})
    clinic_config = config.get("clinic", {})

    writer = ArticleWriter(
        model=article_config.get("model", "claude-sonnet-4-20250514"),
        max_tokens=article_config.get("max_tokens", 4096),
        temperature=article_config.get("temperature", 0.7),
        clinic_info=clinic_config,
    )

    checker = QualityChecker()
    results: list[tuple[str, bool]] = []

    public_output_dir = output_dir.replace("/articles", "/articles_public")
    if public_output_dir == output_dir:
        public_output_dir = output_dir + "_public"

    for i, (cat, topic) in enumerate(all_topics, 1):
        console.print(f"\n[bold cyan]({i}/{len(all_topics)}) {topic['title']}[/bold cyan]")

        try:
            # エビデンス収集
            if no_cache:
                manager.clear_cache(topic["id"])
            collection = manager.collect_evidence(topic)
            console.print(f"  エビデンス: {len(collection.evidences)} 件")

            # 専門版 記事生成
            article = writer.generate_article(
                topic=topic,
                evidence=collection,
                category_name=cat["name"],
                age_range=cat.get("age_range", ""),
            )

            # 専門版 保存
            file_path = writer.save_article(article, topic["id"], output_dir)
            console.print(f"  専門版保存: {file_path}")

            # 専門版 品質チェック
            report = checker.check(article, topic["id"])
            passed = report.passed
            status = "[green]PASS[/green]" if passed else "[red]FAIL[/red]"
            console.print(f"  専門版品質: {status} (Score: {report.score:.0f})")

            # 一般公開版の生成
            if not skip_public:
                public_article = writer.generate_public_version(
                    original_article=article,
                    evidence=collection,
                )
                public_path = writer.save_article(
                    public_article, topic["id"], public_output_dir
                )
                console.print(f"  公開版保存: {public_path}")

                public_report = checker.check(
                    public_article, f"{topic['id']}_public"
                )
                pub_status = (
                    "[green]PASS[/green]"
                    if public_report.passed
                    else "[red]FAIL[/red]"
                )
                console.print(
                    f"  公開版品質: {pub_status} (Score: {public_report.score:.0f})"
                )

            results.append((topic["id"], passed))

        except Exception as e:
            console.print(f"  [red]Error: {e}[/red]")
            results.append((topic["id"], False))

    # サマリー
    passed_count = sum(1 for _, p in results if p)
    console.print(f"\n[bold]完了: {passed_count}/{len(results)} トピック成功[/bold]")

    manager.close()


@main.command()
@click.argument("keyword")
def search(keyword):
    """キーワードでトピックを検索"""
    loader = TopicLoader()
    results = loader.search_topics(keyword)

    if not results:
        console.print(f"[yellow]「{keyword}」に該当するトピックが見つかりません[/yellow]")
        return

    table = Table(title=f"検索結果: 「{keyword}」")
    table.add_column("ID", style="cyan")
    table.add_column("カテゴリ", style="green")
    table.add_column("タイトル", style="white")

    for category, topic in results:
        table.add_row(topic["id"], category["name"], topic["title"])

    console.print(table)


@main.command()
@click.option("--topic-id", "-t", default=None, help="特定トピックのみクリア")
def clear_cache(topic_id):
    """エビデンスキャッシュをクリア"""
    manager = EvidenceManager()
    manager.clear_cache(topic_id)
    target = topic_id if topic_id else "全トピック"
    console.print(f"[green]キャッシュをクリアしました: {target}[/green]")
    manager.close()


if __name__ == "__main__":
    main()
