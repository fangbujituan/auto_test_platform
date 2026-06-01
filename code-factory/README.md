# Code Factory - QA 智能测试自动化平台

Code Factory 是一个企业级智能测试自动化平台，通过 Multi-Agent 协作与 RAG（检索增强生成）技术，实现：

- **测试用例智能生成** - 基于需求文档和公司知识库自动生成测试用例
- **高质量测试数据构造** - 智能生成符合业务规则的测试数据
- **自动化测试脚本编写** - 根据测试用例自动生成可执行的测试脚本

系统严格遵循公司代码规范，支持 Human-in-the-Loop 审核机制，优先使用本地模型以保障数据安全。

## 核心特性

### 1. Multi-Agent 协作编排

基于 LangGraph 的 DAG 工作流引擎，实现多 Agent 协同工作：

- **有状态工作流** - 通过 `AgentState` 在 Agent 间传递结构化状态
- **条件边路由** - 支持根据当前状态动态决定执行路径
- **输出校验与重试** - 自动校验输出 schema，失败时最多重试 2 次
- **不可变字段保护** - `task_id`、`correlation_id`、`workflow_id` 在执行过程中不可修改
- **完整调用日志** - 记录 Agent 名称、输入输出摘要、模型使用、Token 消耗、延迟等

### 2. 智能模型路由

基于 LiteLLM 的统一模型路由系统：

- **复杂度分类** - 根据任务类型和上下文自动评估复杂度（LOW/MEDIUM/HIGH）
- **分层路由** - 低复杂度任务路由到本地模型，高复杂度任务路由到云端模型
- **同层级重试** - 单层模型失败时自动重试（最多 3 次）
- **层级升级** - 本地模型全部不可用时自动升级到云端模型
- **优先本地策略** - 中等复杂度任务默认使用本地模型，保障数据安全

### 3. Human-in-the-Loop 审核机制

可配置的人工审核流程：

- **审核点配置** - 在工作流的任意 Agent 后配置审核点
- **超时提醒** - 可配置超时时间和提醒间隔，支持 Webhook 通知
- **审核决策** - 支持 APPROVED（通过）、REJECTED（拒绝）、PENDING（待审核）状态
- **拒绝反馈路由** - 拒绝时将反馈路由回原 Agent 重新生成
- **持久化记录** - 所有审核决策持久化到 PostgreSQL

### 4. RAG 检索增强生成

企业知识库驱动的智能检索：

- **多策略检索** - 支持密集检索（Dense）、稀疏检索（BM25）、混合检索
- **元数据过滤** - 按项目、模块、内容类型过滤检索结果
- **相似度阈值检查** - 低于阈值时标记为"非依据知识库"，明确提示用户
- **来源引用** - 响应中包含 Chunk ID 引用，可追溯到原始文档
- **增量索引** - 自动检测文档变更，增量更新向量索引

### 5. 多格式文档加载

支持多种文档格式的智能解析：

| 格式 | 加载器 | 特性 |
|------|--------|------|
| Markdown | `MarkdownLoader` | 解析标题层级、代码块、表格 |
| PDF | `PDFLoader` | 提取文本内容，保留结构 |
| Word | `WordLoader` | 解析 .docx 文档结构 |
| Swagger/OpenAPI | `SwaggerLoader` | 解析 API 定义，提取接口信息 |
| 源代码 | `SourceCodeLoader` | 支持 Python、Java、TypeScript 等 |

### 6. 向量存储与索引

基于 PGVector 的向量存储方案：

- **PostgreSQL 原生集成** - 利用 PGVector 扩展进行向量存储
- **语义分块** - `SemanticChunker` 按语义边界智能分块
- **增量更新** - 检测文档变更，仅更新变化部分
- **连接池管理** - asyncpg 连接池，支持高并发访问

## 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 包管理 | Poetry | 依赖管理与构建 |
| Agent 编排 | LangGraph | 有状态 DAG 工作流 |
| LLM 路由 | LiteLLM | 统一模型接口与路由 |
| RAG 框架 | LlamaIndex | 检索增强生成管道 |
| 向量数据库 | PGVector | 文档嵌入存储与检索 |
| 配置管理 | Pydantic Settings | 类型安全配置加载 |
| 日志 | structlog | 结构化 JSON 日志 |
| 测试 | pytest + Hypothesis | 单元测试 + 属性测试 |
| Web 框架 | FastAPI | REST API 服务 |
| 数据库 | asyncpg | 异步 PostgreSQL 驱动 |

## 快速开始

### 前置条件

- Python 3.11+
- Poetry
- PostgreSQL 15+ (with PGVector extension)
- Ollama (可选，用于本地模型)

### 安装

```bash
# 克隆项目
git clone <repository-url>
cd code-factory

# 安装依赖
poetry install

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入实际配置值

# 运行测试
poetry run pytest
```

### 环境配置

1. 复制 `.env.example` 为 `.env`
2. 填入数据库连接信息：
   - `DB_PASSWORD` - 数据库密码
   - `ANTHROPIC_API_KEY` - Claude API Key（可选）
   - `DEEPSEEK_API_KEY` - DeepSeek API Key（可选）
3. 设置 `APP_ENV` 为目标环境（development/testing/production）

### 配置文件说明

```
config/
├── settings.yaml           # 通用配置（日志级别、相似度阈值等）
├── routing_rules.yaml      # 模型路由规则
├── review_gates.yaml       # 审核节点配置
└── environments/           # 环境特定配置
    ├── development.yaml    # 开发环境
    ├── testing.yaml        # 测试环境
    └── production.yaml     # 生产环境
```

## 项目结构

```
code-factory/
├── pyproject.toml              # Poetry 项目配置与依赖声明
├── .env.example                # 环境变量模板
├── README.md                   # 项目说明文档
├── config/                     # 配置文件目录
│   ├── settings.yaml           # 通用配置
│   ├── routing_rules.yaml      # 模型路由规则
│   ├── review_gates.yaml       # 审核节点配置
│   └── environments/           # 环境特定配置
│       ├── development.yaml
│       ├── testing.yaml
│       └── production.yaml
├── src/                        # 核心基础设施
│   ├── __init__.py
│   ├── main.py                 # 应用入口，组件初始化与组装
│   └── core/
│       ├── __init__.py
│       ├── config.py           # Pydantic Settings 配置管理
│       ├── logging.py          # structlog 结构化日志
│       ├── exceptions.py       # 自定义异常层次
│       ├── interfaces.py       # 抽象接口定义
│       └── models.py           # 数据模型定义
├── agents/                     # Multi-Agent 层
│   ├── __init__.py
│   ├── orchestrator.py         # LangGraph 编排引擎
│   └── base_agent.py           # Agent 基类
├── rag/                        # RAG 管道
│   ├── __init__.py
│   ├── pipeline.py             # RAG 主管道（检索 + 生成）
│   ├── document_loader.py      # 文档加载器
│   ├── chunker.py              # 语义分块
│   ├── index_manager.py        # 增量索引管理
│   ├── vector_store.py         # PGVector 向量存储
│   └── loaders/                # 各格式加载器
│       ├── markdown_loader.py
│       ├── pdf_loader.py
│       ├── word_loader.py
│       ├── swagger_loader.py
│       └── source_code_loader.py
├── tools/                      # 工具层
│   ├── __init__.py
│   ├── model_router.py         # LiteLLM 模型路由
│   └── review_gate.py          # Human-in-the-Loop 审核
├── tests/                      # 测试套件
│   ├── __init__.py
│   ├── conftest.py             # 共享 fixtures
│   ├── unit/                   # 单元测试
│   ├── property/               # 属性测试 (Hypothesis)
│   └── integration/            # 集成测试
├── migrations/                 # 数据库迁移
│   └── 001_initial_schema.sql
└── docs/                       # 文档
```

## 核心组件详解

### Orchestrator（编排引擎）

`LangGraphOrchestrator` 实现了 `OrchestratorInterface`，负责协调多 Agent 工作流：

```python
from agents.orchestrator import LangGraphOrchestrator, WorkflowDefinition, WorkflowEdge

# 定义工作流
workflow = WorkflowDefinition(
    name="test_case_generation",
    entry_point="requirement_analyzer",
    edges={
        "requirement_analyzer": [WorkflowEdge(target="test_case_generator")],
        "test_case_generator": [WorkflowEdge(target="review_gate")],
    }
)

# 注册 Agent 和工作流
orchestrator = LangGraphOrchestrator()
orchestrator.register_agent("requirement_analyzer", analyzer_agent)
orchestrator.register_agent("test_case_generator", generator_agent)
orchestrator.register_workflow(workflow)

# 执行工作流
final_state = await orchestrator.run_workflow("test_case_generation", initial_state)
```

### Model Router（模型路由）

`LiteLLMModelRouter` 根据任务复杂度自动选择合适的模型：

```python
from tools.model_router import LiteLLMModelRouter
from src.core.models import LLMRequest, TaskComplexity

router = LiteLLMModelRouter()

# 自动评估复杂度
complexity = router.classify_complexity("test_case_generation", {"context_length": 5000})

# 路由请求
request = LLMRequest(
    messages=[{"role": "user", "content": "生成登录功能的测试用例"}],
    task_type="test_case_generation",
    complexity=complexity,
)
response = await router.route(request)
```

### RAG Pipeline（检索增强生成）

`RAGPipeline` 提供端到端的 RAG 查询能力：

```python
from rag.pipeline import RAGPipeline
from src.core.models import RAGQuery, RetrievalStrategy

pipeline = RAGPipeline(vector_store=vector_store, model_router=model_router)

# 执行查询
query = RAGQuery(
    query_text="用户登录流程的测试要点",
    strategy=RetrievalStrategy.HYBRID,
    top_k=5,
    similarity_threshold=0.7,
    metadata_filter={"project": "user-service"}
)
response = await pipeline.query(query)

# 检查是否基于知识库
if response.is_grounded:
    print("基于知识库的回答:", response.content)
    print("引用来源:", response.citations)
```

### Review Gate（审核机制）

`HumanReviewGate` 管理 Human-in-the-Loop 审核流程：

```python
from tools.review_gate import HumanReviewGate
from src.core.models import ReviewRequest, ReviewRecord, ReviewDecision

gate = HumanReviewGate(db_pool=pool)

# 提交审核
request = ReviewRequest(
    request_id="rev-001",
    workflow_id="wf-001",
    agent_name="test_case_generator",
    content={"test_cases": [...]},
    timeout_seconds=3600
)
await gate.submit_for_review(request)

# 检查审核结果
decision = await gate.get_decision("rev-001")
if decision and decision.decision == ReviewDecision.APPROVED:
    print("审核通过")
```

## 开发指南

### 运行测试

```bash
# 运行所有测试
poetry run pytest

# 运行单元测试
poetry run pytest tests/unit/

# 运行属性测试
poetry run pytest tests/property/

# 运行测试并生成覆盖率报告
poetry run pytest --cov=src --cov=agents --cov=rag --cov=tools
```

### 代码质量

```bash
# 代码格式化与 lint
poetry run ruff check .
poetry run ruff format .

# 类型检查
poetry run mypy src agents rag tools
```

## 架构概览

系统采用分层架构：

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                   │
│              接收用户请求，返回响应结果                    │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│               Orchestration Layer (LangGraph)            │
│          DAG 工作流编排，协调 Agent 协作                   │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                    Agent Layer                           │
│    专业化 Agent（测试用例、测试数据、测试脚本生成）          │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                 Intelligence Layer                       │
│         模型路由 + RAG 检索增强 + Human Review            │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                   Knowledge Layer                        │
│      文档加载 → 分块 → 索引 → 向量存储                      │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                 Infrastructure Layer                     │
│     配置管理 + 结构化日志 + 异常处理 + 数据库连接            │
└─────────────────────────────────────────────────────────┘
```

## 配置示例

### 模型路由规则 (routing_rules.yaml)

```yaml
routing:
  rules:
    - task_type: "test_case_generation"
      complexity_threshold: "medium"
      local_models:
        - "ollama/qwen2.5:32b"
        - "ollama/llama3.1:70b"
      cloud_models:
        - "deepseek/deepseek-chat"
        - "anthropic/claude-3-sonnet"
    
    - task_type: "test_data_generation"
      complexity_threshold: "low"
      local_models:
        - "ollama/qwen2.5:14b"
  
  fallback:
    max_retries: 3
    retry_delay_seconds: 2
    escalation_enabled: true
```

### 审核配置 (review_gates.yaml)

```yaml
review_gates:
  workflows:
    test_case_generation:
      review_points:
        - after_agent: "test_case_generator"
          required: true
          timeout_seconds: 3600
    
    test_script_generation:
      review_points:
        - after_agent: "test_script_generator"
          required: true
          timeout_seconds: 7200
  
  notifications:
    reminder_interval_seconds: 1800
    channels:
      - type: "webhook"
        url: "https://your-webhook-url/review-reminder"
```

## 未来规划

### Agent 注册中心与服务发现

当前 Agent 注册在内存中，重启即丢失。未来计划引入类似 Nacos 的 Agent 注册中心，实现：

#### 1. Agent 服务注册

```python
# agents/nacos_registry.py (规划中)
class NacosAgentRegistry:
    """将 Agent 注册到 Nacos 服务发现"""
    
    async def register_agent(self, agent: AgentInterface, host: str, port: int):
        """注册 Agent 到 Nacos"""
        self.client.add_naming_instance(
            service_name=f"agent-{agent.name}",
            ip=host,
            port=port,
            metadata={
                "agent_type": agent.__class__.__name__,
                "capabilities": json.dumps(agent.capabilities),
                "version": "1.0.0"
            }
        )
    
    async def discover_agents(self, agent_name: str) -> list[AgentEndpoint]:
        """从 Nacos 发现 Agent 实例"""
        instances = self.client.list_naming_instance(f"agent-{agent_name}")
        return [self._to_endpoint(i) for i in instances["hosts"]]
```

#### 2. 备选方案

| 方案 | 适用场景 | 特点 |
|-----|---------|-----|
| **Nacos** | 与 Java 生态统一 | 已有运维经验，支持配置中心 |
| **Consul** | HashiCorp 生态 | 服务网格友好，健康检查完善 |
| **PostgreSQL Registry** | 轻量级方案 | 无额外组件，适合小规模部署 |

#### 3. 可视化方案

| 方案 | 用途 | 特点 |
|-----|------|-----|
| **LangGraph Studio** | DAG 调试 | 官方可视化工具，支持断点调试 |
| **LangFuse** | Tracing & 监控 | 开源，Prompt 管理、评估 |
| **Phoenix (Arize)** | LLM 可观测性 | Embedding 可视化、Tracing |
| **自建 Dashboard** | Agent 状态管理 | FastAPI + Vue/React，完全自定义 |

#### 4. 目标架构

```
┌──────────────────────────────────────────────────────────────────┐
│                        Agent 管理架构                              │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│   │ Agent-A     │     │ Agent-B     │     │ Agent-C     │       │
│   │ (测试生成)   │     │ (代码审查)   │     │ (文档生成)   │       │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘       │
│          │                   │                   │               │
│          └───────────────────┼───────────────────┘               │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Nacos / Consul / Postgres Registry          │   │
│   │  - Agent 注册与发现                                       │   │
│   │  - 健康检查 & 心跳检测                                     │   │
│   │  - 负载均衡                                               │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              LangGraph Orchestrator                       │   │
│   │  - DAG 工作流编排                                         │   │
│   │  - 动态 Agent 发现与调用                                   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                              │                                   │
│                              ▼                                   │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              可视化层                                     │   │
│   │  - LangGraph Studio: DAG 调试                            │   │
│   │  - LangFuse: Tracing & 监控                              │   │
│   │  - 自建 Dashboard: Agent 状态、调用统计                   │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

#### 5. 实现优先级

1. **P0 - 核心功能**
   - Agent 注册与发现接口
   - 健康检查与心跳机制
   - 自动摘除不健康 Agent

2. **P1 - 可观测性**
   - LangFuse 集成（Tracing）
   - Agent 调用统计 Dashboard
   - 工作流执行可视化

3. **P2 - 高级特性**
   - Agent 负载均衡
   - Agent 版本管理与灰度发布
   - 多租户隔离

---

## License

Proprietary - Internal Use Only
