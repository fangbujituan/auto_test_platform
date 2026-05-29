"""
统一日志工厂。

提供全项目统一的日志配置，支持控制台 + 文件双输出，按天轮转。

使用方式：
    from app.utils.logger_factory import get_logger
    logger = get_logger(__name__)
    logger.info("消息")

作者: yandc
创建时间: 2026-05
"""
import os
import logging
from logging.handlers import TimedRotatingFileHandler

# 日志目录：项目根目录/logs/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

# 日志级别：从环境变量读取，默认 INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 确保日志目录存在
os.makedirs(LOG_DIR, exist_ok=True)

# 全局标志，避免重复配置
_initialized_loggers = set()


def get_logger(name: str) -> logging.Logger:
    """
    获取指定模块的 logger 实例。

    Args:
        name: 日志名称，建议使用 __name__ 或自定义名称如 "api.access"

    Returns:
        配置好的 Logger 实例
    """
    logger = logging.getLogger(name)

    if name in _initialized_loggers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（按天生成独立文件）
    log_file = os.path.join(LOG_DIR, "info.log")
    file_handler = TimedRotatingFileHandler(
        filename=log_file,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.namer = lambda name: name.replace("info.log.", "info-") + ".log"
    file_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _initialized_loggers.add(name)
    return logger
