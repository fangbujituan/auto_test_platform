"""
Human-in-the-Loop 审核闸使用的数据模型与枚举。

只承载 **数据**，不含调用逻辑。被 ``review.review_gate`` 共享使用。

迁移自 ``code-factory/src/core/models.py`` 中的 Human Review Gate 部分。

数据结构概览
------------

- :class:`ReviewDecision`   审核决策枚举
- :class:`ReviewRequest`    审核请求（待审内容 + 超时配置）
- :class:`ReviewRecord`     审核结果记录（决策 + 评论 + 时间戳）

作者: yandc
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class ReviewDecision(str, Enum):
    """审核决策。

    继承 ``str`` 便于直接用于 JSON 序列化与数据库 enum 字段。
    """

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class ReviewRequest:
    """提交给审核闸的待审请求。

    Attributes:
        request_id:       请求唯一 ID（建议 UUID）
        workflow_id:      所属工作流 ID
        agent_name:       触发审核的 Agent 名称
        content:          待审核内容（任意字典，由提交方决定结构）
        created_at:       提交时间（UTC）
        timeout_seconds:  超时时间（秒）；超时后审核闸会推送提醒
    """

    request_id: str
    workflow_id: str
    agent_name: str
    content: dict[str, Any]
    created_at: datetime
    timeout_seconds: int


@dataclass
class ReviewRecord:
    """审核完成后的决策记录。

    Attributes:
        request_id:    对应的 ``ReviewRequest.request_id``
        reviewer_id:   审核人 ID（用户 ID 字符串或邮箱）
        decision:      审核决策
        comments:      审核评论；拒绝时承担"反馈给原 Agent 重做"的载荷
        timestamp:     决策时间（UTC）
    """

    request_id: str
    reviewer_id: str
    decision: ReviewDecision
    comments: str
    timestamp: datetime


__all__ = [
    "ReviewDecision",
    "ReviewRequest",
    "ReviewRecord",
]
