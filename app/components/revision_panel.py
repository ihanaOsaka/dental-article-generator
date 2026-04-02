"""記事修正パネルコンポーネント（固定フッター）"""

import streamlit as st

_FOOTER_CSS = """\
<style>
/* マーカーを含むコンテナは非表示 */
div[data-testid="stElementContainer"]:has(.revision-footer-marker) {
    height: 0 !important;
    overflow: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
}
/* マーカーの直後の stLayoutWrapper (= st.columns) を固定フッター化 */
div[data-testid="stElementContainer"]:has(.revision-footer-marker)
  ~ div[data-testid="stLayoutWrapper"] {
    position: fixed !important;
    bottom: 0 !important;
    right: 0 !important;
    background: #ffffff !important;
    border-top: 1px solid #e0e0e0 !important;
    box-shadow: 0 -2px 8px rgba(0,0,0,0.08) !important;
    padding: 0.75rem 2rem 1rem 2rem !important;
    box-sizing: border-box !important;
    max-width: calc(100vw - 300px) !important;
    overflow: hidden !important;
    z-index: 999 !important;
    /* サイドバー展開時：メインコンテンツ領域に合わせる */
    left: 300px !important;
    transition: left 0.3s ease !important;
}
/* サイドバー折りたたみ時 */
section[data-testid="stSidebar"][aria-expanded="false"]
  ~ section[data-testid="stMain"]
  div[data-testid="stElementContainer"]:has(.revision-footer-marker)
  ~ div[data-testid="stLayoutWrapper"] {
    left: 3.5rem !important;
}
/* フッター内のボタンをテキストエリアと揃える */
div[data-testid="stElementContainer"]:has(.revision-footer-marker)
  ~ div[data-testid="stLayoutWrapper"] div[data-testid="stButton"] > button {
    height: 52px !important;
    white-space: nowrap !important;
    min-width: 6rem !important;
}
/* disabled 状態のボタンを視認しやすくする */
div[data-testid="stElementContainer"]:has(.revision-footer-marker)
  ~ div[data-testid="stLayoutWrapper"] div[data-testid="stButton"] > button:disabled {
    background-color: #e0e0e0 !important;
    color: #888 !important;
    border: 1px solid #ccc !important;
}
/* フッター内のテキストエリアを低くする */
div[data-testid="stElementContainer"]:has(.revision-footer-marker)
  ~ div[data-testid="stLayoutWrapper"] textarea {
    height: 52px !important;
    min-height: 52px !important;
}
/* メインコンテンツがフッターに隠れないようにする */
section.main > div.block-container {
    padding-bottom: 8rem !important;
}
</style>
"""


def render_revision_panel(key_prefix: str = "revision",
                          disabled: bool = False):
    """修正指示の固定フッターパネル

    Args:
        key_prefix: Streamlitウィジェットのキー接頭辞
        disabled: Trueの場合、入力とボタンを無効化する

    Returns:
        str | None: 修正指示テキスト（ボタン押下時）、未押下時はNone
    """
    # CSS注入
    st.markdown(_FOOTER_CSS, unsafe_allow_html=True)

    # マーカー（CSSセレクタ用）
    st.markdown('<div class="revision-footer-marker"></div>',
                unsafe_allow_html=True)

    # テキストエリア＋ボタン横並び
    footer_cols = st.columns([3, 1])

    with footer_cols[0]:
        placeholder = ("⏳ 修正を実行中…" if disabled
                       else "記事を読みながらコメントを入力 → まとめて「修正を実行」")
        instructions = st.text_area(
            "修正指示",
            placeholder=placeholder,
            height=52,
            key=f"{key_prefix}_instructions",
            label_visibility="collapsed",
            disabled=disabled,
        )

    with footer_cols[1]:
        submitted = st.button(
            "修正を実行",
            key=f"{key_prefix}_btn",
            disabled=disabled or not instructions.strip(),
            type="primary",
            use_container_width=True,
        )

    if submitted:
        return instructions.strip()

    return None
