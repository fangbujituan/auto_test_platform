"""
用例管理工具（供 Agent 调用）。

迁移自 ai-server/tools/utils/case_tools.py。

功能：
- ``case_create``    创建一个新用例并设置为当前活跃用例
- ``case_get_stats`` 获取当前/指定用例的实时统计（每轮 AI 回复后追加展示）
- ``case_complete``  完成用例，返回最终统计
- ``case_rename``    重命名用例
- ``case_list``      列出最近用例

用例创建后，所有 LLM 调用产生的 token 会自动关联到当前用例（通过
``token_counter`` 的 ContextVar 实现）。
"""

from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from app.utils.token_counter import (
    get_current_case_id,
    get_token_counter,
    set_current_case_id,
)


@tool
def case_create(
    name: Optional[str] = None,
    agent_name: str = "recording_agent",
    thread_id: Optional[str] = None,
) -> dict:
    """创建一个新的测试用例用于跟踪 token 消耗。

    用户开始一个新测试任务时调用此工具。创建后，后续所有 token 会自动关联到该用例。

    Args:
        name: 用例名称（可选）。未指定时自动生成 "未命名_<时间戳>"。
            建议使用有意义的名称，如 "登录测试"、"数据导出"。
        agent_name: Agent 名称，默认 "recording_agent"。
        thread_id: LangGraph thread ID（可选）。

    Returns:
        ``{"case_id": ..., "name": ..., "status": "active", "message": ...}``
    """
    counter = get_token_counter()

    if not name:
        name = f"未命名_{datetime.now().strftime('%Y%m%d_%H%M')}"

    result = counter.create_case(
        name=name,
        agent_name=agent_name,
        thread_id=thread_id,
    )
    set_current_case_id(result["case_id"])
    return result


@tool
def case_get_stats(case_id: Optional[str] = None) -> dict:
    """获取用例的当前统计信息。

    每次 AI 回复时调用，把返回的 ``summary`` 文本追加到回复末尾即可让用户看到
    本次消耗、累计消耗与预估费用。

    Args:
        case_id: 用例 ID（可选）。未指定时使用当前活跃用例。

    Returns:
        包含 ``summary``、``current_message_tokens``、``case_total_tokens`` 等字段。
    """
    counter = get_token_counter()
    case_id = case_id or get_current_case_id()
    if not case_id:
        return {
            "success": False,
            "error": "未找到活跃用例，请先调用 case_create 创建用例",
        }
    return counter.get_case_current_stats(case_id)


@tool
def case_complete(
    status: str = "completed",
    note: Optional[str] = None,
    case_id: Optional[str] = None,
) -> dict:
    """完成当前用例并返回最终统计。

    当用户说 "完成"、"结束"，或开始新任务时调用。完成后用例状态变为
    ``completed`` 或 ``failed``。

    Args:
        status: 最终状态，``completed`` / ``failed``。
        note: 完成备注（可选）。
        case_id: 用例 ID（可选，默认当前活跃用例）。

    Returns:
        包含 ``summary``、``duration_seconds``、``total_tokens``、
        ``estimated_cost_cny`` 等字段。
    """
    counter = get_token_counter()
    case_id = case_id or get_current_case_id()
    if not case_id:
        return {"success": False, "error": "未找到活跃用例"}

    result = counter.complete_case(case_id, status=status, note=note or "")
    set_current_case_id(None)
    return result


@tool
def case_rename(new_name: str, case_id: Optional[str] = None) -> dict:
    """重命名用例。

    用户希望给当前用例起一个更有意义的名字时调用。

    Args:
        new_name: 新名称。
        case_id: 用例 ID（可选，默认当前活跃用例）。
    """
    counter = get_token_counter()
    case_id = case_id or get_current_case_id()
    if not case_id:
        return {"success": False, "error": "未找到活跃用例"}
    return counter.update_case_name(case_id, new_name)


@tool
def case_list(
    status: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """获取用例列表（用户查询历史用例时调用）。

    Args:
        status: 状态筛选，``active`` / ``completed`` / ``failed``，默认全部。
        limit: 返回数量上限，最多 50。
    """
    counter = get_token_counter()
    return counter.get_cases(
        status=status,
        page=1,
        page_size=min(limit, 50),
    )


# 集中导出，便于 agent 一次性挂载
CASE_TOOLS = [
    case_create,
    case_get_stats,
    case_complete,
    case_rename,
    case_list,
]


__all__ = [
    "CASE_TOOLS",
    "case_create",
    "case_get_stats",
    "case_complete",
    "case_rename",
    "case_list",
]
