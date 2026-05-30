"""Agent 系统提示词集合。"""

from app.agents.prompts.recording import RECORDING_SYSTEM_PROMPT
from app.agents.prompts.ui_automation import (
    GENERAL_PURPOSE_DESCRIPTION,
    GENERAL_PURPOSE_SYSTEM_PROMPT,
    MAIN_AGENT_PROMPT,
    SYSTEM_PROMPT,
)

__all__ = [
    "SYSTEM_PROMPT",
    "MAIN_AGENT_PROMPT",
    "GENERAL_PURPOSE_SYSTEM_PROMPT",
    "GENERAL_PURPOSE_DESCRIPTION",
    "RECORDING_SYSTEM_PROMPT",
]
