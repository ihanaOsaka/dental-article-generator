"""記事生成モジュール"""

try:
    from .writer import ArticleWriter
    __all__ = ["ArticleWriter"]
except ImportError:
    __all__ = []
