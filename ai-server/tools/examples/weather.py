"""
天气查询工具模块
"""

from langchain_core.tools import tool


@tool
def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"{city}，今天是晴天，温度为 25 摄氏度。!"
