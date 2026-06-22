# 项目级 Skills 索引

这里收录 ATP 项目研发过程中重复性较高的指令模板，供 Kiro 在合适时机自动激活。

每个 skill 一个目录，目录下 `SKILL.md` 是入口文件，前面的 frontmatter 定义了
名称（`name`）和触发场景（`description`）。当你在对话里描述匹配场景的任务时，
Kiro 会自动把对应 SKILL.md 的完整内容读进上下文，按里面的步骤执行。

## 已有 skill

| name           | 适用场景 | 主要产物 |
|----------------|----------|----------|
| `add-route`    | 新增 RESTful 接口 | `app/routes/<r>.py` + `app/schemas/<r>.py` + 蓝图注册 + （可选）`client/src/api/<r>.js` |
| `add-model`    | 新增 ORM 模型 / 加表加字段 | `app/models/<r>.py` + （改表时）`app/migrations/<r>_migration.py` |
| `add-agent`    | 新增业务 Agent | `app/agents/business/<n>_agent.py` + `business/__init__.py` 导出 |
| `add-workflow` | 新增 LangGraph 工作流 | `app/agents/workflows/<n>_workflow.py` + `build_<n>_orchestrator()` |
| `add-view`     | 新增 Vue 视图页 | `client/src/views/<P>.vue` + `client/src/api/<r>.js` + 路由注册 |
| `code-review`  | 按项目约定审改动 | 三档分级 review 报告（必修 / 建议 / 可忽略） |
| `write-pytest` | 给现有模块补 pytest | `app/tests/test_<m>.py`（三段式：正常 / 边界 / 异常） |

## 触发方式

skill 是**自动激活**的。你直接用日常语言描述任务即可，例如：

- 「给项目加一个标签管理的接口」 → 触发 `add-route`
- 「新增一个评论模型，关联到需求」 → 触发 `add-model`
- 「写一个性能测试 Agent」 → 触发 `add-agent`
- 「把 a/b/c 三个 Agent 串成一条回归工作流」 → 触发 `add-workflow`
- 「加一个评论列表页」 → 触发 `add-view`
- 「review 一下我的改动」 → 触发 `code-review`
- 「给 scheduler_service 写单测」 → 触发 `write-pytest`

如果 Kiro 没自动激活，可以在消息里显式提："请激活 add-route skill"。

## 维护规则

- 每个 SKILL.md 必须以 frontmatter（`---` 包裹的 `name` + `description`）开头。
- `description` 控制在 ~150 字以内，写清楚"做什么 + 关键约束"，方便 Kiro 匹配。
- skill 内容一律中文，与项目 README 风格一致。
- 新增 skill 后，把名字补到本 README 的表格里。
- 项目硬约定有变化时（命名、装饰器顺序、响应格式、Agent 接口等），**所有相关 skill 都要同步更新**，避免新老约定打架。

## 何时升级为 steering

如果某条规则需要"无差别全局生效"（比如「禁止往 main 直接 commit」），更适合放
`.kiro/steering/` 而不是 skill。skill 是按场景激活，steering 是默认包含。
