"""参考文献リンク検証ページ"""

import sys
from pathlib import Path

import streamlit as st

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.state import get_article_index, CATEGORY_LABELS, init_state
from app.components.reference_badges import render_verification_results

init_state()

st.header("🔗 参考文献リンク検証")
st.caption("記事内の参考文献リンク（DOI, PubMed, URL）が有効かどうかを検証します")

article_index = get_article_index()
if not article_index:
    st.warning("記事が見つかりません")
    st.stop()

# 記事選択
col1, col2 = st.columns([2, 1])

with col1:
    selected_id = st.selectbox(
        "検証する記事を選択",
        list(article_index.keys()),
        format_func=lambda x: f"[{CATEGORY_LABELS.get(article_index[x]['category'], '')}] {article_index[x]['title']}",
    )

with col2:
    version = st.radio("バージョン", ["専門版", "一般公開版"], horizontal=True)

if st.button("検証を実行", type="primary"):
    info = article_index[selected_id]

    if version == "専門版":
        file_path = Path(info["professional_path"])
    else:
        if info["public_path"]:
            file_path = Path(info["public_path"])
        else:
            st.error("一般公開版が見つかりません")
            st.stop()

    if not file_path.exists():
        st.error(f"ファイルが見つかりません: {file_path}")
        st.stop()

    article_text = file_path.read_text(encoding="utf-8")

    with st.spinner("参考文献リンクを検証中..."):
        try:
            from app.services.reference_verifier import ReferenceVerifier
            verifier = ReferenceVerifier()
            results = verifier.verify_article(article_text)
            verifier.close()

            cache_key = f"{selected_id}_{version}"
            st.session_state.verification_results[cache_key] = results
        except Exception as e:
            st.error(f"検証中にエラーが発生しました: {e}")
            st.stop()

# 結果表示
for key_suffix in ["専門版", "一般公開版"]:
    cache_key = f"{selected_id}_{key_suffix}"
    if cache_key in st.session_state.get("verification_results", {}):
        results = st.session_state.verification_results[cache_key]
        st.subheader(f"検証結果: {key_suffix}")
        render_verification_results(results)

# 一括検証
st.divider()
st.subheader("一括検証")
st.caption("全記事の参考文献リンクを一括で検証します（時間がかかります）")

if st.button("全記事を一括検証"):
    from app.services.reference_verifier import ReferenceVerifier

    verifier = ReferenceVerifier()
    progress = st.progress(0)
    status_text = st.empty()
    total = len(article_index)
    all_results = {}

    for i, (topic_id, info) in enumerate(article_index.items()):
        status_text.text(f"検証中: {info['title']} ({i+1}/{total})")
        progress.progress((i + 1) / total)

        file_path = Path(info["professional_path"])
        if file_path.exists():
            try:
                text = file_path.read_text(encoding="utf-8")
                results = verifier.verify_article(text)
                all_results[topic_id] = results
            except Exception:
                all_results[topic_id] = []

    verifier.close()
    status_text.text("一括検証完了")

    # サマリー表示
    st.subheader("一括検証サマリー")
    for topic_id, results in all_results.items():
        info = article_index[topic_id]
        valid = sum(1 for r in results if r.status == "valid")
        total_refs = len(results)

        if total_refs == 0:
            st.write(f"🔍 **{info['title']}** — リンクなし")
        elif valid == total_refs:
            st.write(f"✅ **{info['title']}** — {total_refs}/{total_refs} 有効")
        else:
            st.write(f"❌ **{info['title']}** — {valid}/{total_refs} 有効")
            with st.expander("詳細"):
                for r in results:
                    if r.status != "valid":
                        st.write(f"  - {r.ref_type}: `{r.url}` — {r.error_message}")
