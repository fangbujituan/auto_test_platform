"""中间件模块（整合自 ai-server）

提供的中间件：
- DOMCleanerMiddleware: DOM 清理中间件
- CodeCollectorMiddleware: 代码收集中间件
- SemanticSelectorMiddleware: 语义选择器中间件
- TokenControlMiddleware: Token 控制中间件
- ThreadContextMiddleware: 线程上下文中间件
- Base64FilterMiddleware: Base64 过滤中间件
- BeforeAgentMiddleware: 日志中间件
- SelectorScores: 选择器评分工具
"""

from app.utils.middleware.dom_cleaner import DOMCleanerMiddleware
from app.utils.middleware.logging import BeforeAgentMiddleware
from app.utils.middleware.code_collector import CodeCollectorMiddleware, get_collector, reset_collector
from app.utils.middleware.base64_filter import Base64FilterMiddleware
from app.utils.middleware.token_control import TokenControlMiddleware
from app.utils.middleware.semantic_selector import SemanticSelectorMiddleware, get_semantic_selector

__all__ = [
    "DOMCleanerMiddleware",
    "BeforeAgentMiddleware",
    "CodeCollectorMiddleware",
    "Base64FilterMiddleware",
    "TokenControlMiddleware",
    "SemanticSelectorMiddleware",
    "get_collector",
    "reset_collector",
    "get_semantic_selector",
]
