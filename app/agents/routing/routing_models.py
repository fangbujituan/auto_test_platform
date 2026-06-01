"""
模型路由层使用的数据模型与枚举。

只承载 **数据**，不含调用逻辑。被 ``routing.model_router`` 共享使用。

迁移自 ``code-factory/src/core/models.py`` 中的 Model Router 部分。

数据结构概览
------------

- :class:`ModelTier`        模型层级（local / cloud）
- :class:`TaskComplexity`   任务复杂度（low / medium / high）
- :class:`RoutingRule`      单条路由规则
- :class:`LLMRequest`       LLM 调用请求
- :class:`LLMResponse`      LLM 调用响应

作者: yandc
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ModelTier(str, Enum):
    """模型层级。

    继承 ``str`` 便于直接 JSON 序列化与比较。
    """

    LOCAL = "local"
    CLOUD = "cloud"


class TaskComplexity(str, Enum):
    """任务复杂度等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RoutingRule:
    """单条路由规则。

    Attributes:
        complexity: 适用的任务复杂度
        tier:       目标层级
        models:     按优先级排序的候选模型列表（先尝试列表头部）
        max_retries: 同层级内的最大尝试次数（含首次）
    """

    complexity: TaskComplexity
    tier: ModelTier
    models: list[str]
    max_retries: int = 3


@dataclass
class LLMRequest:
    """一次 LLM 调用请求。

    Attributes:
        messages:   OpenAI 风格的消息列表 ``[{"role": ..., "content": ...}]``
        task_type:  任务类型（用于查路由规则，如 "testcase_generation"）
        complexity: 任务复杂度等级
        temperature: 采样温度
        max_tokens:  最大生成 token 数
    """

    messages: list[dict[str, str]]
    task_type: str
    complexity: TaskComplexity
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class LLMResponse:
    """一次 LLM 调用响应。

    Attributes:
        content:     模型生成的文本
        model_used:  实际命中的模型标识
        tier:        命中的层级
        token_count: ``{"input": N, "output": M}``
        latency_ms:  端到端耗时（毫秒）
    """

    content: str
    model_used: str
    tier: ModelTier
    token_count: dict[str, int]
    latency_ms: float


__all__ = [
    "ModelTier",
    "TaskComplexity",
    "RoutingRule",
    "LLMRequest",
    "LLMResponse",
]
