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
    st.divider()

pg.run()
