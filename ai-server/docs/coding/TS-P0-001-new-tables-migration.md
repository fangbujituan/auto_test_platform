# TS-P0-001: 新建数据库表 + 数据迁移

## 任务概述

在 `token_counter.py` 中新增 3 张 v2 数据库表（`threads`、`token_records`、`thread_events`），并实现从 v1 旧表到 v2 新表的数据迁移脚本。

## 原始实现逻辑

### 旧表结构

1. **`token_usage`** — 每次 LLM 调用的 token 记录
   - 以自增 `id` 为主键
   - `case_id` 为可选外键，关联到 `case_usage`
   - 无 `latency_ms`、`is_error` 等字段

2. **`case_usage`** — 用例表
   - 以自生成 UUID `id` 为主键
   - `thread_id` 仅作为可选字段存储，非主键
   - 无 `is_deleted`、`error_count`、`interrupt_count` 等字段

### 问题

- 前端以 `thread_id` 为维度管理会话，但后端以 `case_id` 为主键
- 缺少会话生命周期追踪（中断、错误、事件日志）
- 缺少 LLM 调用延迟、错误记录等关键指标

## 当前实现逻辑

### 新增 3 张表

1. **`threads`** — 会话主表
   - 以 LangGraph `thread_id` 为主键（TEXT PRIMARY KEY）
   - 包含生命周期字段：`status`（active/completed/failed/interrupted）、`created_at`、`updated_at`、`completed_at`
   - 包含聚合统计冗余字段：`total_tokens`、`input_tokens`、`output_tokens`、`message_count`、`error_count`、`interrupt_count`
   - 支持软删除：`is_deleted`、`deleted_at`
   - 索引：status、created_at、agent_name、is_deleted

2. **`token_records`** — LLM 调用明细记录
   - 自增 `id` 主键，`thread_id` 外键关联 `threads`
   - 新增 `is_error`（0/1）、`error_message`、`latency_ms` 字段
   - 索引：thread_id、timestamp、model_provider、agent_name

3. **`thread_events`** — 事件日志
   - 记录会话生命周期中的关键事件
   - `event_type`：created、llm_call、llm_error、interrupted、resumed、completed、failed、deleted、restored、renamed、timeout
   - `detail`：JSON 格式的事件详情
   - 索引：thread_id、event_type、timestamp

### 迁移脚本 `migrate_v1_to_v2()`

- `case_usage` → `threads`：使用 `COALESCE(thread_id, id)` 作为新主键
- `token_usage` → `token_records`：使用 `COALESCE(case_id, 'orphan_' || id)` 关联 thread
- 为无 case 的 token_usage 记录创建 orphan thread
- 旧表保留不删除，作为备份

### `_init_db()` 变更

- 保留 v1 旧表创建语句（向后兼容）
- 新增 v2 三张表的 `CREATE TABLE IF NOT EXISTS`
- 新增 11 个 v2 索引

## 主要修复点

| 修复点 | 说明 |
|--------|------|
| thread_id 为主键 | 从 UUID case_id 切换到 LangGraph thread_id 作为核心维度 |
| 聚合字段冗余 | threads 表包含 total_tokens 等冗余字段，避免每次查询 SUM |
| 软删除机制 | is_deleted + deleted_at，删除后统计数据保留 |
| 事件日志 | thread_events 表记录完整生命周期事件 |
| 错误/延迟追踪 | token_records 新增 is_error、error_message、latency_ms |
| 数据迁移 | migrate_v1_to_v2() 支持从旧表无损迁移到新表 |
| 向后兼容 | 旧表 token_usage、case_usage 保留，v1 API 继续可用 |

## 涉及文件

- `tools/utils/token_counter.py` — `_init_db()` 方法、`migrate_v1_to_v2()` 方法
