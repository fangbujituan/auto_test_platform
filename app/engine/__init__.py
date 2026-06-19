"""
引擎包（engine）。

测试执行引擎的总入口，按测试类型划分为多个子引擎：

- ``api_engine``  接口自动化引擎（**唯一**生效的接口测试入口）
- ``app_engine``  移动 App 自动化引擎（规划中）
- ``ui_engine``   Web UI 自动化引擎
- ``perf_engine`` 性能/压测引擎（规划中）

子目录 ``_legacy/`` 为接口测试的早期实现（``liu_shui_xian`` / ``test_factory``
等 6 个模块），已被 ``api_engine`` 完全替代，仅作历史归档；任何业务路径都不再引用。

接口测试调用方一律使用：

    from app.engine.api_engine import ApiEngine, get_api_engine

作者: yandc
"""
