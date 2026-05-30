"""
测试用例相关的 Agent 工具。

把 ``app.services.testcase_generator`` 包成 LangChain ``@tool``，
- UI Agent 内部可直接装载
- MCP Server 可一键转发为 MCP tool
- HTTP 路由也能直接调底层 service（不走这层）
"""

from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool

from app.services.testcase_generator import (
    TestCaseGenerationResult,
    ai_chat,
    generate_test_cases,
)


@tool
def ai_chat_simple(prompt: str, model: Optional[str] = None) -> str:
    """最简单的 LLM 问答工具，用于流程验证。

    用途场景：
    - 验证整条调用链是通的（不在乎答案质量）
    - 给外部 Agent 一个借用本平台 LLM 的口子
    - 简单的代码 / 思路探讨

    不做任何结构化约束，1+1=? 也能问，连最小的 LLM 也扛得住。

    Args:
        prompt: 用户问题
        model: 模型标识（如 ``local/llama3.2-1b``）。不传走默认网关
    """
    return ai_chat(prompt=prompt, model=model)


@tool
def ai_generate_test_cases(
    requirement: str,
    extra_context: Optional[str] = None,
    model: Optional[str] = None,
) -> dict:
    """根据需求描述自动生成结构化的测试用例列表。

    用例覆盖正常流程、边界条件、异常场景三类，每条用例包含 title、
    precondition、steps、expected_result、priority、case_type。

    Args:
        requirement: 需求描述文本（必填）。可以是产品需求、用户故事、API 描述等
        extra_context: 附加上下文（可选）。例如已有的相关用例、API 字段定义、约束条件
        model: 指定使用的 LLM（可选）。格式如 ``local/llama3.2-1b`` /
            ``aiop/azure/gpt-5.4`` / ``deepseek``。不传走默认网关

    Returns:
        ``{"cases": [...], "summary": str, "case_count": int, "model": str}``
    """
    result: TestCaseGenerationResult = generate_test_cases(
        requirement=requirement,
        model=model,
        extra_context=extra_context,
    )
    return {
        "cases": [c.model_dump() for c in result.cases],
        "summary": result.summary,
        "case_count": result.case_count,
        "model": result.model,
    }


# 集中导出
TESTCASE_TOOLS = [ai_chat_simple, ai_generate_test_cases]


__all__ = [
    "ai_chat_simple",
    "ai_generate_test_cases",
    "TESTCASE_TOOLS",
]
