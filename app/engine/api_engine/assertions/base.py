"""
Assertion 框架核心：

- ``BaseAssertion``：所有断言的抽象基类，子类实现 ``check()``。
- ``AssertionRegistry``：进程级断言注册中心（按 ``type_name`` 索引）。
- ``register_assertion``：装饰器，在 import 时自动把子类注册进去。

扩展指南：
    @register_assertion
    class MyAssertion(BaseAssertion):
        type_name = "my_assertion"
        def check(self, response, config, ctx):
            ...

只要 ``app.engine.api_engine.assertions`` 子包被 import（顶层 ``__init__.py``
已触发），自定义断言模块就会自动注册。

作者: yandc
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from app.engine.api_engine.exceptions import AssertionTypeNotFoundError
from app.engine.api_engine.results import AssertionOutcome

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.results import ResponseRecord


class BaseAssertion(ABC):
    """断言抽象基类。

    子类必须设置 ``type_name``（与 ``AssertionRule.type`` 字符串对应），
    并实现 ``check()``。
    """

    #: 子类必须覆盖；与 AssertionRule.type 字段对应
    type_name: ClassVar[str] = ""

    @abstractmethod
    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,
    ) -> AssertionOutcome:
        """执行断言。

        Args:
            response: 当前 step 的响应快照（StepExecutor 在 send 失败时不会调用本方法）
            config:   AssertionRule.config（断言专属参数）
            ctx:      ExecutionContext（如需读取 ctx.variables 渲染 expected 值）

        Returns:
            AssertionOutcome；断言失败 SHALL **不**抛异常，由 StepExecutor 汇总。
        """


class AssertionRegistry:
    """断言注册中心。"""

    _registry: ClassVar[dict[str, BaseAssertion]] = {}

    @classmethod
    def register(cls, assertion: BaseAssertion) -> None:
        if not assertion.type_name:
            raise ValueError(
                f"断言 {assertion.__class__.__name__} 未设置 type_name"
            )
        cls._registry[assertion.type_name] = assertion

    @classmethod
    def get(cls, type_name: str) -> BaseAssertion:
        try:
            return cls._registry[type_name]
        except KeyError as exc:
            raise AssertionTypeNotFoundError(
                f"未注册的断言类型: '{type_name}'",
                details={"available": sorted(cls._registry.keys())},
            ) from exc

    @classmethod
    def known_types(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """仅供测试使用。"""
        cls._registry.clear()


def register_assertion(target: type[BaseAssertion]) -> type[BaseAssertion]:
    """装饰器：实例化并注册断言子类。

    用法：
        @register_assertion
        class StatusCodeAssertion(BaseAssertion):
            type_name = "status_code"
            ...
    """
    AssertionRegistry.register(target())
    return target
