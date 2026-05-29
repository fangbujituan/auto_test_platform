"""
引擎包（engine）。

测试执行引擎的总入口，按测试类型划分为多个子引擎：

- api_engine  : 接口自动化引擎（api-engine）
- app_engine  : 移动 App 自动化引擎（app-engine）
- ui_engine   : Web UI 自动化引擎（UI-engine）
- perf_engine : 性能/压测引擎（性能引擎）

根目录下现存的流水线模块（read_case、liu_shui_xian、assertion_handler、
report_generator、test_factory、read_env）为接口测试的早期实现，
后续可逐步归并到 api_engine 子包中。

作者: yandc
"""
