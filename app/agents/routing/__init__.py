"""
Agent 模型路由层。

按任务复杂度把请求分发到不同层级（local / cloud）的不同模型，并实现
同层重试与跨层升级，最大化"低任务用本地小模型、高任务用云端大模型"
的 token 经济性。

公开符号
--------

数据：
- :class:`ModelTier`        模型层级
- :class:`TaskComplexity`   任务复杂度
- :class:`RoutingRule`      单条规则
- :class:`LLMRequest`       LLM 调用请求
- :class:`LLMResponse`      LLM 调用响应

实现：
- :class:`LiteLLMModelRouter`  默认实现（基于 LiteLLM，可被覆盖为本地网关）

作者: yandc
"""
from app.agents.routing.model_router import LiteLLMModelRouter, ModelRouter
from app.agents.routing.routing_models import (
    LLMRequest,
    LLMResponse,
    ModelTier,
    RoutingRule,
    TaskComplexity,
)

__all__ = [
    "ModelTier",
    "TaskComplexity",
    "RoutingRule",
    "LLMRequest",
    "LLMResponse",
    "ModelRouter",
    "LiteLLMModelRouter",
]
