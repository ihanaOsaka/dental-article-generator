"""バックグラウンドタスク実行マネージャー"""

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TaskResult:
    """バックグラウンドタスクの結果"""
    topic_id: str = ""
    article_title: str = ""
    instructions: str = ""  # 元の修正指示（リトライ用に保持）
    status: TaskStatus = TaskStatus.PENDING
    progress_message: str = ""
    result: Any = None
    error: str = ""
    error_reason: str = ""  # ユーザー向けのエラー原因説明
    started_at: float = 0.0
    finished_at: float = 0.0


def run_revision_in_background(
    topic_id: str,
    professional_md: str,
    instructions: str,
    pro_path: str,
    pub_path: str | None,
    task_result: TaskResult,
):
    """バックグラウンドスレッドで記事修正を実行する関数。

    task_result はメインスレッドと共有するオブジェクト。
    進捗状況と結果をここに書き込む。
    """
    try:
        task_result.status = TaskStatus.RUNNING
        task_result.started_at = time.time()
        task_result.progress_message = "専門版を修正中..."

        # 遅延インポート（スレッド内で安全に実行）
        from app.services.article_service import ArticleService
        from app.services.revision_service import RevisionService
        from evidence.models import EvidenceCollection
        from pathlib import Path

        service = ArticleService()
        try:
            revision_svc = RevisionService(service.writer)

            # ステップ1: 専門版を修正
            revised_pro = revision_svc.revise_professional(
                professional_md, instructions
            )

            # ステップ2: 一般公開版を再生成
            task_result.progress_message = "一般公開版を再生成中..."
            evidence = service.load_evidence_cache(topic_id)
            if evidence is None:
                evidence = EvidenceCollection(topic_id=topic_id)

            revised_pub = revision_svc.regenerate_public(revised_pro, evidence)

            # ステップ3: ファイルに保存
            task_result.progress_message = "保存中..."
            Path(pro_path).write_text(revised_pro, encoding="utf-8")
            if pub_path:
                pub = Path(pub_path)
                pub.parent.mkdir(parents=True, exist_ok=True)
                pub.write_text(revised_pub, encoding="utf-8")

            # 修正されたので承認を取消し（要再チェック）
            from app.state import revoke_approval
            revoke_approval(topic_id)

            task_result.status = TaskStatus.COMPLETED
            task_result.result = {
                "topic_id": topic_id,
                "professional": revised_pro,
                "public": revised_pub,
            }
            task_result.progress_message = "修正完了"
            logger.info(f"Background revision completed for {topic_id}")

        finally:
            service.close()

    except Exception as e:
        task_result.status = TaskStatus.FAILED
        task_result.error = str(e)
        # ユーザー向けのエラー原因説明
        error_str = str(e)
        if "timed out" in error_str:
            task_result.error_reason = "タイムアウト（処理に時間がかかりすぎました）。再度実行してください。"
        elif "claude" in error_str.lower() and "not found" in error_str.lower():
            task_result.error_reason = "Claude CLIが見つかりません。インストールを確認してください。"
        else:
            task_result.error_reason = "予期しないエラーが発生しました。"
        task_result.progress_message = f"エラー: {task_result.error_reason}"
        logger.error(f"Background revision failed for {topic_id}: {e}")

    finally:
        task_result.finished_at = time.time()


def start_revision_task(
    topic_id: str,
    article_title: str,
    professional_md: str,
    instructions: str,
    pro_path: str,
    pub_path: str | None,
) -> TaskResult:
    """修正タスクをバックグラウンドスレッドで開始する。

    Returns:
        TaskResult: 進捗追跡用のオブジェクト（メインスレッドからポーリング参照）
    """
    task_result = TaskResult(
        topic_id=topic_id,
        article_title=article_title,
        instructions=instructions,
    )

    thread = threading.Thread(
        target=run_revision_in_background,
        args=(topic_id, professional_md, instructions, pro_path, pub_path, task_result),
        daemon=True,
        name=f"revision-{topic_id}",
    )
    thread.start()

    return task_result
