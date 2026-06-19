"""
运行时输入 DTO（spec）。

引擎内部一律消费 spec，**绝不直接接受 ORM 对象或裸 dict**。
所有"数据库模型/前端 JSON → spec"的转换由 ``loaders`` 子包负责。

命名约定：
- ``Spec`` 后缀表示"待执行的描述"
- ``Rule`` 后缀表示"声明式规则"

作者: yandc
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# 显式列出取值，便于 IDE 提示和 mypy 校验
BodyType = Literal["json", "form", "raw", "multipart"]
OnFailurePolicy = Literal["stop", "continue", "inherit"]
FailStrategyName = Literal["fail_fast", "continue"]


@dataclass(frozen=True)
class AssertionRule:
    """单条断言规则。

    type 决定走哪个 ``BaseAssertion`` 子类；config 是该断言所需的参数。
    例：
        AssertionRule(type="status_code", config={"expected": 200})
        AssertionRule(type="json_path", config={"path": "$.data.id", "op": "exists"})
    """

    type: str
    config: dict[str, Any] = field(default_factory=dict)
    name: str = ""  # 可选展示名，仅用于报告

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "config": dict(self.config), "name": self.name}


@dataclass(frozen=True)
class ExtractRule:
    """从响应中抽取字段写入 ExecutionContext。

    例：
        ExtractRule(name="token", type="json_path", expression="$.data.token")
        ExtractRule(name="trace_id", type="header", expression="X-Trace-Id")
    """

    name: str
    type: str
    expression: str
    default: Any = None  # 抽取失败时的回退值；None 表示无回退

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "expression": self.expression,
            "default": self.default,
        }


@dataclass
class RequestSpec:
    """单个接口的执行规格。

    渲染前后都用这个类型；StepExecutor 在 ``ctx.render_request`` 后会得到一个
    新的 RequestSpec（变量已替换）作为"实际请求"传给 HttpClient。
    """

    name: str
    method: str
    url: str  # 可含 {{var}}，可以是完整 URL 或仅 path
    headers: dict[str, Any] = field(default_factory=dict)
    params: dict[str, Any] = field(default_factory=dict)
    body: Any = None
    body_type: BodyType = "json"

    timeout: int = 30
    delay_ms: int = 0  # 本步执行结束后等待时间，给下一步用
    on_failure: OnFailurePolicy = "inherit"

    extracts: list[ExtractRule] = field(default_factory=list)
    assertions: list[AssertionRule] = field(default_factory=list)

    # 路由匹配辅助字段（来自 apis 表，由 prefix_url 解析使用）
    api_id: int | None = None
    case_id: int | None = None  # 当 spec 来自 test_cases 表时填充（与 api_id 互斥）
    module: str | None = None
    service: str | None = None
    prefix_url_id: int | None = None
    base_url: str | None = None  # 接口自带域名（优先级最高）

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "method": self.method,
            "url": self.url,
            "headers": dict(self.headers),
            "params": dict(self.params),
            "body": self.body,
            "body_type": self.body_type,
            "timeout": self.timeout,
            "delay_ms": self.delay_ms,
            "on_failure": self.on_failure,
            "extracts": [r.to_dict() for r in self.extracts],
            "assertions": [r.to_dict() for r in self.assertions],
            "api_id": self.api_id,
            "case_id": self.case_id,
            "module": self.module,
            "service": self.service,
            "prefix_url_id": self.prefix_url_id,
            "base_url": self.base_url,
        }


@dataclass
class CollectionSpec:
    """一组接口的编排执行规格。

    单接口执行 = 长度为 1 的 collection。引擎内部统一走 SequenceRunner，
    避免维护两条管道。
    """

    name: str
    project_id: int
    environment_id: int | None
    requests: list[RequestSpec]
    fail_strategy: FailStrategyName = "continue"
    iterations: int = 1  # 数据驱动留口子，本期固定 1
    initial_variables: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "project_id": self.project_id,
            "environment_id": self.environment_id,
            "requests": [r.to_dict() for r in self.requests],
            "fail_strategy": self.fail_strategy,
            "iterations": self.iterations,
            "initial_variables": dict(self.initial_variables),
        }
