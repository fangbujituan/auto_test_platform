"""
内置断言。

提供 5 种最常用的断言，覆盖 90% 接口测试场景：

- ``status_code``    HTTP 状态码精确匹配
- ``json_path``      JSON 路径取值后按 op 比较（exists / equals / in / contains / regex）
- ``text_contains``  响应文本包含子串（支持 negate 反向断言）
- ``response_time``  响应耗时上限
- ``header``         响应头按 op 比较

新增断言：在本文件追加一个 ``@register_assertion`` 装饰的类即可。

作者: yandc
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from app.engine.api_engine._utils import navigate_json_path
from app.engine.api_engine.assertions.base import BaseAssertion, register_assertion
from app.engine.api_engine.results import AssertionOutcome

if TYPE_CHECKING:
    from app.engine.api_engine.context import ExecutionContext
    from app.engine.api_engine.results import ResponseRecord


# ----------------------------------------------------------------------
# 通用工具
# ----------------------------------------------------------------------

def _name_of(config: dict[str, Any], default: str) -> str:
    return str(config.get("name") or default)


# ----------------------------------------------------------------------
# 1. 状态码断言
# ----------------------------------------------------------------------

@register_assertion
class StatusCodeAssertion(BaseAssertion):
    """期望响应状态码等于某值。

    config:
        - ``expected`` (int): 期望状态码，必填
    """

    type_name = "status_code"

    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> AssertionOutcome:
        try:
            expected = int(config["expected"])
        except (KeyError, TypeError, ValueError):
            return AssertionOutcome(
                type=self.type_name,
                name=_name_of(config, "状态码断言"),
                passed=False,
                message="config.expected 必填且为整数",
                expected=config.get("expected"),
                actual=response.status_code,
            )

        actual = response.status_code
        passed = actual == expected
        return AssertionOutcome(
            type=self.type_name,
            name=_name_of(config, f"状态码 == {expected}"),
            passed=passed,
            message=f"期望 {expected}, 实际 {actual}",
            expected=expected,
            actual=actual,
        )


# ----------------------------------------------------------------------
# 2. JSON 路径断言
# ----------------------------------------------------------------------

@register_assertion
class JsonPathAssertion(BaseAssertion):
    """从 JSON 响应按路径取值后做比较。

    config:
        - ``path`` (str):  JSON 路径，必填，例 ``$.data.token`` / ``items.0.id``
        - ``op`` (str):    比较操作，默认 ``equals``
                           可选: ``exists`` / ``not_exists`` / ``equals`` / ``not_equals``
                                 / ``contains`` / ``in`` / ``regex`` / ``gt`` / ``gte`` / ``lt`` / ``lte``
        - ``value`` (any): 期望值；exists / not_exists 时无意义
    """

    type_name = "json_path"

    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> AssertionOutcome:
        path = str(config.get("path") or "")
        op = str(config.get("op") or "equals").lower()
        expected = config.get("value")
        name = _name_of(config, f"JSON {path} {op}")

        if not path:
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message="config.path 必填",
                expected=expected, actual=None,
            )

        data = response.body
        if not isinstance(data, (dict, list)):
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message=f"响应体不是 JSON 对象/数组，无法按路径断言: {type(data).__name__}",
                expected=expected, actual=data,
            )

        found, actual = navigate_json_path(data, path)

        if op in ("exists", "not_exists"):
            passed = found if op == "exists" else not found
            msg = (
                f"路径 {path} {'存在' if found else '不存在'}，期望 {op}"
            )
            return AssertionOutcome(
                type=self.type_name, name=name, passed=passed,
                message=msg, expected=op, actual=found,
            )

        if not found:
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message=f"路径 {path} 在响应中不存在",
                expected=expected, actual=None,
            )

        passed, msg = self._compare(op, actual, expected)
        return AssertionOutcome(
            type=self.type_name, name=name, passed=passed,
            message=msg, expected=expected, actual=actual,
        )

    @staticmethod
    def _compare(op: str, actual: Any, expected: Any) -> tuple[bool, str]:
        if op == "equals":
            return actual == expected, f"期望 == {expected!r}, 实际 {actual!r}"
        if op == "not_equals":
            return actual != expected, f"期望 != {expected!r}, 实际 {actual!r}"
        if op == "contains":
            try:
                return expected in actual, f"期望包含 {expected!r}, 实际 {actual!r}"
            except TypeError:
                return False, f"实际值类型 {type(actual).__name__} 不支持 contains"
        if op == "in":
            try:
                return actual in expected, f"期望 {actual!r} 在 {expected!r} 中"
            except TypeError:
                return False, f"期望值类型 {type(expected).__name__} 不支持 in"
        if op == "regex":
            pattern = str(expected or "")
            try:
                matched = re.search(pattern, str(actual)) is not None
            except re.error as exc:
                return False, f"正则非法: {exc}"
            return matched, f"实际 {actual!r} {'匹配' if matched else '不匹配'} 模式 {pattern!r}"
        if op in ("gt", "gte", "lt", "lte"):
            try:
                a, e = float(actual), float(expected)
            except (TypeError, ValueError):
                return False, f"数值比较失败: actual={actual!r}, expected={expected!r}"
            comp = {"gt": a > e, "gte": a >= e, "lt": a < e, "lte": a <= e}[op]
            return comp, f"期望 {op} {expected!r}, 实际 {actual!r}"
        return False, f"不支持的 op: {op}"


# ----------------------------------------------------------------------
# 3. 文本包含断言
# ----------------------------------------------------------------------

@register_assertion
class TextContainsAssertion(BaseAssertion):
    """响应文本包含/不包含某子串。

    config:
        - ``value`` (str):    必填，子串
        - ``negate`` (bool):  默认 false；true 表示"不包含才算通过"
        - ``case_sensitive`` (bool): 默认 true
    """

    type_name = "text_contains"

    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> AssertionOutcome:
        substring = config.get("value")
        negate = bool(config.get("negate", False))
        case_sensitive = bool(config.get("case_sensitive", True))
        name = _name_of(
            config,
            f"响应文本{'不' if negate else ''}包含 {substring!r}",
        )

        if substring is None:
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message="config.value 必填", expected=substring, actual=None,
            )

        haystack = response.body_raw or ""
        if not isinstance(haystack, str):
            haystack = str(haystack)
        needle = str(substring)

        if not case_sensitive:
            haystack_cmp, needle_cmp = haystack.lower(), needle.lower()
        else:
            haystack_cmp, needle_cmp = haystack, needle

        contains = needle_cmp in haystack_cmp
        passed = (not contains) if negate else contains
        message = (
            f"{'未包含' if not contains else '包含'} {substring!r}; "
            f"期望 {'不包含' if negate else '包含'}"
        )
        return AssertionOutcome(
            type=self.type_name, name=name, passed=passed,
            message=message, expected=substring,
            actual=(haystack[:200] + "...") if len(haystack) > 200 else haystack,
        )


# ----------------------------------------------------------------------
# 4. 响应耗时断言
# ----------------------------------------------------------------------

@register_assertion
class ResponseTimeAssertion(BaseAssertion):
    """响应耗时不超过给定毫秒数。

    config:
        - ``max_ms`` (int|float): 上限，必填
    """

    type_name = "response_time"

    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> AssertionOutcome:
        try:
            max_ms = float(config["max_ms"])
        except (KeyError, TypeError, ValueError):
            return AssertionOutcome(
                type=self.type_name, name=_name_of(config, "响应耗时"),
                passed=False, message="config.max_ms 必填且为数值",
                expected=config.get("max_ms"), actual=response.elapsed_ms,
            )

        actual = response.elapsed_ms
        passed = actual <= max_ms
        return AssertionOutcome(
            type=self.type_name, name=_name_of(config, f"响应耗时 ≤ {max_ms}ms"),
            passed=passed,
            message=f"耗时 {actual:.1f}ms, 上限 {max_ms}ms",
            expected=max_ms, actual=actual,
        )


# ----------------------------------------------------------------------
# 5. Header 断言
# ----------------------------------------------------------------------

@register_assertion
class HeaderAssertion(BaseAssertion):
    """响应头比较。

    config:
        - ``name`` (str):  Header 名（大小写不敏感），必填
        - ``op`` (str):    ``exists`` / ``equals`` / ``contains`` / ``regex``，默认 ``equals``
        - ``value`` (str): 期望值；exists 时可省略
    """

    type_name = "header"

    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> AssertionOutcome:
        header_name = str(config.get("name") or "")
        op = str(config.get("op") or "equals").lower()
        expected = config.get("value")
        name = _name_of(config, f"Header {header_name} {op}")

        if not header_name:
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message="config.name 必填", expected=expected, actual=None,
            )

        # Header 大小写不敏感查找
        lower_map = {k.lower(): v for k, v in (response.headers or {}).items()}
        actual = lower_map.get(header_name.lower())
        found = actual is not None

        if op == "exists":
            return AssertionOutcome(
                type=self.type_name, name=name, passed=found,
                message=f"Header '{header_name}' {'存在' if found else '不存在'}",
                expected="exists", actual=actual,
            )

        if not found:
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message=f"Header '{header_name}' 不存在",
                expected=expected, actual=None,
            )

        if op == "equals":
            passed = str(actual) == str(expected)
            msg = f"期望 == {expected!r}, 实际 {actual!r}"
        elif op == "contains":
            passed = str(expected) in str(actual)
            msg = f"期望包含 {expected!r}, 实际 {actual!r}"
        elif op == "regex":
            try:
                passed = re.search(str(expected or ""), str(actual)) is not None
                msg = f"实际 {actual!r} {'匹配' if passed else '不匹配'} 模式 {expected!r}"
            except re.error as exc:
                return AssertionOutcome(
                    type=self.type_name, name=name, passed=False,
                    message=f"正则非法: {exc}",
                    expected=expected, actual=actual,
                )
        else:
            return AssertionOutcome(
                type=self.type_name, name=name, passed=False,
                message=f"不支持的 op: {op}",
                expected=expected, actual=actual,
            )

        return AssertionOutcome(
            type=self.type_name, name=name, passed=passed,
            message=msg, expected=expected, actual=actual,
        )


# ----------------------------------------------------------------------
# 6. JSON 子集断言（结构部分匹配）
# ----------------------------------------------------------------------

@register_assertion
class JsonSubsetAssertion(BaseAssertion):
    """期望响应 body 包含给定 expected 子结构。

    递归语义：
    - expected 是 dict：对每个 key，actual 必须有该 key 且其值递归匹配
    - expected 是 list：长度必须一致，每个元素递归匹配
    - 其他（标量）：直接 ``==`` 比较

    用于把 ``test_cases.expected_response`` 这种"声明式部分响应断言"
    无缝迁移到引擎，对应老 ``TestExecutor._match_response`` 行为。

    config:
        - ``expected`` (any): 期望的子结构，必填
    """

    type_name = "json_subset"

    def check(
        self,
        response: ResponseRecord,
        config: dict[str, Any],
        ctx: ExecutionContext,  # noqa: ARG002
    ) -> AssertionOutcome:
        if "expected" not in config:
            return AssertionOutcome(
                type=self.type_name, name=_name_of(config, "JSON 子集"),
                passed=False, message="config.expected 必填",
                expected=None, actual=response.body,
            )

        expected = config["expected"]
        actual = response.body

        diffs: list[str] = []
        passed = self._matches(expected, actual, path="$", diffs=diffs)

        return AssertionOutcome(
            type=self.type_name,
            name=_name_of(config, "响应包含期望子结构"),
            passed=passed,
            message=("子结构匹配通过" if passed else "; ".join(diffs[:5])),
            expected=expected,
            actual=actual,
        )

    def _matches(self, expected: Any, actual: Any, *, path: str, diffs: list[str]) -> bool:
        if isinstance(expected, dict):
            if not isinstance(actual, dict):
                diffs.append(f"{path}: 期望 dict, 实际 {type(actual).__name__}")
                return False
            ok = True
            for key, sub_expected in expected.items():
                if key not in actual:
                    diffs.append(f"{path}.{key}: 缺字段")
                    ok = False
                    continue
                if not self._matches(sub_expected, actual[key], path=f"{path}.{key}", diffs=diffs):
                    ok = False
            return ok

        if isinstance(expected, list):
            if not isinstance(actual, list):
                diffs.append(f"{path}: 期望 list, 实际 {type(actual).__name__}")
                return False
            if len(expected) != len(actual):
                diffs.append(f"{path}: 长度 期望={len(expected)} 实际={len(actual)}")
                return False
            ok = True
            for idx, (e, a) in enumerate(zip(expected, actual)):
                if not self._matches(e, a, path=f"{path}.{idx}", diffs=diffs):
                    ok = False
            return ok

        # 标量
        if expected != actual:
            diffs.append(f"{path}: 期望 {expected!r}, 实际 {actual!r}")
            return False
        return True
