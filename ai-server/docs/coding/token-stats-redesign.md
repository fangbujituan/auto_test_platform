# Token 统计系统重构设计文档

## 1. 背景与目标

### 1.1 现状问题

当前 Token 统计系统以自生成的 `case_id`（UUID）为主维度，`thread_id` 仅作为可选字段存储。这与实际使用场景不匹配：

- 前端工程通过 LangGraph API 与后端交互，每次会话自动分配 `threadId`（如 `5b8b9f96-e9e6-4c06-b5f4-0798bb0b6be8`）
- 前端天然以 `threadId` 为维度管理会话，但后端统计系统无法直接以此为主键关联数据
- 用例（case）的创建依赖 Agent 主动调用工具，缺乏自动化机制
- 缺少中断/异常统计、会话生命周期追踪等关键指标

### 1.2 部署模式

- **单机部署**，使用 SQLite（`data/token_stats.db`）作为唯一存储
- 不依赖任何外部数据库（无需 PostgreSQL、MySQL、Redis 等）
- Python 标准库 `sqlite3` 直接读写，零额外依赖

### 1.3 设计目标

1. **以 `thread_id` 为核心维度**：所有统计数据围绕 LangGraph 的 `thread_id` 组织
2. **自动化采集**：无需 Agent 主动调用工具，token 消耗自动关联到当前 thread
3. **软删除机制**：thread 被删除时逻辑标记，历史统计数据永久保留
4. **双层统计**：单个 thread 维度 + 全局聚合维度
5. **可量化指标扩展**：时间、token、中断、错误率、模型分布等
6. **前端友好**：所有 API 面向前端工程设计，返回结构直接可用于 UI 渲染

### 1.4 前后端职责划分

| 职责 | 归属 | 说明 |
|------|------|------|
| 数据存储（SQLite） | 后端 | `data/token_stats.db`，单机部署 |
| 数据采集（ContextVar + Callback） | 后端 | 自动采集，零侵入 |
| REST API（`/api/v1/token-stats/*`） | 后端 | 提供数据接口 |
| Dashboard 页面渲染 | **前端** | 前端工程调用后端 API，自行实现 UI |
| 图表可视化 | **前端** | 前端选择图表库（ECharts / AntV 等） |
| 实时轮询 / WebSocket | **前端** | 前端控制刷新频率 |

> 后端 `dashboard.py` 中的内嵌 HTML 页面（`DASHBOARD_HTML`）仅为临时演示用途，不作为正式 Dashboard。正式 Dashboard 应由前端工程独立实现。

## 2. 数据模型

### 2.1 数据库表设计

#### 2.1.1 `threads` 表 — 会话主表

以 LangGraph 的 `thread_id` 为主键，记录每个会话的生命周期和聚合统计。

```sql
CREATE TABLE threads (
    -- 主键：LangGraph 分配的 thread_id
    thread_id       TEXT PRIMARY KEY,
    
    -- 基本信息
    name            TEXT NOT NULL DEFAULT '',          -- 会话名称（用户可自定义）
    agent_name      TEXT NOT NULL DEFAULT 'unknown',   -- 使用的 Agent 名称
    
    -- 生命周期
    status          TEXT NOT NULL DEFAULT 'active',    -- active / completed / failed / interrupted
    created_at      TEXT NOT NULL,                     -- 创建时间（ISO 8601）
    updated_at      TEXT NOT NULL,                     -- 最后更新时间
    completed_at    TEXT,                              -- 完成时间
    
    -- 聚合统计（冗余字段，避免每次查询都 SUM）
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    message_count   INTEGER NOT NULL DEFAULT 0,        -- LLM 调用次数
    error_count     INTEGER NOT NULL DEFAULT 0,        -- 错误/异常次数
    interrupt_count INTEGER NOT NULL DEFAULT 0,        -- 中断次数（用户主动停止或超时）
    
    -- 软删除
    is_deleted      INTEGER NOT NULL DEFAULT 0,        -- 0=正常, 1=已删除
    deleted_at      TEXT,                              -- 删除时间
    
    -- 备注
    note            TEXT DEFAULT ''
);

-- 索引
CREATE INDEX idx_threads_status ON threads(status);
CREATE INDEX idx_threads_created ON threads(created_at);
CREATE INDEX idx_threads_agent ON threads(agent_name);
CREATE INDEX idx_threads_deleted ON threads(is_deleted);
```

字段说明：

| 字段 | 类型 | 说明 |
|------|------|------|
| `thread_id` | TEXT PK | LangGraph 分配的会话 ID，如 `5b8b9f96-e9e6-4c06-b5f4-0798bb0b6be8` |
| `name` | TEXT | 会话名称，前端可编辑，默认自动生成（如"会话_20260324_1430"） |
| `agent_name` | TEXT | 使用的 Agent：`agent` / `recording_agent` / `web_agent` |
| `status` | TEXT | 生命周期状态，见 2.2 节 |
| `created_at` | TEXT | 首次收到该 thread 的请求时间 |
| `updated_at` | TEXT | 最后一次 token 记录的时间 |
| `completed_at` | TEXT | 会话完成/失败/中断的时间 |
| `total_tokens` | INTEGER | 累计总 token（input + output） |
| `input_tokens` | INTEGER | 累计输入 token |
| `output_tokens` | INTEGER | 累计输出 token |
| `message_count` | INTEGER | LLM 调用次数（每次 on_llm_end 回调 +1） |
| `error_count` | INTEGER | LLM 调用失败次数（on_llm_error 回调 +1） |
| `interrupt_count` | INTEGER | 中断次数（用户取消、超时、递归限制等） |
| `is_deleted` | INTEGER | 软删除标记，0=正常，1=已删除 |
| `deleted_at` | TEXT | 删除时间 |
| `note` | TEXT | 备注信息 |

#### 2.1.2 `token_records` 表 — 明细记录表

每次 LLM 调用产生一条记录，关联到 `thread_id`。

```sql
CREATE TABLE token_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id       TEXT NOT NULL,                     -- 关联的会话 ID
    timestamp       TEXT NOT NULL,                     -- 记录时间（ISO 8601）
    
    -- 模型信息
    model_provider  TEXT NOT NULL DEFAULT 'unknown',   -- 网关/提供商（aiop/kiro/aiclient）
    model_name      TEXT NOT NULL DEFAULT 'unknown',   -- 模型名称
    
    -- Token 消耗
    input_tokens    INTEGER NOT NULL DEFAULT 0,
    output_tokens   INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    
    -- 请求信息
    agent_name      TEXT NOT NULL DEFAULT 'unknown',
    request_id      TEXT,                              -- 请求追踪 ID
    
    -- 状态
    is_error        INTEGER NOT NULL DEFAULT 0,        -- 0=正常, 1=错误
    error_message   TEXT,                              -- 错误信息（如有）
    
    -- 耗时
    latency_ms      INTEGER,                           -- LLM 响应耗时（毫秒）
    
    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
);

-- 索引
CREATE INDEX idx_records_thread ON token_records(thread_id);
CREATE INDEX idx_records_timestamp ON token_records(timestamp);
CREATE INDEX idx_records_provider ON token_records(model_provider);
CREATE INDEX idx_records_agent ON token_records(agent_name);
```

#### 2.1.3 `thread_events` 表 — 事件日志表

记录会话生命周期中的关键事件（中断、恢复、状态变更等）。

```sql
CREATE TABLE thread_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id       TEXT NOT NULL,
    timestamp       TEXT NOT NULL,
    event_type      TEXT NOT NULL,                     -- 事件类型，见 2.3 节
    detail          TEXT DEFAULT '',                   -- 事件详情（JSON 格式）
    
    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
);

CREATE INDEX idx_events_thread ON thread_events(thread_id);
CREATE INDEX idx_events_type ON thread_events(event_type);
CREATE INDEX idx_events_timestamp ON thread_events(timestamp);
```

### 2.2 会话状态机

```
                    ┌──────────────┐
                    │   created    │  首次收到 thread_id 时自动创建
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
              ┌────▶│    active    │◀────┐
              │     └──┬───┬───┬──┘     │
              │        │   │   │        │
              │        │   │   │     resume
              │        │   │   │        │
              │        ▼   │   ▼        │
              │  ┌─────────┐ ┌──────────────┐
              │  │completed│ │ interrupted  │
              │  └─────────┘ └──────────────┘
              │        │
              │        ▼
              │  ┌─────────┐
              └──│  failed  │
                 └─────────┘
```

| 状态 | 说明 | 触发条件 |
|------|------|----------|
| `active` | 进行中 | 首次收到该 thread 的请求；从 interrupted 恢复 |
| `completed` | 正常完成 | 前端调用完成接口；Agent 调用 case_complete |
| `failed` | 失败 | 连续错误超过阈值；前端标记失败 |
| `interrupted` | 中断 | 用户取消；超时无新请求（可配置，默认 30 分钟） |

### 2.3 事件类型

| event_type | 说明 | detail 示例 |
|------------|------|-------------|
| `created` | 会话创建 | `{"agent_name": "recording_agent"}` |
| `llm_call` | LLM 调用完成 | `{"model": "gpt-5.4", "tokens": 1500}` |
| `llm_error` | LLM 调用失败 | `{"error": "rate_limit_exceeded"}` |
| `interrupted` | 用户中断 | `{"reason": "user_cancel"}` |
| `resumed` | 会话恢复 | `{"from_status": "interrupted"}` |
| `completed` | 会话完成 | `{"total_tokens": 12500}` |
| `failed` | 会话失败 | `{"reason": "max_recursion"}` |
| `deleted` | 软删除 | `{"deleted_by": "user"}` |
| `restored` | 恢复删除 | `{}` |
| `renamed` | 重命名 | `{"old_name": "...", "new_name": "..."}` |
| `timeout` | 超时中断 | `{"idle_minutes": 30}` |

## 3. API 设计

所有接口前缀：`/api/v1/token-stats`

### 3.1 统一响应格式

```typescript
// 成功
{
  "success": true,
  "data": { ... }
}

// 失败
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "会话不存在"
  }
}
```

### 3.2 单个会话统计 API（以 thread_id 为维度）

#### 3.2.1 获取/自动创建会话

```
POST /api/v1/token-stats/threads
```

前端在开始新会话时调用。如果 `thread_id` 已存在则返回现有记录，不存在则自动创建。

请求体：
```json
{
  "thread_id": "5b8b9f96-e9e6-4c06-b5f4-0798bb0b6be8",
  "agent_name": "recording_agent",
  "name": "添加 Billing Item 测试"
}
```

响应：
```json
{
  "success": true,
  "data": {
    "thread_id": "5b8b9f96-e9e6-4c06-b5f4-0798bb0b6be8",
    "name": "添加 Billing Item 测试",
    "agent_name": "recording_agent",
    "status": "active",
    "created_at": "2026-03-24T14:30:00",
    "is_new": true
  }
}
```

#### 3.2.2 获取会话详情

```
GET /api/v1/token-stats/threads/{thread_id}
```

返回单个会话的完整统计信息。

响应：
```json
{
  "success": true,
  "data": {
    "thread_id": "5b8b9f96-e9e6-4c06-b5f4-0798bb0b6be8",
    "name": "添加 Billing Item 测试",
    "agent_name": "recording_agent",
    "status": "completed",
    "created_at": "2026-03-24T14:30:00",
    "updated_at": "2026-03-24T14:45:30",
    "completed_at": "2026-03-24T14:45:30",
    "is_deleted": false,
    
    "stats": {
      "total_tokens": 45230,
      "input_tokens": 32100,
      "output_tokens": 13130,
      "message_count": 12,
      "error_count": 1,
      "interrupt_count": 0,
      "duration_seconds": 930,
      "duration_display": "15分30秒",
      "avg_tokens_per_message": 3769,
      "avg_latency_ms": 2340,
      "estimated_cost_cny": 0.045
    },
    
    "model_breakdown": [
      {
        "provider": "aiop",
        "model": "azure/gpt-5.4",
        "call_count": 10,
        "total_tokens": 40000,
        "percentage": 88.4
      },
      {
        "provider": "kiro",
        "model": "claude-sonnet-4.5",
        "call_count": 2,
        "total_tokens": 5230,
        "percentage": 11.6
      }
    ],
    
    "timeline": [
      {
        "timestamp": "2026-03-24T14:30:05",
        "type": "llm_call",
        "model": "azure/gpt-5.4",
        "input_tokens": 2500,
        "output_tokens": 800,
        "latency_ms": 1850
      },
      {
        "timestamp": "2026-03-24T14:31:20",
        "type": "llm_error",
        "model": "azure/gpt-5.4",
        "error": "timeout"
      }
    ]
  }
}
```

#### 3.2.3 获取会话的 Token 明细记录

```
GET /api/v1/token-stats/threads/{thread_id}/records
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |

响应：
```json
{
  "success": true,
  "data": {
    "thread_id": "5b8b9f96-...",
    "total": 12,
    "page": 1,
    "page_size": 20,
    "records": [
      {
        "id": 1001,
        "timestamp": "2026-03-24T14:30:05",
        "model_provider": "aiop",
        "model_name": "azure/gpt-5.4",
        "input_tokens": 2500,
        "output_tokens": 800,
        "total_tokens": 3300,
        "latency_ms": 1850,
        "is_error": false
      }
    ]
  }
}
```

#### 3.2.4 获取会话事件日志

```
GET /api/v1/token-stats/threads/{thread_id}/events
```

响应：
```json
{
  "success": true,
  "data": {
    "thread_id": "5b8b9f96-...",
    "events": [
      {
        "id": 1,
        "timestamp": "2026-03-24T14:30:00",
        "event_type": "created",
        "detail": {"agent_name": "recording_agent"}
      },
      {
        "id": 5,
        "timestamp": "2026-03-24T14:35:10",
        "event_type": "llm_error",
        "detail": {"error": "timeout", "model": "azure/gpt-5.4"}
      },
      {
        "id": 12,
        "timestamp": "2026-03-24T14:45:30",
        "event_type": "completed",
        "detail": {"total_tokens": 45230}
      }
    ]
  }
}
```

#### 3.2.5 更新会话信息

```
PATCH /api/v1/token-stats/threads/{thread_id}
```

请求体（所有字段可选）：
```json
{
  "name": "新的会话名称",
  "status": "completed",
  "note": "测试通过"
}
```

#### 3.2.6 软删除会话

```
DELETE /api/v1/token-stats/threads/{thread_id}
```

逻辑删除，设置 `is_deleted=1`，统计数据保留。

响应：
```json
{
  "success": true,
  "data": {
    "thread_id": "5b8b9f96-...",
    "message": "会话已删除（统计数据保留）"
  }
}
```

#### 3.2.7 恢复已删除会话

```
POST /api/v1/token-stats/threads/{thread_id}/restore
```

### 3.3 会话列表 API

#### 3.3.1 获取会话列表

```
GET /api/v1/token-stats/threads
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 状态筛选：`active`/`completed`/`failed`/`interrupted` |
| `agent` | string | 否 | Agent 筛选 |
| `date_from` | string | 否 | 起始日期（YYYY-MM-DD） |
| `date_to` | string | 否 | 结束日期（YYYY-MM-DD） |
| `keyword` | string | 否 | 名称关键词搜索 |
| `include_deleted` | bool | 否 | 是否包含已删除的会话，默认 `false` |
| `sort_by` | string | 否 | 排序：`created_at`/`updated_at`/`total_tokens`/`duration`，默认 `created_at` |
| `order` | string | 否 | `asc`/`desc`，默认 `desc` |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20 |

响应：
```json
{
  "success": true,
  "data": {
    "total": 156,
    "page": 1,
    "page_size": 20,
    "threads": [
      {
        "thread_id": "5b8b9f96-...",
        "name": "添加 Billing Item 测试",
        "agent_name": "recording_agent",
        "status": "completed",
        "created_at": "2026-03-24T14:30:00",
        "updated_at": "2026-03-24T14:45:30",
        "total_tokens": 45230,
        "message_count": 12,
        "error_count": 1,
        "interrupt_count": 0,
        "duration_seconds": 930,
        "duration_display": "15分30秒",
        "estimated_cost_cny": 0.045,
        "is_deleted": false
      }
    ]
  }
}
```

### 3.4 全局统计 API（总体维度）

#### 3.4.1 全局概览

```
GET /api/v1/token-stats/overview
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `period` | string | 否 | `today`/`week`/`month`/`all`，默认 `today` |

响应：
```json
{
  "success": true,
  "data": {
    "period": "today",
    "period_start": "2026-03-24T00:00:00",
    
    "summary": {
      "total_tokens": 523400,
      "input_tokens": 378200,
      "output_tokens": 145200,
      "total_requests": 342,
      "total_threads": 28,
      "active_threads": 3,
      "completed_threads": 22,
      "failed_threads": 2,
      "interrupted_threads": 1,
      "total_errors": 5,
      "total_interrupts": 3,
      "estimated_cost_cny": 0.52,
      "avg_tokens_per_thread": 18693,
      "avg_duration_seconds": 720,
      "avg_messages_per_thread": 12.2,
      "error_rate": 1.5
    },
    
    "by_agent": [
      {
        "agent": "recording_agent",
        "thread_count": 18,
        "total_tokens": 380000,
        "request_count": 240,
        "percentage": 72.6,
        "avg_tokens_per_thread": 21111,
        "error_rate": 1.2
      },
      {
        "agent": "agent",
        "thread_count": 8,
        "total_tokens": 120000,
        "request_count": 85,
        "percentage": 22.9,
        "avg_tokens_per_thread": 15000,
        "error_rate": 2.4
      },
      {
        "agent": "web_agent",
        "thread_count": 2,
        "total_tokens": 23400,
        "request_count": 17,
        "percentage": 4.5,
        "avg_tokens_per_thread": 11700,
        "error_rate": 0
      }
    ],
    
    "by_model": [
      {
        "provider": "aiop",
        "model": "azure/gpt-5.4",
        "request_count": 280,
        "total_tokens": 450000,
        "percentage": 86.0,
        "avg_latency_ms": 2100
      },
      {
        "provider": "kiro",
        "model": "claude-sonnet-4.5",
        "request_count": 62,
        "total_tokens": 73400,
        "percentage": 14.0,
        "avg_latency_ms": 3200
      }
    ]
  }
}
```

#### 3.4.2 趋势数据

```
GET /api/v1/token-stats/trend
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `days` | int | 否 | 查询天数，默认 7，最大 90 |
| `granularity` | string | 否 | `hour`/`day`，默认 `day` |

响应：
```json
{
  "success": true,
  "data": {
    "granularity": "day",
    "trend": [
      {
        "time_bucket": "2026-03-18",
        "total_tokens": 89500,
        "input_tokens": 62000,
        "output_tokens": 27500,
        "request_count": 98,
        "thread_count": 8,
        "error_count": 2,
        "avg_latency_ms": 2050
      }
    ]
  }
}
```

#### 3.4.3 费用报表

```
GET /api/v1/token-stats/cost
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `period` | string | 否 | `today`/`week`/`month`/`all`，默认 `month` |

响应：
```json
{
  "success": true,
  "data": {
    "period": "month",
    "currency": "CNY",
    "total_cost": 12.85,
    "breakdown": [
      {
        "provider": "aiop",
        "model": "azure/gpt-5.4",
        "input_tokens": 5200000,
        "output_tokens": 1800000,
        "input_rate": 0.001,
        "output_rate": 0.002,
        "input_cost": 5.20,
        "output_cost": 3.60,
        "total_cost": 8.80,
        "percentage": 68.5
      },
      {
        "provider": "kiro",
        "model": "claude-sonnet-4.5",
        "input_tokens": 1200000,
        "output_tokens": 600000,
        "input_rate": 0.003,
        "output_rate": 0.015,
        "input_cost": 3.60,
        "output_cost": 9.00,
        "total_cost": 4.05,
        "percentage": 31.5,
        "note": "通过 Kiro Gateway 免费额度"
      }
    ]
  }
}
```

#### 3.4.4 全局明细记录

```
GET /api/v1/token-stats/records
```

参数：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `thread_id` | string | 否 | 按会话筛选 |
| `date` | string | 否 | 日期筛选（YYYY-MM-DD） |
| `provider` | string | 否 | 模型提供商筛选 |
| `agent` | string | 否 | Agent 筛选 |
| `is_error` | bool | 否 | 仅显示错误记录 |
| `page` | int | 否 | 页码 |
| `page_size` | int | 否 | 每页条数 |

## 4. 自动化采集机制

### 4.1 thread_id 传递链路

```
前端 (LangGraph Client)
  │
  │  POST /threads/{thread_id}/runs
  │
  ▼
LangGraph API Server
  │
  │  调用 Agent graph
  │
  ▼
Agent (main.py)
  │
  │  LLM 调用（携带 thread_id 上下文）
  │
  ▼
TokenCallbackHandler.on_llm_end()
  │
  │  自动记录到 token_records 表
  │  自动更新 threads 表聚合字段
  │
  ▼
SQLite (data/token_stats.db)
```

### 4.2 ContextVar 传递 thread_id

利用 Python `contextvars` 在请求链路中传递 `thread_id`，无需修改 Agent 代码：

```python
from contextvars import ContextVar

_current_thread_id: ContextVar[str | None] = ContextVar("current_thread_id", default=None)

def set_current_thread_id(thread_id: str):
    _current_thread_id.set(thread_id)

def get_current_thread_id() -> str | None:
    return _current_thread_id.get()
```

### 4.3 自动创建 thread 记录

`TokenCallbackHandler.on_llm_end()` 中，如果 `thread_id` 对应的 `threads` 记录不存在，自动创建：

```python
def _ensure_thread(self, thread_id: str, agent_name: str):
    """确保 thread 记录存在，不存在则自动创建"""
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute(
            "SELECT thread_id FROM threads WHERE thread_id = ?",
            (thread_id,)
        )
        if cursor.fetchone() is None:
            now = datetime.now().isoformat()
            conn.execute(
                """
                INSERT INTO threads (thread_id, agent_name, status, created_at, updated_at)
                VALUES (?, ?, 'active', ?, ?)
                """,
                (thread_id, agent_name, now, now)
            )
            # 记录创建事件
            conn.execute(
                """
                INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                VALUES (?, ?, 'created', ?)
                """,
                (thread_id, now, json.dumps({"agent_name": agent_name}))
            )
            conn.commit()
```

### 4.4 中断检测

通过定时任务或请求时检查，识别超时中断的会话：

```python
def check_idle_threads(idle_minutes: int = 30):
    """检查并标记超时中断的会话"""
    threshold = (datetime.now() - timedelta(minutes=idle_minutes)).isoformat()
    
    with sqlite3.connect(db_path) as conn:
        # 找到超时的 active 会话
        cursor = conn.execute(
            """
            SELECT thread_id FROM threads
            WHERE status = 'active' AND updated_at < ?
            """,
            (threshold,)
        )
        for row in cursor.fetchall():
            thread_id = row[0]
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE threads SET status = 'interrupted', updated_at = ? WHERE thread_id = ?",
                (now, thread_id)
            )
            conn.execute(
                """
                INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                VALUES (?, ?, 'timeout', ?)
                """,
                (thread_id, now, json.dumps({"idle_minutes": idle_minutes}))
            )
        conn.commit()
```

### 4.5 错误捕获

扩展 `TokenCallbackHandler` 增加 `on_llm_error` 回调：

```python
def on_llm_error(self, error, *, run_id, parent_run_id=None, **kwargs):
    """LLM 调用失败时触发"""
    thread_id = get_current_thread_id()
    if not thread_id:
        return
    
    now = datetime.now().isoformat()
    error_msg = str(error)[:500]
    
    with sqlite3.connect(self.db_path) as conn:
        # 更新 thread 错误计数
        conn.execute(
            "UPDATE threads SET error_count = error_count + 1, updated_at = ? WHERE thread_id = ?",
            (now, thread_id)
        )
        # 记录错误事件
        conn.execute(
            """
            INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
            VALUES (?, ?, 'llm_error', ?)
            """,
            (thread_id, now, json.dumps({"error": error_msg}))
        )
        # 记录错误的 token_record
        conn.execute(
            """
            INSERT INTO token_records (thread_id, timestamp, model_provider, model_name, agent_name, is_error, error_message)
            VALUES (?, ?, 'unknown', 'unknown', ?, 1, ?)
            """,
            (thread_id, now, get_current_agent(), error_msg)
        )
        conn.commit()
```

## 5. 可量化指标体系

### 5.1 单个会话（thread）维度

| 指标 | 计算方式 | 用途 |
|------|----------|------|
| `total_tokens` | SUM(input_tokens + output_tokens) | 总消耗量 |
| `input_tokens` | SUM(input_tokens) | 输入消耗 |
| `output_tokens` | SUM(output_tokens) | 输出消耗 |
| `message_count` | COUNT(token_records) | 对话轮次 |
| `error_count` | COUNT(is_error=1) | 错误次数 |
| `interrupt_count` | COUNT(event_type='interrupted') | 中断次数 |
| `duration_seconds` | completed_at - created_at | 会话总时长 |
| `active_duration_seconds` | 排除中断时间的有效时长 | 实际工作时长 |
| `avg_tokens_per_message` | total_tokens / message_count | 平均每轮消耗 |
| `avg_latency_ms` | AVG(latency_ms) | 平均响应延迟 |
| `max_latency_ms` | MAX(latency_ms) | 最大响应延迟 |
| `error_rate` | error_count / message_count × 100 | 错误率（%） |
| `estimated_cost_cny` | 按费率计算 | 预估费用 |
| `model_diversity` | COUNT(DISTINCT model_name) | 使用的模型种类数 |
| `tokens_per_minute` | total_tokens / (duration / 60) | 每分钟消耗速率 |

### 5.2 全局（总体）维度

| 指标 | 计算方式 | 用途 |
|------|----------|------|
| `total_tokens` | SUM(所有 thread) | 总消耗量 |
| `total_threads` | COUNT(threads) | 总会话数 |
| `active_threads` | COUNT(status='active') | 当前活跃会话 |
| `completed_threads` | COUNT(status='completed') | 已完成会话 |
| `failed_threads` | COUNT(status='failed') | 失败会话 |
| `interrupted_threads` | COUNT(status='interrupted') | 中断会话 |
| `completion_rate` | completed / total × 100 | 完成率（%） |
| `avg_tokens_per_thread` | total_tokens / total_threads | 平均每会话消耗 |
| `avg_duration_per_thread` | AVG(duration_seconds) | 平均会话时长 |
| `avg_messages_per_thread` | AVG(message_count) | 平均对话轮次 |
| `global_error_rate` | total_errors / total_requests × 100 | 全局错误率 |
| `peak_hour` | 按小时统计最高消耗时段 | 使用高峰 |
| `daily_avg_tokens` | total_tokens / days | 日均消耗 |
| `total_cost_cny` | SUM(estimated_cost) | 总费用 |
| `cost_per_thread` | total_cost / total_threads | 平均每会话费用 |
| `model_usage_distribution` | 按模型分组统计占比 | 模型使用分布 |
| `agent_usage_distribution` | 按 Agent 分组统计占比 | Agent 使用分布 |

### 5.3 趋势指标（时间序列）

| 指标 | 粒度 | 用途 |
|------|------|------|
| `tokens_trend` | 小时/天 | Token 消耗趋势图 |
| `thread_count_trend` | 天 | 每日会话数趋势 |
| `error_rate_trend` | 天 | 错误率趋势 |
| `latency_trend` | 小时/天 | 响应延迟趋势 |
| `cost_trend` | 天/周 | 费用趋势 |
| `model_shift_trend` | 天 | 模型使用变化趋势 |

## 6. 数据迁移方案

### 6.1 从旧表迁移

保留旧表 `token_usage` 和 `case_usage` 的数据，通过迁移脚本导入新表：

```python
def migrate_v1_to_v2():
    """从 v1 (case_usage + token_usage) 迁移到 v2 (threads + token_records + thread_events)"""
    
    with sqlite3.connect(db_path) as conn:
        # 1. 从 case_usage 迁移到 threads
        conn.execute("""
            INSERT OR IGNORE INTO threads 
                (thread_id, name, agent_name, status, created_at, updated_at, completed_at,
                 total_tokens, input_tokens, output_tokens, message_count)
            SELECT 
                COALESCE(thread_id, id) as thread_id,
                name,
                agent_name,
                status,
                start_time as created_at,
                COALESCE(end_time, start_time) as updated_at,
                end_time as completed_at,
                total_tokens,
                input_tokens,
                output_tokens,
                message_count
            FROM case_usage
        """)
        
        # 2. 从 token_usage 迁移到 token_records
        conn.execute("""
            INSERT INTO token_records 
                (thread_id, timestamp, model_provider, model_name, 
                 input_tokens, output_tokens, total_tokens, agent_name, request_id)
            SELECT 
                COALESCE(case_id, 'orphan_' || id) as thread_id,
                timestamp,
                model_provider,
                model_name,
                input_tokens,
                output_tokens,
                total_tokens,
                agent_name,
                request_id
            FROM token_usage
        """)
        
        # 3. 为没有 case 的 token_usage 记录创建 orphan thread
        conn.execute("""
            INSERT OR IGNORE INTO threads (thread_id, name, agent_name, status, created_at, updated_at)
            SELECT DISTINCT
                'orphan_' || tu.id,
                '未关联会话_' || DATE(tu.timestamp),
                tu.agent_name,
                'completed',
                tu.timestamp,
                tu.timestamp
            FROM token_usage tu
            WHERE tu.case_id IS NULL
        """)
        
        conn.commit()
```

### 6.2 兼容性

- 迁移后旧表保留不删除，作为备份
- 新旧 API 并行运行一段时间，前端逐步切换
- `dashboard.py` 中旧路由（`/token-stats/*`）保留，新路由使用 `/api/v1/token-stats/*`

## 7. 前端集成指南

> **注意**：Dashboard 页面由前端工程独立实现，后端仅提供 REST API 数据接口。以下为前端对接参考。

### 7.1 会话生命周期管理

```typescript
// 前端在创建 LangGraph thread 后，同步注册到统计系统
async function startThread(threadId: string, agentName: string) {
  await fetch('/api/v1/token-stats/threads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: threadId,
      agent_name: agentName,
      name: `会话_${new Date().toLocaleString('zh-CN')}`
    })
  });
}

// 会话结束时标记完成
async function completeThread(threadId: string) {
  await fetch(`/api/v1/token-stats/threads/${threadId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status: 'completed' })
  });
}

// 删除会话（软删除）
async function deleteThread(threadId: string) {
  await fetch(`/api/v1/token-stats/threads/${threadId}`, {
    method: 'DELETE'
  });
}
```

### 7.2 实时统计轮询

```typescript
// 活跃会话的实时统计（建议 5-10 秒轮询一次）
async function pollThreadStats(threadId: string) {
  const res = await fetch(`/api/v1/token-stats/threads/${threadId}`);
  const { data } = await res.json();
  
  // 更新 UI
  updateTokenDisplay(data.stats.total_tokens);
  updateCostDisplay(data.stats.estimated_cost_cny);
  updateDurationDisplay(data.stats.duration_display);
}
```

### 7.3 Dashboard 页面建议结构（供前端参考）

> 以下为 Dashboard 页面的建议布局，由前端工程实现，后端不包含此页面。

```
┌─────────────────────────────────────────────────────────────────────┐
│  Token 统计 Dashboard                                   2026年3月   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ 总消耗   │ │ 会话数   │ │ 完成率   │ │ 错误率   │ │ 预估费用 │ │
│  │ 523.4K   │ │ 28       │ │ 78.6%    │ │ 1.5%     │ │ ¥0.52    │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│                                                                     │
│  ┌─────────────────────────────────────┐ ┌─────────────────────┐   │
│  │ Token 消耗趋势（近7天）             │ │ Agent 分布          │   │
│  │ ┌─────────────────────────────────┐ │ │ ┌─────────────────┐ │   │
│  │ │  📈 折线图 / 柱状图             │ │ │ │  🍩 饼图         │ │   │
│  │ │  - total_tokens                 │ │ │ │                   │ │   │
│  │ │  - error_count                  │ │ │ └─────────────────┘ │   │
│  │ └─────────────────────────────────┘ │ │                     │   │
│  └─────────────────────────────────────┘ └─────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────┐ ┌─────────────────────┐   │
│  │ 模型使用分布                        │ │ 响应延迟分布        │   │
│  │ ┌─────────────────────────────────┐ │ │ ┌─────────────────┐ │   │
│  │ │  📊 堆叠柱状图                  │ │ │ │  📊 直方图       │ │   │
│  │ └─────────────────────────────────┘ │ │ └─────────────────┘ │   │
│  └─────────────────────────────────────┘ └─────────────────────┘   │
│                                                                     │
│  会话列表                                          [筛选] [搜索]    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 会话名称          │ Agent    │ 状态  │ Tokens │ 时长  │ 费用│   │
│  │─────────────────────────────────────────────────────────────│   │
│  │ 添加Billing Item  │ record.. │ ✅完成│ 45.2K  │ 15m30s│¥0.05│   │
│  │ 搜索UOM测试       │ record.. │ 🔄进行│ 12.8K  │ 5m10s │¥0.01│   │
│  │ 数据可视化        │ agent    │ ❌失败│ 8.3K   │ 3m20s │¥0.01│   │
│  │ Web搜索           │ web_ag.. │ ⏸中断 │ 2.1K   │ 1m05s │¥0.00│   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  会话详情（点击展开）                                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ Thread: 5b8b9f96-e9e6-4c06-b5f4-0798bb0b6be8              │   │
│  │ 创建: 2026-03-24 14:30  完成: 2026-03-24 14:45             │   │
│  │                                                             │   │
│  │ Token 消耗时间线                                            │   │
│  │ ┌─────────────────────────────────────────────────────┐     │   │
│  │ │  📈 每次 LLM 调用的 token 消耗散点图/阶梯图        │     │   │
│  │ └─────────────────────────────────────────────────────┘     │   │
│  │                                                             │   │
│  │ 事件日志                                                    │   │
│  │ 14:30:00  🟢 会话创建                                      │   │
│  │ 14:30:05  💬 LLM 调用 (gpt-5.4) 3,300 tokens 1.8s         │   │
│  │ 14:31:20  🔴 LLM 错误 (timeout)                            │   │
│  │ 14:31:25  💬 LLM 调用 (gpt-5.4) 4,100 tokens 2.1s         │   │
│  │ ...                                                         │   │
│  │ 14:45:30  ✅ 会话完成 (总计 45,230 tokens)                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## 8. 配置项

```python
# token_stats_config.py

TOKEN_STATS_CONFIG = {
    # 数据库路径
    "db_path": "data/token_stats.db",
    
    # 中断检测
    "idle_timeout_minutes": 30,        # 超过 30 分钟无新请求视为中断
    "check_interval_seconds": 60,      # 中断检测间隔
    
    # 数据保留
    "retention_days": 90,              # 明细记录保留天数
    "event_retention_days": 180,       # 事件日志保留天数
    "soft_delete_retention_days": 30,  # 软删除数据保留天数（超过后物理删除）
    
    # 费率配置（元/千 tokens）
    "rates": {
        "aiop": {
            "azure/gpt-5.4": {"input": 0.001, "output": 0.002},
            "openai/gpt-4": {"input": 0.03, "output": 0.06},
        },
        "kiro": {
            "claude-sonnet-4.5": {"input": 0.003, "output": 0.015},
            "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
            "deepseek-3.2": {"input": 0.001, "output": 0.002},
        },
        "aiclient": {
            "claude-sonnet-4-6": {"input": 0, "output": 0},  # 免费（OAuth）
            "gemini-2.5-flash": {"input": 0, "output": 0},
        },
    },
    
    # 错误阈值
    "max_consecutive_errors": 5,       # 连续错误超过此值标记为 failed
}
```

## 9. 实现优先级

### 后端（本项目）

| 阶段 | 内容 | 预估工作量 | 状态 |
|------|------|-----------|------|
| P0 | 新建 3 张表 + 数据迁移脚本 | 0.5 天 | ✅ 已完成 |
| P0 | 重构 `TokenCounter` 类，以 `thread_id` 为核心 | 1 天 | ✅ 已完成 |
| P0 | 重构 `TokenCallbackHandler`，增加 `on_llm_error` + `latency_ms` | 0.5 天 | ✅ 已完成 |
| P0 | 实现 `thread_id` 的 ContextVar 传递（ThreadContextMiddleware） | 0.5 天 | ✅ 已完成 |
| P1 | 实现单个会话 API（3.2 节全部接口） | 1 天 | ✅ 已完成 |
| P1 | 实现全局统计 API（3.4 节全部接口） | 1 天 | ✅ 已完成 |
| P1 | 实现会话列表 API（3.3 节） | 0.5 天 | ✅ 已完成 |
| P2 | 中断检测定时任务 | 0.5 天 | ✅ 已完成（check_idle_threads） |
| P3 | 数据清理定时任务（过期数据物理删除） | 0.5 天 | |

### 前端（独立工程，不在本项目范围内）

| 阶段 | 内容 | 说明 |
|------|------|------|
| F1 | 对接 v2 API | 调用 `/api/v1/token-stats/*` 接口 |
| F2 | Dashboard 页面 | 概览卡片、趋势图、模型分布、会话列表 |
| F3 | 会话详情页 | Token 时间线、事件日志、模型分布 |
| F4 | 实时轮询 | 活跃会话 5-10 秒轮询统计数据 |

## 10. 与现有系统的关系

| 现有组件 | 变更说明 |
|----------|----------|
| `tools/utils/token_counter.py` | 重构核心类，新增 `threads` / `token_records` / `thread_events` 表操作 |
| `tools/utils/dashboard.py` | 新增 `/api/v1/token-stats/*` 路由（`router_v2`），旧路由保留兼容 |
| `tools/utils/case_tools.py` | 保留兼容，v1 用例管理工具 |
| `tools/middleware/thread_context.py` | **新增**，ThreadContextMiddleware，自动注入 thread_id |
| `tools/core/agent_factory.py` | 添加 ThreadContextMiddleware 到中间件栈 |
| `tools/playwright/recording_agent.py` | 添加 ThreadContextMiddleware 到中间件栈 |
| `data/token_stats.db` | 新增 3 张表（SQLite，单机部署，无外部依赖），旧表保留 |
| `docs/token-dashboard-api.md` | 保留为旧版文档，新文档为本文件 |

> Dashboard 页面不在后端实现范围内，由前端工程独立开发，调用后端 v2 API。
