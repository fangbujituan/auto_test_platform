# TS-P1-001: v2 API 路由实现

## 任务概述

在 `dashboard.py` 中实现完整的 v2 API 路由（`/api/v1/token-stats/*`），覆盖设计文档 3.2-3.4 节的所有接口。

## 原始实现逻辑

### v1 路由（`/token-stats/*`）

- `POST /token-stats/cases` — 创建用例
- `GET /token-stats/cases` — 用例列表
- `GET /token-stats/cases/{case_id}` — 用例详情
- `PUT /token-stats/cases/{case_id}` — 更新用例名称
- `POST /token-stats/cases/{case_id}/complete` — 完成用例
- `GET /token-stats/cases/stats/overview` — 用例统计
- `GET /token-stats/overview` — 总体概览
- `GET /token-stats/trend` — 趋势数据
- `GET /token-stats/records` — 详细记录
- `GET /token-stats/cost` — 费用估算
- `GET /token-stats/dashboard` — Dashboard HTML

### 问题

- 以 `case_id` 为核心，不支持 `thread_id` 维度
- 无软删除/恢复接口
- 无事件日志接口
- 无错误率、延迟等指标

## 当前实现逻辑

### v2 路由（`/api/v1/token-stats/*`）

#### 会话管理（3.2 节）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/threads` | 创建或获取会话 |
| GET | `/threads` | 会话列表（支持筛选、排序、分页） |
| GET | `/threads/{thread_id}` | 会话详情（含 stats、model_breakdown） |
| PATCH | `/threads/{thread_id}` | 更新会话（name/status/note） |
| DELETE | `/threads/{thread_id}` | 软删除会话 |
| POST | `/threads/{thread_id}/restore` | 恢复已删除会话 |
| GET | `/threads/{thread_id}/records` | 会话 Token 明细 |
| GET | `/threads/{thread_id}/events` | 会话事件日志 |

#### 全局统计（3.4 节）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/overview` | 全局概览（summary + by_agent + by_model） |
| GET | `/trend` | 趋势数据（支持 hour/day 粒度） |
| GET | `/cost` | 费用报表（按模型细分） |
| GET | `/records` | 全局明细记录（支持多条件筛选） |

#### 管理接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/migrate` | 执行 v1→v2 数据迁移 |
| POST | `/check-idle` | 检查超时中断会话 |

### 请求/响应模型

使用 Pydantic BaseModel：
- `ThreadCreateRequest`: thread_id, agent_name, name
- `ThreadUpdateRequest`: name?, status?, note?

### 统一响应格式

```json
{
  "success": true,
  "data": { ... }
}
```

### v1 路由保留

所有 v1 路由（`/token-stats/*`）保留不变，继续基于 `token_usage` + `case_usage` 表。

## 主要修复点

| 修复点 | 说明 |
|--------|------|
| 双路由并行 | v1 (`router`) 和 v2 (`router_v2`) 独立运行 |
| thread_id 为核心 | 所有 v2 接口以 thread_id 为主键 |
| 软删除/恢复 | DELETE + restore 接口 |
| 事件日志 | events 接口返回完整生命周期事件 |
| 全局统计增强 | overview 包含 by_agent、by_model、error_rate 等 |
| 数据迁移接口 | /migrate 一键迁移旧数据 |
| 中断检测接口 | /check-idle 标记超时会话 |

## 涉及文件

- `tools/utils/dashboard.py` — 新增 `router_v2` 和所有 v2 路由
