"""参考文献検証結果の表示コンポーネント"""

import streamlit as st

from app.state import VerificationResult


STATUS_ICONS = {
    "valid": "✅",
    "invalid": "❌",
    "timeout": "⏱️",
    "error": "⚠️",
    "not_found": "🔍",
}


def render_verification_results(results: list[VerificationResult]):
    """検証結果をバッジ付きで表示"""
    if not results:
        st.info("検証対象の参考文献リンクが見つかりませんでした")
        return

    valid_count = sum(1 for r in results if r.status == "valid")
    total = len(results)

    if valid_count == total:
        st.success(f"全 {total} 件のリンクが有効です")
    else:
        st.warning(f"{valid_count}/{total} 件のリンクが有効（{total - valid_count} 件に問題あり）")

    for r in results:
        icon = STATUS_ICONS.get(r.status, "❓")
        col1, col2 = st.columns([1, 12])

        with col1:
            st.markdown(f"### {icon}")
        with col2:
            label = f"**[{r.ref_type}]** "
            if r.status == "valid":
                label += f"[{_truncate(r.url, 80)}]({r.url})"
                if r.resolved_title:
                    label += f"\n> {r.resolved_title}"
            elif r.status == "invalid":
                label += f"`{_truncate(r.url, 80)}` — {r.error_message}"
            elif r.status == "timeout":
                label += f"`{_truncate(r.url, 80)}` — タイムアウト（サイトが応答しません）"
            else:
                label += f"`{_truncate(r.url, 80)}` — {r.error_message}"

            st.markdown(label)

            if r.reference_text and r.reference_text != r.url:
                st.caption(_truncate(r.reference_text, 150))

        st.divider()


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text
