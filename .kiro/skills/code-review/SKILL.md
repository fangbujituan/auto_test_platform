---
name: code-review
description: 按 ATP 项目约定对一组改动做 code review（命名 / 分层 / 装饰器顺序 / 响应格式 / from __future__ / token 经济性 / 安全），输出按文件聚合 + 必修 / 建议 / 可忽略三档分级的报告。
---

# 项目级 Code Review

## 何时激活

用户说要"review / 评审 / 审一下 / 检查一下"代码、PR、commit、改动；或者你刚做完一组改动想自检。
典型触发词：「review 一下我的改动」「帮我审一下这个 PR」「检查这段代码有没有问题」。

## 必要输入

确认（缺哪个问哪个）：

- 评审范围：未提交工作区改动（`git diff` / `git diff --staged`）/ 某个 commit / 某个分支 vs main / 用户指定的文件列表
- 是否需要给修改建议（默认是，输出修改后片段）

## 评审清单（按层依次扫描）

### 通用（所有 Python 文件）

- [ ] **首行 docstring**：模块顶部有 `""" ... """` 描述 + `作者: yandc` + `创建时间: YYYY-MM-DD`（参考 `app/models/bug.py`）。**新文件无 docstring 直接 ❌ 必修**。
- [ ] **`from __future__ import annotations`**：`app/agents/**` 下所有 .py 文件**必须**包含。其他目录推荐但不强制。
- [ ] **命名**：双词 / 职责明确，禁止 `utils.py` / `helpers.py` / `tools.py`（`app/utils/` 已经是聚合目录，里面文件可以叫 `permission.py` / `crypto.py`）。
- [ ] **import 顺序**：标准库 → 第三方 → `app.*`，组间空行，组内字母序（项目大体如此，PEP 8）。
- [ ] **type hints**：函数参数 / 返回值有 type 标注（不强制 `mypy --strict`）。
- [ ] **日志**：用 `from app.utils.debug import logs`（agents）或 `logging.getLogger(__name__)`（routes / services）；**禁用 `print`**（`if __name__ == "__main__"` 的脚本除外）。

### 路由层（`app/routes/`）

- [ ] 用 `flask_smorest.Blueprint` + `MethodView`，**不要**裸 `@bp.route` + 函数。
- [ ] Blueprint 命名 `<resource>_blp`，并保留 `<resource>_bp = <resource>_blp`。
- [ ] 装饰器顺序自上而下：`@xxx_blp.route` → `@xxx_blp.response` / `@xxx_blp.alt_response` → `@login_required` → `@check_project_permission(...)`。
- [ ] **响应统一格式**：`return jsonify({"code": 0, "data": ..., "message": "..."})`；失败 `return jsonify({"code": 1, "message": ...}), 500`。**不要**返回裸 dict，**不要**用 `success: true`。
- [ ] **写库必须 `try/except + db.session.rollback()`**。
- [ ] 取当前用户用 `g.get('current_user')`，不再次解析 token。
- [ ] 路由层逻辑超过 30 行 / 多步事务 / 跨表必须抽 service。
- [ ] 新接口必须在 `app/flask_app.py` 的 `create_app()` 里 `api.register_blueprint(...)`。
- [ ] 项目级路由前缀：`/api/projects/<int:project_id>/<resource>`，全局接口才用 `/api/<resource>`。

### 模型层（`app/models/`）

- [ ] 继承 `BaseModel`，**不要**重复声明 `id` / `created_at` / `updated_at`。
- [ ] `__tablename__` 复数 snake_case。
- [ ] 每列 `comment="..."` 中文注释，状态 / 优先级类字符串列出可选值。
- [ ] `to_dict()` 中 datetime 用 `.strftime("%Y-%m-%d %H:%M:%S")`，JSON 字段 `or []` / `or {}` 兜底。
- [ ] 修改已有表 / 加列必须配 `app/migrations/<verb>_<scope>_migration.py`，且**幂等可重入**（先查 `INFORMATION_SCHEMA` 再 ALTER）。
- [ ] 修改 README 数据库表清单（仅当用户没说"不更 README"）。

### Schema 层（`app/schemas/`）

- [ ] Marshmallow `Schema`，必填 `required=True`，可选 `load_default=...`，**不要混用** `missing` / `default`。
- [ ] 每个字段加 `metadata={"description": "..."}`（Swagger 文档可见）。

### Agent 层（`app/agents/business/`）

- [ ] **首行** `from __future__ import annotations`。
- [ ] 文件名双词（`xxx_agent.py`），类名 `XxxAgent` 继承 `BaseAgent`。
- [ ] 必须有 `name` / `output_schema` / `async def _process()`。
- [ ] **不要**覆盖 `execute()` / `validate_output()`。
- [ ] **必须支持 mock**：`if state.input_data.get("mock"):` 直接返回 fake + `state.metadata["model_used"] = "mock"`。
- [ ] LLM 调用必须用 `await self._call_llm(...)`，**不要**直接 `litellm.completion` / `openai.chat...` —— 绕过 `ModelRouter` 等于让 `routing_rules.yaml` 失效。
- [ ] 不修改 `task_id` / `correlation_id` / `workflow_id`（不可变字段）。
- [ ] 在 `app/agents/business/__init__.py` 显式 import + 加 `__all__`。
- [ ] 重型依赖（litellm、playwright）延迟到 `_process` 内 import。

### Workflow 层（`app/agents/workflows/`）

- [ ] 只组合 Agent，不写业务逻辑、不实例化 LLM。
- [ ] 导出 `<name>_workflow` + `build_<name>_orchestrator` + `__all__`。
- [ ] 条件边函数 `_xxx(state) -> bool`，**只读 state、无副作用**。
- [ ] DAG 不成环。
- [ ] docstring 必须含 ASCII DAG + token 经济性表。

### 前端（`client/src/`）

- [ ] view 用 `<script setup>`（Composition API），**不要**用 Options API。
- [ ] HTTP 调用走 `@/api/<resource>`，**不要在 view 里 `import axios`**。
- [ ] 注意拦截器：成功响应已剥掉一层 `code`，view 里看 `res.data`。
- [ ] Element Plus 组件直接用，图标按需 `import { Xxx } from '@element-plus/icons-vue'`。
- [ ] 路由必须在 `client/src/router/index.js` 集中注册，需登录的页加 `meta: { requiresAuth: true }`。
- [ ] 路由 path / name / component 名一律英文。

### Token 经济性（项目 README 列为硬规则）

- [ ] 简单分类 / 路由用 small tier 模型（本地 llama3.2-1b / deepseek），重活才上 large tier。
- [ ] 新 Agent 必须支持 mock 模式。
- [ ] 命中已有脚本（`recording_agent` 等）直接回放，不再调 LLM。
- [ ] LLM 生成内容应有缓存（同 prompt-hash 走缓存）—— 这条是建议级别，无缓存基础设施时可降为「待办」。

### 安全 / 数据

- [ ] 不把密钥 / 密码 / token 硬编码到代码或日志（README 已列明 `MYSQL_PASSWORD` / `SECRET_KEY` / `AI_ENCRYPTION_KEY` 走 `.env`）。
- [ ] 用户输入拼 SQL 必须用 ORM 或 `text(...)` + bind params，**不要 f-string 拼 SQL**。
- [ ] 生产路径不开 debug / `app.run(debug=True)` 不要进生产。

## 输出格式

按此结构产出报告（Markdown）：

```
## Code Review

### 总览
- 范围：<git diff / 文件列表>
- 改动：N 个文件 / +X / -Y 行
- 结论：✅ 可合并 / ⚠ 需修改 / ❌ 必须修改

### 必修（阻断合并）
1. **<file>:<line>** — <一句话问题>
   <代码片段>
   建议：<修改后片段>

### 建议（合入后跟进）
1. ...

### 可忽略（仅记录）
1. ...

### 漏检风险
- <如果某些改动需要数据库 migration / 文档同步 / 前后端联动校验，但 PR 没带，列在这里>
```

## 实现步骤

1. 用 `git diff` / `git diff --staged` / `git diff <base>...HEAD` 拿到改动（按用户指定范围）。
2. 解析每个文件归属（route / model / agent / view / ...），按对应清单逐项核对。
3. 命中清单的问题归档到「必修」；风格 / 可读性问题归「建议」；个人偏好（如换 list comprehension）归「可忽略」。
4. 输出报告，**不要主动改代码**，除非用户在原始指令里说"顺手帮我改了"。
5. 如果改动跨多文件且有"漏检风险"（例如改了 model 但没改 README 的数据库表清单 / 加了路由但没注册到 `flask_app.py`），单独列在「漏检风险」段，不要混进必修。

## 验证

- 报告里每条问题都有 file:line（如不可定位则注明"全文件级"）。
- 必修条目都有"建议修改片段"，可直接 patch 应用。
- 总条目数应稳定收敛 —— 不要重复报告同一类问题，归为一条 + 标注"出现 N 处"。

## 反模式

- 给鸡蛋里挑骨头的 nitpick 当必修（如"建议变量名换成 xxx"）—— 必修限于硬约束 + 安全 + 正确性。
- 不给修改建议、只指出问题 —— 项目内的 review 必须可执行。
- 跨范围 review（用户只让看 A 文件，你顺手把 B 也审了）—— 严格按范围。
