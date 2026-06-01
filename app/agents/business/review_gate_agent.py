"""
审核闸 Agent 适配器。

把 :class:`HumanReviewGate` 包装成一个可以挂到 DAG 上的 BaseAgent 节点。
**Step 3 阶段提供的是同步轮询版**：在节点内部短暂等待审核结果，超时
则把工作流标记为失败。

为什么不在 Orchestrator 里硬编码 ReviewGate
-------------------------------------------
保持 Orchestrator 的"无业务感知"特性——它只懂 Agent + DAG，不懂审核。
把审核能力封装为一个普通 Agent，对编排器透明。

输入 / 输出契约
---------------

- ``state.input_data["mock_review"]``        可选，True 时直接通过
- ``state.input_data["review_workflow"]``    可选，对应 ``review_gates.yaml``
                                              的 workflow 名（默认根据本 Agent
                                              所属工作流推断）
- ``state.input_data["review_timeout_s"]``   可选，等待超时（秒），默认 5
- ``state.input_data["review_decision"]``    测试 / 模拟通道：
                                              "approved" / "rejected"，本 Agent
                                              直接采纳不走真实闸
- 写出：
  - ``state.output_data["review_decision"]``   "approved" / "rejected" / "timeout"
  - ``state.output_data["review_comments"]``   审核员留言（如有）

设计取舍
--------
真实生产里审核应当**异步**——把工作流挂起，等审核 webhook 回调后再
继续。这超出 Step 3 的"先把链路跑通"目标，留待 P1 阶段引入挂起/恢复
机制；当前同步版本足以验证"审核闸节点"的位置与契约。

作者: yandc
"""
from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from app.agents.orchestration import AgentState, BaseAgent
from app.agents.review import (
    HumanReviewGate,
    ReviewDecision,
    ReviewRecord,
    ReviewRequest,
)
from app.utils.debug import logs


class ReviewGateAgent(BaseAgent):
    """同步轮询版 Human-in-the-Loop 审核节点。"""

    name = "review_gate"
    output_schema = {
        "type": "object",
        "required": ["review_decision"],
        "properties": {
            "review_decision": {"type": "string"},
            "review_comments": {"type": "string"},
        },
    }

    def __init__(self, gate: HumanReviewGate | None = None) -> None:
        super().__init__()
        self._gate = gate or HumanReviewGate()

    async def _process(self, state: AgentState) -> AgentState:
        # 模拟通道：直接采纳预设决策，便于单测与 mock e2e
        # 触发条件：显式 mock_review、显式 review_decision、或全局 mock
        forced = state.input_data.get("review_decision")
        if (
            state.input_data.get("mock_review")
            or state.input_data.get("mock")
            or forced
        ):
            decision = forced or "approved"
            state.output_data["review_decision"] = decision
            state.output_data["review_comments"] = (
                state.input_data.get("review_comments") or "(mock auto)"
            )
            state.metadata["model_used"] = "mock"
            logs.info(f"[review_gate_agent] mock | decision={decision}")
            if decision == "rejected":
                state.metadata["status"] = "rejected"
            return state

        # 真实闸：提交 → 轮询
        gate = self._gate
        request_id = f"rev-{uuid.uuid4().hex[:12]}"
        request = ReviewRequest(
            request_id=request_id,
            workflow_id=state.workflow_id,
            agent_name=state.history[-1]["agent_name"] if state.history else "unknown",
            content=dict(state.output_data),
            created_at=datetime.now(timezone.utc),
            timeout_seconds=int(state.input_data.get("review_timeout_s", 5)),
        )
        await gate.submit_for_review(request)
        logs.info(
            f"[review_gate_agent] submitted | request_id={request_id} "
            f"timeout={request.timeout_seconds}s"
        )

        decision_text = "timeout"
        comments = ""
        deadline = time.monotonic() + request.timeout_seconds
        while time.monotonic() < deadline:
            decision_record = await gate.get_decision(request_id)
            if decision_record is not None:
                decision_text = decision_record.decision.value
                comments = decision_record.comments or ""
                break
            await asyncio.sleep(0.2)

        state.output_data["review_decision"] = decision_text
        state.output_data["review_comments"] = comments
        state.metadata["model_used"] = "human_review"
        logs.info(
            f"[review_gate_agent] done | request_id={request_id} "
            f"decision={decision_text}"
        )
        if decision_text != ReviewDecision.APPROVED.value:
            state.metadata["status"] = "rejected"
            state.metadata["failure_reason"] = (
                "review_timeout" if decision_text == "timeout" else "review_rejected"
            )
        return state

    # 测试 / 集成入口：让外部代码方便地塞决策（例如来自前端 UI）
    async def record_decision(
        self,
        request_id: str,
        reviewer_id: str,
        approved: bool,
        comments: str = "",
    ) -> None:
        """提供给上层 UI / API 的快捷调用。"""
        await self._gate.record_decision(
            ReviewRecord(
                request_id=request_id,
                reviewer_id=reviewer_id,
                decision=ReviewDecision.APPROVED if approved else ReviewDecision.REJECTED,
                comments=comments,
                timestamp=datetime.now(timezone.utc),
            )
        )


__all__ = ["ReviewGateAgent"]
