"""
数据库提示词模板适配器。

把 ``ai_prompt_templates`` 表里的提示词，按 scene 加载并包装成
LangChain ``ChatPromptTemplate``，方便 chain / agent 直接使用。

设计原则
--------
- **真实数据来源在数据库**：这里只读不写，不缓存（首版保持简单，后续可加 LRU）。
- **占位符语法保持与 AIService 一致**：使用 ``{var}`` 形式，由 LangChain
  的默认 f-string 模板引擎渲染。AIService 用的是 ``str.format_map``，二者
  对单层 ``{var}`` 占位符语义等价。
- **强校验**：scene 不存在时直接抛 ``PromptNotFoundError``，避免静默退化
  到默认 prompt 造成业务侧难以排查。

作者: yandc
"""
from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate


class PromptNotFoundError(LookupError):
    """指定 scene 在 ``ai_prompt_templates`` 表中不存在时抛出。"""


def load_chat_prompt(scene: str) -> ChatPromptTemplate:
    """
    按 scene 从数据库加载提示词，返回 LangChain ``ChatPromptTemplate``。

    Args:
        scene: ``ai_prompt_templates.scene`` 字段的值，如 ``test_case_generation``

    Returns:
        ChatPromptTemplate: 已包含 system + user 两条消息模板。

    Raises:
        PromptNotFoundError: 找不到对应 scene 的模板。

    注意：
        - 必须在 Flask app context 内调用（要查 ORM）。
        - 由于模板内容用 f-string 渲染，业务变量名要避免与 LangChain 保留字
          冲突。如果模板里需要写字面 ``{`` / ``}``，记得用 ``{{`` / ``}}`` 转义。
    """
    # 延迟导入，避免在 agent 包导入期就拉起 Flask / SQLAlchemy
    from app.models.ai_prompt import AIPromptTemplate

    template = AIPromptTemplate.query.filter_by(scene=scene).first()
    if not template:
        raise PromptNotFoundError(
            f"未找到场景 '{scene}' 的提示词模板（ai_prompt_templates）"
        )

    return ChatPromptTemplate.from_messages(
        [
            ("system", template.system_prompt),
            ("human", template.user_prompt_template),
        ]
    )


def render_messages(scene: str, variables: dict) -> list:
    """
    便捷函数：加载模板并立即渲染成消息列表。

    适合"只想拿一组现成 messages 喂给 ChatModel"的简单场景。

    Args:
        scene: 场景标识
        variables: 模板变量字典

    Returns:
        list[BaseMessage]: LangChain 消息列表，可直接传给 ``ChatModel.invoke``。
    """
    prompt = load_chat_prompt(scene)
    return prompt.format_messages(**variables)
