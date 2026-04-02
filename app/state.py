"""Streamlit セッション状態管理"""

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import streamlit as st

_STATUS_FILE = Path(__file__).parent.parent / "data" / "article_status.json"


@dataclass
class VerificationResult:
    """文献リンク検証結果"""
    reference_text: str
    url: str
    ref_type: str  # "DOI" | "PMID" | "URL"
    status: str  # "valid" | "invalid" | "timeout" | "error" | "not_found"
    http_status: int | None = None
    resolved_title: str = ""
    error_message: str = ""


@dataclass
class GenerationResult:
    """記事生成の結果"""
    topic_id: str
    professional: str
    public: str
    quality_score: float = 0.0
    verification_results: list[VerificationResult] = field(default_factory=list)


# カテゴリ接頭辞 → 表示名
CATEGORY_LABELS = {
    "infant": "乳児期（0〜1歳）",
    "preschool": "幼児期（2〜5歳）",
    "elem": "学童期（6〜12歳）",
    "teen": "中高生（13〜18歳）",
    "ortho": "矯正・口腔習癖",
    "pregnancy": "妊娠期",
    "gen": "一般・共通",
    "custom": "カスタム記事",
}


def init_state():
    """セッション状態の初期化（未設定のキーのみ）"""
    defaults = {
        "selected_article_id": None,
        "current_professional": "",
        "current_public": "",
        "revision_in_progress": False,
        "revision_tasks": {},
        "generation_in_progress": False,
        "generation_result": None,
        "verification_results": {},
        "free_form_topic": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def get_article_index(articles_dir: str = "output/articles",
                      public_dir: str = "output/articles_public") -> dict:
    """既存記事の一覧を取得"""
    base = Path(__file__).parent.parent
    articles_path = base / articles_dir
    public_path = base / public_dir

    index = {}
    if articles_path.exists():
        for f in sorted(articles_path.glob("*.md")):
            topic_id = f.stem
            title = _extract_title(f)
            category = _get_category(topic_id)
            public_file = public_path / f.name
            index[topic_id] = {
                "title": title,
                "category": category,
                "professional_path": str(f),
                "public_path": str(public_file) if public_file.exists() else None,
            }
    return index


def _extract_title(file_path: Path) -> str:
    """Markdownファイルの最初の見出しをタイトルとして取得"""
    try:
        text = file_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].split("—")[0].split("——")[0].strip()
        return file_path.stem
    except Exception:
        return file_path.stem


def _get_category(topic_id: str) -> str:
    """topic_idからカテゴリ接頭辞を取得"""
    for prefix in CATEGORY_LABELS:
        if topic_id.startswith(prefix):
            return prefix
    return "custom"


# --- 記事承認ステータス管理 ---

def load_article_status() -> dict:
    """記事の承認ステータスを読み込む"""
    if _STATUS_FILE.exists():
        return json.loads(_STATUS_FILE.read_text(encoding="utf-8"))
    return {}


def save_article_status(status: dict):
    """記事の承認ステータスを保存する"""
    _STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATUS_FILE.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def approve_article(topic_id: str):
    """記事を承認済みにする"""
    status = load_article_status()
    status[topic_id] = {
        "approved": True,
        "approved_at": str(date.today()),
        "notes": "",
    }
    save_article_status(status)


def revoke_approval(topic_id: str):
    """記事の承認を取り消す（修正後など）"""
    status = load_article_status()
    if topic_id in status:
        status[topic_id]["approved"] = False
        status[topic_id]["approved_at"] = ""
    save_article_status(status)


def is_approved(topic_id: str) -> bool:
    """記事が承認済みかどうか"""
    status = load_article_status()
    entry = status.get(topic_id, {})
    return entry.get("approved", False)
