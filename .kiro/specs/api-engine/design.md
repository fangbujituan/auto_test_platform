# API 执行引擎（api_engine）设计文档

> 关联文档：`requirements.md`
> 实现位置：`app/engine/api_engine/`

---

## 1. 设计原则

1. **单/多接口共用一条核心管道**：单接口 = 长度为 1 的 collection。`Runner` 内部循环 `StepExecutor`，避免两套实现漂移。
2. **数据契约（DTO）与数据库模型解耦**：引擎只认 `RequestSpec` / `CollectionSpec` 这种 dataclass。DB 表通过 loader 转换进来。引擎核心可以**不依赖 Flask app context** 进行单元测试。
3. **失败策略可插拔**：`FailFast` / `ContinueOnError` / `Retry` 当成策略对象传入，不是散落的 if-else。
4. **变量域清晰隔离**：`ExecutionContext` 按 `run_id` 隔离；变量优先级 = 抽取 > 环境 > 全局；不读不写任何全局可变状态。
5. **复用现有件**：`RequestFactory`、`variable_replacer.resolve_prefix_url`、`variable_replacer.merge_global_params` 不重写，包装进引擎层。
6. **命名严格见名知意**：禁止 `liu_shui_xian` 这类隐喻。引擎组件命名按"做什么"而不是"是什么"。

---

## 2. 顶层架构

```
                       ┌────────────────────────────┐
                       │     Routes / Services       │  调用方（路由、自动化、调度）
                       └──────────────┬──────────────┘
                                      │  ApiEngine 门面
                       ┌──────────────▼──────────────┐
                       │         ApiEngine            │  engine.py
                       │  run_single_api()            │
                       │  run_api_sequence()          │
                       │  run_inline_request()        │
                       │  run_test_case()             │
                       │  run_automation_task()       │
                       └──────────────┬──────────────┘
                                      │ 组装 Spec + Context
                       ┌──────────────▼──────────────┐
                       │   Loader 数据适配层          │  loaders/
                       │   ApiModelLoader             │
                       │   TestCaseLoader             │
                       │   InlineRequestLoader        │
                       │   AutomationTaskLoader       │
                       └──────────────┬──────────────┘
                                      │ RequestSpec / CollectionSpec
                       ┌──────────────▼──────────────┐
                       │       SequenceRunner        │  runner/sequence_runner.py
                       │   按顺序调用 StepExecutor    │
                       │   接 FailureStrategy        │
                       └──────────────┬──────────────┘
                                      │ 单步
                       ┌──────────────▼──────────────┐
                       │       StepExecutor          │  runner/step_executor.py
                       │  render → send → extract     │
                       │       → assert → result      │
                       └──────────────┬──────────────┘
                                      │
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
   ┌───────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
   │  HttpClient       │  │  AssertionRegistry   │  │  ExtractorRegistry   │
   │  http/client.py   │  │  assertions/*.py      │  │  extractors/*.py     │
   └───────────────────┘  └──────────────────────┘  └──────────────────────┘

                                      │
                       ┌──────────────▼──────────────┐
                       │    Reporter（多挂载）         │  reporters/
                       │  ConsoleReporter             │
                       │  AutomationDbReporter        │
                       │  TestResultDbReporter        │
                       └──────────────────────────────┘
```

---

## 3. 目录结构

```
app/engine/api_engine/
├── __init__.py                         # 公开 ApiEngine 一个入口
├── README.md                           # 设计/扩展指南
│
├── specs.py                            # 运行时 DTO（替代笼统的 models.py，更见名知意）
├── results.py                          # 执行结果 DTO
├── exceptions.py                       # 引擎自有异常
├── context.py                          # ExecutionContext
│
├── http/
│   ├── __init__.py
│   └── client.py                       # HttpClient（薄封装 RequestFactory）
│
├── variables/
│   ├── __init__.py
│   ├── resolver.py                     # VariableResolver：渲染 {{var}} + 整合环境/全局/抽取
│   └── prefix_url.py                   # 适配 variable_replacer.resolve_prefix_url
│
├── assertions/
│   ├── __init__.py                     # AssertionRegistry
│   ├── base.py                         # BaseAssertion ABC
│   └── builtin.py                      # status_code / json_path / contains / response_time / header
│
├── extractors/
│   ├── __init__.py                     # ExtractorRegistry
│   ├── base.py                         # BaseExtractor ABC
│   └── builtin.py                      # json_path / regex / header
│
├── strategies/
│   ├── __init__.py
│   └── failure_strategy.py             # FailureStrategy ABC + FailFast / ContinueOnError
│
├── runner/
│   ├── __init__.py
│   ├── step_executor.py                # 单步执行：渲染→请求→抽取→断言
│   └── sequence_runner.py              # 顺序执行多步
│
├── loaders/
│   ├── __init__.py
│   ├── base.py                         # SpecLoader Protocol
│   ├── api_model_loader.py             # apis 表 → RequestSpec
│   ├── test_case_loader.py             # test_cases 表 → RequestSpec
│   ├── inline_request_loader.py        # 前端临时 JSON → RequestSpec
│   └── automation_task_loader.py       # automation_tasks → CollectionSpec
│
├── reporters/
│   ├── __init__.py
│   ├── base.py                         # Reporter Protocol
│   ├── console_reporter.py             # 终端摘要
│   ├── automation_db_reporter.py       # 写 task_executions / task_execution_details
│   └── test_result_db_reporter.py      # 写 test_results
│
└── engine.py                           # ApiEngine 门面
```

> **命名说明**：
> - 文件名后缀 `_executor` / `_runner` / `_resolver` / `_loader` / `_reporter` 直接表达职责。
> - 老 `liu_shui_xian` 不出现在新代码任何位置。

---

## 4. 核心 DTO 设计

### 4.1 `specs.py` —— 输入契约

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class AssertionRule:
    """单条断言规则。type 决定走哪个 Assertion 实现。"""
    type: str                       # status_code | json_path | text_contains | response_time | header
    config: dict                    # 断言所需配置，例：{"path": "$.data.id", "op": "exists"}
    name: str = ""                  # 可选展示名

@dataclass(frozen=True)
class ExtractRule:
    """从响应中抽字段写入上下文。"""
    name: str                       # 写入 ctx.variables 的 key
    type: str                       # json_path | regex | header
    expression: str                 # $.data.token / Authorization / pattern
    default: Any = None             # 抽取失败时的回退值（None 表示报错）

@dataclass
class RequestSpec:
    """单个接口的执行规格。"""
    name: str
    method: str
    url: str                        # 可含 {{var}}，可以是完整 URL 或仅 path
    headers: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    body: Any = None
    body_type: str = "json"         # json | form | raw | multipart

    timeout: int = 30
    delay_ms: int = 0               # 执行后等待
    on_failure: str = "inherit"     # stop | continue | inherit

    extracts: list[ExtractRule] = field(default_factory=list)
    assertions: list[AssertionRule] = field(default_factory=list)

    # 路由匹配辅助（来自 apis 表，引擎不解析；交给 prefix_url resolver）
    api_id: int | None = None
    module: str | None = None
    service: str | None = None
    prefix_url_id: int | None = None
    base_url: str | None = None     # 接口自带域名（优先级最高）

@dataclass
class CollectionSpec:
    """一组接口的编排执行规格。"""
    name: str
    project_id: int
    environment_id: int | None
    requests: list[RequestSpec]
    fail_strategy: str = "continue" # fail_fast | continue
    iterations: int = 1             # 数据驱动留口子，本期固定 1
    initial_variables: dict = field(default_factory=dict)
```

### 4.2 `results.py` —— 输出契约

```python
@dataclass
class AssertionOutcome:
    type: str
    name: str
    passed: bool
    message: str
    expected: Any = None
    actual: Any = None

@dataclass
class ExtractOutcome:
    name: str
    type: str
    value: Any
    succeeded: bool
    message: str = ""

@dataclass
class RequestRecord:
    """实际发出的请求快照（变量已渲染）。"""
    method: str
    url: str
    headers: dict
    params: dict
    body: Any
    body_type: str

@dataclass
class ResponseRecord:
    """响应快照。"""
    status_code: int
    status_text: str
    headers: dict
    body: Any
    body_raw: str | None
    size: int
    encoding: str | None

@dataclass
class StepResult:
    """单接口执行结果（替代 RequestResult，更突出"步骤"语义）。"""
    name: str
    api_id: int | None
    step_index: int
    passed: bool
    request: RequestRecord | None
    response: ResponseRecord | None
    assertions: list[AssertionOutcome]
    extracts: list[ExtractOutcome]
    duration: float                 # 秒
    started_at: datetime
    finished_at: datetime
    error: str | None = None
    error_type: str | None = None
    warnings: list[str] = field(default_factory=list)

@dataclass
class CollectionResult:
    run_id: str                     # uuid4
    name: str
    project_id: int
    environment_id: int | None
    started_at: datetime
    finished_at: datetime
    duration: float
    total: int
    passed: int
    failed: int
    error: int
    skipped: int
    fail_strategy: str
    steps: list[StepResult]
    error_message: str | None = None
```

### 4.3 `exceptions.py`

```python
class ApiEngineError(Exception): ...
class InvalidRequestSpecError(ApiEngineError): ...
class AssertionTypeNotFoundError(ApiEngineError): ...
class ExtractorTypeNotFoundError(ApiEngineError): ...
class ExtractFailedError(ApiEngineError): ...
class HttpInvocationError(ApiEngineError): ...
class LoaderError(ApiEngineError): ...
```

---

## 5. ExecutionContext 详细设计

```python
class ExecutionContext:
    """
    执行上下文。每次 run() 创建一个，按 run_id 隔离，绝不共享。

    变量优先级（高 → 低）：
      step_extracted > initial_variables > environment_variables > global_variables
    """

    def __init__(self, *, project_id: int, environment_id: int | None,
                 initial_variables: dict | None = None):
        self.run_id: str = str(uuid4())
        self.project_id = project_id
        self.environment_id = environment_id
        self._global: dict = self._load_global_variables(project_id)
        self._env: dict = self._load_environment_variables(project_id, environment_id)
        self._initial: dict = dict(initial_variables or {})
        self._extracted: dict = {}

    # 公开属性（合并视图，只读）
    @property
    def variables(self) -> dict:
        merged = {}
        merged.update(self._global)
        merged.update(self._env)
        merged.update(self._initial)
        merged.update(self._extracted)
        return merged

    def update_extracted(self, kv: dict) -> None: ...

    def render_string(self, text: str) -> str: ...
    def render_value(self, value: Any) -> Any: ...
    def render_request(self, spec: RequestSpec) -> RequestSpec: ...

    def resolve_full_url(self, base_url: str, path: str,
                         module: str | None, service: str | None,
                         prefix_url_id: int | None) -> str: ...

    def merge_global_params_into_headers(self, headers: dict) -> dict: ...
```

> 实现要点：
> - `_load_global_variables` / `_load_environment_variables` 内部直接走 `GlobalVariable` / `EnvironmentVariable` 模型查询；这是引擎层**唯一**的数据库依赖（loader 之外）。如果未来要做无 DB 的纯 spec 执行，传 `initial_variables` 即可。
> - `render_request` 返回**新的** `RequestSpec`（替换 dataclass.replace），不修改入参。
> - 未解析的 `{{var}}` 不抛错，原样保留并写 `warnings`，由 `StepResult.warnings` 上报。

---

## 6. HttpClient 设计

```python
class HttpClient:
    """
    HTTP 调用客户端。薄封装 services.request_factory.RequestFactory。
    引擎层不直接 import requests，所有 HTTP IO 收敛在这里，便于将来替换或加 Mock。
    """

    def __init__(self, factory: RequestFactory | None = None, default_timeout: int = 30):
        self._factory = factory or get_request_factory()
        self._default_timeout = default_timeout

    def send(self, rendered: RequestSpec) -> tuple[RequestRecord, ResponseRecord | None, str | None]:
        """
        发送请求并返回三元组：(请求快照, 响应快照, 错误消息)。
        send 内部捕获 RequestFactory 的异常并转换为引擎语义。
        """
```

---

## 7. Assertion 与 Extractor 注册中心

### 7.1 `assertions/base.py`

```python
class BaseAssertion(ABC):
    type_name: ClassVar[str]

    @abstractmethod
    def check(self, response: ResponseRecord, config: dict,
              ctx: ExecutionContext) -> AssertionOutcome: ...

class AssertionRegistry:
    _registry: dict[str, BaseAssertion] = {}

    @classmethod
    def register(cls, assertion: BaseAssertion) -> None: ...

    @classmethod
    def get(cls, type_name: str) -> BaseAssertion: ...

def register_assertion(cls):
    AssertionRegistry.register(cls())
    return cls
```

### 7.2 `assertions/builtin.py`

```python
@register_assertion
class StatusCodeAssertion(BaseAssertion):
    type_name = "status_code"
    def check(self, response, config, ctx):
        expected = int(config["expected"])
        actual = response.status_code
        passed = (actual == expected)
        return AssertionOutcome(
            type=self.type_name, name=config.get("name", ""),
            passed=passed, expected=expected, actual=actual,
            message=f"期望状态码 {expected}, 实际 {actual}"
        )

@register_assertion
class JsonPathAssertion(BaseAssertion):
    type_name = "json_path"
    # config: {"path": "$.data.id", "op": "exists" | "equals" | "in" | "regex", "value": ...}

@register_assertion
class TextContainsAssertion(BaseAssertion):
    type_name = "text_contains"
    # config: {"value": "ok", "negate": false}

@register_assertion
class ResponseTimeAssertion(BaseAssertion):
    type_name = "response_time"
    # config: {"max_ms": 1000}

@register_assertion
class HeaderAssertion(BaseAssertion):
    type_name = "header"
    # config: {"name": "Content-Type", "value": "application/json", "op": "equals"}
```

### 7.3 Extractor 同构

```python
class BaseExtractor(ABC):
    type_name: ClassVar[str]

    @abstractmethod
    def extract(self, response: ResponseRecord, expression: str,
                default: Any) -> ExtractOutcome: ...

# JsonPathExtractor / RegexExtractor / HeaderExtractor 内置三件套
```

---

## 8. StepExecutor 详细流程

```python
class StepExecutor:
    def __init__(self, http: HttpClient): ...

    def execute(self, spec: RequestSpec, ctx: ExecutionContext,
                step_index: int) -> StepResult:
        started_at = datetime.now()

        # 1. 渲染（spec → rendered_spec）
        rendered = ctx.render_request(spec)

        # 2. 解析最终 URL（base_url + prefix_url）
        full_url = ctx.resolve_full_url(
            base_url=rendered.base_url or "",
            path=rendered.url,
            module=rendered.module, service=rendered.service,
            prefix_url_id=rendered.prefix_url_id,
        )
        rendered = replace(rendered, url=full_url)

        # 3. 合并全局 Header
        rendered = replace(rendered,
                           headers=ctx.merge_global_params_into_headers(rendered.headers))

        # 4. 发送请求
        request_record, response_record, error = self._http.send(rendered)

        # 5. 抽取（即使断言失败也跑，方便排查）
        extract_outcomes = []
        if response_record is not None:
            for rule in spec.extracts:
                outcome = self._run_extractor(rule, response_record)
                extract_outcomes.append(outcome)
                if outcome.succeeded:
                    ctx.update_extracted({rule.name: outcome.value})

        # 6. 断言
        assertion_outcomes = []
        if response_record is not None:
            for rule in spec.assertions:
                outcome = self._run_assertion(rule, response_record, ctx)
                assertion_outcomes.append(outcome)

        # 7. 判定 step 通过 = 无 error 且所有断言通过
        passed = error is None and all(a.passed for a in assertion_outcomes)

        finished_at = datetime.now()
        return StepResult(...)
```

---

## 9. SequenceRunner

```python
class SequenceRunner:
    def __init__(self, http: HttpClient, strategy: FailureStrategy,
                 reporters: list[Reporter]):
        self._step_executor = StepExecutor(http)
        self._strategy = strategy
        self._reporters = reporters

    def run(self, spec: CollectionSpec, ctx: ExecutionContext) -> CollectionResult:
        run_started = datetime.now()
        for r in self._reporters:
            r.on_collection_started(spec, ctx)

        steps: list[StepResult] = []
        for idx, req_spec in enumerate(spec.requests):
            step_result = self._step_executor.execute(req_spec, ctx, step_index=idx)
            steps.append(step_result)

            for r in self._reporters:
                r.on_step_completed(step_result, ctx)

            if not step_result.passed and self._strategy.should_stop(step_result, req_spec):
                break

            if req_spec.delay_ms:
                time.sleep(req_spec.delay_ms / 1000)

        result = self._summarize(spec, ctx, steps, run_started)
        for r in self._reporters:
            r.on_collection_finished(result, ctx)
        return result
```

### 9.1 FailureStrategy

```python
class FailureStrategy(ABC):
    @abstractmethod
    def should_stop(self, step: StepResult, spec: RequestSpec) -> bool: ...

class ContinueOnError(FailureStrategy):
    def should_stop(self, step, spec):
        return spec.on_failure == "stop"

class FailFast(FailureStrategy):
    def should_stop(self, step, spec):
        return spec.on_failure != "continue"
```

---

## 10. Loader 设计

每个 Loader 实现 `SpecLoader` Protocol：

```python
class SpecLoader(Protocol):
    def load_request(self, *args, **kwargs) -> RequestSpec: ...
    def load_collection(self, *args, **kwargs) -> CollectionSpec: ...
```

具体实现：

| Loader | 输入 | 产出 |
|--------|------|------|
| `ApiModelLoader` | `api_id` 或 `Api` 实例 + 可选 `overrides` | `RequestSpec` |
| `TestCaseLoader` | `case_id` 或 `TestCase` 实例 | `RequestSpec`（自动把 `expected_status` / `expected_response` 转 AssertionRule） |
| `InlineRequestLoader` | dict | `RequestSpec`（校验必填字段，否则 `InvalidRequestSpecError`） |
| `AutomationTaskLoader` | `task_id` | `CollectionSpec`（按 `automation_task_cases.sort_order` 拉用例） |

`ApiModelLoader.load_collection(api_ids)` 直接组多个 `RequestSpec` 成 `CollectionSpec`，供 Story 2 用。

---

## 11. Reporter 设计

```python
class Reporter(Protocol):
    def on_collection_started(self, spec: CollectionSpec, ctx: ExecutionContext): ...
    def on_step_completed(self, step: StepResult, ctx: ExecutionContext): ...
    def on_collection_finished(self, result: CollectionResult, ctx: ExecutionContext): ...
```

| Reporter | 输出 | 用途 |
|----------|------|------|
| `ConsoleReporter` | logger.info | 调试 / 命令行 |
| `AutomationDbReporter` | `task_executions` + `task_execution_details` | 替代现 AutomationExecutor 内部写库逻辑 |
| `TestResultDbReporter` | `test_results` | 替代现 TestExecutor 内部写库逻辑 |

**默认挂载策略**：
- `run_single_api` / `run_inline_request` / `run_api_sequence` → `ConsoleReporter`（仅日志，不落库，也不生成 JSON 文件）
- `run_test_case` → `ConsoleReporter` + `TestResultDbReporter`
- `run_automation_task` → `ConsoleReporter` + `AutomationDbReporter`

---

## 12. ApiEngine 门面

```python
class ApiEngine:
    def __init__(self, *, http: HttpClient | None = None,
                 default_strategy: FailureStrategy | None = None,
                 default_reporters: list[Reporter] | None = None):
        self._http = http or HttpClient()
        self._default_strategy = default_strategy or ContinueOnError()
        self._default_reporters = default_reporters or [ConsoleReporter()]

    # 单接口（路由 /apis/{id}/test）
    def run_single_api(self, *, api_id: int, project_id: int,
                       environment_id: int | None = None,
                       overrides: dict | None = None) -> StepResult: ...

    # 多接口顺序执行
    def run_api_sequence(self, *, api_ids: list[int], project_id: int,
                         environment_id: int | None = None,
                         fail_strategy: str = "continue",
                         name: str = "ad-hoc-sequence") -> CollectionResult: ...

    # 临时 JSON
    def run_inline_request(self, *, payload: dict, project_id: int,
                           environment_id: int | None = None) -> StepResult: ...

    # 单条 test_case
    def run_test_case(self, *, case_id: int) -> StepResult: ...

    # 自动化任务（替换 AutomationExecutor 内部逻辑）
    def run_automation_task(self, *, task_id: int,
                            environment_id: int | None = None,
                            trigger_source: str = "manual") -> CollectionResult: ...
```

> 单接口入口仍返回 `StepResult` 而不是只长度 1 的 `CollectionResult`，保持调用方使用直觉。但**内部实现**统一走 `SequenceRunner` 跑长度为 1 的 collection，再 unwrap 第一条 step。

---

## 13. 数据模型增强

### 13.1 `apis` 表新增字段

```python
class Api(BaseModel):
    # ...existing fields...
    assertions = db.Column(db.JSON, comment="断言规则数组：[{type,config,name?}]")
    extracts   = db.Column(db.JSON, comment="抽取规则数组：[{name,type,expression,default?}]")
    timeout    = db.Column(db.Integer, nullable=True, comment="单接口超时秒数，覆盖默认 30")
```

`to_dict()` 同步加这三个字段。所有字段允许 NULL，旧数据读取视为 `[]` / 默认值。

### 13.2 迁移脚本

```
migrations/versions/xxxx_add_api_engine_fields.py
  - upgrade: ALTER TABLE apis ADD COLUMN assertions JSON, extracts JSON, timeout INT
  - downgrade: ALTER TABLE apis DROP COLUMN assertions, extracts, timeout
```

### 13.3 不在本期范围（仅记录）

- `api_collections` / `api_collection_items` —— 待前端集合管理需求确认后再加
- `engine_executions` / `engine_execution_steps` —— 现有 `task_executions` 体系可继续兼容，引入需要数据迁移成本

---

## 14. 路由层迁移方案

### 14.1 阶段 1：引擎骨架（零侵入）

新增包，不改任何现有路由 / service。

### 14.2 阶段 2：单接口路由切流

`POST /api/projects/{project_id}/apis/{api_id}/test`：

**Before**:
```python
factory = get_request_factory()
# ...一堆 base_url/path/headers 手工拼接...
result = factory.execute(...)
return jsonify({"code": 0, "data": result})
```

**After**:
```python
engine = get_api_engine()
step_result = engine.run_single_api(
    api_id=api_id, project_id=project_id,
    environment_id=data.get("environment_id"),
    overrides={
        "method": data.get("method"),
        "base_url": data.get("base_url"),
        "path": data.get("path"),
        "headers": data.get("headers"),
        "params": data.get("params"),
        "body": data.get("body"),
        "body_type": data.get("body_type"),
    },
)
return jsonify({"code": 0, "data": _to_legacy_response(step_result)})
```

`_to_legacy_response` 将 `StepResult` 转成现路由返回的 JSON 结构（`{success, request, response, error, duration, timestamp}`），保证前端无感。

### 14.3 阶段 3：新增多接口路由（增量）

```
POST /api/projects/{project_id}/apis/run-sequence
body: {"api_ids": [1,2,3], "environment_id": 5, "fail_strategy": "continue"}
→ 返回 CollectionResult.to_dict()
```

### 14.4 阶段 4：AutomationExecutor 委托

`AutomationExecutor.execute_task` 改为：
```python
def execute_task(self, task_id, environment_id=None, trigger_source="manual"):
    if self._check_running(task_id):
        raise DuplicateExecutionError(...)
    engine = get_api_engine()
    collection_result = engine.run_automation_task(
        task_id=task_id, environment_id=environment_id, trigger_source=trigger_source,
    )
    # 取出对应 TaskExecution 行（由 AutomationDbReporter 写入）
    return TaskExecution.query.filter_by(...).order_by(...).first()
```

`AutomationDbReporter` 替代当前 `_execute_cases` / `_summarize` 中的 `db.session.add` 逻辑。

### 14.5 阶段 5：TestExecutor 委托

`TestExecutor.run_case` 改为：
```python
def run_case(self, case):
    engine = get_api_engine()
    step_result = engine.run_test_case(case_id=case.id)
    # `TestResultDbReporter` 已在内部写入 test_results
    return TestResult.query.filter_by(case_id=case.id).order_by(TestResult.id.desc()).first()
```

### 14.6 阶段 6：归档老代码

将 `engine/liu_shui_xian.py`、`engine/test_factory.py`、`engine/read_env.py`、`engine/read_case.py`、`engine/assertion_handler.py`、`engine/report_generator.py` 移入 `engine/_legacy/` 子目录并加 `# DEPRECATED` 注释。**不直接删除，留作历史参考**，符合需求 7.3。

---

## 15. 错误处理策略

| 场景 | 行为 |
|------|------|
| 渲染时找不到变量 | 原样保留 `{{var}}`，加 warning |
| HTTP 请求超时 / 连接错 | StepResult.passed=false, error_type="HttpError" |
| 抽取失败且 default 为 None | StepResult.warnings 加一条；不阻断 step 通过/失败的判定（除非该变量被后续 step 使用并断言） |
| 抽取失败且配置了 default | 使用 default，标记 outcome.succeeded=false 但 ctx.update |
| 断言类型未注册 | 整个 step 标 error，error_type="AssertionTypeNotFound" |
| Loader 找不到记录 | `LoaderError`，路由层翻译为 404 |
| 引擎内部未捕获异常 | `SequenceRunner` 顶层 try/except，CollectionResult.error_message 落 traceback，状态置 error |

---

## 16. 日志策略

每条日志附带 `run_id`、`step_index`、`api_id`，便于全链路追溯：

```
[api_engine] run_id=ab12 step=0 api_id=15 阶段=render 渲染完成
[api_engine] run_id=ab12 step=0 api_id=15 阶段=send 发送 GET https://api/test (耗时 312ms)
[api_engine] run_id=ab12 step=0 api_id=15 阶段=extract token <- $.data.token = "ey..."
[api_engine] run_id=ab12 step=0 api_id=15 阶段=assert 通过 3 条 / 失败 0 条
```

---

## 17. 测试策略

| 层级 | 工具 | 关注点 |
|------|------|--------|
| 单元测试 | pytest，无 Flask | DTO 序列化、Resolver 渲染、AssertionRegistry、ExtractorRegistry、StepExecutor（mock HttpClient）、FailureStrategy |
| 集成测试 | pytest + 测试 DB | Loader、Reporter（写库）、ApiEngine 门面 |
| 端到端 | requests 打本地 Flask | 路由 `/apis/{id}/test`、`/apis/run-sequence` |

**最低标线**：StepExecutor 与 Resolver 的单测覆盖率不低于 85%。

> 按规则不主动加测试。本节仅记录后续若用户提出测试需求时的执行依据。

---

## 18. 验证 / 回归方案

每完成一个迁移阶段，**录制一组对比用例**：
1. 切换前调用旧路径，记录 JSON 响应作为 baseline
2. 切换后调用新路径，diff JSON 字段（关键字段必须 byte-equal，时间戳类字段允许差异）

任何字段层 diff 都必须有解释（"这个字段我们故意改了"或"这是 bug 修复"）。

---

## 19. 设计取舍备忘

| 取舍 | 选择 | 理由 |
|------|------|------|
| 单接口入口返回 `StepResult` 还是 `CollectionResult` | `StepResult` | 调用方语义清晰，外部不需要 `result.steps[0]` |
| 是否引入新的统一执行表 `engine_executions` | 暂不 | 风险大，老表能继续承载；列入演进规划 |
| Pre-request 是否上 JS 沙箱 | 不上 | 99% 场景声明式抽取够用；剩余场景不值得引入 V8 |
| 渲染未解析变量是否报错 | 不报错只 warning | 兼容历史用例；强校验等所有数据迁移完毕再开关 |
| Reporter 写库事务边界 | 每次回调独立事务 | 一条失败不影响整批；与现 AutomationExecutor 行为一致 |
