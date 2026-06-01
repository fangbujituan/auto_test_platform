# Engine 架构说明

> 本文档说明 `app/engine/` 的目录结构、设计决策与扩展方式。

---

## 一、整体定位（What）

`app/engine/` 是测试**执行引擎层**，负责"拿到用例数据后，真正发请求 / 操作浏览器 / 跑压测"这件事。

它与 `app/agents/` 的关系：
- **agents** = 大脑（决定"测什么、怎么测"）
- **engine** = 手脚（执行"发请求、点按钮、收集结果"）

Agent 产出的用例最终交给 Engine 执行，Engine 不关心用例怎么来的。

---

## 二、目录结构（What）

```
app/engine/
├── api_engine/             # 接口自动化引擎（规划中，待归并）
├── ui_engine/              # Web UI 自动化引擎（Playwright）
│   ├── config.py           #   配置（浏览器、超时、目录路径）
│   └── playwright/         #   Playwright 具体实现
│       ├── executor.py     #     脚本执行器
│       ├── report.py       #     结果解析器
│       ├── script_generator.py  # 脚本生成器
│       ├── script_index.py #     脚本索引管理
│       └── script_manager.py    # 脚本文件管理
├── app_engine/             # 移动 App 引擎（Appium，规划中）
├── perf_engine/            # 性能/压测引擎（Locust/JMeter，规划中）
│
│  ── 以下为接口测试的早期实现（流水线模式）──
├── test_factory.py         # 控制器：组装各部件、驱动整个执行流程
├── liu_shui_xian.py        # 执行驱动：逐步骤发 HTTP 请求 + 断言
├── read_env.py             # 环境变量：从数据库读取运行时变量
├── read_case.py            # 数据加工：把数据库原始数据格式化为可执行结构
├── assertion_handler.py    # 断言处理：状态码 / JSON / 文本断言
└── report_generator.py     # 报告生成：控制台摘要 + JSON 报告文件
```

---

## 三、各模块职责与设计理由（What + Why）

### 根目录流水线模块（接口测试早期实现）

这是最早落地的执行能力，采用"工厂 + 流水线"模式：

| 文件 | 是什么 | 为什么这么设计 |
|------|--------|---------------|
| `test_factory.py` | 执行入口（控制器） | 把"读环境 → 读用例 → 初始化断言 → 执行 → 生成报告"串起来，一个入口启动全流程 |
| `liu_shui_xian.py` | 执行驱动（流水线） | 逐步骤发 HTTP 请求并执行断言，支持失败终止/继续两种策略 |
| `read_env.py` | 环境变量加载器 | 从数据库按 `env_group_code` 读取变量（base_url、token 等），运行时变量替换 |
| `read_case.py` | 数据格式化 | 数据库原始数据结构不能直接执行，需要标准化为 `{steps: [...]}` 格式 |
| `assertion_handler.py` | 断言引擎 | 支持状态码、JSON 字段、文本包含三种断言；可配置失败时终止或继续 |
| `report_generator.py` | 报告生成器 | 输出控制台摘要 + JSON 文件，便于人工查看和系统集成 |

**设计决策**：
- 各部件独立实例化，通过 `TestFactory` 组装 — 方便单独替换任何一个环节
- `terminate_on_failure` 可配置 — 有些场景需要"跑完所有步骤再看结果"，有些需要"第一个失败就停"
- 环境变量支持 `{variable}` 模板替换 — URL、Header、Body 中都可以引用变量

### `ui_engine/` — Web UI 自动化引擎

| 文件 | 是什么 | 为什么需要 |
|------|--------|-----------|
| `config.py` | `UIAutomationConfig` 配置类 | 所有配置从环境变量读取，支持不同部署环境 |
| `playwright/executor.py` | 脚本执行器 | 调用 Playwright CLI 运行测试脚本 |
| `playwright/report.py` | 结果解析器 | 解析 Playwright 输出为结构化数据 |
| `playwright/script_generator.py` | 脚本生成器 | 根据用例数据生成 Playwright 测试代码 |
| `playwright/script_index.py` | 脚本索引 | 管理已生成脚本的元数据，支持查找和去重 |
| `playwright/script_manager.py` | 脚本文件管理 | 脚本的保存、读取、删除等文件操作 |

**设计决策**：
- 对外暴露 LangChain `Tool` 接口（`get_ui_engine_tools()`）— Agent 可以直接调用
- 配置全部走环境变量 — 容器化部署时只需改 `.env`，不动代码
- 录制能力不在这里 — 录制走 `app/agents/recording_agent`（基于 Playwright MCP 实时录制），这里只负责"执行已有脚本"

### `api_engine/` / `app_engine/` / `perf_engine/`

目前为占位目录，规划中：

| 引擎 | 规划用途 | 技术方案 |
|------|----------|----------|
| `api_engine` | 接口自动化（归并根目录流水线模块） | 复用现有 `liu_shui_xian` + `assertion_handler` |
| `app_engine` | 移动端自动化 | Appium |
| `perf_engine` | 性能/压测 | Locust 或 JMeter |

---

## 四、执行流程（How it works）

### 接口测试执行流程

```
TestFactory.run_automation(ids)
  │
  ├─ 1. ReadEnv.read_env(env_group_code)     ← 从数据库加载环境变量
  │
  ├─ 2. ApiService.get_api_list_service()    ← 从数据库获取用例原始数据
  │
  ├─ 3. FormattingData.get_case_data()       ← 格式化为可执行结构
  │
  ├─ 4. AssertionHandler(terminate_on_failure) ← 初始化断言策略
  │
  ├─ 5. LiuShuiXian(env, assertion_handler)  ← 初始化执行驱动
  │
  ├─ 6. 遍历用例 → execute_test_case()
  │     │
  │     └─ 遍历步骤 → execute_test_step()
  │           ├─ 变量替换（URL / Header / Body）
  │           ├─ 发送 HTTP 请求
  │           ├─ 执行断言（状态码 / JSON / 文本）
  │           └─ 返回 TestCaseStepResult
  │
  └─ 7. TestReportGenerator
        ├─ generate_console_summary()        ← 控制台输出
        └─ generate_json_report()            ← JSON 文件
```

### UI 测试执行流程

```
Agent 调用 get_ui_engine_tools() 获取工具
  │
  ├─ create_script_generator_tool()  → 生成 Playwright 脚本
  ├─ create_script_save_tool()       → 保存到文件系统
  ├─ create_playwright_executor_tool() → 执行脚本
  └─ create_result_parser_tool()     → 解析执行结果
```

---

## 五、编码约定（How）

### 5.1 命名风格

- 文件名用下划线分隔，表达"做什么"：`assertion_handler`、`report_generator`
- 类名用中文隐喻命名也可以（如 `LiuShuiXian` 流水线），但需在 docstring 中说明含义

### 5.2 断言扩展

在 `AssertionHandler` 中新增方法即可，遵循统一签名：

```python
def assert_xxx(self, actual, expected) -> AssertionResult:
    passed = (actual == expected)
    message = f"断言描述：期望 {expected}, 实际 {actual}"
    if not passed and self.terminate_on_failure:
        raise AssertionError(message)
    return AssertionResult(passed, message, details={...})
```

### 5.3 环境变量替换

所有字符串值支持 `{variable_name}` 格式，运行时从 `ReadEnv.env_variables` 字典中替换。

### 5.4 与 Agent 层的集成

Engine 对外暴露两种接入方式：
1. **直接调用**：`TestFactory(terminate_on_failure=True).run_automation(ids)` — 路由层直接用
2. **Tool 接口**：`get_ui_engine_tools()` 返回 LangChain Tool 列表 — Agent 通过 tool calling 调用

---

## 六、扩展指南（Then）

| 想做什么 | 怎么做 |
|----------|--------|
| 新增断言类型 | 在 `assertion_handler.py` 的 `AssertionHandler` 类中新增方法 |
| 支持新的 HTTP 方法 | 在 `liu_shui_xian.py` 的 `_send_http_request` 中新增分支 |
| 归并流水线到 api_engine | 把根目录的 6 个文件移入 `api_engine/`，更新 import 路径 |
| 实现 App 引擎 | 在 `app_engine/` 中参照 `ui_engine/` 的结构实现 Appium 集成 |
| 实现性能引擎 | 在 `perf_engine/` 中集成 Locust，暴露 LangChain Tool 接口 |
| 新增报告格式 | 在 `report_generator.py` 中新增 `generate_html_report()` 等方法 |
| 修改执行策略 | 调整 `TestFactory` 的构造参数或新增策略类 |
