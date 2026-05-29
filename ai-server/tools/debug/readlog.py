# -*- coding: UTF-8 -*-
import os
import sys
from loguru import logger

class Log:
    """
    修复后的日志类，解决后台服务化运行时日志不能按日切分的问题
    """
    LOG_FORMAT = (
        "<green>{time:ddd, DD MMM YYYY HH:mm:ss}</green> - "
        "<cyan>{name}</cyan> - "
        "<cyan>{file}</cyan> - "
        "[line:<cyan>{line}</cyan>] - "
        "<level>{level}</level> - [日志信息]: <level>{message}</level>"
    )
    LOG_FILE_SIZE = "500 MB"
    LOG_RETENTION = "30 days"  # 增加保留时间
    # 自动获取项目根目录
    # __file__ = tools/debug/readlog.py
    # dirname(tools/debug/readlog.py) = tools/debug/
    # dirname(tools/debug/) = tools/
    # dirname(tools/) = sevice/ (项目根目录)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    # 然后继续使用 os.path.join 拼接
    report_dir = 'logs'
    log_path = os.path.join(base_dir, report_dir)

    def __init__(self, logname="Root"):
        self._setup_logger(logname)

    def _ensure_log_directory(self):
        """确保日志目录存在"""
        log_dir = os.path.dirname(self.log_path)
        os.makedirs(log_dir, exist_ok=True)

    def _get_log_file_pattern(self, log_type="all"):
        """
        获取日志文件模式，使用loguru的时间模板实现真正的按日切分

        Args:
            log_type (str): 日志类型，"all" 或 "error"

        Returns:
            str: 日志文件路径模式
        """
        self._ensure_log_directory()

        if log_type == "error":
            return f"{self.log_path}/{{time:YYYY-MM-DD}}_error.log"
        else:
            return f"{self.log_path}/{{time:YYYY-MM-DD}}.log"

    def _setup_logger(self, logname):
        """设置日志记录器，修复按日切分问题"""
        # 移除默认处理器
        logger.remove()

        # 添加按日切分的全量日志 - 使用loguru的时间模板
        logger.add(
            self._get_log_file_pattern("all"),
            level="INFO",
            format=self.LOG_FORMAT,
            rotation="00:00",  # 每天午夜切换日志文件
            retention=self.LOG_RETENTION,
            compression="zip",  # 压缩旧日志文件
            enqueue=True,
            encoding="utf-8",
            catch=True  # 捕获异常
        )

        # 添加按日切分的错误日志 - 使用loguru的时间模板
        logger.add(
            self._get_log_file_pattern("error"),
            level="ERROR",
            format=self.LOG_FORMAT,
            rotation="00:00",  # 每天午夜切换日志文件
            retention=self.LOG_RETENTION,
            compression="zip",  # 压缩旧日志文件
            enqueue=True,
            encoding="utf-8",
            catch=True  # 捕获异常
        )

        # 添加控制台处理器
        self._add_console_handler(self.LOG_FORMAT)

        self.logger = logger.bind(name=logname)

    def _add_console_handler(self, format):
        """添加控制台处理器"""
        logger.add(
            sys.stdout,  # 使用 sys.stdout 而不是 sys.__stdout__
            level="INFO",
            format=format,
            enqueue=True,
            catch=True
        )

    def getLog(self):
        """获取日志记录器"""
        return self.logger

logs = Log(logname="MyLogger").getLog()
# 示例用法
if __name__ == "__main__":
    logs.info("This is an info message")
    logs.error("This is an error message")
    logs.debug("This is a debug message")
    logs.warning("This is a warning message")
