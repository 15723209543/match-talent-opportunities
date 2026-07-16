"""本模块公开双向人岗匹配引擎的主要调用函数，方便其他脚本复用。"""

from .engine import match_pair

__all__ = ["match_pair"]
__version__ = "4.2.0"
