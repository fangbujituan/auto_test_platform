"""Agent 提示词集合。

包含两类来源：

1. **代码内置**（``recording.py`` / ``ui_automation.py``）——
   写死在源码里的稳定提示词，主要给录制 / UI 自动化等 agent 用。
2. **数据库托管**（``db_prompt.py``）——
   通过 ``ai_prompt_templates`` 表管理，可在前端编辑、热更新。
   通用业务场景优先走这条路径。
"""

from app.agents.prompts.db_prompt import (
    PromptNotFoundError,
    load_chat_prompt,
    render_messages,
)
from app.agents.prompts.recording import RECORDING_SYSTEM_PROMPT
from app.agents.prompts.ui_automation import (
    GENERAL_PURPOSE_DESCRIPTION,
    GENERAL_PURPOSE_SYSTEM_PROMPT,
    MAIN_AGENT_PROMPT,
    SYSTEM_PROMPT,
)

__all__ = [
    # 数据库提示词
    "load_chat_prompt",
    "render_messages",
    "PromptNotFoundError",
    # 代码内置提示词
    "SYSTEM_PROMPT",
    "MAIN_AGENT_PROMPT",
    "GENERAL_PURPOSE_SYSTEM_PROMPT",
    "GENERAL_PURPOSE_DESCRIPTION",
    "RECORDING_SYSTEM_PROMPT",
]
