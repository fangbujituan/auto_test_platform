"""抽取器子包：基类、注册中心、内置抽取器。

导入本子包会自动加载 ``builtin`` 模块以触发内置抽取器注册。
"""
from app.engine.api_engine.extractors.base import (  # noqa: F401
    BaseExtractor,
    ExtractorRegistry,
    register_extractor,
)
from app.engine.api_engine.extractors import builtin  # noqa: F401  # 触发内置注册
