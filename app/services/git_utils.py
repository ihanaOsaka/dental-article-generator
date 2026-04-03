"""Git操作ユーティリティ — 未コミット記事の検出とコミット・プッシュ"""

import logging
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).parent.parent.parent

# コミット対象のディレクトリ（記事・エビデンス・ステータスのみ）
_TRACKED_PATHS = [
    "output/articles",
    "output/articles_public",
    "data/evidence_cache",
    "data/article_status.json",
    "data/ada_topics.csv",
]


def _run_git(*args: str) -> tuple[bool, str]:
    """gitコマンドを実行し、(成功, 出力) を返す"""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip()
            return False, err or output
        return True, output
    except Exception as e:
        return False, str(e)


def get_uncommitted_articles() -> list[str]:
    """未コミットの記事関連ファイルを取得"""
    ok, output = _run_git("status", "--short")
    if not ok or not output:
        return []

    uncommitted = []
    for line in output.splitlines():
        # " M output/articles/foo.md" or "?? output/articles/foo.md"
        status = line[:2].strip()
        filepath = line[3:].strip().strip('"')
        # 対象パスのみ
        if any(filepath.startswith(p) for p in _TRACKED_PATHS):
            uncommitted.append(filepath)

    return uncommitted


def commit_and_push() -> tuple[bool, str]:
    """記事関連ファイルをコミット＆プッシュ

    Returns:
        (成功, メッセージ)
    """
    uncommitted = get_uncommitted_articles()
    if not uncommitted:
        return True, "コミット対象の変更はありません"

    # ステージング
    for path in _TRACKED_PATHS:
        full = _PROJECT_ROOT / path
        if full.exists():
            _run_git("add", path)

    # コミットメッセージ生成
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    n_files = len(uncommitted)

    # 新規と変更を分類
    new_articles = [f for f in uncommitted if f.startswith("output/articles/")
                    and not f.startswith("output/articles_public/")]
    msg = f"記事更新: {n_files}件の変更を保存（{now}）"
    if new_articles:
        names = [Path(f).stem for f in new_articles[:3]]
        msg = f"記事更新: {', '.join(names)}{'他' if len(new_articles) > 3 else ''}（{now}）"

    ok, output = _run_git(
        "commit", "-m", msg,
    )
    if not ok:
        if "nothing to commit" in output:
            return True, "コミット対象の変更はありません"
        return False, f"コミット失敗: {output}"

    # プッシュ
    ok, output = _run_git("push", "origin", "HEAD")
    if not ok:
        return False, f"プッシュ失敗: {output}"

    return True, f"✅ {n_files}件の変更をコミット・プッシュしました"
