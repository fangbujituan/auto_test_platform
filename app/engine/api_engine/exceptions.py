"""
api_engine 内部异常体系。

设计要点：
- 所有引擎自有异常都继承 ``ApiEngineError``，便于路由层统一捕获翻译为 HTTP 错误。
- 异常携带的 ``details`` 字段用于附带结构化信息（如 missing 字段列表），
  避免调用方解析消息字符串。

作者: yandc
"""
from __future__ import annotations

from typing import Any


class ApiEngineError(Exception):
    """api_engine 所有自有异常的基类。"""

    def __init__(self, message: str = "", *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


class InvalidRequestSpecError(ApiEngineError):
    """RequestSpec / CollectionSpec 缺少必填字段或字段类型不合法。"""


class AssertionTypeNotFoundError(ApiEngineError):
    """AssertionRule.type 未在 AssertionRegistry 中注册。"""


class ExtractorTypeNotFoundError(ApiEngineError):
    """ExtractRule.type 未在 ExtractorRegistry 中注册。"""


class ExtractFailedError(ApiEngineError):
    """抽取过程异常（表达式无效、响应不匹配且无 default）。"""


class HttpInvocationError(ApiEngineError):
    """HTTP 调用过程异常（超时、连接失败、解析失败等）。"""


class LoaderError(ApiEngineError):
    """Loader 找不到数据库记录或字段不合法。"""
