"""失败策略子包：FailureStrategy + 内置策略。"""
from app.engine.api_engine.strategies.failure_strategy import (  # noqa: F401
    ContinueOnError,
    FailFast,
    FailureStrategy,
    make_strategy,
)
