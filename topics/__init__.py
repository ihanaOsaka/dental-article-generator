"""トピック管理モジュール"""

try:
    from .loader import TopicLoader
    __all__ = ["TopicLoader"]
except ImportError:
    __all__ = []
