"""品質チェックモジュール"""

try:
    from .checker import QualityChecker
    __all__ = ["QualityChecker"]
except ImportError:
    __all__ = []
