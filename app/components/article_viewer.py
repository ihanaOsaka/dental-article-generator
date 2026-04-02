"""記事プレビューコンポーネント"""

import hashlib

import streamlit as st


def render_article_viewer(professional_md: str, public_md: str,
                          key_prefix: str = "viewer"):
    """専門版・一般公開版のタブ切替ビューア"""
    tab_pro, tab_pub = st.tabs(["📋 専門版（あなた向け）", "👥 一般公開版"])

    with tab_pro:
        if professional_md:
            # iframeでレンダリングしてReactのDOM差分更新を回避
            _render_md_isolated(professional_md, key_prefix + "_pro")
        else:
            st.info("専門版記事がありません")

    with tab_pub:
        if public_md:
            _render_md_isolated(public_md, key_prefix + "_pub")
        else:
            st.info("一般公開版記事がありません")


def _render_md_isolated(md_text: str, key: str):
    """MarkdownをHTMLに変換してiframe内にレンダリングする。
    React DOM diffの影響を受けないため記事切替時のエラーを防ぐ。"""
    import streamlit.components.v1 as components

    try:
        import markdown as md_lib
        html_body = md_lib.markdown(
            md_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )
    except ImportError:
        # markdownライブラリがなければst.markdownにフォールバック
        st.markdown(md_text)
        return

    # コンテンツのハッシュをキーにして不要な再レンダリングを防ぐ
    content_hash = hashlib.md5(md_text.encode()).hexdigest()[:8]

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: "Source Sans Pro", sans-serif;
    line-height: 1.8;
    color: #262730;
    padding: 0 0.5rem;
    margin: 0;
  }}
  h1 {{ font-size: 1.8rem; margin-top: 0; }}
  h2 {{ font-size: 1.4rem; border-bottom: 1px solid #e6e6e6; padding-bottom: 0.3rem; }}
  h3 {{ font-size: 1.15rem; }}
  a {{ color: #1a73e8; }}
  blockquote {{
    border-left: 3px solid #ccc;
    margin-left: 0;
    padding: 0.5rem 1rem;
    background: #f9f9f9;
  }}
  ul, ol {{ padding-left: 1.5rem; }}
  hr {{ border: none; border-top: 1px solid #e6e6e6; margin: 1.5rem 0; }}
  code {{ background: #f0f0f0; padding: 0.15rem 0.3rem; border-radius: 3px; font-size: 0.9em; }}
</style>
</head>
<body>{html_body}</body>
</html>"""

    # 高さを内容に合わせて自動調整
    line_count = md_text.count("\n")
    estimated_height = max(400, min(line_count * 28, 3000))
    components.html(full_html, height=estimated_height, scrolling=True)
