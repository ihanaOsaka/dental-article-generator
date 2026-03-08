"""記事修正パネルコンポーネント"""

import streamlit as st


def render_revision_panel(key_prefix: str = "revision"):
    """修正指示の入力パネル

    Returns:
        str | None: 修正指示テキスト（ボタン押下時）、未押下時はNone
    """
    st.markdown("### 修正指示")
    st.caption("専門版を修正すると、一般公開版も自動で再生成されます")

    instructions = st.text_area(
        "修正内容を入力してください",
        placeholder="例: フッ素の安全性についてもう少し詳しく説明してください\n"
                    "例: 参考文献を追加してください\n"
                    "例: 「当院からのご提案」セクションを削除してください",
        height=120,
        key=f"{key_prefix}_instructions",
    )

    if st.button("修正を実行", key=f"{key_prefix}_btn",
                 disabled=not instructions.strip(),
                 type="primary"):
        return instructions.strip()

    return None
