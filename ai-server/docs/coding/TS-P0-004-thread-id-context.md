# TS-P0-004: thread_id ContextVar 自动注入

## 任务概述

实现 `thread_id` 从 LangGraph 运行时配置自动注入到 ContextVar，使 `TokenCallbackHandler` 能自动关联 token 消耗到对应会话，无需 Agent 主动调用工具。

## 原始实现逻辑

### 问题

- `TokenCallbackHandler.on_llm_end()` 中无法获取当前 `thread_id`
- token 记录只能关联到 `case_id`（需要 Agent 主动调用 `case_create`）
- 缺少自动化的 `thread_id` 传递机制

### 旧的 agent_name 设置方式

- `set_current_agent()` 在某些地方手动调用
- 无统一的注入点

## 当前实现逻辑

### 新增 ThreadContextMiddleware

创建 `tools/middleware/thread_context.py`，实现 `AgentMiddleware`：

```python
class ThreadContextMiddleware(AgentMiddleware):
    def __init__(self, agent_name: str = "unknown"):
        self.agent_name = agent_name
    
    def before_model(self, state, runtime):
        # 1. 设置 agent_name
        set_current_agent(self.agent_name)
        # 2. 从 runtime 提取 thread_id 并注入 ContextVar
        thread_id = self._extract_thread_id(state, runtime)
        if thread_id:
            set_current_thread_id(thread_id)
```

### thread_id 提取策略（按优先级）

1. `runtime.config["configurable"]["thread_id"]` — LangGraph 标准方式
2. `runtime.thread_id` — 直接属性
3. `runtime.run_id` / `runtime.session_id` — 备选属性
4. `state["thread_id"]` — state 中的字段

### 集成到 Agent 工厂

在两个 Agent 工厂的 middleware 列表最前面添加：

1. **agent_factory.py**（主 Agent）：
   ```python
   middleware = [
       ThreadContextMiddleware(agent_name="agent"),
       BeforeAgentMiddleware(),
       DOMCleanerMiddleware(),
       TokenControlMiddleware(...),
   ]
   ```

2. **recording_agent.py**（录制回放 Agent）：
   ```python
   middleware = [
       ThreadContextMiddleware(agent_name="recording_agent"),
       BeforeAgentMiddleware(),
       SemanticSelectorMiddleware(),
       CodeCollectorMiddleware(),
       ...
   ]
   ```

### 数据流

```
前端 POST /threads/{thread_id}/runs
  ↓
LangGraph API Server（将 thread_id 放入 config.configurable）
  ↓
Agent graph 执行
  ↓
ThreadContextMiddleware.before_model()
  → set_current_thread_id(thread_id)
  → set_current_agent(agent_name)
  ↓
LLM 调用
  ↓
TokenCallbackHandler.on_llm_end()
  → get_current_thread_id()  ← 自动获取
  → counter.record(thread_id=thread_id)
  → _ensure_thread() 自动创建 thread 记录
  → 更新 threads 聚合字段
```

## 主要修复点

| 修复点 | 说明 |
|--------|------|
| 新增 ThreadContextMiddleware | 专用中间件，从 runtime 提取 thread_id |
| 多来源提取 | 支持 4 种 thread_id 来源，兼容不同 LangGraph 版本 |
| 最先执行 | 放在 middleware 列表第一位，确保后续所有操作都能获取 thread_id |
| agent_name 统一设置 | 同时设置 agent_name，替代分散的手动调用 |
| 零侵入 | 不修改 Agent 代码，不修改工具代码，纯中间件注入 |

## 涉及文件

- `tools/middleware/thread_context.py` — 新增文件
- `tools/core/agent_factory.py` — 添加 ThreadContextMiddleware
- `tools/playwright/recording_agent.py` — 添加 ThreadContextMiddleware
