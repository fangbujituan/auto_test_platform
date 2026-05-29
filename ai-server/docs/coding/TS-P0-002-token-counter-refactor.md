# TS-P0-002: TokenCounter 核心重构（thread_id 为核心）

## 任务概述

重构 `TokenCounter` 类，以 `thread_id` 为核心维度，新增 ContextVar 传递、自动创建 thread、v2 CRUD 方法、全局统计方法。

## 原始实现逻辑

### ContextVar

- 仅有 `_current_agent` 和 `_current_case_id` 两个 ContextVar
- 无 `thread_id` 的自动传递机制

### record() 方法

- 仅写入 `token_usage` 表
- 仅更新 `case_usage` 聚合字段
- 无 `latency_ms`、`is_error` 参数

### 费率配置

- 仅包含 deepseek、zhipu、scnet 三个提供商
- 不支持 aiop、kiro、aiclient 三网关

### 统计方法

- `get_overview()`、`get_trend()`、`get_records()`、`get_cost()` 均基于 `token_usage` 表
- 无 thread 维度的统计

## 当前实现逻辑

### 新增 ContextVar

```python
_current_thread_id: ContextVar[Optional[str]] = ContextVar("current_thread_id", default=None)
set_current_thread_id(thread_id: str)
get_current_thread_id() -> Optional[str]
```

### record() 方法增强

- 新增参数：`thread_id`、`latency_ms`、`is_error`、`error_message`
- 双写机制：同时写入 v1 `token_usage` 和 v2 `token_records`
- 自动获取 `thread_id`（从 ContextVar）
- 自动调用 `_ensure_thread()` 创建 thread 记录
- 更新 `threads` 表聚合字段（total_tokens、message_count、error_count 等）

### 费率配置扩展

新增三网关费率：
- `aiop`: azure/gpt-5.4, openai/gpt-4
- `kiro`: claude-sonnet-4.5, claude-sonnet-4-6, deepseek-3.2
- `aiclient`: claude-sonnet-4-6（免费 OAuth）, gemini-2.5-flash（免费）

### 新增 v2 方法

| 方法 | 说明 |
|------|------|
| `_ensure_thread()` | 自动创建 thread 记录（如不存在） |
| `_record_event()` | 记录会话事件到 thread_events |
| `check_idle_threads()` | 检查超时中断的会话 |
| `get_thread()` | 获取会话详情（含 stats、model_breakdown） |
| `get_thread_records()` | 获取会话的 token 明细记录 |
| `get_thread_events()` | 获取会话事件日志 |
| `create_or_get_thread()` | 创建或获取会话（前端调用） |
| `update_thread()` | 更新会话信息（name/status/note） |
| `delete_thread()` | 软删除会话 |
| `restore_thread()` | 恢复已删除会话 |
| `get_threads()` | 获取会话列表（支持筛选、排序、分页） |
| `get_global_overview()` | 全局概览统计（基于 token_records） |
| `get_global_trend()` | 全局趋势数据 |
| `get_global_cost()` | 全局费用报表 |
| `get_global_records()` | 全局明细记录 |
| `_calculate_thread_cost()` | 计算单个会话费用 |
| `_calculate_cost_v2()` | 计算全局费用（v2） |

### 向后兼容

- 保留所有 v1 方法：`create_case()`、`get_case()`、`get_cases()`、`complete_case()` 等
- v1 方法标记为兼容层，继续基于 `token_usage` + `case_usage` 表
- `record()` 双写确保 v1 和 v2 数据同步

## 主要修复点

| 修复点 | 说明 |
|--------|------|
| thread_id ContextVar | 新增 `_current_thread_id`，支持请求链路自动传递 |
| record() 双写 | 同时写入 v1 旧表和 v2 新表，确保兼容 |
| _ensure_thread() | 自动创建 thread 记录 + created 事件 |
| 三网关费率 | RATE_CONFIG 扩展支持 aiop/kiro/aiclient |
| 全局统计 v2 | 基于 token_records 的全新统计方法 |
| 会话 CRUD | 完整的 thread 增删改查 + 软删除/恢复 |
| 中断检测 | check_idle_threads() 标记超时会话 |

## 涉及文件

- `tools/utils/token_counter.py` — TokenCounter 类全面重构
