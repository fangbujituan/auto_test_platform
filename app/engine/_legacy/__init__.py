"""
DEPRECATED：早期接口测试引擎实现，仅作历史参考。

本目录下的 6 个模块（``liu_shui_xian``、``test_factory``、``read_case``、
``read_env``、``assertion_handler``、``report_generator``）都是 ``api_engine``
重构（2026-01）之前的"用例 → 步骤"流水线实现，已被新引擎完全取代。

迁移路径：
    旧                                       新
    ─────────────────────────────────────────────────────────────────────
    LiuShuiXian / SequenceRunner            app.engine.api_engine.SequenceRunner
    TestFactory                              app.engine.api_engine.ApiEngine
    ReadEnv                                  app.engine.api_engine.ExecutionContext
    FormattingData (read_case)               app.engine.api_engine.loaders.*
    AssertionHandler                         app.engine.api_engine.assertions.*
    TestReportGenerator                      app.engine.api_engine.reporters.*

调用方禁止 import 本子包；保留只是为了归档与对照。

作者: yandc（归档时间：2026-01-20）
"""
import warnings

warnings.warn(
    "app.engine._legacy 已废弃，请使用 app.engine.api_engine。"
    "本子包仅作历史参考，未来版本将移除。",
    DeprecationWarning,
    stacklevel=2,
)
