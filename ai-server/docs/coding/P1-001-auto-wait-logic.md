# P1-001: 操作后自动插入等待逻辑

## 概述

在生成的 Playwright 脚本中自动插入等待逻辑，解决慢网络环境下脚本回放超时失败的问题。

## 修改文件

- `tools/middleware/code_collector.py`

## 原来实现逻辑

- `browser_navigate` 生成 `page.goto(url)` 后没有任何等待
- `browser_click` 后没有等待，即使是提交按钮（Save、Confirm 等）
- 脚本回放时在慢网络（20-30s）下容易因页面未加载完成而超时失败

## 当前实现逻辑

### 1. 导航后自动等待

```typescript
// 之前
await page.goto('https://example.com');

// 现在
await page.goto('https://example.com');
await page.waitForLoadState('networkidle');
```

### 2. 提交类按钮点击后自动等待

通过 `_is_submit_like_button()` 检测按钮描述文本中的关键词：

- 英文: submit, save, confirm, ok, yes, apply, create, add, delete, remove, update, send, login, sign in, register
- 中文: 提交, 保存, 确认, 确定, 删除, 新增, 添加, 登录, 注册, 发送, 应用, 创建, 更新

```typescript
// 之前
await page.getByRole('button', { name: 'Save Item' }).click();

// 现在
await page.getByRole('button', { name: 'Save Item' }).click();
await page.waitForLoadState('networkidle');  // 等待提交完成
```

### 3. 操作跟踪

新增 `_last_tool_name` 实例变量，跟踪上一次工具调用名称，为后续更复杂的等待策略（如检测页面跳转）提供基础。

## 主要修复点

1. `_generate_code_from_tool_call` 中 `browser_navigate` 分支：添加 `waitForLoadState('networkidle')`
2. `_generate_code_from_tool_call` 中 `browser_click` 分支末尾：检测提交类按钮并添加等待
3. 新增 `_is_submit_like_button()` 方法：基于关键词匹配判断按钮类型
4. `__init__` 和 `reset` 中新增 `_last_tool_name` 跟踪变量

## 预期效果

- 超时错误减少约 75%（从 ~7 次降到 ~2 次）
- 脚本回放稳定性在慢网络环境下显著提升
