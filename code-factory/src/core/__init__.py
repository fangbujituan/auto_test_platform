"""Core infrastructure: configuration, logging, exceptions, models, and interfaces."""

from src.core.exceptions import (
    AgentExecutionError,
    CodeFactoryError,
    ConfigurationError,
    DocumentLoadError,
    MissingConfigError,
    ModelRoutingError,
    ModelTierExhaustedError,
    SchemaValidationError,
    UnsupportedFormatError,
)
from src.core.interfaces import (
    AgentInterface,
    ChunkerInterface,
    DocumentLoaderInterface,
    IndexManagerInterface,
    ModelRouterInterface,
    OrchestratorInterface,
    RAGPipelineInterface,
    ReviewGateInterface,
    VectorStoreInterface,
)
from src.core.models import (
    AgentInvocationLog,
    AgentState,
    Chunk,
    ChunkConfig,
    ChunkMetadata,
    DocumentFormat,
    DocumentUnit,
    EmbeddingRecord,
    IndexUpdateLog,
    LLMRequest,
    LLMResponse,
    LoadedDocument,
    ModelTier,
    RAGContext,
    RAGQuery,
    RAGResponse,
    RetrievalStrategy,
    ReviewDecision,
    ReviewRecord,
    ReviewRequest,
    RoutingRule,
    SearchResult,
    TaskComplexity,
    WorkflowStatus,
)

__all__ = [
    # Exceptions
    "AgentExecutionError",
    "CodeFactoryError",
    "ConfigurationError",
    "DocumentLoadError",
    "MissingConfigError",
    "ModelRoutingError",
    "ModelTierExhaustedError",
    "SchemaValidationError",
    "UnsupportedFormatError",
    # Interfaces
    "AgentInterface",
    "ChunkerInterface",
    "DocumentLoaderInterface",
    "IndexManagerInterface",
    "ModelRouterInterface",
    "OrchestratorInterface",
    "RAGPipelineInterface",
    "ReviewGateInterface",
    "VectorStoreInterface",
    # Models - Model Router
    "ModelTier",
    "TaskComplexity",
    "RoutingRule",
    "LLMRequest",
    "LLMResponse",
    # Models - Agent Orchestrator
    "AgentState",
    "AgentInvocationLog",
    "WorkflowStatus",
    # Models - Human Review Gate
    "ReviewDecision",
    "ReviewRequest",
    "ReviewRecord",
    # Models - Document Loader
    "DocumentFormat",
    "DocumentUnit",
    "LoadedDocument",
    # Models - Chunker
    "ChunkMetadata",
    "Chunk",
    "ChunkConfig",
    # Models - Vector Store & Index Manager
    "EmbeddingRecord",
    "SearchResult",
    "IndexUpdateLog",
    # Models - RAG Pipeline
    "RAGQuery",
    "RAGContext",
    "RAGResponse",
    "RetrievalStrategy",
]
