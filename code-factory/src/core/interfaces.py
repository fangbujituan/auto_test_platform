"""Abstract base classes (interfaces) for Code Factory components.

Defines the contracts for all major system components:
- ModelRouterInterface: Model routing and complexity classification
- AgentInterface: Individual agent execution and output validation
- OrchestratorInterface: Multi-agent workflow orchestration
- ReviewGateInterface: Human-in-the-loop review mechanism
- DocumentLoaderInterface: Multi-format document loading
- ChunkerInterface: Semantic document chunking
- VectorStoreInterface: Vector storage and similarity search
- IndexManagerInterface: Incremental index management
- RAGPipelineInterface: Retrieval-augmented generation pipeline
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from src.core.models import (
    AgentState,
    Chunk,
    ChunkConfig,
    EmbeddingRecord,
    IndexUpdateLog,
    LLMRequest,
    LLMResponse,
    LoadedDocument,
    RAGContext,
    RAGQuery,
    RAGResponse,
    ReviewRecord,
    ReviewRequest,
    SearchResult,
    TaskComplexity,
)


# =============================================================================
# Model Router Interface
# =============================================================================


class ModelRouterInterface(ABC):
    """模型路由接口：根据任务复杂度选择合适的模型并调用"""

    @abstractmethod
    async def route(self, request: LLMRequest) -> LLMResponse:
        """根据路由规则选择模型并调用"""
        ...

    @abstractmethod
    def classify_complexity(self, task_type: str, context: dict) -> TaskComplexity:
        """评估任务复杂度"""
        ...


# =============================================================================
# Agent Orchestrator Interfaces
# =============================================================================


class AgentInterface(ABC):
    """Agent 接口：定义单个 Agent 的执行与校验契约"""

    @abstractmethod
    async def execute(self, state: AgentState) -> AgentState:
        """执行 Agent 任务，返回更新后的状态"""
        ...

    @abstractmethod
    def validate_output(self, state: AgentState) -> bool:
        """校验输出是否符合 schema"""
        ...


class OrchestratorInterface(ABC):
    """编排引擎接口：管理多 Agent 工作流的执行"""

    @abstractmethod
    async def run_workflow(self, workflow_name: str, initial_state: AgentState) -> AgentState:
        """执行完整工作流"""
        ...

    @abstractmethod
    def register_agent(self, name: str, agent: AgentInterface) -> None:
        """注册 Agent 到编排引擎"""
        ...


# =============================================================================
# Human Review Gate Interface
# =============================================================================


class ReviewGateInterface(ABC):
    """审核机制接口：管理人工审核流程"""

    @abstractmethod
    async def submit_for_review(self, request: ReviewRequest) -> str:
        """提交内容等待审核，返回 request_id"""
        ...

    @abstractmethod
    async def get_decision(self, request_id: str) -> Optional[ReviewRecord]:
        """获取审核结果"""
        ...

    @abstractmethod
    async def record_decision(self, record: ReviewRecord) -> None:
        """记录审核决策"""
        ...


# =============================================================================
# Document Loader Interface
# =============================================================================


class DocumentLoaderInterface(ABC):
    """文档加载器接口：从多种格式文件中提取结构化内容"""

    @abstractmethod
    def load(self, file_path: str) -> LoadedDocument:
        """加载文档并提取结构化内容"""
        ...

    @abstractmethod
    def supports_format(self, file_path: str) -> bool:
        """检查是否支持该文件格式"""
        ...


# =============================================================================
# Chunker Interface
# =============================================================================


class ChunkerInterface(ABC):
    """智能分块接口：将文档拆分为语义完整的分块"""

    @abstractmethod
    def chunk_document(self, document: LoadedDocument, config: ChunkConfig) -> list[Chunk]:
        """将文档拆分为语义完整的分块"""
        ...

    @abstractmethod
    def generate_chunk_id(self, source_path: str, position: int, version: str) -> str:
        """生成唯一分块标识"""
        ...


# =============================================================================
# Vector Store & Index Manager Interfaces
# =============================================================================


class VectorStoreInterface(ABC):
    """向量存储接口：管理嵌入向量的存储与检索"""

    @abstractmethod
    async def upsert(self, records: list[EmbeddingRecord]) -> int:
        """插入或更新嵌入记录"""
        ...

    @abstractmethod
    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[SearchResult]:
        """相似度搜索"""
        ...

    @abstractmethod
    async def delete_by_document(self, source_path: str) -> int:
        """删除指定文档的所有分块"""
        ...


class IndexManagerInterface(ABC):
    """索引管理接口：管理知识库索引的构建与更新"""

    @abstractmethod
    async def update_index(self, documents: list[LoadedDocument]) -> IndexUpdateLog:
        """增量更新索引"""
        ...

    @abstractmethod
    async def detect_changes(self, document: LoadedDocument) -> dict[str, list[str]]:
        """检测文档变更，返回 {"added": [...], "modified": [...], "deleted": [...]}"""
        ...


# =============================================================================
# RAG Pipeline Interface
# =============================================================================


class RAGPipelineInterface(ABC):
    """RAG 管道接口：检索增强生成的完整流程"""

    @abstractmethod
    async def retrieve(self, query: RAGQuery) -> RAGContext:
        """检索相关上下文"""
        ...

    @abstractmethod
    async def generate(self, query: RAGQuery, context: RAGContext) -> RAGResponse:
        """基于上下文生成响应"""
        ...

    @abstractmethod
    async def query(self, query: RAGQuery) -> RAGResponse:
        """端到端 RAG 查询（检索 + 生成）"""
        ...
