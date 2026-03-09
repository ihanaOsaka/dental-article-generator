"""記事生成モジュール"""

try:
    from .writer import ArticleWriter
except ImportError:
    pass

__all__ = ["ArticleWriter"]
