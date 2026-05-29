# -*- coding: UTF-8 -*-
"""日志桥接器，适配主项目的日志系统"""
import logging
from app.utils.logger_config import logger as main_logger


class LogBridge:
    """
    桥接主项目的日志系统，保持 ai-server 代码的兼容性
    """

    def _convert_to_main_logger(self):
        """获取主项目的 logger 实例"""
        return main_logger

    def info(self, message, *args, **kwargs):
        self._convert_to_main_logger().info(message, *args, **kwargs)

    def debug(self, message, *args, **kwargs):
        self._convert_to_main_logger().debug(message, *args, **kwargs)

    def warning(self, message, *args, **kwargs):
        self._convert_to_main_logger().warning(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        self._convert_to_main_logger().error(message, *args, **kwargs)

    def critical(self, message, *args, **kwargs):
        self._convert_to_main_logger().critical(message, *args, **kwargs)

    def exception(self, message, *args, **kwargs):
        self._convert_to_main_logger().exception(message, *args, **kwargs)


# 创建全局日志实例
logs = LogBridge()

if __name__ == "__main__":
    logs.info("This is an info message")
    logs.error("This is an error message")
    logs.debug("This is a debug message")
    logs.warning("This is a warning message")
