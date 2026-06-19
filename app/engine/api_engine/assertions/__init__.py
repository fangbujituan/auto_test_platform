"""断言子包：基类、注册中心、内置断言。

导入本子包会自动加载 ``builtin`` 模块以触发内置断言注册。
"""
from app.engine.api_engine.assertions.base import (  # noqa: F401
    AssertionRegistry,
    BaseAssertion,
    register_assertion,
)
from app.engine.api_engine.assertions import builtin  # noqa: F401  # 触发内置注册
