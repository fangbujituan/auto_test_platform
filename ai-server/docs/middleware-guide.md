# LangChain Agent Middleware 开发指南

> 本文档基于实际开发经验总结，记录 SubAgent 与 Middleware 的关系、DOM 清理中间件开发心得。

## 一、架构概览

### 1.1 SubAgent 与 Middleware 层级关系

```
┌─────────────────────────────────────────────────────────────┐
│                      Main Agent                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Main Agent Middleware Stack                            ││
│  │  [BeforeAgentMiddleware, DOMCleanerMiddleware, ...]    ││
│  │                          │                               ││
│  │                          ▼                               ││
│  │  ┌─────────────────────────────────────────────────┐    ││
│  │  │              ToolNode                            │    ││
│  │  │  - 工具调用在这里发生                             │    ││
│  │  │  - awrap_tool_call 在这里被触发                   │    ││
│  │  └─────────────────────────────────────────────────┘    ││
│  └─────────────────────────────────────────────────────────┘│
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  SubAgentMiddleware                                     ││
│  │  - 提供 `task` 工具                                     ││
│  │  - 管理所有 subagents                                   ││
│  └─────────────────────────────────────────────────────────┘│
│                          │                                   │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  SubAgent (general-purpose)                             ││
│  │  ┌───────────────────────────────────────────────────┐  ││
│  │  │  SubAgent Middleware Stack                        │  ││
│  │  │  [TodoListMiddleware, FilesystemMiddleware, ...]  │  ││
│  │  └───────────────────────────────────────────────────┘  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### 1.2 关键发现

**工具调用发生位置**：

`deepagents` 的 `create_deep_agent` 会将工具传给**主 agent**，主 agent 可以直接调用工具，**不需要**通过 `task` 工具委托给 subagent。

```python
# deepagents/graph.py
return create_agent(
    model,
    tools=tools,  # ⚠️ 主 agent 直接拥有工具！
    middleware=deepagent_middleware,
)
```

**结论**：如果需要在工具调用时执行自定义逻辑，middleware 必须添加到**主 agent** 的 middleware stack 中。

## 二、Middleware 开发指南

### 2.1 AgentMiddleware 基类

```python
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ToolCallRequest

class MyMiddleware(AgentMiddleware):
    """自定义中间件示例"""
    
    @property
    def name(self) -> str:
        return "my_middleware"
    
    # 工具调用拦截（异步）
    async def awrap_tool_call(self, request: ToolCallRequest, handler):
        """拦截工具执行，可在执行前后添加自定义逻辑"""
        # 执行前
        tool_name = request.tool_call.get("name", "unknown")
        print(f"工具调用: {tool_name}")
        
        # 执行工具
        result = await handler(request)
        
        # 执行后 - 可修改结果
        return result
    
    # 模型调用拦截
    async def awrap_model_call(self, request, handler):
        """拦截模型调用"""
        return await handler(request)
    
    # 模型调用前
    async def abefore_model(self, state, runtime):
        """模型调用前的钩子"""
        return None
    
    # 模型调用后
    async def aafter_model(self, state, runtime):
        """模型调用后的钩子"""
        return None
```

### 2.2 可用的钩子方法

| 方法 | 用途 | 执行时机 |
|------|------|----------|
| `awrap_tool_call` | 拦截工具执行 | 工具调用时 |
| `wrap_tool_call` | 同步版本 | 工具调用时 |
| `awrap_model_call` | 拦截模型调用 | 模型调用时 |
| `abefore_model` | 模型调用前钩子 | 模型调用前 |
| `aafter_model` | 模型调用后钩子 | 模型调用后 |
| `abefore_agent` | Agent 执行前钩子 | Agent 启动时 |
| `aafter_agent` | Agent 执行后钩子 | Agent 结束时 |

### 2.3 ToolCallRequest 结构

```python
@dataclass
class ToolCallRequest:
    tool_call: ToolCall  # {'name': str, 'args': dict, 'id': str}
    tool: BaseTool | None  # 工具实例
    state: Any  # Agent 状态
    runtime: ToolRuntime  # 运行时上下文
```

### 2.4 正确配置 Middleware

```python
# ✅ 正确：添加到主 agent 的 middleware
middleware = [
    BeforeAgentMiddleware(),
    DOMCleanerMiddleware(),  # 工具调用拦截
    SummarizationMiddleware(...),
]

agent = create_deep_agent(
    tools=all_tools,
    system_prompt=SYSTEM_PROMPT,
    model=model,
    middleware=middleware,  # 主 agent 的 middleware
)

# ❌ 错误：仅配置在 subagent 中
# 工具调用发生在主 agent 层面，subagent 的 middleware 不会被触发
```

## 三、DOM 清理中间件实战

### 3.1 问题背景

Playwright MCP 返回的 YAML 格式 Snapshot 包含大量冗余信息：
- `### Ran Playwright code` 代码块
- `### Events` 控制台日志
- `[cursor=pointer]` 鼠标样式
- `[active]` 激活状态

这些信息消耗大量 token，需要清理。

### 3.2 清理规则

#### 必须保留的属性

| 属性 | 说明 |
|------|------|
| `[ref=ex]` | **Playwright 定位元素必需**，如 `[ref=e7]` 对应 `ref=e7` |
| 元素类型 | `textbox`, `button`, `generic` 等 |
| 元素文本 | `"Username:"`, `"Sign in"` 等 |

#### 可以移除的内容

| 内容 | 说明 |
|------|------|
| `### Ran Playwright code` | 执行代码记录，无信息价值 |
| `### Events` | 控制台日志，通常无用 |
| `[cursor=xxx]` | 鼠标样式，仅视觉提示 |
| `[active]` | 激活状态标记 |
| `/url:` 链接 | 可选移除 |

### 3.3 清理效果示例

**清理前：**
```yaml
### Ran Playwright code
```js
await page.goto('https://bnp-test.item.pub/');
```
### Page
- Page URL: https://bnp-test.item.pub/
- Page Title: Login Form
### Snapshot
```yaml
- generic [ref=e1]:
  - img [ref=e3]
  - group [ref=e5]:
    - generic [ref=e6] [cursor=pointer]: "Username:"
    - textbox [ref=e7]
    - generic [ref=e8] [cursor=pointer]: "Password:"
    - textbox [ref=e9]
  - contentinfo [ref=e10]:
    - button "Sign in" [ref=e12] [cursor=pointer]
    - generic [ref=e13]: Forgot Password
```
### Events
- [LOG] undefined @ https://bnp-test.item.pub/:260
- [VERBOSE] [DOM] Password field is not contained in...
```

**清理后：**
```yaml
### Page
- Page URL: https://bnp-test.item.pub/
- Page Title: Login Form
### Snapshot
```yaml
- generic [ref=e1]:
  - img [ref=e3]
  - group [ref=e5]:
    - generic [ref=e6]: "Username:"
    - textbox [ref=e7]
    - generic [ref=e8]: "Password:"
    - textbox [ref=e9]
  - contentinfo [ref=e10]:
    - button "Sign in" [ref=e12]
    - generic [ref=e13]: Forgot Password
```
```

**压缩率**：约 30-50%

### 3.4 核心代码

```python
# tools/utils.py
def clean_playwright_snapshot(content: str) -> str:
    """清理 Playwright Snapshot，减少 token 消耗"""
    
    # 1. 移除 "### Ran Playwright code" 代码块
    result = re.sub(
        r'### Ran Playwright code\s*```js.*?```\s*',
        '', content, flags=re.DOTALL
    )
    
    # 2. 移除 "### Events" 部分
    result = re.sub(
        r'### Events\s*\n.*?(?=###|$)',
        '', result, flags=re.DOTALL
    )
    
    # 3. 【保留】ref 属性 - Playwright 操作必需！
    # 不要执行: result = re.sub(r'\s*\[ref=[\w\d_]+\]', '', result)
    
    # 4. 移除 cursor/active
    result = re.sub(r'\s*\[cursor=[\w]+\]', '', result)
    result = re.sub(r'\s*\[active\]', '', result)
    
    # 5. 清理空行
    result = re.sub(r'\n{3,}', '\n\n', result)
    
    return result.strip()
```

```python
# tools/dom_cleaner.py
class DOMCleanerMiddleware(AgentMiddleware):
    """DOM 清理中间件"""
    
    async def awrap_tool_call(self, request, handler):
        result = await handler(request)
        return self._clean_result(result)
    
    def _clean_result(self, result):
        """处理 ToolMessage.content 为列表的情况"""
        if isinstance(result, ToolMessage):
            content = result.content
            if isinstance(content, list):
                # Playwright MCP 返回: [{'type': 'text', 'text': '...'}]
                cleaned = []
                for item in content:
                    if isinstance(item, dict) and 'text' in item:
                        cleaned.append({
                            **item,
                            'text': clean_playwright_snapshot(item['text'])
                        })
                    else:
                        cleaned.append(item)
                return ToolMessage(
                    content=cleaned,
                    name=result.name,
                    tool_call_id=result.tool_call_id,
                )
        return result
```

## 四、问题诊断流程

### 4.1 Middleware 不生效检查清单

```
问题：awrap_tool_call 不被调用
        │
        ▼
┌───────────────────────────────────────┐
│ 1. 检查 middleware 是否被正确初始化     │
│    日志：[XXXMiddleware] 初始化完成     │
└───────────────────────────────────────┘
        │ ✅ 已初始化
        ▼
┌───────────────────────────────────────┐
│ 2. 检查 middleware 被添加到哪个 agent   │
│    - 主 agent? ← 正确位置              │
│    - subagent? ← 可能无效              │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 3. 确认工具调用流程                     │
│    主 agent → ToolNode → middleware    │
└───────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│ 4. 检查结果格式处理                     │
│    ToolMessage.content 可能是列表       │
└───────────────────────────────────────┘
```

### 4.2 调试技巧

```python
class DebugMiddleware(AgentMiddleware):
    async def awrap_tool_call(self, request, handler):
        # 调试信息
        print(f"[Debug] 工具名称: {request.tool_call.get('name')}")
        print(f"[Debug] 工具 ID: {request.tool_call.get('id')}")
        
        result = await handler(request)
        
        print(f"[Debug] 结果类型: {type(result).__name__}")
        if isinstance(result, ToolMessage):
            print(f"[Debug] content 类型: {type(result.content).__name__}")
        
        return result
```

## 五、最佳实践

### 5.1 DO ✅

- 将需要拦截工具调用的 middleware 添加到**主 agent**
- 保留 `[ref=ex]` 元素引用，这是 Playwright 定位的基础
- 处理 `ToolMessage.content` 可能是列表格式的情况
- 添加调试日志便于问题排查

### 5.2 DON'T ❌

- 不要移除 `[ref=ex]` 属性
- 不要在类方法上使用 `@wrap_tool_call` 装饰器（仅适用于独立函数）
- 不要假设工具返回结果一定是字符串
- 不要只配置 subagent 的 middleware 而忽略主 agent

## 六、参考资料

- [LangChain Agents 文档](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain Middleware 文档](https://docs.langchain.com/oss/python/langchain/middleware)
- [deepagents SubAgents 文档](https://docs.langchain.com/oss/python/deepagents/subagents)
- [Playwright MCP](https://github.com/microsoft/playwright-mcp)

---

*文档版本：2026-03-13*
*基于实际开发经验总结*
