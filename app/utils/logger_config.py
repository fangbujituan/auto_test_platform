"""
@Author: <yandc>
@Time: 2025/05/29
日志工具
"""
import logging
import os
import sys
import inspect
from datetime import datetime

# 定义日志文件路径
# LOG_DIR 设置为 auto-flask 根目录下的 logs 文件夹
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../logs')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 根据当前日期生成日志文件名
LOG_FILE_NAME = datetime.now().strftime("info-%Y-%m-%d.log")
LOG_FILE_PATH = os.path.join(LOG_DIR, LOG_FILE_NAME)

# 全局标志，确保日志配置只初始化一次
_logging_configured = False


def setup_logging():
    """
    配置自动化平台的日志系统。
    日志将同时输出到控制台和文件中，文件日志按天生成，并在当天文件中追加。
    此函数只需在应用启动时调用一次。
    """
    global _logging_configured
    if _logging_configured:
        return

    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 清除所有现有的处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        if isinstance(handler, logging.FileHandler):
            handler.close()

    # 创建文件处理器
    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding='utf-8', mode='a')
    file_handler.setLevel(logging.INFO)

    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # 定义日志格式
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 添加处理器到根日志记录器
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    _logging_configured = True


# 在应用启动时调用一次配置
setup_logging()


# 创建一个自定义的 Logger 类，自动获取调用者模块名
class CallerAwareLogger:
    def __init__(self):
        self._logger = logging.getLogger('automation_engine')

    @staticmethod
    def _get_caller_name():
        # 获取调用者的模块名
        stack = inspect.stack()
        # 跳过当前类和日志模块的调用帧
        for frame in stack[2:]:
            module = inspect.getmodule(frame[0])
            if module and module.__name__ != __name__:
                return module.__name__
        return 'unknown'

    def info(self, msg, *args, **kwargs):
        caller_name = self._get_caller_name()
        # 临时修改日志记录器的名称
        original_name = self._logger.name
        self._logger.name = caller_name
        self._logger.info(msg, *args, **kwargs)
        # 恢复原始名称
        self._logger.name = original_name

    def debug(self, msg, *args, **kwargs):
        caller_name = self._get_caller_name()
        original_name = self._logger.name
        self._logger.name = caller_name
        self._logger.debug(msg, *args, **kwargs)
        self._logger.name = original_name

    def warning(self, msg, *args, **kwargs):
        caller_name = self._get_caller_name()
        original_name = self._logger.name
        self._logger.name = caller_name
        self._logger.warning(msg, *args, **kwargs)
        self._logger.name = original_name

    def error(self, msg, *args, **kwargs):
        caller_name = self._get_caller_name()
        original_name = self._logger.name
        self._logger.name = caller_name
        self._logger.error(msg, *args, **kwargs)
        self._logger.name = original_name

    def critical(self, msg, *args, **kwargs):
        caller_name = self._get_caller_name()
        original_name = self._logger.name
        self._logger.name = caller_name
        self._logger.critical(msg, *args, **kwargs)
        self._logger.name = original_name

    def exception(self, msg, *args, **kwargs):
        caller_name = self._get_caller_name()
        original_name = self._logger.name
        self._logger.name = caller_name
        self._logger.exception(msg, *args, **kwargs)
        self._logger.name = original_name


# 创建全局 logger 实例
logger = CallerAwareLogger()
if __name__ == '__main__':
    # 示例用法
    logger.info("日志系统初始化成功！")
    logger.debug("这是一个调试信息。")  # 调试信息不会被记录，因为级别是INFO
    logger.warning("这是一个警告信息。")
    # try:
    #     1 / 0
    # except ZeroDivisionError:
    #     logger.error("发生了一个错误：除零错误。", exc_info=True)

    # 验证日志文件生成
    current_log_file = datetime.now().strftime("info-%Y%m%d.log")
    print(f"日志文件将生成到: {os.path.join(LOG_DIR, current_log_file)}")
    print(f"请检查 '{LOG_DIR}' 目录来查看日志文件。")

    # 模拟在同一天多次运行，日志应该追加
    logger.info("这是第一次运行脚本时记录的日志。")
