# AI-Server 整合方案

## 一、项目现状分析

### 1.1 主项目结构
```
app/
├── agents/              # 已有基础 Agent 框架
│   ├── llm_bridge.py       # LLM 桥接层
│   └── testcase_agent_demo.py  # 测试用例生成 Demo
├── models/             # 数据模型
├── routes/            # API 路由
├── services/          # 业务逻辑
│   ├── ai_service.py       # AI 服务
│   └── ai_adapters.py     # AI 适配器
├── engine/           # 执行引擎
└── tools/            # 工具模块
```

### 1.2 AI-Server 结构
```
ai-server/
├── llms.py               # LLM 多网关支持
├── main.py              # Agent 入口
├── tools/
│   ├── core/           # 核心架构
│   ├── middleware/       # 中间件
│   ├── mcp/          # MCP 客户端
│   ├── playwright/     # Playwright 自动化
│   └── utils/         # 工具函数
└── requirements.txt      # Python 依赖
```

---

## 二、整合方案设计

### 2.1 整合目标
将 ai-server 的核心能力整合到主平台：
1. **LLM 多网关支持（AIOP/Kiro/AIClient2API）
2. **Playwright 浏览器自动化
3. **LangGraph Agent 编排
4. **Token 用量追踪
5. **中间件系统

### 2.2 整合策略
采用**渐进式整合**策略：
1. **Step 1: 合并依赖
2. **Step 2: 整合 LLM 网关
3. **Step 3: 整合工具模块
4. **Step 4: 整合 Playwright 能力
5. **Step 5: 整合 Agent 系统

---

## 三、详细整合计划

### Step 1: 合并依赖 (10分钟)

将 ai-server/requirements.txt 的依赖合并到主项目 requirements.txt

**新增依赖**：
- langchain[openai]
- langchain-deepseek
- langchain-zhipuai
- langchain-mcp-adapters
- langgraph-cli[inmem]
- beautifulsoup4
- deepagents
- loguru
- fastapi
- playwright
- websockets

### Step 2: 整合 LLM 网关 (30分钟)

**目标**：将 ai-server/llms.py 的多网关能力整合到主项目

**整合位置**：app/services/llm_gateway.py（新建）

**功能**：
- 支持 AIOP Gateway
- 支持 Kiro Gateway
- 支持 AIClient2API Gateway
- 整合 Token 追踪回调

### Step 3: 整合工具模块 (1小时)

**整合内容**：
- tools/middleware/ -> app/utils/middleware/
- tools/utils/ -> app/utils/
- tools/core/ -> app/agents/core/

### Step 4: 整合 Playwright 能力 (1小时)

**整合内容**：
- tools/playwright/ -> app/engine/ui_engine/

### Step 5: 整合 Agent 系统 (1小时)

**整合内容**：
- main.py 的 Agent 能力 -> app/agents/

---

## 四、目录结构调整

### 4.1 最终目标结构

```
app/
├── agents/                      # Agent 系统
│   ├── core/                 # 核心架构 (来自 ai-server/tools/core/
│   ├── llm_bridge.py          # 原有 LLM 桥接
│   └── testcase_agent_demo.py
│
├── services/                   # 业务逻辑
│   ├── llm_gateway.py          # 新建：多网关 LLM 服务
│   ├── ai_service.py         # 原有 AI 服务
│   └── ...
│
├── utils/                      # 工具函数
│   ├── middleware/            # 新建：中间件模块
│   │   ├── dom_cleaner.py
│   │   ├── code_collector.py
│   │   ├── token_control.py
│   │   └── ...
│   ├── token_counter.py        # Token 统计
│   └── ...
│
├── engine/                    # 执行引擎
│   ├── ui_engine/             # 扩展：UI 自动化引擎
│   │   ├── playwright/         # Playwright 工具
│   │   ├── agent.py
│   │   └── ...
│   ├── api_engine/
│   └── ...
│
├── models/                    # 数据模型
│   └── (可能需要新增 Token 相关模型
```

---

## 五、实施步骤

### 阶段一：依赖整合
- [ ] 合并 requirements.txt
- [ ] 验证依赖安装

### 阶段二：LLM 网关整合
- [ ] 创建 app/services/llm_gateway.py
- [ ] 移植 ai-server/llms.py
- [ ] 整合到现有 ai_service.py
- [ ] 测试多网关调用

### 阶段三：工具模块整合
- [ ] 创建 app/utils/middleware/
- [ ] 移植中间件模块
- [ ] 移植 Token 统计工具

### 阶段四：Playwright 整合
- [ ] 创建 app/engine/ui_engine/
- [ ] 移植 Playwright 工具

### 阶段五：Agent 整合
- [ ] 扩展 app/agents/
- [ ] 整合 LangGraph Agent
- [ ] 集成测试

---

## 六、注意事项

1. **向后兼容**：保留现有功能不受影响
2. **渐进式**：分步骤进行，每步可独立运行
3. **代码复用**：最大化代码复用，避免重复
4. **测试**：每步完成后进行测试

---

**文档创建时间**：2026-05-30
