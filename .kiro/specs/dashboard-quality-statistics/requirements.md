# Requirements Document

## Introduction

本特性将自动化测试平台（ATP）现有的"控制面板（Dashboard）"从"5 个总数统计卡片 + 模拟列表"升级为面向质量数据的"大数据看板（Quality Dashboard）"。新看板基于平台已落库的真实数据（项目、接口、用例、Bug、执行结果、需求、冲刺、操作日志、项目成员等），围绕"测试执行、Bug 质量、用例覆盖、需求质量、项目总览、团队效能、数据导出"7 大主题，提供多维度图表、筛选、对比与导出能力。

特性的取舍原则：

- 仅承诺基于现有数据模型可支撑的指标；对数据模型不支持的指标，本文档明确标注并降级或剔除。
- 保留现有 `/api/dashboard/stats` 接口与 5 张总数卡片，确保平滑迁移。
- 新增能力以独立子模块"质量数据统计"承载，与基础统计共存于同一个 Dashboard 页面，可通过 Tab 或 Section 切换。
- 所有统计接口必须遵守平台的项目级权限隔离规则。

## Glossary

- **Quality_Dashboard_Backend**：后端质量统计模块，承载于 Flask 蓝图（建议路由前缀 `/api/dashboard/quality`），由 `routes/quality_dashboard.py`、`schemas/quality_dashboard.py`、`services/quality_metrics_service.py` 等文件构成。
- **Quality_Dashboard_Frontend**：前端质量看板模块，承载于 `client/src/views/Dashboard.vue` 改造及其拆分出的子组件（如 `client/src/views/dashboard/` 目录下的图表组件）。
- **Basic_Stats_Card**：现有的 5 张总数卡片（项目数、目录数、接口数、用例数、Bug 数），由 `/api/dashboard/stats` 提供。
- **Visible_Project_Set**：当前登录用户基于 `project_members` 表可见的项目集合；平台管理员（admin 角色）的可见集合等于 `projects` 表全集。
- **Quality_Filter**：质量看板的全局筛选条件对象，至少包含字段 `project_ids: int[]`、`start_date: date`、`end_date: date`，可选字段 `module: string`、`version: string`、`sprint_id: int`。
- **Time_Range**：由 `start_date` 与 `end_date` 表示的闭区间时间范围，单位为日；当未传入时默认取最近 30 天。
- **Pass_Rate**：在给定 Time_Range 与 Visible_Project_Set 下，`test_results.status='passed'` 的记录数除以 `test_results` 全部记录数的比值，用百分数表示，保留 2 位小数；分母为 0 时返回 `null`。
- **Fail_Rate**：在同一约束下，`test_results.status` 为 `failed` 或 `error` 的记录数除以全部记录数的比值。
- **Api_Coverage_Rate**：在 Visible_Project_Set 中，被至少 1 条 `test_case_management` 通过 `test_case_api_bindings` 关联的 `apis` 记录数，除以 `apis` 全部记录数的比值。
- **Bug_Convergence_Rate**：在给定 Time_Range 与 Visible_Project_Set 下，`bugs.status` 为 `resolved` 或 `closed` 的记录数除以 `bugs` 全部记录数的比值。
- **Bug_Avg_Fix_Duration**：对所有满足 `resolved_at IS NOT NULL` 的 Bug，`resolved_at - created_at` 的平均小时数。
- **Sprint_Completion_Rate**：在某个冲刺范围内，`requirements.status` 为 `done` 或 `closed` 的需求数除以该冲刺关联需求总数的比值。
- **Project_Health_Score**：单个项目的健康度评分，由"用例覆盖率、Bug 收敛率、执行通过率、需求完成率"4 项指标按各自权重加权得到的 0–100 分数；权重默认各 25%，可在配置文件或后端常量中调整。
- **Quality_Cache_Layer**：质量统计接口的内存缓存层（建议基于进程内字典 + TTL 实现，遵循 `flask_caching` 的接口或自实现），用于缓解高代价聚合查询的压力。
- **Export_Job**：导出任务，对应 PDF 或 Excel 格式的质量报告生成请求。

## Requirements

### Requirement 1: 保留基础统计与平滑迁移

**User Story:** 作为一名平台用户，我希望进入控制面板时仍能立即看到现有的 5 张总数卡片，以便在新的质量看板加载完成前先获得概览。

#### Acceptance Criteria

1. THE Quality_Dashboard_Backend SHALL 保留 `GET /api/dashboard/stats` 接口及其响应结构 `{code: 0, data: {project_count, folder_count, api_count, test_case_count, bug_count}}`。
2. WHEN 当前登录用户加载 Dashboard 页面，THE Quality_Dashboard_Frontend SHALL 在顶部展示 5 张 Basic_Stats_Card，数据来源于 `GET /api/dashboard/stats`。
3. WHEN 当前登录用户加载 Dashboard 页面，THE Quality_Dashboard_Frontend SHALL 在 Basic_Stats_Card 下方提供入口（Tab 或 Section）进入质量数据统计模块。
4. IF `GET /api/dashboard/stats` 请求失败，THEN THE Quality_Dashboard_Frontend SHALL 在卡片区显示占位错误提示并允许用户点击重试。
5. THE Quality_Dashboard_Frontend SHALL 移除现有 Dashboard.vue 中"最近执行记录""项目列表""快捷操作"区域的硬编码 mock 数据，并以质量看板模块替代或改造为接入真实接口。

### Requirement 2: 全局筛选（项目与时间范围）

**User Story:** 作为一名测试经理，我希望按项目和时间范围筛选质量看板的数据，以便聚焦关注的项目与周期。

#### Acceptance Criteria

1. THE Quality_Dashboard_Backend SHALL 在所有质量统计接口（路径前缀 `/api/dashboard/quality/`）中接受查询参数 `project_ids`（整数数组，可多选，缺省表示 Visible_Project_Set 全量）、`start_date`、`end_date`（ISO 8601 日期格式）。
2. WHEN `start_date` 或 `end_date` 缺失，THE Quality_Dashboard_Backend SHALL 将 Time_Range 默认设置为"今天往前 30 天（含今天）"。
3. IF `start_date` 晚于 `end_date`，THEN THE Quality_Dashboard_Backend SHALL 返回 `{code: 1, message: "时间范围非法：start_date 不能晚于 end_date"}` 并使用 HTTP 400。
4. IF `start_date` 与 `end_date` 跨度超过 365 天，THEN THE Quality_Dashboard_Backend SHALL 返回 `{code: 1, message: "时间跨度不得超过 365 天"}` 并使用 HTTP 400。
5. WHEN 请求中 `project_ids` 包含不在调用方 Visible_Project_Set 中的项目 ID，THE Quality_Dashboard_Backend SHALL 在聚合前过滤掉这些项目 ID，并在响应中通过字段 `filtered_project_ids` 返回实际生效的项目 ID 列表。
6. THE Quality_Dashboard_Frontend SHALL 在质量看板顶部提供项目多选下拉与时间范围选择器（快捷选项至少包含"近 7 天 / 近 30 天 / 近 90 天 / 自定义"）。
7. WHEN 用户改变筛选条件，THE Quality_Dashboard_Frontend SHALL 在 500 毫秒内向所有受影响的质量统计接口发起新的请求，并展示加载状态。

### Requirement 3: 项目级数据权限隔离

**User Story:** 作为一名项目成员，我只希望在质量看板中看到自己有权限访问的项目数据，避免信息越权。

#### Acceptance Criteria

1. THE Quality_Dashboard_Backend SHALL 对所有质量统计接口应用 `@login_required` 装饰器。
2. WHEN 调用方为非 admin 用户，THE Quality_Dashboard_Backend SHALL 通过 `project_members` 表计算调用方的 Visible_Project_Set，并将所有聚合查询限制在该集合内。
3. WHEN 调用方持有 admin 角色，THE Quality_Dashboard_Backend SHALL 将 Visible_Project_Set 设置为 `projects` 表全集。
4. IF 调用方的 Visible_Project_Set 为空集，THEN THE Quality_Dashboard_Backend SHALL 返回 `{code: 0, data: {empty: true, ...}}` 且所有指标值取空集对应的零值或 `null`，HTTP 状态保持 200。
5. THE Quality_Dashboard_Backend SHALL 在 `bugs`、`test_results`、`test_case_management`、`apis`、`requirements`、`sprints` 等表的查询中均通过 `project_id` 字段（或经 `case_id → test_cases.project_id` 的关联）执行权限过滤。

### Requirement 4: 测试执行统计

**User Story:** 作为一名测试负责人，我希望查看测试执行的通过率/失败率趋势与耗时分布，以便评估测试稳定性与效率。

#### Acceptance Criteria

1. WHEN 调用方请求 `GET /api/dashboard/quality/execution/trend` 且通过 Quality_Filter，THE Quality_Dashboard_Backend SHALL 按日聚合 Time_Range 内的 `test_results`，返回每日 `total`、`passed`、`failed`、`error`、`skipped`、`pass_rate`、`fail_rate`。
2. WHEN 调用方请求 `GET /api/dashboard/quality/execution/by-project`，THE Quality_Dashboard_Backend SHALL 按 `test_cases.project_id` 分组返回每个项目在 Time_Range 内的执行总数、通过数、失败数、Pass_Rate。
3. WHEN 调用方请求 `GET /api/dashboard/quality/execution/duration-distribution`，THE Quality_Dashboard_Backend SHALL 返回 Time_Range 内 `test_results.duration` 在以下分桶的次数：`[0,0.5), [0.5,1), [1,2), [2,5), [5,10), [10,+∞)`，单位为秒。
4. THE Quality_Dashboard_Frontend SHALL 使用折线图展示通过率/失败率趋势，使用堆叠柱状图展示按项目维度的执行结果分布，使用柱状图展示耗时分桶分布。
5. IF Time_Range 内无任何 `test_results` 记录，THEN THE Quality_Dashboard_Backend SHALL 在响应 `data` 中返回空数组并附带 `empty: true`。
6. THE Quality_Dashboard_Backend SHALL 不实现"按模块维度"的执行统计；模块维度统计在 `test_results` 与 `test_cases` 中均无可用字段，本特性以"按项目维度"作为替代。

### Requirement 5: Bug 质量分析

**User Story:** 作为一名质量分析师，我希望查看 Bug 的状态、严重程度、优先级、趋势、修复时长与按模块/版本的缺陷密度，以便定位质量风险点。

#### Acceptance Criteria

1. WHEN 调用方请求 `GET /api/dashboard/quality/bug/status-distribution`，THE Quality_Dashboard_Backend SHALL 返回 Time_Range 与 Visible_Project_Set 内 `bugs.status` 各取值（`open`、`in_progress`、`resolved`、`closed`、`reopened`）的计数。
2. WHEN 调用方请求 `GET /api/dashboard/quality/bug/priority-severity-distribution`，THE Quality_Dashboard_Backend SHALL 同时返回 `priority`（`low/medium/high/critical`）与 `severity`（`trivial/minor/normal/major/critical`）两个维度的计数。
3. WHEN 调用方请求 `GET /api/dashboard/quality/bug/trend`，THE Quality_Dashboard_Backend SHALL 按日返回 Time_Range 内"新增 Bug 数（按 `created_at`）"与"关闭 Bug 数（按 `resolved_at`，状态为 `resolved` 或 `closed`）"两条序列。
4. WHEN 调用方请求 `GET /api/dashboard/quality/bug/avg-fix-duration`，THE Quality_Dashboard_Backend SHALL 返回 Bug_Avg_Fix_Duration（小时，保留 2 位小数）以及参与计算的样本数 `sample_count`。
5. WHEN 调用方请求 `GET /api/dashboard/quality/bug/density`，THE Quality_Dashboard_Backend SHALL 按 `module`（字符串字段）、`version`（字符串字段）两个维度分别返回 Bug 计数 Top 10 列表。
6. IF `bugs.module` 或 `bugs.version` 字段值为 `NULL` 或空字符串，THEN THE Quality_Dashboard_Backend SHALL 将该记录归入分组键 `"未指定"` 并参与计数。
7. THE Quality_Dashboard_Frontend SHALL 使用饼图展示 Bug 状态与严重程度分布，使用双折线图展示新增 vs 关闭趋势，使用柱状图展示按模块/版本的 Top 10 缺陷密度，使用单值卡片展示平均修复时长。

### Requirement 6: 用例覆盖度

**User Story:** 作为一名测试经理，我希望查看接口覆盖率、用例优先级与状态分布，以便评估测试资产的健康度。

#### Acceptance Criteria

1. WHEN 调用方请求 `GET /api/dashboard/quality/coverage/api`，THE Quality_Dashboard_Backend SHALL 返回 Visible_Project_Set 中 `apis` 总数 `api_total`、被 `test_case_api_bindings` 关联的 `apis` 数 `api_covered`、覆盖率 `coverage_rate = api_covered / api_total`，并按 `project_id` 分组同时返回每个项目的同名指标。
2. WHEN 调用方请求 `GET /api/dashboard/quality/coverage/case-priority`，THE Quality_Dashboard_Backend SHALL 返回 `test_case_management.priority`（`P0/P1/P2/P3`）各取值的计数，未匹配上述四个值的记录归入 `"其他"`。
3. WHEN 调用方请求 `GET /api/dashboard/quality/coverage/case-status`，THE Quality_Dashboard_Backend SHALL 返回 `test_case_management.case_status`（`草稿/已评审/已废弃`）各取值的计数。
4. IF `apis` 总数为 0，THEN `coverage_rate` SHALL 返回 `null`，前端展示为 `"-"`。
5. THE Quality_Dashboard_Frontend SHALL 使用环形图（或仪表盘）展示接口覆盖率，使用饼图分别展示用例优先级与用例状态分布。

### Requirement 7: 需求质量追踪

**User Story:** 作为一名产品负责人，我希望查看需求状态分布、冲刺完成率与冲刺燃尽情况，以便评估迭代进度。

#### Acceptance Criteria

1. WHEN 调用方请求 `GET /api/dashboard/quality/requirement/status-distribution`，THE Quality_Dashboard_Backend SHALL 返回 Visible_Project_Set 与 Time_Range 内 `requirements.status`（`draft/pending/approved/in_progress/testing/done/closed/rejected`）各取值的计数。
2. WHEN 调用方请求 `GET /api/dashboard/quality/requirement/sprint-completion`，THE Quality_Dashboard_Backend SHALL 按 `sprint_id` 分组返回各冲刺的需求总数、完成数（`status` 为 `done` 或 `closed`）、Sprint_Completion_Rate，并按 `sprints.start_date` 倒序排列。
3. WHEN 调用方请求 `GET /api/dashboard/quality/requirement/burndown` 且查询参数包含 `sprint_id`，THE Quality_Dashboard_Backend SHALL 返回该冲刺从 `start_date` 到 `min(end_date, today)` 之间每日的"理论剩余需求数"与"实际剩余需求数"，其中实际剩余基于 `operation_logs.target_type='requirement'` 中的状态变更日志重建。
4. IF 指定冲刺的状态变更日志在 `operation_logs` 中缺失或无法解析为状态变更，THEN THE Quality_Dashboard_Backend SHALL 在响应中返回 `actual_burndown_supported: false` 并仅返回理论燃尽线，前端 SHALL 展示"实际燃尽数据缺失"的提示。
5. WHEN 调用方请求 `GET /api/dashboard/quality/requirement/related-counts`，THE Quality_Dashboard_Backend SHALL 按需求关联冲刺为聚合维度，返回每个 `sprint_id` 关联的需求数、Bug 数（`bugs.project_id` 与需求同项目且 `bugs.created_at` 落在冲刺起止时间内）、用例数（同上规则）。
6. THE Quality_Dashboard_Backend SHALL 不在本特性中提供"需求与用例的逐条精确关联"指标；当前数据模型中 `requirements` 与 `test_cases`、`bugs` 之间不存在外键关联，本特性以"同冲刺范围内的弱关联计数"作为降级方案，并在响应中以字段 `association_mode: "sprint_scope"` 标识。
7. THE Quality_Dashboard_Frontend SHALL 使用饼图展示需求状态分布，使用横向柱状图展示多冲刺完成率对比，使用折线图展示燃尽图（理论线为虚线、实际线为实线）。

### Requirement 8: 项目质量总览

**User Story:** 作为一名研发主管，我希望横向对比多个项目的质量评分并查看单项目的健康度雷达图，以便整体判断各项目质量水位。

#### Acceptance Criteria

1. WHEN 调用方请求 `GET /api/dashboard/quality/project/scoreboard`，THE Quality_Dashboard_Backend SHALL 对 Visible_Project_Set 中每个项目，在给定 Time_Range 内计算 Api_Coverage_Rate、Bug_Convergence_Rate、Pass_Rate、Sprint_Completion_Rate 4 项指标，并按权重加权得出 Project_Health_Score。
2. THE Quality_Dashboard_Backend SHALL 在响应中返回每个项目的 4 项原始指标（百分比，保留 2 位小数）、Project_Health_Score（0–100，保留 1 位小数）、`level`（`excellent`≥85、`good` 70–84、`warning` 50–69、`critical`<50）。
3. IF 某项指标在该项目无数据可计算（如该项目无任何 Bug 或无任何执行记录），THEN 对应指标 SHALL 取 `null`，并按权重在评分中视作 0 分参与计算，同时响应字段 `missing_metrics` 列出缺失项。
4. WHEN 调用方请求 `GET /api/dashboard/quality/project/radar` 且查询参数包含 `project_id`，THE Quality_Dashboard_Backend SHALL 返回该项目 4 项指标的雷达图数据点。
5. IF `project_id` 不在调用方 Visible_Project_Set 中，THEN THE Quality_Dashboard_Backend SHALL 返回 `{code: 1, message: "无权访问该项目"}` 并使用 HTTP 403。
6. THE Quality_Dashboard_Frontend SHALL 使用横向柱状图（或评分卡矩阵）展示项目质量评分对比，使用雷达图展示单项目健康度。

### Requirement 9: 团队效能统计

**User Story:** 作为一名团队负责人，我希望查看成员的 Bug 提交/解决排行与用例相关操作量，以便了解团队成员的工作贡献分布。

#### Acceptance Criteria

1. WHEN 调用方请求 `GET /api/dashboard/quality/team/bug-ranking`，THE Quality_Dashboard_Backend SHALL 在 Time_Range 与 Visible_Project_Set 内分别返回 Top 10：
   - 提交排行：按 `bugs.reporter_id` 分组的 Bug 创建数；
   - 解决排行：按 `bugs.resolved_by` 分组（`status` 为 `resolved` 或 `closed`）的 Bug 解决数。
2. WHEN 调用方请求 `GET /api/dashboard/quality/team/case-activity`，THE Quality_Dashboard_Backend SHALL 基于 `operation_logs` 中 `target_type='test_case'` 或 `target_type='test_case_management'` 的记录，按 `operator_id` 分组返回 Top 10 操作量。
3. THE Quality_Dashboard_Backend SHALL 在团队效能接口的响应中以 `username` 替换裸 ID，便于前端直接展示。
4. THE Quality_Dashboard_Backend SHALL 不在本特性中提供"成员真实用例执行量"指标；`test_results` 表无 `executor_id` 字段，本特性以"基于 operation_logs 的用例操作量（含创建、编辑、执行触发等动作）"作为降级方案，并在响应中以字段 `metric_basis: "operation_logs"` 标识。
5. THE Quality_Dashboard_Frontend SHALL 使用横向柱状图（Top 10）展示三类排行榜，并在卡片标题处标注"基于操作日志近似"。

### Requirement 10: 数据导出（Excel 与 PDF）

**User Story:** 作为一名测试经理，我希望按当前筛选条件一键导出质量报告，以便在评审会议或汇报中使用。

#### Acceptance Criteria

1. WHEN 调用方请求 `POST /api/dashboard/quality/export` 且请求体包含 `format`（`excel` 或 `pdf`）、Quality_Filter、`sections`（字符串数组，取值范围与上述 7 大主题对应），THE Quality_Dashboard_Backend SHALL 同步生成报告文件并以二进制流形式返回，响应头 `Content-Disposition` 携带形如 `quality_report_{YYYYMMDD_HHMMSS}.{ext}` 的文件名。
2. WHEN `format='excel'`，THE Quality_Dashboard_Backend SHALL 使用 `openpyxl` 输出 `.xlsx` 文件，并按 `sections` 列表为每个主题创建一个工作表，工作表内容包含图表对应的明细数据表。
3. WHEN `format='pdf'`，THE Quality_Dashboard_Backend SHALL 使用 `reportlab`（推荐）或等效库输出 `.pdf` 文件，包含封面（项目范围、时间范围、生成时间）、各主题指标卡片与统计数据表。
4. IF `sections` 为空数组，THEN THE Quality_Dashboard_Backend SHALL 返回 `{code: 1, message: "请至少选择一个导出主题"}` 并使用 HTTP 400。
5. IF 报告生成耗时超过 30 秒，THEN THE Quality_Dashboard_Backend SHALL 中止导出并返回 `{code: 1, message: "报告生成超时，请缩小时间范围或减少导出主题"}` 并使用 HTTP 504。
6. WHEN 调用方触发导出，THE Quality_Dashboard_Backend SHALL 在 `operation_logs` 写入一条 `action='导出质量报告'` 的记录用于审计。
7. WHERE 服务器未安装 PDF 依赖库，THE Quality_Dashboard_Backend SHALL 在 `format='pdf'` 时返回 `{code: 1, message: "服务端未启用 PDF 导出能力，请使用 Excel 导出"}` 并使用 HTTP 501，且不影响 Excel 导出能力。
8. THE Quality_Dashboard_Frontend SHALL 在质量看板提供"导出"按钮与导出弹窗，弹窗内允许用户勾选导出格式与主题清单。

### Requirement 11: 性能与缓存

**User Story:** 作为一名平台运维，我希望质量看板接口具备可控的响应时间与缓存机制，以避免高代价聚合查询拖慢系统。

#### Acceptance Criteria

1. WHEN 单个质量统计接口被调用，THE Quality_Dashboard_Backend SHALL 在 95 分位响应时间不超过 2000 毫秒（数据规模基准：单项目 10 万条 `test_results`、5 千条 `bugs`、5 千条 `requirements` 时）。
2. THE Quality_Dashboard_Backend SHALL 通过 Quality_Cache_Layer 对每个质量统计接口的响应实现按"调用方用户 ID + 接口路径 + 排序后的 Quality_Filter 序列化串"为键的缓存，缓存有效期 60 秒。
3. WHEN 缓存命中，THE Quality_Dashboard_Backend SHALL 在响应头中加入 `X-Cache: HIT`；WHEN 未命中，SHALL 加入 `X-Cache: MISS`。
4. WHEN 调用方在请求中携带查询参数 `refresh=true`，THE Quality_Dashboard_Backend SHALL 跳过缓存读取并以新结果覆盖缓存。
5. IF 单次聚合查询执行时间超过 10 秒，THEN THE Quality_Dashboard_Backend SHALL 中止查询并返回 `{code: 1, message: "查询超时，请缩小项目或时间范围"}` 并使用 HTTP 504。
6. THE Quality_Dashboard_Backend SHALL 为参与高频聚合的字段（至少包括 `bugs.project_id`、`bugs.status`、`bugs.created_at`、`bugs.resolved_at`、`test_results.created_at`、`test_results.case_id`、`requirements.project_id`、`requirements.sprint_id`、`requirements.status`、`operation_logs.target_type`、`operation_logs.operator_id`、`operation_logs.created_at`）核查并补齐数据库索引；缺失的索引以 Alembic 迁移脚本或 SQL 脚本形式提供。

### Requirement 12: 错误处理与可观测性

**User Story:** 作为一名平台开发者，我希望质量看板的失败场景具备一致的错误响应与日志记录，便于排查问题。

#### Acceptance Criteria

1. THE Quality_Dashboard_Backend SHALL 对所有质量统计接口的成功响应统一使用 `{code: 0, data: ...}` 结构。
2. THE Quality_Dashboard_Backend SHALL 对所有质量统计接口的失败响应统一使用 `{code: 1, message: "..."}` 结构，并按错误类别使用 HTTP 400/403/500/504 等状态码。
3. IF 后端在执行聚合查询时抛出异常，THEN THE Quality_Dashboard_Backend SHALL 记录异常堆栈到 `logs/info.log`（或对应日志文件）并向调用方返回 `{code: 1, message: "服务异常，请稍后再试"}` 与 HTTP 500，且 SHALL NOT 将异常堆栈泄露到响应体。
4. THE Quality_Dashboard_Frontend SHALL 在任意质量统计接口失败时，于对应图表区域显示错误提示与"重试"按钮，且 SHALL NOT 因单个图表失败导致整个 Dashboard 页面崩溃。
5. THE Quality_Dashboard_Frontend SHALL 在所有图表加载阶段显示骨架屏或加载动画，加载完成后再渲染图表实例。
