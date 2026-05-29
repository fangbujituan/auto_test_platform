# TS-P0-003: TokenCallbackHandler 重构

## 任务概述

增强 `TokenCallbackHandler`，新增 `on_llm_start`（记录开始时间）、`on_llm_error`（捕获错误）回调，支持 `latency_ms` 延迟追踪。

## 原始实现逻辑

### TokenCallbackHandler

- 仅实现 `on_llm_end` 回调
- 无 `on_llm_start`，无法计算 LLM 响应延迟
- 无 `on_llm_error`，LLM 调用失败时无记录
- `_infer_provider()` 仅支持 deepseek、zhipu、scnet

### 问题

- 无法追踪 LLM 响应延迟（latency_ms）
- LLM 调用失败时无任何记录，丢失错误信息
- 无法统计错误率
- 模型提供商推断不完整

## 当前实现逻辑

### on_llm_start（新增）

```python
def on_llm_start(self, serialized, prompts, *, run_id, **kwargs):
    self._start_times[str(run_id)] = time.monotonic()
```

- 使用 `time.monotonic()` 记录开始时间（不受系统时钟调整影响）
- 以 `run_id` 为 key 存储到 `_start_times` 字典

### on_llm_end（增强）

- 从 `_start_times` 中取出开始时间，计算 `latency_ms`
- 将 `latency_ms` 传递给 `counter.record()`
- 其余逻辑不变

### on_llm_error（新增）

```python
def on_llm_error(self, error, *, run_id, **kwargs):
```

当 LLM 调用失败时：
1. 清理 `_start_times` 中的开始时间，计算 latency_ms
2. 获取当前 `thread_id`（从 ContextVar）
3. 更新 `threads` 表的 `error_count`
4. 记录 `llm_error` 事件到 `thread_events`
5. 记录错误的 `token_record`（`is_error=1`）
6. 错误信息截断到 500 字符

### _infer_provider（增强）

新增模型提供商推断规则：
- `claude` → `kiro`
- `gpt` → `aiop`
- `gemini` → `aiclient`

## 主要修复点

| 修复点 | 说明 |
|--------|------|
| latency_ms 追踪 | on_llm_start 记录开始时间，on_llm_end 计算延迟 |
| 错误捕获 | on_llm_error 记录错误到 threads + thread_events + token_records |
| _start_times 清理 | on_llm_end 和 on_llm_error 都会清理 _start_times，防止内存泄漏 |
| 提供商推断增强 | 支持 claude→kiro、gpt→aiop、gemini→aiclient |
| time.monotonic | 使用单调时钟，不受系统时间调整影响 |

## 涉及文件

- `tools/utils/token_counter.py` — TokenCallbackHandler 类
