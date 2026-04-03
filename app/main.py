"""歯科記事ジェネレーター — Streamlit アプリ"""

import sys
from pathlib import Path

import streamlit as st

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.state import init_state

st.set_page_config(
    page_title="歯科記事ジェネレーター",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_state()

# ページ定義
browse_page = st.Page("pages/1_browse.py", title="記事一覧", icon="📚")
create_page = st.Page("pages/2_create.py", title="新規作成", icon="✏️")
verify_page = st.Page("pages/3_verify.py", title="リンク検証", icon="🔗")

pg = st.navigation([browse_page, create_page, verify_page])

# サイドバー
with st.sidebar:
    st.title("🦷 歯科記事ジェネレーター")
    st.caption("エビデンスベースの歯科記事を自動生成")

    # バックグラウンドタスクの進捗表示（複数タスク対応）
    from app.services.background_task import TaskStatus, start_revision_task
    import time

    _tasks = st.session_state.get("revision_tasks", {})
    _to_remove = []
    _to_retry = []
    for _tid, _task in _tasks.items():
        _title = _task.article_title or _tid
        if _task.status == TaskStatus.RUNNING:
            elapsed = int(time.time() - _task.started_at)
            st.info(f"⏳ {_title}（{elapsed}秒）")
        elif _task.status == TaskStatus.COMPLETED:
            st.success(f"✅ {_title}")
            if st.button("クリア", key=f"sb_clear_{_tid}"):
                _to_remove.append(_tid)
        elif _task.status == TaskStatus.FAILED:
            with st.expander(f"❌ {_title}", expanded=True):
                st.caption(_task.error_reason or "原因不明のエラー")
                if _task.instructions:
                    st.text_area(
                        "送信した修正指示",
                        value=_task.instructions,
                        height=60,
                        disabled=True,
                        key=f"sb_instr_{_tid}",
                    )
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("再実行", key=f"sb_retry_{_tid}"):
                        _to_retry.append(_tid)
                with col2:
                    if st.button("閉じる", key=f"sb_dismiss_{_tid}"):
                        _to_remove.append(_tid)

    # 再実行処理
    for _tid in _to_retry:
        _old = st.session_state.revision_tasks[_tid]
        # 記事インデックスからパスを再取得
        from app.state import get_article_index
        _idx = get_article_index()
        if _tid in _idx:
            _info = _idx[_tid]
            _pro_path = _info["professional_path"]
            _pub_path = _info["public_path"]
            _pro_md = Path(_pro_path).read_text(encoding="utf-8")
            new_task = start_revision_task(
                topic_id=_tid,
                article_title=_old.article_title,
                professional_md=_pro_md,
                instructions=_old.instructions,
                pro_path=_pro_path,
                pub_path=_pub_path,
            )
            st.session_state.revision_tasks[_tid] = new_task
    if _to_retry:
        st.rerun()

    if _to_remove:
        for _tid in _to_remove:
            st.session_state.revision_tasks.pop(_tid, None)
        st.rerun()

    st.divider()

    # --- 未コミット記事の通知 & コミット・プッシュボタン ---
    from app.services.git_utils import get_uncommitted_articles, commit_and_push

    _uncommitted = get_uncommitted_articles()
    if _uncommitted:
        with st.expander(f"📦 未保存の変更（{len(_uncommitted)}件）", expanded=False):
            for f in _uncommitted[:10]:
                st.caption(f"• {f}")
            if len(_uncommitted) > 10:
                st.caption(f"  …他 {len(_uncommitted) - 10} 件")
            if st.button("コミット＆プッシュ", key="sb_commit_push",
                         type="primary"):
                with st.spinner("保存中..."):
                    ok, msg = commit_and_push()
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)

    st.divider()

pg.run()
