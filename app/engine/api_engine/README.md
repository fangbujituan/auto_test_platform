# api_engine — 接口测试统一执行引擎

> 位置：`app/engine/api_engine/`
> 关联 spec：`.kiro/specs/api-engine/`（requirements / design / tasks 三件套）
> 状态：✅ 已落地，5 个 Phase 27 个任务全部完成

---

## 一、定位

接口测试的**唯一执行引擎**。把"读用例 → 渲染变量 → 发请求 → 抽取字段 → 断言 → 出报告"这条管道收敛到同一抽象。

历史上"接口执行"散落在 3 处独立实现：

```
services/executor.py        ── 单条 test_case 执行 (TestExecutor)
services/automation_executor.py ── 自动化任务调度执行 (AutomationExecutor)
engine/liu_shui_xian.py + test_factory.py ── 早期独立流水线
```

现在三者**都委托给 `api_engine`**，`engine/_legacy/` 仅作历史归档。

参考 Postman / Apifox 的核心概念：

```
Postman 概念       本项目映射
─────────────────────────────────────────
Request           RequestSpec          单条 HTTP 请求 DTO
Collection        CollectionSpec       一组请求的编排 DTO
Environment       Environment 表        通过 ExecutionContext 加载
Globals           GlobalVariable 表     同上
Pre-request       —                     不上 JS 沙箱，用声明式抽取替代
Tests/Assertions  AssertionRule         status_code / json_path / json_subset 等
Variable extract  ExtractRule           json_path / regex / header
Runner            SequenceRunner        顺序执行 + 失败策略
Reporter          Reporter Protocol     控制台 / 数据库（不出 JSON 文件）
```

---

## 二、目录结构

```
api_engine/
├── __init__.py                # 顶层公开 ApiEngine / get_api_engine / 全部 DTO
├── README.md                  # 本文档
│
├── specs.py                   # 输入 DTO：RequestSpec / CollectionSpec / AssertionRule / ExtractRule
├── results.py                 # 输出 DTO：StepResult / CollectionResult / 各类 Outcome
├── exceptions.py              # ApiEngineError 基类 + 6 个细分异常
├── context.py                 # ExecutionContext（变量 + run_id 隔离）
├── engine.py                  # ApiEngine 门面 + get_api_engine 单例
├── _utils.py                  # 内部共享工具（json path 导航器）
│
├── http/
│   └── client.py              # HttpClient（薄封装 RequestFactory，唯一 HTTP IO 出口）
│
├── variables/
│   ├── resolver.py            # {{var}} 渲染器（无副作用）
│   └── prefix_url.py          # 复用 services.variable_replacer：prefix_url + global_params
│
├── assertions/
│   ├── base.py                # BaseAssertion ABC + AssertionRegistry + register_assertion
│   └── builtin.py             # 6 个内置：status_code / json_path / json_subset
│                              #         / text_contains / response_time / header
├── extractors/
│   ├── base.py                # BaseExtractor ABC + ExtractorRegistry + register_extractor
│   └── builtin.py             # 3 个内置：json_path / regex / header
│
├── strategies/
│   └── failure_strategy.py    # FailureStrategy + ContinueOnError + FailFast + make_strategy
│
├── runner/
│   ├── step_executor.py       # 单步执行：render → send → extract → assert → result
│   └── sequence_runner.py     # 顺序执行 + 失败策略 + reporter 钩子
│
├── loaders/                   # 数据适配层
│   ├── base.py                    # BaseLoader 抽象
│   ├── inline_request_loader.py   # dict → RequestSpec
│   ├── api_model_loader.py        # apis 表 → RequestSpec
│   ├── test_case_loader.py        # test_cases 表 → RequestSpec
│   └── automation_task_loader.py  # automation_tasks → CollectionSpec
│
└── reporters/
    ├── base.py                    # Reporter Protocol + NoopReporter
    ├── _step_mapping.py           # StepResult → DB 行 字段映射（reporter 共享）
    ├── console_reporter.py        # 控制台日志摘要
    ├── automation_db_reporter.py  # 写 task_executions / task_execution_details
    └── test_result_db_reporter.py # 写 test_results
```

> 命名约定：所有目录、文件、类、方法见名知意。`_executor` / `_runner` / `_resolver` / `_loader` / `_reporter` 后缀直接表达职责。**禁止**使用 `liu_shui_xian` 这类隐喻命名。

---

## 三、对外 API（门面）

调用方只需要：

```python
from app.engine.api_engine import get_api_engine

engine = get_api_engine()          # 进程级单例
result = engine.run_inline_request(
    payload={
        "method": "GET",
        "url": "https://httpbin.org/get",
        "assertions": [{"type": "status_code", "config": {"expected": 200}}],
    },
    project_id=1,
)
print(result.passed, result.duration)
```

完整入口表：

| 入口 | 数据源 | 返回类型 | 用途 |
|------|--------|---------|------|
| `run_inline_request(payload, project_id, ...)` | 前端 dict（不入库） | `StepResult` | 临时调试单接口 |
| `run_inline_sequence(payloads, project_id, ...)` | 前端 dict 列表 | `CollectionResult` | 临时调试多接口 |
| `run_single_api(api_id, project_id, ...)` | `apis` 表 | `StepResult` | 前端"点发送"，已切流到 `routes/api.py /test` |
| `run_api_sequence(api_ids, project_id, ...)` | `apis` 表 | `CollectionResult` | 多接口编排（链式抽取），路由 `/apis/run-sequence` |
| `run_test_case(case=...)` 或 `(case_id=...)` | `test_cases` 表 | `TestResult` (ORM) | `TestExecutor.run_case` 内部委托 |
| `run_test_cases(cases=...)` | `test_cases` 表批量 | `list[TestResult]` | `TestExecutor.run_cases` 内部委托 |
| `run_automation_task(task_id, ...)` | `automation_tasks` | `TaskExecution` (ORM) | `AutomationExecutor.execute_task` 内部委托 |

---

## 四、典型场景示例

### 4.1 单接口调试（前端"点发送"）

```python
result = engine.run_inline_request(
    payload={
        "method": "POST",
        "url": "https://api.example.com/login",
        "headers": {"Content-Type": "application/json"},
        "body": {"username": "admin", "password": "{{password}}"},
        "assertions": [
            {"type": "status_code", "config": {"expected": 200}},
            {"type": "json_path",   "config": {"path": "$.code", "op": "equals", "value": 0}},
            {"type": "response_time", "config": {"max_ms": 1000}},
        ],
    },
    project_id=1,
    environment_id=5,
)
```

### 4.2 多接口编排（登录 → 拿 token → 调业务接口）

```python
result = engine.run_inline_sequence(
    payloads=[
        {
            "name": "登录",
            "method": "POST",
            "url": "https://api.example.com/login",
            "body": {"username": "admin", "password": "123"},
            "extracts": [
                {"name": "token", "type": "json_path", "expression": "$.data.token"},
            ],
        },
        {
            "name": "查询订单",
            "method": "GET",
            "url": "https://api.example.com/orders",
            "headers": {"Authorization": "Bearer {{token}}"},
            "assertions": [
                {"type": "status_code", "config": {"expected": 200}},
            ],
        },
    ],
    project_id=1,
    fail_strategy="fail_fast",   # 登录失败就不跑业务接口
)
```

### 4.3 数据库 apis 表执行（前端发送按钮）

`apis` 表新增了 `assertions / extracts / timeout` 三列后，前端可以保存断言/抽取规则，点击发送时引擎会读出来跑：

```python
# 这正是 routes/api.py /test 端点内部做的事
step = engine.run_single_api(
    api_id=42,
    project_id=1,
    environment_id=5,
    overrides={"headers": {"X-Debug": "1"}},  # 调试态字段覆盖
)
# step.assertions 包含每条断言的通过情况；step.extracts 包含抽取结果
```

### 4.4 自动化任务（替代旧 AutomationExecutor 内部逻辑）

```python
# AutomationExecutor.execute_task 内部就是这两行
engine = get_api_engine()
execution = engine.run_automation_task(
    task_id=task_id,
    environment_id=environment_id,
    trigger_source="manual",  # / "cron" / "webhook"
)
# 返回 TaskExecution ORM 实体，task_executions / task_execution_details 已写库
```

---

## 五、扩展指南

### 5.1 新增断言

在 `assertions/builtin.py`（或新建文件）追加一个类即可：

```python
from app.engine.api_engine.assertions.base import BaseAssertion, register_assertion
from app.engine.api_engine.results import AssertionOutcome

@register_assertion
class JsonSchemaAssertion(BaseAssertion):
    type_name = "json_schema"

    def check(self, response, config, ctx):
        # ... 校验 response.body 是否符合 config['schema']
        return AssertionOutcome(
            type=self.type_name,
            name=config.get("name", "JSON Schema 校验"),
            passed=True,
            message="...",
        )
```

只要类被 import 一次（建议在 `assertions/__init__.py` 中追加 `from . import json_schema`），就会自动注册到 `AssertionRegistry`。

### 5.2 新增抽取器

`extractors/builtin.py` 同样套路：

```python
@register_extractor
class XPathExtractor(BaseExtractor):
    type_name = "xpath"

    def extract(self, response, name, expression, default):
        # ... 用 lxml 取值
        return ExtractOutcome(...)
```

### 5.3 新增报告器

实现 `Reporter` Protocol（duck typing，不需要继承）：

```python
class HtmlReporter:
    def on_collection_started(self, spec, ctx): ...
    def on_step_completed(self, step, ctx): ...
    def on_collection_finished(self, result, ctx): ...
```

构造引擎时注入：

```python
engine = ApiEngine(default_reporters=[ConsoleReporter(), HtmlReporter()])
```

或单次执行时通过 `extra_reporters` 临时挂载。

### 5.4 新增失败策略

```python
class RetryStrategy(FailureStrategy):
    name = "retry"

    def __init__(self, max_retries=3): ...

    def should_stop(self, step, spec):
        # 自定义逻辑
        ...
```

并在 `make_strategy` 中加分支或直接传策略对象给 `ApiEngine`。

---

## 六、设计原则备忘

1. **单/多接口共用一条管道**：`run_inline_request` / `run_single_api` / `run_test_case` 等单步入口内部都走 `SequenceRunner` 跑长度为 1 的 collection，再 unwrap 第一条 step。避免维护两套实现漂移。
2. **DTO 与 ORM 解耦**：引擎核心**不**直接 import `Api` / `TestCase` 等模型；DB 接入收敛在 `loaders/` 子包。这让引擎核心可以脱离 Flask app context 单测。
3. **永不外抛**：StepExecutor / SequenceRunner 顶层都做 try/except 兜底；HTTP / 抽取 / 断言 / reporter 异常均自吞 + 转 result 字段，路由层不需要担心未捕获异常炸掉请求。
4. **变量域隔离**：`ExecutionContext` 按 `run_id` 隔离，**绝不**读写全局可变状态。变量优先级：`extracted > initial > environment > global`。
5. **未命中变量不报错**：`{{xxx}}` 找不到时原样保留并写 `warnings`；强校验等所有迁移完成后再开关。
6. **不生成 JSON 文件报告**：本期只支持控制台 + 数据库两条报告路径。
7. **HTTP 不走系统代理**：`HttpClient` 内部把 `Session.trust_env=False`，避免被 macOS / 系统级代理拦截造成 502。

---

## 七、与老引擎代码的关系

`app/engine/_legacy/` 已归档以下 6 个早期接口测试模块：

```
liu_shui_xian.py       早期"用例 → 步骤"流水线
test_factory.py        旧执行入口
read_env.py            旧环境变量加载
read_case.py           旧用例数据格式化
assertion_handler.py   旧断言体系
report_generator.py    旧报告生成
```

它们：
- **不被任何业务路径引用**（routes / agents / services 全清扫过）
- 文件顶部都加了 `# DEPRECATED` 注释
- import `app.engine._legacy` 会触发 `DeprecationWarning`
- 保留只是为了历史参考与回滚兜底，未来版本会移除

**新代码禁止 import `_legacy`，请使用 `api_engine`**。

---

## 八、迁移路径（完成情况）

| Phase | 范围 | 状态 |
|-------|------|------|
| 1 | 引擎骨架 + Reporter + 控制台 + 临时 dict 入口 | ✅ 完成 |
| 2 | `apis` 表加字段 + Loader + 单接口路由切流 + 多接口路由 | ✅ 完成 |
| 3 | AutomationTaskLoader + AutomationDbReporter + AutomationExecutor 委托 | ✅ 完成 |
| 4 | TestCaseLoader + TestResultDbReporter + TestExecutor 委托 | ✅ 完成 |
| 5 | 老 engine 代码归档 + 全量回归 | ✅ 完成 |

每个 Phase 完成都是可独立合并的稳定状态。详见 `.kiro/specs/api-engine/tasks.md`。

---

## 九、`apis` 表 Phase 2 新增字段

为了承载断言/抽取/超时配置，`apis` 表加了 3 个字段（均可空，向后兼容）：

| 列 | 类型 | 用途 | 示例 |
|----|------|------|------|
| `assertions` | `JSON NULL` | 断言规则数组 | `[{"type":"status_code","config":{"expected":200}}]` |
| `extracts` | `JSON NULL` | 抽取规则数组 | `[{"name":"token","type":"json_path","expression":"$.data.token"}]` |
| `timeout` | `INT NULL` | 单接口超时秒数 | `60`（NULL 表示用引擎默认 30s） |

迁移由 `app/init_all.py:auto_migrate()` 处理，幂等，已在生产数据库执行。

---

## 十、内置断言与抽取器

### 6 种内置断言（`AssertionRegistry.known_types()`）

| type | 配置 | 说明 |
|------|------|------|
| `status_code` | `{expected: 200}` | HTTP 状态码精确匹配 |
| `json_path` | `{path, op, value}` | JSON 路径取值后比较（exists / equals / not_equals / contains / in / regex / gt/gte/lt/lte）|
| `json_subset` | `{expected: {...}}` | 响应包含期望子结构（递归部分匹配，对应老 `expected_response` 语义）|
| `text_contains` | `{value, negate?, case_sensitive?}` | 响应文本包含/不包含子串 |
| `response_time` | `{max_ms: 1000}` | 响应耗时上限 |
| `header` | `{name, op, value}` | 响应头比较（exists / equals / contains / regex）|

### 3 种内置抽取器（`ExtractorRegistry.known_types()`）

| type | expression | 说明 |
|------|------------|------|
| `json_path` | `$.data.token` | JSON 路径取值（支持 `items.0.id` 索引语法）|
| `regex` | `trace_id=(\\w+)` | 正则提取，默认取第 1 个分组 |
| `header` | `X-Trace-Id` | 响应头取值（大小写不敏感）|

抽取失败处理：
- 配了 `default` → 回退到 default 值，`succeeded=False`，仍写入 ctx
- 没配 `default` → 不写入 ctx，加 warning
- 失败本身**不**导致 step 失败，只有断言才决定通过/失败
