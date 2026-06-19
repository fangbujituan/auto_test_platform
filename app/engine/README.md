# Engine 架构说明

> `app/engine/` 是测试**执行引擎层**：拿到用例数据后，真正发请求 / 操作浏览器 / 跑压测。

它与 `app/agents/` 的关系：
- **agents** = 大脑（决定"测什么、怎么测"）
- **engine** = 手脚（执行"发请求、点按钮、收集结果"）

Agent 产出的用例最终交给 Engine 执行，Engine 不关心用例怎么来的。

---

## 一、目录结构

```
app/engine/
├── api_engine/             # 接口自动化引擎（统一入口，详见 api_engine/README.md）
│
├── ui_engine/              # Web UI 自动化引擎（Playwright）
│   ├── config.py
│   └── playwright/
│       ├── executor.py
│       ├── report.py
│       ├── script_generator.py
│       ├── script_index.py
│       └── script_manager.py
│
├── app_engine/             # 移动 App 引擎（Appium，规划中）
├── perf_engine/            # 性能/压测引擎（Locust/JMeter，规划中）
│
└── _legacy/                # 已归档：接口测试早期流水线实现
    ├── test_factory.py
    ├── liu_shui_xian.py
    ├── read_env.py
    ├── read_case.py
    ├── assertion_handler.py
    └── report_generator.py
```

---

## 二、接口测试：使用 `api_engine`

接口测试**只有一个入口**：

```python
from app.engine.api_engine import get_api_engine

engine = get_api_engine()
step = engine.run_single_api(api_id=1, project_id=1, environment_id=5)
```

提供的入口：

| 入口                     | 数据源                          | 返回 |
|--------------------------|---------------------------------|-------|
| `run_inline_request`     | 前端 dict（不入库）              | StepResult |
| `run_inline_sequence`    | 前端 dict 列表（不入库）          | CollectionResult |
| `run_single_api`         | `apis` 表 + ApiModelLoader      | StepResult |
| `run_api_sequence`       | `apis` 表 + ApiModelLoader      | CollectionResult |
| `run_test_case`          | `test_cases` 表 + TestCaseLoader | TestResult |
| `run_test_cases`         | `test_cases` 表批量              | list[TestResult] |
| `run_automation_task`    | `automation_tasks` 完整流程      | TaskExecution |

详细设计与扩展指南见 `api_engine/README.md`。

---

## 三、UI 测试：`ui_engine/`

提供 LangChain Tool 给 agent 调用：

```python
from app.engine.ui_engine import get_ui_engine_tools
tools = get_ui_engine_tools()  # 脚本生成 / 保存 / 执行 / 解析
```

| 文件 | 职责 |
|------|------|
| `config.py` | 所有配置从环境变量读取，支持不同部署环境 |
| `playwright/script_generator.py` | 根据用例数据生成 Playwright 测试脚本 |
| `playwright/script_manager.py` | 脚本的保存、读取、删除 |
| `playwright/script_index.py` | 已生成脚本的元数据索引 |
| `playwright/executor.py` | 调用 Playwright CLI 跑脚本 |
| `playwright/report.py` | 解析 Playwright 输出为结构化数据 |

录制能力**不在这里**——录制走 `app/agents/recording_agent`（基于 Playwright MCP 实时录制），这里只负责"执行已有脚本"。

---

## 四、`_legacy/`：已归档代码

`_legacy/` 包含 6 个早期接口测试模块（`liu_shui_xian` / `test_factory` / `read_env` / `read_case` / `assertion_handler` / `report_generator`），已被 `api_engine` 完全取代。

**任何业务路径都不再引用** `_legacy/`。保留只是为了：
1. 历史参考与对照
2. 重构期间快速回滚

新代码**禁止** import `_legacy`，未来版本会移除。

---

## 五、规划

| 引擎 | 用途 | 技术方案 | 状态 |
|------|------|----------|------|
| `api_engine` | 接口自动化 | 自研 | ✅ 已落地 |
| `ui_engine` | Web UI 自动化 | Playwright | ✅ 已落地 |
| `app_engine` | 移动端自动化 | Appium | ⬜ 规划中 |
| `perf_engine` | 性能/压测 | Locust 或 JMeter | ⬜ 规划中 |
