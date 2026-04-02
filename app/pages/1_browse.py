"""記事一覧・閲覧・修正ページ"""

import sys
import time
from pathlib import Path

import streamlit as st

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.state import (
    CATEGORY_LABELS,
    get_article_index,
    init_state,
    is_approved,
    approve_article,
    load_article_status,
    change_article_category,
)
from app.components.article_viewer import render_article_viewer
from app.components.revision_panel import render_revision_panel
from app.components.reference_badges import render_verification_results
from app.services.background_task import TaskStatus, start_revision_task

init_state()

st.header("📚 記事一覧")

# --- バックグラウンド修正タスクの管理 ---
# revision_tasks: dict[topic_id, TaskResult]
if "revision_tasks" not in st.session_state:
    st.session_state.revision_tasks = {}
# 旧形式からの移行
if "revision_task" in st.session_state:
    old = st.session_state.pop("revision_task")
    if old is not None and hasattr(old, "topic_id") and old.topic_id:
        st.session_state.revision_tasks[old.topic_id] = old

# 記事インデックスを取得
article_index = get_article_index()

if not article_index:
    st.warning("記事が見つかりません。`output/articles/` ディレクトリを確認してください。")
    st.stop()

# カテゴリでグループ化
categories = {}
for topic_id, info in article_index.items():
    cat = info["category"]
    categories.setdefault(cat, []).append((topic_id, info))

# サイドバーで記事選択
with st.sidebar:
    st.subheader("記事を選択")

    # カテゴリフィルタ
    available_cats = list(categories.keys())
    cat_labels = [CATEGORY_LABELS.get(c, c) for c in available_cats]

    selected_cat = st.selectbox(
        "カテゴリ",
        available_cats,
        format_func=lambda x: CATEGORY_LABELS.get(x, x),
    )

    # 記事リスト（承認ステータス付き）
    articles_in_cat = categories.get(selected_cat, [])
    _status = load_article_status()
    article_options = {}
    for tid, inf in articles_in_cat:
        icon = "✅" if _status.get(tid, {}).get("approved") else "⏳"
        article_options[tid] = f"{icon} {inf['title']}"

    if article_options:
        selected_id = st.radio(
            "記事",
            list(article_options.keys()),
            format_func=lambda x: article_options[x],
        )
        st.session_state.selected_article_id = selected_id
    else:
        st.info("このカテゴリに記事はありません")
        st.stop()

# メインエリア：記事表示
selected_id = st.session_state.selected_article_id
if not selected_id or selected_id not in article_index:
    st.info("左のサイドバーから記事を選択してください")
    st.stop()

info = article_index[selected_id]

# 承認ステータス・カテゴリ変更
_approved = is_approved(selected_id)
_current_cat = info["category"]

col_status, col_cat_label, col_cat_select, col_cat_btn = st.columns([2, 1, 1, 1])

with col_status:
    if _approved:
        st.caption("✅ この記事はチェック済みです")
    else:
        if st.button("✅ OK（チェック完了）", key=f"approve_{selected_id}",
                     type="primary"):
            approve_article(selected_id)
            st.rerun()
        st.caption("⏳ 未チェック")

with col_cat_label:
    st.caption("カテゴリ変更")

with col_cat_select:
    _cat_options = list(CATEGORY_LABELS.keys())
    _cat_idx = _cat_options.index(_current_cat) if _current_cat in _cat_options else 0
    new_cat = st.selectbox(
        "カテゴリ変更",
        _cat_options,
        index=_cat_idx,
        format_func=lambda x: CATEGORY_LABELS.get(x, x),
        key=f"cat_change_{selected_id}",
        label_visibility="collapsed",
    )

with col_cat_btn:
    if new_cat != _current_cat:
        if st.button("変更", key=f"cat_apply_{selected_id}"):
            new_id = change_article_category(selected_id, new_cat)
            st.session_state.selected_article_id = new_id
            st.rerun()

# 記事を読み込み
pro_path = Path(info["professional_path"])
pub_path = Path(info["public_path"]) if info["public_path"] else None

professional_md = pro_path.read_text(encoding="utf-8") if pro_path.exists() else ""
public_md = pub_path.read_text(encoding="utf-8") if pub_path and pub_path.exists() else ""

# 記事ビューア
render_article_viewer(professional_md, public_md, key_prefix=selected_id)

# 修正パネル（固定フッター）— この記事が修正中の場合のみ無効化
_current_task = st.session_state.revision_tasks.get(selected_id)
_is_this_article_revising = (
    _current_task is not None and _current_task.status == TaskStatus.RUNNING
)
instructions = render_revision_panel(
    key_prefix=f"browse_{selected_id}",
    disabled=_is_this_article_revising,
)

if instructions:
    # バックグラウンドでタスクを開始
    task_result = start_revision_task(
        topic_id=selected_id,
        article_title=info["title"],
        professional_md=professional_md,
        instructions=instructions,
        pro_path=str(pro_path),
        pub_path=str(pub_path) if pub_path else None,
    )
    st.session_state.revision_tasks[selected_id] = task_result
    st.rerun()
