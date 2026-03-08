"""トピックYAMLの読み込み・管理"""

from pathlib import Path

import yaml


class TopicLoader:
    """topics.yamlからトピック情報を読み込む"""

    def __init__(self, topics_file: str | Path | None = None):
        if topics_file is None:
            topics_file = Path(__file__).parent / "topics.yaml"
        self.topics_file = Path(topics_file)
        self._data: dict | None = None

    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = yaml.safe_load(
                self.topics_file.read_text(encoding="utf-8")
            )
        return self._data

    def get_all_categories(self) -> list[dict]:
        """全カテゴリを返す"""
        return self.data.get("categories", [])

    def get_all_topics(self) -> list[tuple[dict, dict]]:
        """全トピックを (category, topic) タプルのリストで返す"""
        results = []
        for category in self.get_all_categories():
            for topic in category.get("topics", []):
                results.append((category, topic))
        return results

    def get_topic_by_id(self, topic_id: str) -> tuple[dict, dict] | None:
        """IDでトピックを検索"""
        for category in self.get_all_categories():
            for topic in category.get("topics", []):
                if topic["id"] == topic_id:
                    return (category, topic)
        return None

    def search_topics(self, keyword: str) -> list[tuple[dict, dict]]:
        """キーワードでトピックを検索"""
        keyword_lower = keyword.lower()
        results = []
        for category in self.get_all_categories():
            for topic in category.get("topics", []):
                searchable = (
                    f"{topic['title']} {' '.join(topic.get('keywords', []))}"
                ).lower()
                if keyword_lower in searchable:
                    results.append((category, topic))
        return results

    def get_topic_count(self) -> int:
        """トピック総数を返す"""
        return sum(
            len(cat.get("topics", []))
            for cat in self.get_all_categories()
        )

    def list_topics_table(self) -> str:
        """トピック一覧をテーブル形式で返す"""
        lines = ["ID | カテゴリ | タイトル", "---|---|---"]
        for category, topic in self.get_all_topics():
            lines.append(f"{topic['id']} | {category['name']} | {topic['title']}")
        return "\n".join(lines)
