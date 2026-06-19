"""
api_engine 内部共享工具（assertions 与 extractors 共用）。

下划线前缀表示内部模块，不在 ``__init__.py`` 中导出。

作者: yandc
"""
from __future__ import annotations

from typing import Any


def navigate_json_path(data: Any, path: str) -> tuple[bool, Any]:
    """按点号路径在 dict / list 中取值。

    支持的语法（对齐 Postman 与 liu_shui_xian 历史用法）：

    - ``$.data.token``   根对象前的 ``$`` 可省略
    - ``data.token``     同上
    - ``items.0.id``     纯数字段视为 list 索引（支持负数）
    - ``code``           顶层字段

    Returns:
        (是否找到, 取到的值)；未找到时 value 为 None。
    """
    if not path:
        return True, data

    if path.startswith("$."):
        cleaned = path[2:]
    elif path.startswith("$"):
        cleaned = path[1:]
    else:
        cleaned = path

    if not cleaned:
        return True, data

    current: Any = data
    for segment in cleaned.split("."):
        if segment == "":
            continue
        if isinstance(current, dict) and segment in current:
            current = current[segment]
            continue
        if isinstance(current, list) and segment.lstrip("-").isdigit():
            idx = int(segment)
            if -len(current) <= idx < len(current):
                current = current[idx]
                continue
        return False, None
    return True, current
