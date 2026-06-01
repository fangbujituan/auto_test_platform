"""Code Factory 的共享数据模型和枚举。

包含系统各组件使用的全部 dataclasses 和枚举：
- Model Router: ModelTier, TaskComplexity, RoutingRule, LLMRequest, LLMResponse
- Agent Orchestrator: AgentState, WorkflowStatus, AgentInvocationLog
- Human Review Gate: ReviewDecision, ReviewRequest, ReviewRecord
- Document Loader: DocumentFormat, DocumentUnit, LoadedDocument
- Chunker: ChunkMetadata, Chunk, ChunkConfig
- Vector Store & Index Manager: EmbeddingRecord, SearchResult, IndexUpdateLog
- RAG Pipeline: RAGQuery, RAGContext, RAGResponse, RetrievalStrategy
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


# =============================================================================
# Model Router Models
# =============================================================================


class ModelTier(Enum):
    """模型层级：本地或云端"""

    LOCAL = "local"
    CLOUD = "cloud"


class TaskComplexity(Enum):
    """任务复杂度等级"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class RoutingRule:
    """模型路由规则"""

    complexity: TaskComplexity
    tier: ModelTier
    models: list[str]  # 按优先级排序的模型列表
    max_retries: int = 3


@dataclass
class LLMRequest:
    """LLM 调用请求"""

    messages: list[dict[str, str]]
    task_type: str
    complexity: TaskComplexity
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class LLMResponse:
    """LLM 调用响应"""

    content: str
    model_used: str
    tier: ModelTier
    token_count: dict[str, int]  # {"input": N, "output": M}
    latency_ms: float


# =============================================================================
# Agent Orchestrator Models
# =============================================================================


class WorkflowStatus(Enum):
    """工作流状态"""

    PENDING = "pending"
    RUNNING = "running"
    WAITING_REVIEW = "waiting_review"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentState:
    """Agent 间传递的状态对象"""

    task_id: str
    correlation_id: str
    workflow_id: str
    input_data: dict[str, Any]
    output_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentInvocationLog:
    """Agent 调用日志"""

    agent_name: str
    input_summary: str
    output_summary: str
    model_used: str
    token_count: dict[str, int]
    latency_ms: float
    status: str
    correlation_id: str


# =============================================================================
# Human Review Gate Models
# =============================================================================


class ReviewDecision(Enum):
    """审核决策"""

    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass
class ReviewRequest:
    """审核请求"""

    request_id: str
    workflow_id: str
    agent_name: str
    content: dict
    created_at: datetime
    timeout_seconds: int


@dataclass
class ReviewRecord:
    """审核记录"""

    request_id: str
    reviewer_id: str
    decision: ReviewDecision
    comments: str
    timestamp: datetime


# =============================================================================
# Document Loader Models
# =============================================================================


class DocumentFormat(Enum):
    """支持的文档格式"""

    PDF = "pdf"
    MARKDOWN = "markdown"
    WORD = "word"
    SWAGGER_JSON = "swagger_json"
    SWAGGER_YAML = "swagger_yaml"
    PYTHON = "python"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"


@dataclass
class DocumentUnit:
    """文档逻辑单元"""

    content: str
    unit_type: str  # "heading", "code_block", "table", "api_endpoint", "function", "class"
    metadata: dict[str, Any]
    source_path: str
    position: int  # 在文档中的位置序号


@dataclass
class LoadedDocument:
    """加载后的文档"""

    source_path: str
    format: DocumentFormat
    units: list[DocumentUnit]
    raw_text: str
    structural_info: dict[str, Any]  # 保留的结构信息


# =============================================================================
# Chunker Models
# =============================================================================


@dataclass
class ChunkMetadata:
    """分块元数据"""

    project_name: str
    module_name: str
    document_version: str
    content_type: str  # "requirement", "bug", "api", "test_case", "code_specification"
    source_path: str
    chunk_position: int


@dataclass
class Chunk:
    """文档分块"""

    chunk_id: str  # 基于 source_path + position + version 生成
    content: str
    metadata: ChunkMetadata
    token_count: int


@dataclass
class ChunkConfig:
    """分块配置"""

    max_tokens: int = 512
    overlap_tokens: int = 50
    code_block_max_tokens: int = 2048


# =============================================================================
# Vector Store & Index Manager Models
# =============================================================================


@dataclass
class EmbeddingRecord:
    """嵌入记录"""

    chunk_id: str
    embedding: list[float]
    content: str
    metadata: dict[str, Any]


@dataclass
class SearchResult:
    """搜索结果"""

    chunk_id: str
    content: str
    metadata: dict[str, Any]
    similarity_score: float


@dataclass
class IndexUpdateLog:
    """索引更新日志"""

    timestamp: datetime
    operation: str  # "add", "update", "delete"
    affected_documents: list[str]
    chunks_added: int
    chunks_removed: int
    chunks_updated: int


# =============================================================================
# RAG Pipeline Models
# =============================================================================


class RetrievalStrategy(Enum):
    """检索策略"""

    DENSE = "dense"
    SPARSE = "sparse"  # BM25
    HYBRID = "hybrid"


@dataclass
class RAGQuery:
    """RAG 查询"""

    query_text: str
    strategy: RetrievalStrategy = RetrievalStrategy.HYBRID
    top_k: int = 5
    similarity_threshold: float = 0.7
    metadata_filter: Optional[dict[str, Any]] = None


@dataclass
class RAGContext:
    """检索到的上下文"""

    chunks: list[SearchResult]
    is_grounded: bool  # 是否有足够相关上下文
    source_citations: list[str]  # chunk_id 列表


@dataclass
class RAGResponse:
    """RAG 生成响应"""

    content: str
    context: RAGContext
    is_grounded: bool
    citations: list[str]
