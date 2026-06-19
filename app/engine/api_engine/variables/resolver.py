"""
变量渲染器：把字符串 / dict / list / JSON body 中的 ``{{var}}`` 占位符
替换成给定上下文里的值。

设计要点：
- 占位符未命中时**原样保留**，并把缺失的变量名累计到 ``missing_keys``，由调用方决定是否上报为 warning。
- 不会就地修改入参，所有递归调用都返回新对象，dataclass 友好。
- 支持嵌套结构与 JSON 字符串（body 既可能是 dict，也可能是 str）。

复用了 ``app/services/variable_replacer.py`` 的 ``VARIABLE_PATTERN`` 语义，
但**不**直接 import 那里的私有函数，避免循环依赖。

作者: yandc
"""
from __future__ import annotations

import re
from typing import Any

# 与 services.variable_replacer 保持一致的 {{var}} 语法
VARIABLE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


class VariableResolver:
    """无副作用的变量渲染器。

    多次调用同一实例时 ``missing_keys`` 会累计；调用方需要自行 ``reset()`` 或
    新建实例。
    """

    def __init__(self) -> None:
        self.missing_keys: set[str] = set()

    def reset(self) -> None:
        self.missing_keys = set()

    def render_string(self, text: str, variables: dict[str, Any]) -> str:
        """替换字符串中所有 ``{{var}}`` 占位符。"""
        if not isinstance(text, str):
            return text

        def _sub(match: re.Match[str]) -> str:
            key = match.group(1)
            if key in variables:
                value = variables[key]
                # 非字符串值转 str；None 转空串与 Postman 行为一致
                return "" if value is None else str(value)
            self.missing_keys.add(key)
            return match.group(0)

        return VARIABLE_PATTERN.sub(_sub, text)

    def render_value(self, value: Any, variables: dict[str, Any]) -> Any:
        """递归替换值中的占位符。

        支持 str / dict / list / tuple；其他类型原样返回。
        """
        if isinstance(value, str):
            return self.render_string(value, variables)
        if isinstance(value, dict):
            return {k: self.render_value(v, variables) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render_value(item, variables) for item in value]
        if isinstance(value, tuple):
            return tuple(self.render_value(item, variables) for item in value)
        return value
