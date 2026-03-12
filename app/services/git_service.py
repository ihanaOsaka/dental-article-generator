"""記事変更の自動 git commit & push"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_project_root = Path(__file__).parent.parent.parent


def auto_commit_and_push(
    files: list[str],
    message: str,
) -> bool:
    """変更されたファイルを git add → commit → push する

    Args:
        files: コミットするファイルパスのリスト（プロジェクトルートからの相対パス or 絶対パス）
        message: コミットメッセージ

    Returns:
        True: 成功, False: 失敗（ログに記録するが例外は投げない）
    """
    try:
        cwd = str(_project_root)

        # git add
        result = subprocess.run(
            ["git", "add"] + files,
            capture_output=True, text=True, cwd=cwd, encoding="utf-8",
        )
        if result.returncode != 0:
            logger.warning(f"git add failed: {result.stderr.strip()}")
            return False

        # 変更があるか確認
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            capture_output=True, text=True, cwd=cwd,
        )
        if result.returncode == 0:
            logger.info("No staged changes, skipping commit.")
            return True

        # git commit
        result = subprocess.run(
            ["git", "commit", "-m", message],
            capture_output=True, text=True, cwd=cwd, encoding="utf-8",
        )
        if result.returncode != 0:
            logger.warning(f"git commit failed: {result.stderr.strip()}")
            return False

        logger.info(f"Committed: {message}")

        # git push
        result = subprocess.run(
            ["git", "push"],
            capture_output=True, text=True, cwd=cwd, encoding="utf-8",
            timeout=30,
        )
        if result.returncode != 0:
            logger.warning(f"git push failed: {result.stderr.strip()}")
            return False

        logger.info("Pushed to remote.")
        return True

    except Exception as e:
        logger.warning(f"Auto commit/push failed: {e}")
        return False
