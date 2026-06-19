"""
内置抽取器：3 种最常用的抽取方式。

- ``json_path``  按 dotted path 取 JSON 响应字段（与 JsonPathAssertion 同语法）
- ``regex``      按正则在响应文本中提取（默认取第 1 个分组，支持 group=N）
- ``header``     按 Header 名取值（大小写不敏感）

新增抽取器：在本文件追加 ``@register_extractor`` 装饰的类即可。

作者: yandc
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.engine.api_engine._utils import navigate_json_path
from app.engine.api_engine.extractors.base import BaseExtractor, register_extractor
from app.engine.api_engine.results import ExtractOutcome

if TYPE_CHECKING:
    from app.engine.api_engine.results import ResponseRecord


def _build_outcome(
    *,
    name: str,
    type_name: str,
    expression: str,
    succeeded: bool,
    value: Any,
    default: Any,
    fail_message: str,
) -> ExtractOutcome:
    """构造 ExtractOutcome：未成功且配置了 default 时回退到 default。"""
    if succeeded:
        return ExtractOutcome(
            name=name, type=type_name, expression=expression,
            value=value, succeeded=True,
            message=f"抽取成功: {name} = {value!r}",
        )
    if default is not None:
        return ExtractOutcome(
            name=name, type=type_name, expression=expression,
            value=default, succeeded=False,
            message=f"{fail_message}; 已使用 default={default!r}",
        )
    return ExtractOutcome(
        name=name, type=type_name, expression=expression,
        value=None, succeeded=False, message=fail_message,
    )


# ----------------------------------------------------------------------
# 1. JSON Path
# ----------------------------------------------------------------------

@register_extractor
class JsonPathExtractor(BaseExtractor):
    """从 JSON 响应按路径取字段。

    例：
        ExtractRule(name="token", type="json_path", expression="$.data.token")
    """

    type_name = "json_path"

    def extract(
        self,
        response: ResponseRecord,
        name: str,
        expression: str,
        default: Any,
    ) -> ExtractOutcome:
        if not expression:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message="expression 必填",
            )

        data = response.body
        if not isinstance(data, (dict, list)):
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message=f"响应体不是 JSON 对象/数组: {type(data).__name__}",
            )

        found, value = navigate_json_path(data, expression)
        if not found:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message=f"路径 {expression} 未命中",
            )

        return _build_outcome(
            name=name, type_name=self.type_name, expression=expression,
            succeeded=True, value=value, default=default,
            fail_message="",
        )


# ----------------------------------------------------------------------
# 2. Regex
# ----------------------------------------------------------------------

@register_extractor
class RegexExtractor(BaseExtractor):
    """按正则从响应文本中抽取。

    expression: 正则模式；默认取第 1 个分组（无分组则取整段命中）。
    可通过 ``ExtractRule`` 暂不暴露 group 配置（后续按需扩展）。

    例：
        ExtractRule(name="trace", type="regex", expression="trace_id=(\\w+)")
    """

    type_name = "regex"

    def extract(
        self,
        response: ResponseRecord,
        name: str,
        expression: str,
        default: Any,
    ) -> ExtractOutcome:
        if not expression:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message="expression 必填",
            )

        haystack = response.body_raw or ""
        if not isinstance(haystack, str):
            haystack = str(haystack)

        try:
            match = re.search(expression, haystack)
        except re.error as exc:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message=f"正则非法: {exc}",
            )

        if match is None:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message=f"未匹配到模式 {expression!r}",
            )

        # 优先取第 1 个分组，没有分组就取整段
        value = match.group(1) if match.groups() else match.group(0)
        return _build_outcome(
            name=name, type_name=self.type_name, expression=expression,
            succeeded=True, value=value, default=default,
            fail_message="",
        )


# ----------------------------------------------------------------------
# 3. Header
# ----------------------------------------------------------------------

@register_extractor
class HeaderExtractor(BaseExtractor):
    """按 Header 名（大小写不敏感）从响应头中取值。

    例：
        ExtractRule(name="trace_id", type="header", expression="X-Trace-Id")
    """

    type_name = "header"

    def extract(
        self,
        response: ResponseRecord,
        name: str,
        expression: str,
        default: Any,
    ) -> ExtractOutcome:
        if not expression:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message="expression 必填（应为 Header 名）",
            )

        lower_map = {k.lower(): v for k, v in (response.headers or {}).items()}
        value = lower_map.get(expression.lower())

        if value is None:
            return _build_outcome(
                name=name, type_name=self.type_name, expression=expression,
                succeeded=False, value=None, default=default,
                fail_message=f"Header '{expression}' 不存在",
            )

        return _build_outcome(
            name=name, type_name=self.type_name, expression=expression,
            succeeded=True, value=value, default=default,
            fail_message="",
        )
