"""新規記事作成ページ"""

import sys
from pathlib import Path

import streamlit as st

project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.state import init_state
from app.components.article_viewer import render_article_viewer
from app.components.reference_badges import render_verification_results

init_state()

st.header("✏️ 新規記事作成")

# Step 1: トピック入力
st.subheader("1. トピックを入力")

input_mode = st.radio(
    "入力方式",
    ["自由入力", "既存トピックから選択"],
    horizontal=True,
)

topic_data = None

if input_mode == "自由入力":
    user_input = st.text_area(
        "書きたい記事のテーマを自由に入力してください",
        placeholder="例: 子供の歯ぎしりについて\n"
                    "例: 乳歯が抜ける前に永久歯が生えてきた場合の対処法\n"
                    "例: 小児の口臭の原因と対策",
        height=100,
    )

    if st.button("トピックを分析", disabled=not user_input.strip()):
        with st.spinner("トピックを分析中..."):
            try:
                from app.services.topic_generator import TopicGenerator
                generator = TopicGenerator()
                topic_data = generator.generate(user_input.strip())
                st.session_state.free_form_topic = topic_data
            except Exception as e:
                st.error(f"トピック分析に失敗しました: {e}")

    # 前回の分析結果があれば復元
    if st.session_state.get("free_form_topic"):
        topic_data = st.session_state.free_form_topic

    if topic_data:
        st.subheader("2. トピック情報を確認・編集")
        st.caption("必要に応じて内容を修正してから記事を生成してください")

        col1, col2 = st.columns(2)
        with col1:
            topic_data["title"] = st.text_input(
                "タイトル", value=topic_data.get("title", ""))
            topic_data["category_name"] = st.text_input(
                "カテゴリ", value=topic_data.get("category_name", "一般"))
            topic_data["age_range"] = st.text_input(
                "対象年齢", value=topic_data.get("age_range", ""))

        with col2:
            keywords_str = st.text_input(
                "キーワード（カンマ区切り）",
                value=", ".join(topic_data.get("keywords", [])))
            topic_data["keywords"] = [k.strip() for k in keywords_str.split(",") if k.strip()]

            en_terms_str = st.text_input(
                "英語検索語（カンマ区切り）",
                value=", ".join(topic_data.get("search_terms", {}).get("en", [])))
            topic_data.setdefault("search_terms", {})["en"] = [
                t.strip() for t in en_terms_str.split(",") if t.strip()
            ]

        with st.expander("PICO設定"):
            pico = topic_data.get("pico", {})
            pico["population"] = st.text_input("P（対象）", value=pico.get("population", ""))
            pico["intervention"] = st.text_input("I（介入）", value=pico.get("intervention", ""))
            pico["comparison"] = st.text_input("C（比較）", value=pico.get("comparison", ""))
            pico["outcome"] = st.text_input("O（結果）", value=pico.get("outcome", ""))
            topic_data["pico"] = pico

        # 編集内容をセッションに保存
        st.session_state.free_form_topic = topic_data

else:
    # 既存トピックから選択
    try:
        from topics.loader import TopicLoader
        loader = TopicLoader()
        all_topics = loader.get_all_topics()

        if all_topics:
            topic_options = {t["id"]: f"[{c['name']}] {t['title']}"
                           for c, t in all_topics}
            selected_id = st.selectbox(
                "トピックを選択",
                list(topic_options.keys()),
                format_func=lambda x: topic_options[x],
            )
            for cat, top in all_topics:
                if top["id"] == selected_id:
                    topic_data = top.copy()
                    topic_data["category_name"] = cat["name"]
                    topic_data["age_range"] = cat.get("age_range", "")
                    break
    except Exception as e:
        st.error(f"トピック一覧の読み込みに失敗しました: {e}")

# Step 3: 記事生成
if topic_data:
    st.divider()
    st.subheader("3. 記事を生成")

    if st.button("記事を生成する", type="primary"):
        with st.status("記事を生成中...", expanded=True) as status:
            try:
                from app.services.article_service import ArticleService

                service = ArticleService()

                def progress_cb(msg):
                    st.write(msg)

                result = service.generate_from_topic(
                    topic=topic_data,
                    category_name=topic_data.get("category_name", ""),
                    age_range=topic_data.get("age_range", ""),
                    progress_callback=progress_cb,
                )

                # 結果を保存
                service.save_result(result)
                st.session_state.generation_result = result
                st.session_state.verification_results[result.topic_id] = result.verification_results

                # 自動 git commit & push
                progress_cb("変更を git にコミット中...")
                from app.services.git_service import auto_commit_and_push

                commit_files = [
                    f"output/articles/{result.topic_id}.md",
                    f"output/articles_public/{result.topic_id}.md",
                ]
                commit_msg = f"Add article: {result.topic_id}"
                auto_commit_and_push(commit_files, commit_msg)

                service.close()
                status.update(label="生成完了", state="complete")

            except Exception as e:
                status.update(label="エラー", state="error")
                st.error(f"記事生成に失敗しました: {e}")

    # 生成結果の表示
    result = st.session_state.get("generation_result")
    if result:
        st.divider()
        st.subheader("生成結果")
        st.metric("品質スコア", f"{result.quality_score:.0f}")

        render_article_viewer(result.professional, result.public)

        # 参考文献検証結果
        with st.expander("参考文献リンク検証結果", expanded=True):
            render_verification_results(result.verification_results)

        st.success(f"記事を保存しました: `output/articles/{result.topic_id}.md`")
