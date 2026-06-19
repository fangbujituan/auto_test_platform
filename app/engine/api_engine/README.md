# api_engine — 接口测试统一执行引擎

> 位置：`app/engine/api_engine/`
> 关联 spec：`.kiro/specs/api-engine/`
> 老参考代码：`app/engine/liu_shui_xian.py`、`app/engine/test_factory.py`（**仅作历史参考，不被本包引用**）

---

## 一、定位

接口测试的**唯一执行引擎**。把"读用例 → 渲染变量 → 发请求 → 抽取字段 → 断言 → 出报告"这条管道，从原本散落在 `services/executor.py` / `services/automation_executor.py` / 老 `engine/liu_shui_xian.py` 三处的实现里收敛到同一抽象。

参考 Postman / Apifox 的核心概念：

```
Postman 概念       本项目映射
─────────────────────────────────────────
Request           RequestSpec          单条 HTTP 请求 DTO
Collection        CollectionSpec       一组请求的编排 DTO
Environment       Environment 表        通过 ExecutionContext 加载
Globals           GlobalVariable 表     同上
Pre-request       —                     不上 JS 沙箱，用声明式抽取替代
Tests/Assertions  AssertionRule         status_code / json_path 等
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
│   └── builtin.py             # 5 个内置：status_code / json_path / text_contains
│                              #         / response_time / header
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
├── loaders/                   # 数据适配层（Phase 2/3/4 逐步加入）
│   ├── inline_request_loader.py   # Phase 2：dict → RequestSpec
│   ├── api_model_loader.py        # Phase 2：apis 表 → RequestSpec
│   ├── test_case_loader.py        # Phase 4：test_cases 表 → RequestSpec
│   └── automation_task_loader.py  # Phase 3：automation_tasks → CollectionSpec
│
└── reporters/
    ├── base.py                    # Reporter Protocol + NoopReporter
    ├── console_reporter.py        # 控制台日志摘要
    ├── automation_db_reporter.py  # Phase 3：写 task_executions / task_execution_details
    └── test_result_db_reporter.py # Phase 4：写 test_results
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

完整入口表（按落地阶段）：

| 入口 | 阶段 | 说明 |
|------|------|------|
| `run_inline_request(payload, project_id, ...)` | Phase 1 ✓ | 单条 dict → `StepResult` |
| `run_inline_sequence(payloads, project_id, ...)` | Phase 1 ✓ | 多条 dict 顺序执行 → `CollectionResult` |
| `run_single_api(api_id, project_id, ...)` | Phase 2 | `apis` 表 → 单接口执行 |
| `run_api_sequence(api_ids, project_id, ...)` | Phase 2 | `apis` 表 → 多接口顺序执行（链式抽取） |
| `run_test_case(case_id)` | Phase 4 | `test_cases` 表 → 自动转 status/json 断言 |
| `run_automation_task(task_id, ...)` | Phase 3 | `automation_tasks` → 写库 |

未实现入口会抛 `NotImplementedError`，并在消息中标注对应任务编号。

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

---

## 五、扩展指南

### 5.1 新增断言

只需在 `assertions/builtin.py`（或新建文件）追加一个类：

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

或单次执行时通过 `extra_reporters` 临时挂载（如调度器要落库）。

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

1. **单/多接口共用一条管道**：`run_inline_request` 等单步入口内部都走 `SequenceRunner` 跑长度为 1 的 collection，再 unwrap 第一条 step。避免维护两套实现漂移。
2. **DTO 与 ORM 解耦**：引擎核心**不**直接 import `Api` / `TestCase` 等模型；DB 接入收敛在 `loaders/` 子包。这让引擎核心可以脱离 Flask app context 单测。
3. **永不外抛**：StepExecutor / SequenceRunner 顶层都做 try/except 兜底；HTTP / 抽取 / 断言 / reporter 异常均自吞 + 转 result 字段，路由层不需要担心未捕获异常炸掉请求。
4. **变量域隔离**：`ExecutionContext` 按 `run_id` 隔离，**绝不**读写全局可变状态。变量优先级：`extracted > initial > environment > global`。
5. **未命中变量不报错**：`{{xxx}}` 找不到时原样保留并写 `warnings`；强校验等所有迁移完成后再开关。
6. **不生成 JSON 文件报告**：本期只支持控制台 + 数据库两条报告路径（spec 明确决议）。

---

## 七、与老引擎代码的关系

`app/engine/liu_shui_xian.py` 与 `app/engine/test_factory.py` 是早期的"用例 → 步骤"流水线实现：

- 它们**不被本包任何代码引用**；
- 仅作历史参考保留在原位；
- Phase 5 任务 26 会把它们与 `read_env.py` / `read_case.py` / `assertion_handler.py` / `report_generator.py` 一起迁入 `app/engine/_legacy/` 子目录，并加 DEPRECATED 注释。

如果你看到 `from app.engine.liu_shui_xian import ...` 出现在新代码里，那是 bug，请改用 api_engine。

---

## 八、迁移路径（spec tasks 摘要）

| Phase | 范围 | 状态 |
|-------|------|------|
| 1 | 引擎骨架 + Reporter + 控制台 + 临时 dict 入口 | ✅ 完成 |
| 2 | `apis` 表加字段 + Loader + 单接口路由切流 + 多接口路由 | 待开始 |
| 3 | AutomationTaskLoader + AutomationDbReporter + AutomationExecutor 委托 | 待开始 |
| 4 | TestCaseLoader + TestResultDbReporter + TestExecutor 委托 | 待开始 |
| 5 | 老 engine 代码归档 + 全量回归 | 待开始 |

每个 Phase 完成后都是可独立合并的稳定状态。详见 `.kiro/specs/api-engine/tasks.md`。
