"""
统一日志配置（项目唯一的日志入口）。

设计要点
--------
- 仅在 **进程启动时** 调用一次 :func:`setup_logging`，配置 root logger
  的控制台 + 按天文件双 handler。
- 业务代码统一通过标准方式取 logger：``logging.getLogger(__name__)``。
- 模块级常量 ``logger`` 仅为兼容历史用法保留（多处旧代码 ``from
  app.utils.logger_config import logger``）；新代码请直接用
  ``logging.getLogger(__name__)`` 以便日志归属信息更清晰。

历史包袱已清理
--------------
- 删除 ``CallerAwareLogger``：旧实现每次 ``info()`` 调用都用
  ``inspect.stack()`` 反推调用者模块名，性能差；标准 logging 已能通过
  ``getLogger(__name__)`` 在每个模块拿到同样信息。
- 删除并发时改写 ``self._logger.name`` 的危险写法。

@Author: yandc（重构于 2026-06）
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

# -----------------------------------------------------------------------------
# 路径与文件名
# -----------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# 按天分文件，例：info-2026-06-01.log
LOG_FILE_NAME = datetime.now().strftime("info-%Y-%m-%d.log")
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

# 防止重复初始化
_logging_configured = False


def setup_logging() -> None:
    """配置 root logger（控制台 + 当日文件）。

    幂等：多次调用只会初始化一次。
    """
    global _logging_configured
    if _logging_configured:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除已有 handler，避免重载场景下重复输出
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        if isinstance(handler, logging.FileHandler):
            handler.close()

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8", mode="a")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    _logging_configured = True


# 模块加载时自动配置（保持原有行为）
setup_logging()


# -----------------------------------------------------------------------------
# 兼容别名（旧代码：from app.utils.logger_config import logger）
# -----------------------------------------------------------------------------
# 直接用标准 logger，name="automation_engine" 兼容历史日志归属
logger = logging.getLogger("automation_engine")


__all__ = ["setup_logging", "logger", "LOG_DIR", "LOG_FILE_PATH"]


if __name__ == "__main__":
    logger.info("日志系统初始化成功")
    logger.warning("WARN 测试")
    logger.error("ERROR 测试")
    print(f"日志文件位置: {LOG_FILE_PATH}")
