"""
运行时输出 DTO。

每个执行结果都自带 ``to_dict()``，便于 Reporter 序列化或路由层直接 jsonify。

作者: yandc
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


def _isoformat(dt: datetime | None) -> str | None:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


@dataclass
class AssertionOutcome:
    """单条断言的执行结果。"""

    type: str
    name: str
    passed: bool
    message: str
    expected: Any = None
    actual: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "passed": self.passed,
            "message": self.message,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class ExtractOutcome:
    """单条抽取的执行结果。"""

    name: str
    type: str
    expression: str
    value: Any
    succeeded: bool  # 是否真正抽到值（用 default 兜底时也会是 false）
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "expression": self.expression,
            "value": self.value,
            "succeeded": self.succeeded,
            "message": self.message,
        }


@dataclass
class RequestRecord:
    """实际发出的请求快照（变量已渲染、URL 已拼接）。"""

    method: str
    url: str
    headers: dict[str, Any]
    params: dict[str, Any]
    body: Any
    body_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "url": self.url,
            "headers": dict(self.headers),
            "params": dict(self.params),
            "body": self.body,
            "body_type": self.body_type,
        }


@dataclass
class ResponseRecord:
    """响应快照。"""

    status_code: int
    status_text: str
    headers: dict[str, Any]
    body: Any
    body_raw: str | None
    size: int
    encoding: str | None
    elapsed_ms: float  # 单接口耗时，AssertResponseTime 直接读取

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "status_text": self.status_text,
            "headers": dict(self.headers),
            "body": self.body,
            "body_raw": self.body_raw,
            "size": self.size,
            "encoding": self.encoding,
            "elapsed_ms": self.elapsed_ms,
        }


@dataclass
class StepResult:
    """单接口（单 step）执行结果。"""

    name: str
    api_id: int | None
    step_index: int
    passed: bool
    request: RequestRecord | None
    response: ResponseRecord | None
    assertions: list[AssertionOutcome]
    extracts: list[ExtractOutcome]
    duration: float  # 秒
    started_at: datetime
    finished_at: datetime
    case_id: int | None = None  # spec 来自 test_cases 表时填充
    error: str | None = None
    error_type: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "api_id": self.api_id,
            "case_id": self.case_id,
            "step_index": self.step_index,
            "passed": self.passed,
            "request": self.request.to_dict() if self.request else None,
            "response": self.response.to_dict() if self.response else None,
            "assertions": [a.to_dict() for a in self.assertions],
            "extracts": [e.to_dict() for e in self.extracts],
            "duration": self.duration,
            "started_at": _isoformat(self.started_at),
            "finished_at": _isoformat(self.finished_at),
            "error": self.error,
            "error_type": self.error_type,
            "warnings": list(self.warnings),
        }


@dataclass
class CollectionResult:
    """一次 collection 执行的整体结果。"""

    run_id: str  # uuid4
    name: str
    project_id: int
    environment_id: int | None
    started_at: datetime
    finished_at: datetime
    duration: float
    total: int
    passed: int
    failed: int
    error: int
    skipped: int
    fail_strategy: str
    steps: list[StepResult]
    error_message: str | None = None  # 整批级别的异常 traceback

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "name": self.name,
            "project_id": self.project_id,
            "environment_id": self.environment_id,
            "started_at": _isoformat(self.started_at),
            "finished_at": _isoformat(self.finished_at),
            "duration": self.duration,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "error": self.error,
            "skipped": self.skipped,
            "fail_strategy": self.fail_strategy,
            "steps": [s.to_dict() for s in self.steps],
            "error_message": self.error_message,
        }
