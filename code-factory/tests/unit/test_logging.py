"""Unit tests for the structured logging system.

Tests JSON output format, correlation_id propagation, per-module log levels,
and exception logging with stack trace.
"""

import json
import logging
import sys
from io import StringIO
from unittest.mock import patch

import pytest
import structlog

from src.core.logging import (
    bind_correlation_id,
    clear_correlation_id,
    configure_logging,
    get_correlation_id,
    get_logger,
    install_exception_hook,
    log_unhandled_exception,
)


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging state between tests."""
    # Clear any bound context vars
    clear_correlation_id()
    structlog.contextvars.clear_contextvars()
    # Reset structlog configuration
    structlog.reset_defaults()
    # Clear root logger handlers
    root = logging.getLogger()
    root.handlers.clear()
    yield
    # Cleanup after test
    clear_correlation_id()
    structlog.contextvars.clear_contextvars()
    structlog.reset_defaults()
    root.handlers.clear()


def _capture_log_output(func, *args, **kwargs):
    """Helper to capture log output as a string."""
    stream = StringIO()
    root = logging.getLogger()
    # Remove existing handlers and add our capture handler
    root.handlers.clear()
    handler = logging.StreamHandler(stream)
    # Use the same formatter that configure_logging sets up
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Rename event to message
            lambda _, __, ed: (
                ed.__setitem__("message", ed.pop("event")) or ed
                if "event" in ed
                else ed
            ),
            # Clean internal keys
            lambda _, __, ed: (
                ed.pop("_logger_name", None) or ed
            ),
            structlog.processors.JSONRenderer(),
        ],
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
    func(*args, **kwargs)
    handler.flush()
    return stream.getvalue()


class TestConfigureLogging:
    """Tests for configure_logging function."""

    def test_configure_sets_up_json_handler(self):
        """After configure_logging, root logger should have a handler with JSON formatter."""
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1
        handler = root.handlers[0]
        assert isinstance(handler.formatter, structlog.stdlib.ProcessorFormatter)

    def test_configure_sets_default_level(self):
        """configure_logging should set the root logger to the specified level."""
        configure_logging(default_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_configure_sets_module_levels(self):
        """configure_logging should set per-module log levels."""
        configure_logging(
            default_level="INFO",
            module_levels={"rag.pipeline": "DEBUG", "tools.model_router": "WARNING"},
        )
        assert logging.getLogger("rag.pipeline").level == logging.DEBUG
        assert logging.getLogger("tools.model_router").level == logging.WARNING

    def test_reconfigure_clears_old_handlers(self):
        """Calling configure_logging twice should not duplicate handlers."""
        configure_logging()
        configure_logging()
        root = logging.getLogger()
        assert len(root.handlers) == 1


class TestJSONOutput:
    """Tests for JSON log output format."""

    def test_log_output_is_valid_json(self):
        """Log output should be parseable as JSON."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        logger = get_logger("test_module")
        logger.info("test message")

        output = stream.getvalue().strip()
        # Should be valid JSON
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_log_contains_required_fields(self):
        """Log output should contain timestamp, level, module, message, correlation_id."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        bind_correlation_id("test-cid-123")
        logger = get_logger("test_module")
        logger.info("hello world")

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["level"] == "info"
        assert parsed["module"] == "test_module"
        assert parsed["message"] == "hello world"
        assert parsed["correlation_id"] == "test-cid-123"

    def test_log_without_correlation_id_has_null(self):
        """When no correlation_id is bound, it should be None/null in output."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        logger = get_logger("test_module")
        logger.info("no correlation")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["correlation_id"] is None


class TestCorrelationId:
    """Tests for correlation_id context binding and propagation."""

    def test_bind_and_get_correlation_id(self):
        """bind_correlation_id should set the value retrievable by get_correlation_id."""
        bind_correlation_id("abc-123")
        assert get_correlation_id() == "abc-123"

    def test_clear_correlation_id(self):
        """clear_correlation_id should reset the value to None."""
        bind_correlation_id("abc-123")
        clear_correlation_id()
        assert get_correlation_id() is None

    def test_correlation_id_propagates_across_loggers(self):
        """Once bound, correlation_id should appear in logs from different loggers."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        bind_correlation_id("propagation-test")

        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")

        logger1.info("from module a")
        logger2.info("from module b")

        lines = stream.getvalue().strip().split("\n")
        assert len(lines) == 2

        for line in lines:
            parsed = json.loads(line)
            assert parsed["correlation_id"] == "propagation-test"


class TestPerModuleLogLevels:
    """Tests for configurable log levels per module."""

    def test_module_level_filters_messages(self):
        """A module set to WARNING should not output INFO messages."""
        configure_logging(
            default_level="DEBUG",
            module_levels={"quiet_module": "WARNING"},
        )
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        # Use standard logging to test level filtering
        quiet_logger = logging.getLogger("quiet_module")
        quiet_logger.info("this should be filtered")
        quiet_logger.warning("this should appear")

        output = stream.getvalue().strip()
        lines = [l for l in output.split("\n") if l.strip()]

        # Only the warning should appear
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert "this should appear" in str(parsed)


class TestExceptionLogging:
    """Tests for unhandled exception logging."""

    def test_log_unhandled_exception_includes_stack_trace(self):
        """log_unhandled_exception should include the full stack trace."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        try:
            raise ValueError("test error")
        except ValueError as e:
            log_unhandled_exception(e, correlation_id="exc-cid-456")

        output = stream.getvalue().strip()
        parsed = json.loads(output)

        assert parsed["level"] == "error"
        assert parsed["correlation_id"] == "exc-cid-456"
        assert parsed["exception_type"] == "ValueError"
        assert parsed["exception_message"] == "test error"
        assert "stack_trace" in parsed
        assert "ValueError: test error" in parsed["stack_trace"]
        assert "Traceback" in parsed["stack_trace"]

    def test_log_unhandled_exception_uses_context_correlation_id(self):
        """If no correlation_id is passed, it should use the context value."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        bind_correlation_id("context-cid-789")

        try:
            raise RuntimeError("context test")
        except RuntimeError as e:
            log_unhandled_exception(e)

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["correlation_id"] == "context-cid-789"

    def test_install_exception_hook(self):
        """install_exception_hook should replace sys.excepthook."""
        original = sys.excepthook
        try:
            install_exception_hook()
            assert sys.excepthook is not original
        finally:
            sys.excepthook = original


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_bound_logger(self):
        """get_logger should return a structlog BoundLogger."""
        configure_logging()
        logger = get_logger("my_module")
        # Should be usable as a logger
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")

    def test_get_logger_includes_module_in_output(self):
        """Logger from get_logger should include the module name in output."""
        configure_logging(default_level="DEBUG")
        stream = StringIO()
        root = logging.getLogger()
        root.handlers[0].stream = stream

        logger = get_logger("agents.orchestrator")
        logger.info("orchestrator event")

        output = stream.getvalue().strip()
        parsed = json.loads(output)
        assert parsed["module"] == "agents.orchestrator"
