"""
Human-in-the-Loop 审核闸（HITL Review Gate）。

迁移自 ``code-factory/tools/review_gate.py``，针对本项目做了三点调整：

1. **DB 部分默认内存化**：``db_pool`` 为 ``None`` 时纯内存运行，asyncpg
   仍是延迟导入，未安装也不影响主流程。
2. **日志统一**：用 ``app.utils.debug.logs`` 替换 structlog。
3. **配置默认路径**：``app/agents/config/review_gates.yaml``。

提供能力
--------

- ``submit_for_review`` 提交内容等待审核（暂停工作流）
- ``record_decision``   记录审核决策（通过 / 拒绝）
- ``get_decision``      查询决策结果
- ``check_timeouts``    定时巡检超时并发提醒
- 拒绝反馈路由（``get_rejection_feedback`` 把审核员评论回灌给原 Agent）

作者: yandc
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from app.agents.orchestration.interfaces import ReviewGateInterface
from app.agents.review.review_models import (
    ReviewDecision,
    ReviewRecord,
    ReviewRequest,
)
from app.utils.debug import logs


# 默认配置路径
_DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent / "config" / "review_gates.yaml"
)


class HumanReviewGate(ReviewGateInterface):
    """人工审核闸，用于在工作流中插入 HITL 决策点。

    使用方式::

        gate = HumanReviewGate()  # 默认内存模式

        request = ReviewRequest(
            request_id="rev-001",
            workflow_id="wf-001",
            agent_name="testcase_agent",
            content={"cases": [...]},
            created_at=datetime.now(timezone.utc),
            timeout_seconds=3600,
        )
        await gate.submit_for_review(request)

        # 后续审核员通过 UI / API 触发：
        record = ReviewRecord(
            request_id="rev-001",
            reviewer_id="user-42",
            decision=ReviewDecision.APPROVED,
            comments="OK",
            timestamp=datetime.now(timezone.utc),
        )
        await gate.record_decision(record)

        decision = await gate.get_decision("rev-001")
    """

    def __init__(
        self,
        db_pool: Any | None = None,
        config_path: Optional[str | Path] = None,
        review_config: Optional[dict[str, Any]] = None,
    ) -> None:
        """构造审核闸。

        Args:
            db_pool: 可选的 asyncpg 连接池；为 None 时纯内存运行
            config_path: YAML 配置路径；不传时用项目内置默认
            review_config: 已加载的配置字典（优先级最高，便于单测注入）
        """
        self._db_pool = db_pool

        if review_config is not None:
            self._config = review_config
        else:
            self._config = self._load_config(
                Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
            )

        # 内存存储
        self._pending_requests: dict[str, ReviewRequest] = {}
        self._decisions: dict[str, ReviewRecord] = {}
        self._reminder_sent: dict[str, list[float]] = {}

        notifications = self._config.get("review_gates", {}).get(
            "notifications", {}
        )
        self._reminder_interval_seconds: int = notifications.get(
            "reminder_interval_seconds", 1800
        )
        self._notification_channels: list[dict[str, Any]] = notifications.get(
            "channels", []
        )

    # ------------------------------------------------------------------
    # 配置加载
    # ------------------------------------------------------------------
    @staticmethod
    def _load_config(config_path: Path) -> dict[str, Any]:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            logs.error(
                f"[review_gate] failed to load config | "
                f"path={config_path} error={e}"
            )
            return {}

    # ------------------------------------------------------------------
    # 公开 API（实现 ReviewGateInterface）
    # ------------------------------------------------------------------
    async def submit_for_review(self, request: ReviewRequest) -> str:
        """提交一条待审请求。"""
        self._pending_requests[request.request_id] = request
        self._reminder_sent[request.request_id] = []

        logs.info(
            f"[review_gate] submitted | "
            f"request_id={request.request_id} workflow_id={request.workflow_id} "
            f"agent={request.agent_name} timeout={request.timeout_seconds}s"
        )

        if self._db_pool is not None:
            await self._persist_request(request)

        return request.request_id

    async def get_decision(
        self, request_id: str
    ) -> Optional[ReviewRecord]:
        """查询某次审核的决策结果，未决时返回 None。"""
        if request_id in self._decisions:
            return self._decisions[request_id]

        if self._db_pool is not None:
            record = await self._fetch_decision_from_db(request_id)
            if record is not None:
                self._decisions[request_id] = record
                return record

        return None

    async def record_decision(self, record: ReviewRecord) -> None:
        """记录审核决策（通过 / 拒绝）。"""
        self._decisions[record.request_id] = record
        self._pending_requests.pop(record.request_id, None)
        self._reminder_sent.pop(record.request_id, None)

        logs.info(
            f"[review_gate] decision recorded | "
            f"request_id={record.request_id} reviewer={record.reviewer_id} "
            f"decision={record.decision.value}"
        )

        if self._db_pool is not None:
            await self._persist_decision(record)

    # ------------------------------------------------------------------
    # 配置查询便捷方法
    # ------------------------------------------------------------------
    def get_review_config(
        self, workflow_name: str
    ) -> Optional[dict[str, Any]]:
        """取某工作流的审核点配置；无则返回 None。"""
        workflows = self._config.get("review_gates", {}).get("workflows", {})
        return workflows.get(workflow_name)

    def is_review_required(
        self, workflow_name: str, agent_name: str
    ) -> bool:
        """判断某工作流在指定 agent 后是否需要审核。"""
        cfg = self.get_review_config(workflow_name)
        if not cfg:
            return False
        for point in cfg.get("review_points", []):
            if (
                point.get("after_agent") == agent_name
                and point.get("required", False)
            ):
                return True
        return False

    def get_timeout_for_review_point(
        self, workflow_name: str, agent_name: str
    ) -> int:
        """取审核点超时秒数；未配置返回 3600 秒兜底值。"""
        cfg = self.get_review_config(workflow_name)
        if not cfg:
            return 3600
        for point in cfg.get("review_points", []):
            if point.get("after_agent") == agent_name:
                return point.get("timeout_seconds", 3600)
        return 3600

    # ------------------------------------------------------------------
    # 超时巡检
    # ------------------------------------------------------------------
    async def check_timeouts(self) -> list[str]:
        """巡检所有待审请求，到达提醒间隔时发提醒，到达总超时时打 final 标记。

        Returns:
            本次触发提醒的 ``request_id`` 列表
        """
        now = time.time()
        reminded: list[str] = []

        for request_id, request in list(self._pending_requests.items()):
            elapsed = (
                datetime.now(timezone.utc) - request.created_at
            ).total_seconds()

            if elapsed >= request.timeout_seconds:
                await self._send_timeout_reminder(
                    request_id, request, is_final=True
                )
                reminded.append(request_id)
                continue

            last_reminders = self._reminder_sent.get(request_id, [])
            last_time = last_reminders[-1] if last_reminders else 0.0

            if (
                (now - last_time) >= self._reminder_interval_seconds
                and elapsed >= self._reminder_interval_seconds
            ):
                await self._send_timeout_reminder(
                    request_id, request, is_final=False
                )
                self._reminder_sent.setdefault(request_id, []).append(now)
                reminded.append(request_id)

        return reminded

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------
    def get_pending_reviews(self) -> dict[str, ReviewRequest]:
        """返回当前所有待审请求（拷贝）。"""
        return dict(self._pending_requests)

    def get_rejection_feedback(
        self, request_id: str
    ) -> Optional[dict[str, Any]]:
        """拿到拒绝反馈，方便 Orchestrator 把任务路由回原 Agent 重做。"""
        decision = self._decisions.get(request_id)
        if decision is None or decision.decision != ReviewDecision.REJECTED:
            return None
        return {
            "request_id": decision.request_id,
            "reviewer_id": decision.reviewer_id,
            "comments": decision.comments,
            "timestamp": decision.timestamp.isoformat(),
            "decision": decision.decision.value,
        }

    # ------------------------------------------------------------------
    # 内部：通知
    # ------------------------------------------------------------------
    async def _send_timeout_reminder(
        self,
        request_id: str,
        request: ReviewRequest,
        is_final: bool,
    ) -> None:
        reminder_type = "final_timeout" if is_final else "reminder"
        logs.warning(
            f"[review_gate] timeout reminder | "
            f"request_id={request_id} workflow_id={request.workflow_id} "
            f"agent={request.agent_name} type={reminder_type} "
            f"channels={[c.get('type') for c in self._notification_channels]}"
        )
        for channel in self._notification_channels:
            if channel.get("type") == "webhook":
                await self._send_webhook_notification(
                    channel, request_id, request, reminder_type
                )

    async def _send_webhook_notification(
        self,
        channel: dict[str, Any],
        request_id: str,
        request: ReviewRequest,
        reminder_type: str,
    ) -> None:
        """Webhook 通知占位实现，目前只打日志。

        正式接入时改为 ``httpx.AsyncClient`` 发 POST 即可。
        """
        logs.info(
            f"[review_gate] webhook fired | "
            f"url={channel.get('url', '')} request_id={request_id} "
            f"workflow_id={request.workflow_id} type={reminder_type}"
        )

    # ------------------------------------------------------------------
    # 内部：DB 持久化（可选，asyncpg 延迟导入）
    # ------------------------------------------------------------------
    async def _persist_request(self, request: ReviewRequest) -> None:
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO review_records
                        (request_id, workflow_id, agent_name, content,
                         decision, timeout_seconds, created_at)
                    VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                    ON CONFLICT (request_id) DO NOTHING
                    """,
                    request.request_id,
                    request.workflow_id,
                    request.agent_name,
                    json.dumps(request.content, default=str),
                    ReviewDecision.PENDING.value,
                    request.timeout_seconds,
                    request.created_at,
                )
        except Exception as e:  # noqa: BLE001
            logs.error(
                f"[review_gate] persist request failed | "
                f"request_id={request.request_id} error={e}"
            )

    async def _persist_decision(self, record: ReviewRecord) -> None:
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE review_records
                    SET reviewer_id = $1,
                        decision = $2,
                        comments = $3,
                        decided_at = $4
                    WHERE request_id = $5
                    """,
                    record.reviewer_id,
                    record.decision.value,
                    record.comments,
                    record.timestamp,
                    record.request_id,
                )
        except Exception as e:  # noqa: BLE001
            logs.error(
                f"[review_gate] persist decision failed | "
                f"request_id={record.request_id} error={e}"
            )

    async def _fetch_decision_from_db(
        self, request_id: str
    ) -> Optional[ReviewRecord]:
        try:
            async with self._db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT request_id, reviewer_id, decision, comments, decided_at
                    FROM review_records
                    WHERE request_id = $1 AND decision != $2
                    """,
                    request_id,
                    ReviewDecision.PENDING.value,
                )
                if row is None:
                    return None
                return ReviewRecord(
                    request_id=row["request_id"],
                    reviewer_id=row["reviewer_id"],
                    decision=ReviewDecision(row["decision"]),
                    comments=row["comments"] or "",
                    timestamp=row["decided_at"],
                )
        except Exception as e:  # noqa: BLE001
            logs.error(
                f"[review_gate] fetch decision failed | "
                f"request_id={request_id} error={e}"
            )
            return None


__all__ = ["HumanReviewGate"]
