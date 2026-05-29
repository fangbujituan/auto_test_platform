"""
用例管理工具

供 Agent 调用的用例管理工具，支持创建、完成、重命名用例。
"""

from typing import Optional

from langchain_core.tools import tool

from tools.utils.token_counter import (
    get_token_counter,
    set_current_case_id,
    get_current_case_id,
)


@tool
def case_create(
    name: Optional[str] = None,
    agent_name: str = "recording_agent",
    thread_id: Optional[str] = None,
) -> dict:
    """
    创建一个新的测试用例用于跟踪 token 消耗。

    当用户开始一个新的测试任务时调用此工具创建用例。
    用例创建后，后续所有的 token 消耗都会自动关联到该用例。

    Args:
        name: 用例名称（可选）。如未指定，将自动生成"未命名_时间戳"格式。
              建议使用有意义的名称，如"登录测试"、"数据导出"等。
        agent_name: Agent 名称，默认为 "recording_agent"
        thread_id: LangGraph thread ID（可选）

    Returns:
        包含 case_id 和创建信息的字典，例如：
        {
            "case_id": "abc123",
            "name": "登录测试_20260320_1430",
            "status": "active",
            "message": "用例创建成功"
        }
    """
    from datetime import datetime

    counter = get_token_counter()

    # 自动生成名称
    if not name:
        name = f"未命名_{datetime.now().strftime('%Y%m%d_%H%M')}"

    result = counter.create_case(
        name=name,
        agent_name=agent_name,
        thread_id=thread_id,
    )

    # 设置当前用例 ID，后续 token 记录会自动关联
    set_current_case_id(result["case_id"])

    return result


@tool
def case_get_stats(case_id: Optional[str] = None) -> dict:
    """
    获取用例的当前统计信息。

    每次 AI 回复时调用此工具获取 token 消耗统计，然后追加到回复末尾展示给用户。

    Args:
        case_id: 用例 ID（可选）。如未指定，使用当前活跃用例。

    Returns:
        用例统计信息，包含格式化的摘要文本：
        {
            "success": True,
            "case_id": "abc123",
            "name": "登录测试",
            "current_message_tokens": 1250,
            "case_total_tokens": 5430,
            "message_count": 5,
            "estimated_cost_cny": 0.008,
            "summary": "📊 本次消耗: 1,250 tokens\n📋 用例总计: 5,430 tokens\n💰 预估费用: ¥0.008"
        }

    使用示例：
        # 在每次回复后调用
        stats = case_get_stats()
        # 将 stats["summary"] 追加到 AI 回复末尾
    """
    counter = get_token_counter()

    if not case_id:
        case_id = get_current_case_id()

    if not case_id:
        return {
            "success": False,
            "error": "未找到活跃用例，请先调用 case_create 创建用例"
        }

    return counter.get_case_current_stats(case_id)


@tool
def case_complete(
    status: str = "completed",
    note: Optional[str] = None,
    case_id: Optional[str] = None,
) -> dict:
    """
    完成当前用例并返回最终统计。

    当用户发送"完成"、"结束"或开始新任务时调用此工具。
    完成后，用例状态将变为 "completed" 或 "failed"。

    Args:
        status: 最终状态，可选值：
            - "completed": 任务成功完成（默认）
            - "failed": 任务失败
        note: 完成备注（可选）
        case_id: 用例 ID（可选，默认使用当前用例）

    Returns:
        用例完成统计信息：
        {
            "success": True,
            "case_id": "abc123",
            "name": "登录测试",
            "status": "completed",
            "duration_seconds": 180,
            "message_count": 10,
            "total_tokens": 12500,
            "estimated_cost_cny": 0.018,
            "summary": "✅ 用例完成\n📊 总消耗: 12,500 tokens\n⏱️ 耗时: 3分0秒\n💰 费用: ¥0.018\n🔄 对话轮次: 10"
        }

    使用场景：
        - 用户说"完成了"、"结束"
        - 用户开始新的测试任务（自动结束上一个用例）
        - 测试执行失败
    """
    counter = get_token_counter()

    if not case_id:
        case_id = get_current_case_id()

    if not case_id:
        return {
            "success": False,
            "error": "未找到活跃用例"
        }

    result = counter.complete_case(case_id, status=status, note=note or "")

    # 清除当前用例 ID
    set_current_case_id(None)

    return result


@tool
def case_rename(new_name: str, case_id: Optional[str] = None) -> dict:
    """
    重命名用例。

    当用户想要给当前用例一个更有意义的名称时调用。

    Args:
        new_name: 新的用例名称
        case_id: 用例 ID（可选，默认使用当前用例）

    Returns:
        更新结果：
        {
            "success": True,
            "case_id": "abc123",
            "name": "登录测试_v2",
            "message": "用例名称更新成功"
        }

    使用示例：
        用户: "把这个用例命名为登录测试"
        AI: 调用 case_rename("登录测试")
    """
    counter = get_token_counter()

    if not case_id:
        case_id = get_current_case_id()

    if not case_id:
        return {
            "success": False,
            "error": "未找到活跃用例"
        }

    return counter.update_case_name(case_id, new_name)


@tool
def case_list(
    status: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """
    获取用例列表。

    当用户想要查看历史用例记录时调用。

    Args:
        status: 状态筛选（可选）：
            - "active": 进行中
            - "completed": 已完成
            - "failed": 已失败
        limit: 返回数量限制，默认 10 条

    Returns:
        用例列表：
        {
            "total": 25,
            "cases": [
                {
                    "id": "abc123",
                    "name": "登录测试",
                    "status": "completed",
                    "total_tokens": 12500,
                    "message_count": 10,
                    "estimated_cost_cny": 0.018
                }
            ]
        }
    """
    counter = get_token_counter()
    return counter.get_cases(
        status=status,
        page=1,
        page_size=min(limit, 50),
    )


# 导出所有工具
CASE_TOOLS = [
    case_create,
    case_get_stats,
    case_complete,
    case_rename,
    case_list,
]
