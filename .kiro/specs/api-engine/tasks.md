# API 执行引擎（api_engine）实施任务

> 关联：`requirements.md`、`design.md`
> 实施顺序严格按编号；每个 Phase 结束都应是**可独立合并的稳定状态**。

---

## Phase 1：引擎骨架（零侵入新增）

- [ ] 1. 准备目录与公共契约
  - 创建 `app/engine/api_engine/` 子目录骨架（`http/`、`variables/`、`assertions/`、`extractors/`、`strategies/`、`runner/`、`loaders/`、`reporters/`），每个目录建 `__init__.py`
  - 编写 `api_engine/specs.py`：`AssertionRule`、`ExtractRule`、`RequestSpec`、`CollectionSpec`
  - 编写 `api_engine/results.py`：`AssertionOutcome`、`ExtractOutcome`、`RequestRecord`、`ResponseRecord`、`StepResult`、`CollectionResult` 与各自 `to_dict()`
  - 编写 `api_engine/exceptions.py`：本 spec §4.3 列出的所有异常
  - _Requirements: 2.1, Story 6, 设计 §3 §4_

- [ ] 2. 实现 ExecutionContext 与变量解析
  - 编写 `api_engine/variables/resolver.py`：`{{var}}` 字符串与嵌套结构（dict/list/JSON body）的渲染
  - 编写 `api_engine/variables/prefix_url.py`：包装 `services.variable_replacer.resolve_prefix_url` + `merge_global_params`
  - 编写 `api_engine/context.py`：`ExecutionContext`（变量优先级 = 抽取 > initial > env > global），`render_request`、`resolve_full_url`、`merge_global_params_into_headers`、`update_extracted`
  - 未解析变量原样保留并写 `warnings`（不抛异常）
  - _Requirements: Story 1.2, Story 1.3, Story 1.4, Story 2.2, 设计 §5_

- [ ] 3. 实现 HttpClient
  - 编写 `api_engine/http/client.py`：`HttpClient.send(rendered_spec) -> (RequestRecord, ResponseRecord | None, error)`
  - 内部委托 `services.request_factory.RequestFactory`，捕获其异常并转换为 `HttpInvocationError` 语义
  - 引擎层禁止其他模块直接 `import requests`
  - _Requirements: 设计 §2 §6_

- [ ] 4. 实现 Assertion 框架
  - 编写 `api_engine/assertions/base.py`：`BaseAssertion` ABC + `AssertionRegistry` + `register_assertion` 装饰器
  - 编写 `api_engine/assertions/builtin.py`：`StatusCodeAssertion`、`JsonPathAssertion`（支持 `op` = exists/equals/in/regex）、`TextContainsAssertion`、`ResponseTimeAssertion`、`HeaderAssertion`
  - 在 `api_engine/__init__.py` 中触发 builtin 注册（`from .assertions import builtin`）
  - 未注册的 `type` 抛 `AssertionTypeNotFoundError`，被 StepExecutor 翻译成 step 错
  - _Requirements: Story 1, Story 6.1, 设计 §7_

- [ ] 5. 实现 Extractor 框架
  - 编写 `api_engine/extractors/base.py`：`BaseExtractor` ABC + `ExtractorRegistry`
  - 编写 `api_engine/extractors/builtin.py`：`JsonPathExtractor`、`RegexExtractor`、`HeaderExtractor`
  - 抽取失败：有 default → 用 default 且 outcome.succeeded=false；无 default → outcome.succeeded=false 加 warning，不写 ctx
  - _Requirements: Story 2.2, Story 6.2, 设计 §7_

- [ ] 6. 实现 FailureStrategy
  - 编写 `api_engine/strategies/failure_strategy.py`：`FailureStrategy` ABC、`ContinueOnError`、`FailFast`
  - 提供 `make_strategy(name: str)` 工厂方法，从字符串构造（`"fail_fast"` / `"continue"`）
  - _Requirements: Story 2.3, Story 2.4, 设计 §9.1_

- [ ] 7. 实现 StepExecutor
  - 编写 `api_engine/runner/step_executor.py`：单步执行流（render → resolve_url → merge_headers → send → extract → assert）
  - 处理超时、连接错、解析错；任何异常不外抛，写入 StepResult.error
  - 即使 send 失败，也产出 `StepResult`（带 error_type）
  - 日志按设计 §16 格式输出
  - _Requirements: Story 1.1, Story 1.5, Story 1.6, Story 7.2, 设计 §8 §15 §16_

- [ ] 8. 实现 SequenceRunner
  - 编写 `api_engine/runner/sequence_runner.py`：循环 step、应用 FailureStrategy、调用 reporter 钩子、汇总 CollectionResult
  - 顶层 try/except 兜住所有异常，落 `error_message`
  - 处理 `delay_ms` 与 `iterations`（本期 iterations 固定 1，不循环）
  - _Requirements: Story 2.1, Story 2.3-2.6, 设计 §9_

- [ ] 9. 实现 Reporter 框架与 ConsoleReporter
  - 编写 `api_engine/reporters/base.py`：`Reporter` Protocol（三个钩子）
  - 编写 `api_engine/reporters/console_reporter.py`：按 step / 按 collection 输出 logger 摘要
  - 不实现 JSON 文件 reporter（明确不在本期范围）
  - _Requirements: Story 6.3, 设计 §11_

- [ ] 10. 实现 ApiEngine 门面
  - 编写 `api_engine/engine.py`：`ApiEngine` 类 + `get_api_engine()` 单例
  - 实现 `run_inline_request`、`run_api_sequence` 两个最不依赖 DB 模型的入口
  - `run_single_api`、`run_test_case`、`run_automation_task` 留 `NotImplementedError` 由后续任务填充
  - _Requirements: 设计 §12_

- [ ] 11. 编写 README
  - 编写 `app/engine/api_engine/README.md`：模块定位、目录结构、扩展指南（怎么加断言/抽取/报告器）、与 `engine/` 根目录老代码的关系说明（仅作参考，不引用）

---

## Phase 2：Loaders + 单接口入口接通

- [ ] 12. 实现 InlineRequestLoader
  - 编写 `api_engine/loaders/base.py`：`SpecLoader` Protocol
  - 编写 `api_engine/loaders/inline_request_loader.py`：dict → `RequestSpec`，校验必填（method/url），校验断言/抽取规则结构
  - 缺字段抛 `InvalidRequestSpecError(missing=[...])`
  - _Requirements: Story 3, 设计 §10_

- [ ] 13. 数据模型增强：apis 表加字段
  - 修改 `app/models/api.py`：新增 `assertions`、`extracts`、`timeout` 三列，`to_dict()` 同步
  - 生成 Alembic 迁移：`migrations/versions/xxxx_add_api_engine_fields.py`，upgrade 加列、downgrade 删列
  - 验证旧数据 `assertions=NULL` 时引擎读取等价于 `[]`
  - _Requirements: 4.1, 设计 §13_

- [ ] 14. 实现 ApiModelLoader
  - 编写 `api_engine/loaders/api_model_loader.py`：
    - `load_request(api_id, overrides=None) -> RequestSpec`
    - `load_collection(api_ids, project_id, environment_id, fail_strategy) -> CollectionSpec`
  - 把 `Api.method/path/base_url/headers/params/body/body_type/module/service/prefix_url_id/assertions/extracts/timeout` 映射到 `RequestSpec`
  - `overrides` 字段（前端"调试时临时改 headers"）覆盖到 spec
  - _Requirements: Story 1, Story 2, 设计 §10_

- [ ] 15. 完善 ApiEngine.run_single_api 与 run_api_sequence
  - `run_single_api`：用 `ApiModelLoader.load_request` + `SequenceRunner` 跑长度 1 的 collection，unwrap 第一条 step 返回
  - `run_api_sequence`：用 `ApiModelLoader.load_collection` + `SequenceRunner`
  - 都注入 `ConsoleReporter`，不写库
  - _Requirements: Story 1.1, Story 2.1, 设计 §12_

- [ ] 16. 切流 `routes/api.py` 的单接口测试端点
  - 修改 `POST /api/projects/<project_id>/apis/<api_id>/test`：调用 `engine.run_single_api`
  - 编写 `_to_legacy_response(step_result) -> dict`：转成原有 `{success, request, response, error, duration, timestamp}` 结构
  - 录制切流前后的对比用例（至少 3 个：成功 GET、失败 404、超时），diff JSON 字段一致
  - _Requirements: Story 1, Story 7.2, 设计 §14.2_

- [ ] 17. 新增多接口顺序执行路由
  - 在 `routes/api.py` 增加 `POST /api/projects/<project_id>/apis/run-sequence`
  - body：`{"api_ids": [...], "environment_id": int|null, "fail_strategy": "continue"|"fail_fast"}`
  - 调用 `engine.run_api_sequence`，返回 `CollectionResult.to_dict()`
  - 加权限装饰器（与现 ApiTestView 一致）
  - _Requirements: Story 2, 设计 §14.3_

---

## Phase 3：自动化任务委托

- [ ] 18. 实现 AutomationTaskLoader
  - 编写 `api_engine/loaders/automation_task_loader.py`：`load_collection(task_id) -> CollectionSpec`
  - 按 `automation_task_cases.sort_order` 拉出关联 `test_cases.id` 转换为 `RequestSpec`（复用 TestCaseLoader 的转换逻辑，下个任务实现）
  - _Requirements: Story 4, 设计 §10_

- [ ] 19. 实现 TestCaseLoader
  - 编写 `api_engine/loaders/test_case_loader.py`：
    - `load_request(case_id) -> RequestSpec`
    - 自动把 `expected_status` 转成 `AssertionRule(type="status_code", config={"expected": ...})`
    - 自动把 `expected_response` 转成 `AssertionRule(type="json_path", ...)` 或 `JsonContains` 等价规则
  - _Requirements: Story 5, 设计 §10_

- [ ] 20. 实现 AutomationDbReporter
  - 编写 `api_engine/reporters/automation_db_reporter.py`：
    - `on_collection_started`：建 `TaskExecution(status=running)` 行，写入 `_execution_id` 实例属性
    - `on_step_completed`：`db.session.add(TaskExecutionDetail(...))` + commit
    - `on_collection_finished`：更新 `TaskExecution.status/total/passed/failed/error/duration/error_message`
  - 重复触发场景由调用方（AutomationExecutor）保护，Reporter 不感知
  - _Requirements: Story 4.2, Story 4.3, 设计 §11_

- [ ] 21. 完善 ApiEngine.run_automation_task
  - 注入 `AutomationDbReporter` + `ConsoleReporter`
  - 任务的 `environment_id` 优先级：参数 > task.environment_id
  - 异常兜底（与设计 §15 一致）
  - 返回 `CollectionResult`（含 `automation_db_reporter._execution_id`，由调用方查实体）
  - _Requirements: Story 4, 设计 §12 §15_

- [ ] 22. AutomationExecutor 委托给引擎
  - 修改 `app/services/automation_executor.py`：
    - 保留 `execute_task(task_id, environment_id, trigger_source)` 签名与 `DuplicateExecutionError` 抛出逻辑
    - 内部调用 `engine.run_automation_task(...)`，然后 `TaskExecution.query.get(reporter._execution_id)` 返回
    - 删除 `_execute_cases` / `_prepare_case` / `_summarize` 方法（注释掉，标 DEPRECATED，留 1 个 PR 内可回滚）
  - 录制对比：切流前后任意 1 个真实任务的 `task_executions` + `task_execution_details` 行级 diff
  - _Requirements: Story 4.1, Story 7.2, 设计 §14.4_

---

## Phase 4：用例执行委托

- [ ] 23. 实现 TestResultDbReporter
  - 编写 `api_engine/reporters/test_result_db_reporter.py`：`on_step_completed` 写入 `test_results` 行（字段映射设计 §13 表）
  - 暴露 `_last_result_id` 给调用方读取
  - _Requirements: Story 5, 设计 §11_

- [ ] 24. 完善 ApiEngine.run_test_case
  - 用 `TestCaseLoader.load_request` + `SequenceRunner` 跑长度 1 的 collection
  - 注入 `TestResultDbReporter` + `ConsoleReporter`
  - 返回 `StepResult`
  - _Requirements: Story 5, 设计 §12_

- [ ] 25. TestExecutor 委托给引擎
  - 修改 `app/services/executor.py`：
    - 保留 `run_case(case)` 与 `run_cases(cases)` 签名
    - 内部调用 `engine.run_test_case(case_id=case.id)`，按 `_last_result_id` 查 `TestResult` 返回
    - 不再直接 `requests.request`
  - 录制对比：`/api/execute/case/{case_id}` 切流前后响应 diff
  - _Requirements: Story 5, Story 7.2, 设计 §14.5_

---

## Phase 5：归档与清理

- [x] 26. 老引擎代码归档
  - 创建 `app/engine/_legacy/` 子目录
  - 移入 `liu_shui_xian.py`、`test_factory.py`、`read_env.py`、`read_case.py`、`assertion_handler.py`、`report_generator.py`
  - 每个文件顶部加 `# DEPRECATED: 已被 app/engine/api_engine 替代，仅作历史参考`
  - `_legacy/__init__.py` 在 import 时触发 ``DeprecationWarning``
  - 全仓搜索 import 路径，确认无业务路径再引用（agents、services、routes 全清扫）
  - 更新 `app/engine/__init__.py` 与 `app/engine/README.md` 描述
  - _Requirements: Story 7.3, 设计 §14.6_

- [x] 27. 全量回归
  - app 启动正常（所有 blueprint 注册）
  - 5 条关键路由全部就位（apis/test、apis/run-sequence、automations/execute、execute/case、execute/batch）
  - ApiEngine 7 个入口齐全（run_inline_request / run_inline_sequence / run_single_api / run_api_sequence / run_test_case / run_test_cases / run_automation_task）
  - 6 种断言 + 3 种抽取器 + 4 个 Loader + 3 个 Reporter 注册到位
  - 端到端 inline_request 真实 HTTP 调用成功
  - 全仓 grep 确认无业务路径引用 `_legacy` 模块
  - import `app.engine._legacy` 触发 DeprecationWarning

---

## 任务依赖关系图

```
Phase 1（1 → 11）独立完成
        │
        ▼
Phase 2（12 → 17）依赖 Phase 1 全部
        │
        ├──▶ Phase 3（18 → 22）依赖 Phase 2 完成（测/合并）
        │
        └──▶ Phase 4（23 → 25）可与 Phase 3 并行（无相互依赖）
                                    │
                                    ▼
                            Phase 5（26 → 27）依赖 Phase 3 + Phase 4
```

每个 Phase 完成都应有可验证产物：
- Phase 1：可在 Python REPL 中 `from app.engine.api_engine import ApiEngine; ApiEngine().run_inline_request(...)` 跑通一次
- Phase 2：单接口测试页面与"批量运行"路由可用
- Phase 3：自动化任务行为与切流前完全一致（数据库行级 diff 通过）
- Phase 4：`/api/execute/case/{case_id}` 行为与切流前完全一致
- Phase 5：老 engine 代码归档完成，仓库无业务引用残留
