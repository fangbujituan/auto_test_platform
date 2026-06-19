"""
Extractor 框架核心。

抽取器在 step 执行后从响应中取字段，写入 ``ExecutionContext``，供后续 step
通过 ``{{var}}`` 引用。这是实现链式调用（登录拿 token → 后续接口用 token）的关键能力。

设计要点：
- 抽取失败时**不抛异常**：
  - 配了 ``default`` → 返回 default 值，``succeeded=False``，写入 ctx
  - 没配 ``default`` → ``succeeded=False``，**不**写入 ctx，由 StepExecutor 转 warning
- 这与断言失败的处理不同：断言失败影响 step 的 passed；抽取失败本身不影响 step
  通过/失败，但会让"依赖该变量的后续步骤"在断言时显式失败。

作者: yandc
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from app.engine.api_engine.exceptions import ExtractorTypeNotFoundError
from app.engine.api_engine.results import ExtractOutcome

if TYPE_CHECKING:
    from app.engine.api_engine.results import ResponseRecord


class BaseExtractor(ABC):
    """抽取器抽象基类。"""

    #: 子类必须覆盖；与 ExtractRule.type 字段对应
    type_name: ClassVar[str] = ""

    @abstractmethod
    def extract(
        self,
        response: ResponseRecord,
        name: str,
        expression: str,
        default: Any,
    ) -> ExtractOutcome:
        """执行抽取。

        子类需自己处理"未抽到 → 是否用 default"的逻辑，并填充 ExtractOutcome。
        """


class ExtractorRegistry:
    """抽取器注册中心。"""

    _registry: ClassVar[dict[str, BaseExtractor]] = {}

    @classmethod
    def register(cls, extractor: BaseExtractor) -> None:
        if not extractor.type_name:
            raise ValueError(
                f"抽取器 {extractor.__class__.__name__} 未设置 type_name"
            )
        cls._registry[extractor.type_name] = extractor

    @classmethod
    def get(cls, type_name: str) -> BaseExtractor:
        try:
            return cls._registry[type_name]
        except KeyError as exc:
            raise ExtractorTypeNotFoundError(
                f"未注册的抽取器类型: '{type_name}'",
                details={"available": sorted(cls._registry.keys())},
            ) from exc

    @classmethod
    def known_types(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def clear(cls) -> None:
        """仅供测试使用。"""
        cls._registry.clear()


def register_extractor(target: type[BaseExtractor]) -> type[BaseExtractor]:
    """装饰器：实例化并注册抽取器子类。"""
    ExtractorRegistry.register(target())
    return target
