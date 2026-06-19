"""
api_engine：接口测试统一执行引擎。

对外只暴露一个门面 ``ApiEngine``，内部按职责拆分子包：

- ``specs``       运行时输入 DTO（RequestSpec / CollectionSpec / AssertionRule / ExtractRule）
- ``results``     运行时输出 DTO（StepResult / CollectionResult / 各类 Outcome）
- ``exceptions``  引擎自有异常
- ``context``     ExecutionContext，按 run_id 隔离的上下文
- ``variables``   变量解析（{{var}} 渲染、prefix_url 解析、global params 合并）
- ``http``        HttpClient，唯一的 HTTP IO 出口
- ``assertions``  断言注册中心 + 内置断言
- ``extractors``  抽取注册中心 + 内置抽取器
- ``strategies``  失败策略
- ``runner``      StepExecutor + SequenceRunner
- ``loaders``     数据适配层（数据库模型 / dict → spec），逐步加入
- ``reporters``   报告器（控制台、数据库）

调用方仅需：

    from app.engine.api_engine import ApiEngine, get_api_engine

老的 ``app/engine/liu_shui_xian.py`` 与 ``app/engine/test_factory.py``
在本期中**仅作历史参考**，不被本包引用，后续会迁入 ``app/engine/_legacy/``。

作者: yandc
"""

# 异常
from app.engine.api_engine.exceptions import (  # noqa: F401
    ApiEngineError,
    AssertionTypeNotFoundError,
    ExtractorTypeNotFoundError,
    ExtractFailedError,
    HttpInvocationError,
    InvalidRequestSpecError,
    LoaderError,
)

# 输入 DTO
from app.engine.api_engine.specs import (  # noqa: F401
    AssertionRule,
    CollectionSpec,
    ExtractRule,
    RequestSpec,
)

# 输出 DTO
from app.engine.api_engine.results import (  # noqa: F401
    AssertionOutcome,
    CollectionResult,
    ExtractOutcome,
    RequestRecord,
    ResponseRecord,
    StepResult,
)

# 门面（同时触发内置断言/抽取器注册：经由子包 __init__.py 链式 import）
from app.engine.api_engine.engine import (  # noqa: F401
    ApiEngine,
    get_api_engine,
    reset_api_engine,
)

__all__ = [
    # 异常
    "ApiEngineError",
    "AssertionTypeNotFoundError",
    "ExtractorTypeNotFoundError",
    "ExtractFailedError",
    "HttpInvocationError",
    "InvalidRequestSpecError",
    "LoaderError",
    # 输入 DTO
    "AssertionRule",
    "CollectionSpec",
    "ExtractRule",
    "RequestSpec",
    # 输出 DTO
    "AssertionOutcome",
    "CollectionResult",
    "ExtractOutcome",
    "RequestRecord",
    "ResponseRecord",
    "StepResult",
    # 门面
    "ApiEngine",
    "get_api_engine",
    "reset_api_engine",
]
