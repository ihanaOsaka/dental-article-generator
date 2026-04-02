"""記事一覧・閲覧・修正ページ"""

import sys
from pathlib import Path

import streamlit as st

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.state import (
    CATEGORY_LABELS,
    get_article_index,
    init_state,
)
from app.components.article_viewer import render_article_viewer
from app.components.revision_panel import render_revision_panel
from app.components.reference_badges import render_verification_results

init_state()

st.header("📚 記事一覧")

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

    # 記事リスト
    articles_in_cat = categories.get(selected_cat, [])
    article_options = {tid: info["title"] for tid, info in articles_in_cat}

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
st.subheader(info["title"])

# 記事を読み込み
pro_path = Path(info["professional_path"])
pub_path = Path(info["public_path"]) if info["public_path"] else None

professional_md = pro_path.read_text(encoding="utf-8") if pro_path.exists() else ""
public_md = pub_path.read_text(encoding="utf-8") if pub_path and pub_path.exists() else ""

# 記事ビューア
render_article_viewer(professional_md, public_md, key_prefix=selected_id)

# 修正パネル（固定フッター）
instructions = render_revision_panel(key_prefix=f"browse_{selected_id}")

if instructions:
    with st.status("記事を修正中...", expanded=True) as status:
        try:
            from app.services.article_service import ArticleService
            from app.services.revision_service import RevisionService
            from evidence.models import EvidenceCollection

            service = ArticleService()

            st.write("専門版を修正中...")
            revision_svc = RevisionService(service.writer)
            revised_pro = revision_svc.revise_professional(professional_md, instructions)

            st.write("一般公開版を再生成中...")
            # エビデンスキャッシュを読み込み（なければ空）
            evidence = service.load_evidence_cache(selected_id)
            if evidence is None:
                evidence = EvidenceCollection(topic_id=selected_id)

            revised_pub = revision_svc.regenerate_public(revised_pro, evidence)

            # 保存
            st.write("保存中...")
            pro_path.write_text(revised_pro, encoding="utf-8")
            if pub_path:
                pub_path.parent.mkdir(parents=True, exist_ok=True)
                pub_path.write_text(revised_pub, encoding="utf-8")

            service.close()
            status.update(label="修正完了", state="complete")

            st.success("記事を修正しました。ページを再読み込みすると反映されます。")
            st.rerun()

        except Exception as e:
            status.update(label="エラー", state="error")
            st.error(f"修正中にエラーが発生しました: {e}")
