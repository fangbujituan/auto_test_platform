# -*- coding: UTF-8 -*-
"""
``logs`` 兼容入口（保留这个名字仅因为有 16+ 处历史调用方）。

历史包袱
--------
原实现是 ``LogBridge``：把 ``CallerAwareLogger`` 再包一层，每次方法调用
都先 ``_convert_to_main_logger()`` 再转发，纯属冗余。重构后**直接暴露
标准 logger**，对外接口（``logs.info / debug / warning / error / critical
/ exception``）完全不变。

新代码请直接用 ``logging.getLogger(__name__)``；本模块仅为兼容现有
``from app.utils.debug.readlog import logs`` / ``from app.utils.debug
import logs`` 写法保留。

@Author: yandc（重构于 2026-06）
"""
import logging

# 触发一次 setup_logging（导入即生效），确保 root handler 就绪
from app.utils.logger_config import setup_logging  # noqa: F401

# 业务侧统一用 "app" 作为根名称，便于按 logger 名过滤
logs = logging.getLogger("app")


__all__ = ["logs"]


if __name__ == "__main__":
    logs.info("This is an info message")
    logs.error("This is an error message")
    logs.debug("This is a debug message")  # 默认 INFO，看不到
    logs.warning("This is a warning message")
