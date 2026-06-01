"""
Agent 框架核心抽象接口（ABC）。

定义编排层、Agent 层、模型路由层、审核闸的统一契约，便于后续替换
具体实现（例如把 LangGraphOrchestrator 换成自研编排，或把
LiteLLMModelRouter 换成走 ``llm_gateway`` 的简化路由）而不影响上层。

迁移自 ``code-factory/src/core/interfaces.py``，**剔除** RAG / 文档加载
等无关接口。

接口列表
--------

- :class:`AgentInterface`           单个 Agent 的执行 + 校验契约
- :class:`OrchestratorInterface`    多 Agent 工作流的编排契约
- :class:`ModelRouterInterface`     按复杂度路由的模型选择契约
- :class:`ReviewGateInterface`      Human-in-the-Loop 审核契约

作者: yandc
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

# 仅类型提示时引用，避免运行时循环依赖
if TYPE_CHECKING:
    from app.agents.orchestration.state import AgentState
    from app.agents.routing.routing_models import (
        LLMRequest,
        LLMResponse,
        TaskComplexity,
    )
    from app.agents.review.review_models import (
        ReviewRecord,
        ReviewRequest,
    )


# ---------------------------------------------------------------------------
# Agent 执行 / 编排
# ---------------------------------------------------------------------------
class AgentInterface(ABC):
    """单个 Agent 的执行与输出校验契约。"""

    @abstractmethod
    async def execute(self, state: "AgentState") -> "AgentState":
        """执行 Agent，返回更新后的状态。"""

    @abstractmethod
    def validate_output(self, state: "AgentState") -> bool:
        """校验输出是否符合 schema，True 通过 / False 不通过。"""


class OrchestratorInterface(ABC):
    """多 Agent 工作流的编排契约。"""

    @abstractmethod
    async def run_workflow(
        self, workflow_name: str, initial_state: "AgentState"
    ) -> "AgentState":
        """执行注册的工作流并返回最终状态。"""

    @abstractmethod
    def register_agent(self, name: str, agent: "AgentInterface") -> None:
        """按名称注册 Agent 到编排器。"""


# ---------------------------------------------------------------------------
# 模型路由
# ---------------------------------------------------------------------------
class ModelRouterInterface(ABC):
    """按复杂度选择模型并调用的统一接口。"""

    @abstractmethod
    async def route(self, request: "LLMRequest") -> "LLMResponse":
        """根据路由规则选择具体模型并发起调用。"""

    @abstractmethod
    def classify_complexity(
        self, task_type: str, context: dict
    ) -> "TaskComplexity":
        """评估任务复杂度等级。"""


# ---------------------------------------------------------------------------
# 人工审核闸
# ---------------------------------------------------------------------------
class ReviewGateInterface(ABC):
    """Human-in-the-Loop 审核闸契约。"""

    @abstractmethod
    async def submit_for_review(self, request: "ReviewRequest") -> str:
        """提交内容等待审核，返回 request_id。"""

    @abstractmethod
    async def get_decision(self, request_id: str) -> Optional["ReviewRecord"]:
        """查询某次审核的决策结果，未决时返回 None。"""

    @abstractmethod
    async def record_decision(self, record: "ReviewRecord") -> None:
        """记录审核决策。"""


__all__ = [
    "AgentInterface",
    "OrchestratorInterface",
    "ModelRouterInterface",
    "ReviewGateInterface",
]
