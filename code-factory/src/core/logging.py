"""Code Factory 的结构化日志系统。

使用 structlog 和 JSON 输出，支持 correlation_id 上下文传播、
每模块日志级别配置和未处理异常日志记录。

Requirements: 10.1, 10.2, 10.3, 10.4, 10.5
"""

import logging
import sys
import traceback
from contextvars import ContextVar
from typing import Any

import structlog

# Context variable for correlation_id propagation (thread-safe)
_correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "correlation_id", default=None
)


def bind_correlation_id(correlation_id: str) -> None:
    """将 correlation_id 绑定到当前上下文。

    correlation_id 将在同一个请求上下文内的所有日志条目中传播
    （使用 contextvars 实现线程安全）。

    Args:
        correlation_id: 当前请求的唯一标识符。
    """
    _correlation_id_ctx.set(correlation_id)
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)


def get_correlation_id() -> str | None:
    """从上下文获取当前的 correlation_id。

    Returns:
        当前的 correlation_id，如果未设置则返回 None。
    """
    return _correlation_id_ctx.get()


def clear_correlation_id() -> None:
    """清除当前上下文中的 correlation_id。"""
    _correlation_id_ctx.set(None)
    structlog.contextvars.unbind_contextvars("correlation_id")


def _add_correlation_id(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """处理器：如果 event_dict 中不存在 correlation_id，则从上下文添加。"""
    if "correlation_id" not in event_dict:
        cid = _correlation_id_ctx.get()
        event_dict["correlation_id"] = cid
    return event_dict


def _add_module_field(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """处理器：确保 'module' 字段存在。"""
    if "module" not in event_dict:
        # Use the logger name as the module if not explicitly set
        event_dict["module"] = event_dict.get("_logger_name", "root")
    return event_dict


def _rename_event_to_message(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """处理器：将 'event' 重命名为 'message' 用于 JSON 输出。"""
    if "event" in event_dict:
        event_dict["message"] = event_dict.pop("event")
    return event_dict


def _rename_level_field(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """处理器：确保 'level' 字段存在。"""
    if "level" not in event_dict:
        event_dict["level"] = method_name.upper()
    return event_dict


def _clean_internal_keys(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """移除不应出现在输出中的内部 structlog 键。"""
    event_dict.pop("_logger_name", None)
    event_dict.pop("_record", None)
    return event_dict


def configure_logging(
    default_level: str = "INFO",
    module_levels: dict[str, str] | None = None,
) -> None:
    """配置结构化日志系统。

    设置 structlog 以 JSON 输出包含必需字段：
    timestamp, level, module, message, correlation_id。

    Args:
        default_level: 所有模块的默认日志级别（例如 "INFO", "DEBUG"）。
        module_levels: 可选的字典，将模块名称映射到其日志级别。
                       示例：{"rag.pipeline": "DEBUG", "tools.model_router": "WARNING"}
    """
    module_levels = module_levels or {}

    # Configure standard logging for integration with structlog
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, default_level.upper(), logging.INFO))

    # Apply per-module log levels
    for module_name, level in module_levels.items():
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers to avoid duplicates on reconfiguration
    root_logger.handlers.clear()

    # Structlog processor chain
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _add_correlation_id,
        _add_module_field,
        _rename_level_field,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set up a StreamHandler with structlog's ProcessorFormatter for JSON output
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _rename_event_to_message,
            _clean_internal_keys,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(module_name: str) -> structlog.stdlib.BoundLogger:
    """为特定模块获取结构化日志器。

    日志器会自动在所有日志条目中包含模块名称，
    并从当前上下文继承 correlation_id。

    Args:
        module_name: 模块名称（例如 "rag.pipeline", "agents.orchestrator"）。

    Returns:
        一个绑定的 structlog 日志器实例。
    """
    return structlog.get_logger(module_name, module=module_name)


def log_unhandled_exception(
    exc: BaseException,
    correlation_id: str | None = None,
) -> None:
    """以 ERROR 级别记录未处理的异常，并包含完整的堆栈跟踪。

    包含 correlation_id 用于可追溯性。如果未提供 correlation_id，
    尝试从当前上下文获取。

    Args:
        exc: 要记录的未处理异常。
        correlation_id: 可选的 correlation_id。如果为 None，使用上下文值。
    """
    cid = correlation_id or get_correlation_id()
    logger = get_logger("exception_handler")

    # Format the full stack trace
    tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
    full_traceback = "".join(tb_lines)

    logger.error(
        "Unhandled exception occurred",
        correlation_id=cid,
        exception_type=type(exc).__name__,
        exception_message=str(exc),
        stack_trace=full_traceback,
        exc_info=False,  # We include our own formatted traceback
    )


def install_exception_hook() -> None:
    """安装全局异常钩子，记录未处理的异常。

    这会替换 sys.excepthook，确保所有未处理的异常在进程继续
    （或在非异步上下文中终止）之前都使用 correlation_id 和完整堆栈跟踪进行记录。
    """
    original_hook = sys.excepthook

    def _exception_hook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        # Log the exception with our structured logger
        log_unhandled_exception(exc_value)
        # Call the original hook (prints to stderr by default)
        original_hook(exc_type, exc_value, exc_tb)

    sys.excepthook = _exception_hook
