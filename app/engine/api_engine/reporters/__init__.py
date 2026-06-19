"""报告子包：Reporter Protocol + 各类 reporter 实现。

本期实现 ``ConsoleReporter`` + ``AutomationDbReporter`` + ``TestResultDbReporter``。
明确不做 JSON 文件 reporter。
"""
from app.engine.api_engine.reporters.automation_db_reporter import (  # noqa: F401
    AutomationDbReporter,
)
from app.engine.api_engine.reporters.base import Reporter  # noqa: F401
from app.engine.api_engine.reporters.console_reporter import ConsoleReporter  # noqa: F401
from app.engine.api_engine.reporters.test_result_db_reporter import (  # noqa: F401
    TestResultDbReporter,
)
