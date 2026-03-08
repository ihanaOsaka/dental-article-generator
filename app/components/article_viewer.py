"""記事プレビューコンポーネント"""

import streamlit as st


def render_article_viewer(professional_md: str, public_md: str,
                          key_prefix: str = "viewer"):
    """専門版・一般公開版のタブ切替ビューア"""
    tab_pro, tab_pub = st.tabs(["📋 専門版（あなた向け）", "👥 一般公開版"])

    with tab_pro:
        if professional_md:
            st.markdown(professional_md)
        else:
            st.info("専門版記事がありません")

    with tab_pub:
        if public_md:
            st.markdown(public_md)
        else:
            st.info("一般公開版記事がありません")
