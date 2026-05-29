# Token 消耗统计 API 文档

## 概述

Token 统计系统用于记录和展示 AI 模型的 token 消耗情况，支持按日期、模型、Agent、用例维度进行统计分析。

## 数据模型

### TokenUsage 记录结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | int | 自增主键 |
| `timestamp` | datetime | 记录时间 |
| `model_provider` | string | 模型提供商（deepseek/scnet/zhipu） |
| `model_name` | string | 模型名称（如 deepseek-chat） |
| `agent_name` | string | Agent 名称（agent/recording_agent/web_agent） |
| `input_tokens` | int | 输入 token 数 |
| `output_tokens` | int | 输出 token 数 |
| `total_tokens` | int | 总 token 数 |
| `request_id` | string | 请求 ID（可选，用于追踪） |
| `case_id` | string | 所属用例 ID（关联 case_usage 表） |

### CaseUsage 用例结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | string | 用例 ID（UUID） |
| `name` | string | 用例名称（如"登录测试_20260320_1430"） |
| `agent_name` | string | Agent 名称 |
| `thread_id` | string | LangGraph thread ID |
| `status` | string | 状态：`active`/`completed`/`failed` |
| `start_time` | datetime | 开始时间 |
| `end_time` | datetime | 结束时间（可选） |
| `total_tokens` | int | 总 token 消耗 |
| `input_tokens` | int | 总输入 token |
| `output_tokens` | int | 总输出 token |
| `message_count` | int | 消息轮次 |
| `estimated_cost_cny` | float | 预估费用（元） |

---

## API 接口

### 1. 获取统计概览

**GET** `/token-stats/overview`

获取 token 消耗的总体统计信息。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `period` | string | 否 | 统计周期：`today`/`week`/`month`/`all`，默认 `today` |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "period": "today",
    "summary": {
      "total_tokens": 125430,
      "input_tokens": 85200,
      "output_tokens": 40230,
      "request_count": 156,
      "estimated_cost_cny": 1.25,
      "case_count": 12,
      "completed_cases": 10,
      "success_rate": 83.3
    },
    "by_provider": [
      {
        "provider": "deepseek",
        "total_tokens": 100000,
        "input_tokens": 68000,
        "output_tokens": 32000,
        "request_count": 120,
        "percentage": 79.7
      }
    ],
    "by_agent": [
      {
        "agent": "recording_agent",
        "total_tokens": 80000,
        "input_tokens": 55000,
        "output_tokens": 25000,
        "request_count": 100,
        "percentage": 63.8
      }
    ],
    "case_stats": {
      "total_cases": 12,
      "completed_cases": 10,
      "failed_cases": 2,
      "success_rate": 83.3,
      "avg_tokens_per_case": 10452.5,
      "max_tokens_case": {
        "id": "abc123",
        "name": "批量导入测试_20260320_1430",
        "total_tokens": 45000
      }
    }
  }
}
```

---

### 2. 获取趋势数据

**GET** `/token-stats/trend`

获取指定时间范围内的 token 消耗趋势。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `days` | int | 否 | 查询天数，默认 7 天 |
| `granularity` | string | 否 | 粒度：`hour`/`day`，默认 `day` |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "granularity": "day",
    "trend": [
      {
        "date": "2026-03-14",
        "total_tokens": 89500,
        "input_tokens": 62000,
        "output_tokens": 27500,
        "request_count": 98,
        "case_count": 8
      },
      {
        "date": "2026-03-15",
        "total_tokens": 102300,
        "input_tokens": 71000,
        "output_tokens": 31300,
        "request_count": 112,
        "case_count": 10
      }
    ]
  }
}
```

---

### 3. 获取详细记录

**GET** `/token-stats/records`

获取 token 消耗的详细记录列表。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `date` | string | 否 | 日期筛选（YYYY-MM-DD） |
| `provider` | string | 否 | 模型提供商筛选 |
| `agent` | string | 否 | Agent 筛选 |
| `case_id` | string | 否 | 用例 ID 筛选 |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20，最大 100 |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "total": 156,
    "page": 1,
    "page_size": 20,
    "records": [
      {
        "id": 1234,
        "timestamp": "2026-03-17T14:32:15",
        "model_provider": "deepseek",
        "model_name": "deepseek-chat",
        "agent_name": "recording_agent",
        "input_tokens": 1250,
        "output_tokens": 480,
        "total_tokens": 1730,
        "case_id": "abc123",
        "case_name": "登录测试_20260320_1430"
      }
    ]
  }
}
```

---

### 4. 获取费用估算

**GET** `/token-stats/cost`

获取 token 消耗的费用估算。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `period` | string | 否 | 统计周期：`today`/`week`/`month`/`all`，默认 `month` |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "period": "month",
    "currency": "CNY",
    "breakdown": [
      {
        "provider": "deepseek",
        "model": "deepseek-chat",
        "input_tokens": 1500000,
        "output_tokens": 500000,
        "input_rate": 0.001,
        "output_rate": 0.002,
        "input_cost": 1.50,
        "output_cost": 1.00,
        "total_cost": 2.50
      }
    ],
    "total_cost": 2.50,
    "saved_hours": 24.5,
    "saved_cost_cny": 2450.0
  }
}
```

---

### 5. 用例管理 API

#### 5.1 创建用例

**POST** `/token-stats/cases`

创建一个新的用例记录。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 用例名称，如未指定将自动生成"未命名_时间戳"格式 |
| `agent` | string | 否 | Agent 名称，默认 `unknown` |
| `thread_id` | string | 否 | LangGraph thread ID |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "case_id": "uuid-xxx-xxx",
    "name": "登录测试_20260320_1430",
    "status": "active",
    "start_time": "2026-03-20T14:30:00",
    "message": "用例创建成功"
  }
}
```

---

#### 5.2 获取当前用例统计

**GET** `/token-stats/cases/current`

获取当前活跃用例的实时统计（供 AI 返回给用户）。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `case_id` | string | 是 | 用例 ID |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "case_id": "uuid-xxx-xxx",
    "name": "登录测试_20260320_1430",
    "status": "active",
    "duration_seconds": 180,
    "message_count": 5,
    "current_message_tokens": 1250,
    "case_total_tokens": 8750,
    "case_input_tokens": 6200,
    "case_output_tokens": 2550,
    "estimated_cost_cny": 0.0088,
    "summary": "📊 本次消耗: 1,250 tokens\n📋 用例总计: 8,750 tokens\n💰 预估费用: ¥0.009"
  }
}
```

---

#### 5.3 完成用例

**POST** `/token-stats/cases/{case_id}/complete`

标记用例为完成状态，并返回统计摘要。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 最终状态：`completed`/`failed`，默认 `completed` |
| `note` | string | 否 | 完成备注 |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "case_id": "uuid-xxx-xxx",
    "name": "登录测试_20260320_1430",
    "status": "completed",
    "start_time": "2026-03-20T14:30:00",
    "end_time": "2026-03-20T14:35:30",
    "duration_seconds": 330,
    "message_count": 8,
    "total_tokens": 12500,
    "input_tokens": 8500,
    "output_tokens": 4000,
    "estimated_cost_cny": 0.0125,
    "summary": "✅ 用例完成\n📊 总消耗: 12,500 tokens\n⏱️ 耗时: 5分30秒\n💰 费用: ¥0.013\n🔄 对话轮次: 8"
  }
}
```

---

#### 5.4 获取用例列表

**GET** `/token-stats/cases`

获取用例列表，支持筛选和排序。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 状态筛选：`active`/`completed`/`failed` |
| `agent` | string | 否 | Agent 筛选 |
| `date` | string | 否 | 日期筛选（YYYY-MM-DD） |
| `sort_by` | string | 否 | 排序字段：`tokens`/`time`/`date`，默认 `date` |
| `order` | string | 否 | 排序方向：`asc`/`desc`，默认 `desc` |
| `page` | int | 否 | 页码 |
| `page_size` | int | 否 | 每页条数 |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "total": 45,
    "page": 1,
    "page_size": 20,
    "cases": [
      {
        "id": "uuid-xxx-xxx",
        "name": "登录测试_20260320_1430",
        "agent_name": "recording_agent",
        "status": "completed",
        "start_time": "2026-03-20T14:30:00",
        "end_time": "2026-03-20T14:35:30",
        "duration_seconds": 330,
        "total_tokens": 12500,
        "message_count": 8,
        "estimated_cost_cny": 0.0125
      }
    ]
  }
}
```

---

#### 5.5 获取用例详情

**GET** `/token-stats/cases/{case_id}`

获取单个用例的详细信息，包括所有 token 记录。

#### 返回示例

```json
{
  "success": true,
  "data": {
    "id": "uuid-xxx-xxx",
    "name": "登录测试_20260320_1430",
    "agent_name": "recording_agent",
    "thread_id": "thread_abc123",
    "status": "completed",
    "start_time": "2026-03-20T14:30:00",
    "end_time": "2026-03-20T14:35:30",
    "duration_seconds": 330,
    "total_tokens": 12500,
    "input_tokens": 8500,
    "output_tokens": 4000,
    "message_count": 8,
    "estimated_cost_cny": 0.0125,
    "records": [
      {
        "timestamp": "2026-03-20T14:30:15",
        "model_provider": "deepseek",
        "input_tokens": 1500,
        "output_tokens": 400,
        "total_tokens": 1900
      }
    ]
  }
}
```

---

#### 5.6 更新用例名称

**PUT** `/token-stats/cases/{case_id}`

更新用例名称。

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | 新用例名称 |

#### 返回示例

```json
{
  "success": true,
  "data": {
    "case_id": "uuid-xxx-xxx",
    "name": "批量导入测试_20260320_1430",
    "message": "用例名称更新成功"
  }
}
```

---

## 费率配置

默认费率（元/千 tokens）：

| 提供商 | 模型 | 输入费率 | 输出费率 |
|--------|------|----------|----------|
| deepseek | deepseek-chat | 0.001 | 0.002 |
| zhipu | glm-4-flash | 0.0001 | 0.0001 |
| zhipu | glm-4 | 0.1 | 0.1 |
| scnet | Qwen3-30B-A3B | 0 | 0（免费） |

> 注：费率可通过环境变量或配置文件自定义

---

## 数据存储

- **存储位置**：`data/token_stats.db`（SQLite）
- **表名**：`token_usage`、`case_usage`
- **保留策略**：默认保留 90 天，可通过配置调整

---

## AI 回复中的 Token 统计格式

当用户需要查看 token 消耗时，AI 应在回复末尾追加统计信息：

### 单次对话格式

```
任务完成！

📊 本次消耗: 1,250 tokens
📋 用例总计: 8,750 tokens
💰 预估费用: ¥0.009
```

### 用例完成格式

```
✅ 用例完成

📊 总消耗: 12,500 tokens
⏱️ 耗时: 5分30秒
💰 费用: ¥0.013
🔄 对话轮次: 8
📈 平均每轮: 1,562 tokens
```

---

## 前端集成建议

### Dashboard 页面结构

```
┌─────────────────────────────────────────────────────────────────┐
│  Token 消耗统计                                    2026年3月    │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │ 今日消耗    │  │ 本月消耗    │  │ 预估费用    │  │ 完成用例│ │
│  │ 125,430     │  │ 2,345,678   │  │ ¥2.50       │  │ 12/15   │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────┘ │
├─────────────────────────────────────────────────────────────────┤
│  用例统计                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ 成功率      │  │ 平均消耗    │  │ 最大消耗    │             │
│  │ 83.3%       │  │ 10,452 tok  │  │ 45,000 tok  │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│  消耗趋势（近7天）                                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │     📊 柱状图/折线图                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────┤
│  用例列表                                        [查看更多]     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ 名称              │ 状态    │ Tokens   │ 耗时    │ 费用  │   │
│  │ 登录测试          │ ✅完成  │ 12,500   │ 5分30秒 │ ¥0.01 │   │
│  │ 批量导入          │ 🔄进行中│ 8,750    │ 3分15秒 │ ¥0.01 │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 推荐技术栈

- **图表库**：ECharts / Chart.js
- **UI 框架**：Vue 3 / React
- **HTTP 客户端**：axios / fetch

---

## 错误响应

所有接口统一错误格式：

```json
{
  "success": false,
  "error": {
    "code": "INVALID_PARAMETER",
    "message": "参数 period 必须是 today/week/month/all 之一"
  }
}
```

### 错误码

| 错误码 | 说明 |
|--------|------|
| `INVALID_PARAMETER` | 参数无效 |
| `CASE_NOT_FOUND` | 用例不存在 |
| `DATABASE_ERROR` | 数据库错误 |
| `INTERNAL_ERROR` | 内部错误 |

---

## Agent 工具

为方便 Agent 调用，提供了 LangChain 工具封装（`tools/utils/case_tools.py`）。

### 可用工具

| 工具名 | 说明 |
|--------|------|
| `case_create` | 创建新用例 |
| `case_get_stats` | 获取当前用例统计 |
| `case_complete` | 完成用例 |
| `case_rename` | 重命名用例 |
| `case_list` | 获取用例列表 |

### 使用示例

```python
from tools.utils.case_tools import CASE_TOOLS

# 在 Agent 中注册工具
agent = create_deep_agent(
    model=model,
    tools=CASE_TOOLS,
    system_prompt=prompt
)
```

### 工具调用流程

1. **任务开始**：调用 `case_create` 创建用例
2. **对话进行中**：每次 AI 回复后调用 `case_get_stats` 获取统计，追加到回复末尾
3. **用户说"完成"**：调用 `case_complete` 完成用例
4. **需要重命名**：调用 `case_rename` 更新用例名称

### 统计信息格式

`case_get_stats` 返回的 `summary` 字段可直接追加到 AI 回复末尾：

```
📊 本次消耗: 1,250 tokens
📋 用例总计: 8,750 tokens
💰 预估费用: ¥0.009
```

`case_complete` 返回的 `summary` 字段：

```
✅ 用例完成
📊 总消耗: 12,500 tokens
⏱️ 耗时: 5分30秒
💰 费用: ¥0.013
🔄 对话轮次: 8
```