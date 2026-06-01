"""Code Factory 应用入口点。

初始化配置、日志、数据库连接，并将所有组件连接在一起：
Model Router、Agent Orchestrator、RAG Pipeline、
Review Gate、Vector Store、Index Manager。

实现启动验证序列：
1. 加载并验证配置 (load_config_or_exit)
2. 配置结构化日志
3. 安装全局异常钩子
4. 测试数据库连接
5. 初始化所有组件
6. 记录启动成功日志

Requirements: 1.5, 9.1, 9.3, 9.4
"""

import asyncio
import sys
from dataclasses import dataclass
from typing import Any

import asyncpg

from src.core.config import AppConfig, load_config_or_exit
from src.core.logging import (
    configure_logging,
    get_logger,
    install_exception_hook,
)

logger = get_logger("src.main")


@dataclass
class AppContext:
    """应用上下文，保存所有已连接的组件。

    提供对所有已初始化组件和数据库连接池的访问。
    使用 `close()` 可以干净地关闭连接。
    """

    config: AppConfig
    db_pool: asyncpg.Pool
    vector_store: Any  # PGVectorStore
    index_manager: Any  # IncrementalIndexManager
    rag_pipeline: Any  # RAGPipeline
    model_router: Any  # LiteLLMModelRouter
    orchestrator: Any  # LangGraphOrchestrator
    review_gate: Any  # HumanReviewGate

    async def close(self) -> None:
        """干净地关闭所有连接和资源。"""
        if self.db_pool is not None:
            await self.db_pool.close()
        if hasattr(self.vector_store, "close"):
            await self.vector_store.close()


async def _create_db_pool(config: AppConfig) -> asyncpg.Pool:
    """从应用配置创建 asyncpg 连接池。

    Args:
        config: 验证后的应用配置。

    Returns:
        一个 asyncpg 连接池。

    Raises:
        SystemExit: 如果无法建立数据库连接。
    """
    dsn = (
        f"postgresql://{config.database.user}:{config.database.password}"
        f"@{config.database.host}:{config.database.port}/{config.database.database}"
    )
    try:
        pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=10)
        return pool
    except (OSError, asyncpg.PostgresError, Exception) as e:
        logger.error(
            "Failed to connect to database",
            host=config.database.host,
            port=config.database.port,
            database=config.database.database,
            error=str(e),
        )
        print(
            f"ERROR: Cannot connect to database at "
            f"{config.database.host}:{config.database.port}/{config.database.database}: {e}",
            file=sys.stderr,
        )
        sys.exit(1)


async def _test_db_connection(pool: asyncpg.Pool) -> None:
    """通过执行简单查询测试数据库连接。

    Args:
        pool: 要测试的 asyncpg 连接池。

    Raises:
        SystemExit: 如果连接测试失败。
    """
    try:
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            if result != 1:
                raise RuntimeError("Unexpected result from database health check")
        logger.info("Database connection verified successfully")
    except Exception as e:
        logger.error("Database connection test failed", error=str(e))
        print(f"ERROR: Database connection test failed: {e}", file=sys.stderr)
        sys.exit(1)


def _initialize_model_router(config: AppConfig) -> Any:
    """初始化 LiteLLM 模型路由。

    Args:
        config: 验证后的应用配置。

    Returns:
        一个已初始化的 LiteLLMModelRouter 实例。
    """
    from tools.model_router import LiteLLMModelRouter

    return LiteLLMModelRouter()


def _initialize_vector_store(pool: asyncpg.Pool) -> Any:
    """使用连接池初始化 PGVector 存储。

    Args:
        pool: asyncpg 连接池。

    Returns:
        一个已初始化的 PGVectorStore 实例。
    """
    from rag.vector_store import PGVectorStore

    return PGVectorStore(pool=pool)


def _initialize_index_manager(vector_store: Any, pool: asyncpg.Pool) -> Any:
    """初始化增量索引管理器。

    Args:
        vector_store: 已初始化的向量存储。
        pool: asyncpg 连接池。

    Returns:
        一个已初始化的 IncrementalIndexManager 实例。
    """
    from rag.chunker import SemanticChunker
    from rag.index_manager import IncrementalIndexManager

    chunker = SemanticChunker()
    return IncrementalIndexManager(
        vector_store=vector_store,
        pool=pool,
        chunker=chunker,
    )


def _initialize_rag_pipeline(vector_store: Any, model_router: Any) -> Any:
    """初始化 RAG 管道。

    Args:
        vector_store: 已初始化的向量存储。
        model_router: 已初始化的模型路由。

    Returns:
        一个已初始化的 RAGPipeline 实例。
    """
    from rag.pipeline import RAGPipeline

    return RAGPipeline(
        vector_store=vector_store,
        model_router=model_router,
    )


def _initialize_orchestrator() -> Any:
    """初始化 LangGraph Agent 编排器。

    Returns:
        一个已初始化的 LangGraphOrchestrator 实例。
    """
    from agents.orchestrator import LangGraphOrchestrator

    return LangGraphOrchestrator()


def _initialize_review_gate(pool: asyncpg.Pool) -> Any:
    """初始化人工审核网关。

    Args:
        pool: 用于持久化审核记录的 asyncpg 连接池。

    Returns:
        一个已初始化的 HumanReviewGate 实例。
    """
    from tools.review_gate import HumanReviewGate

    return HumanReviewGate(db_pool=pool)


async def create_app() -> AppContext:
    """创建并初始化完整的应用上下文。

    执行启动验证序列：
    1. 加载并验证配置（失败时退出）
    2. 配置结构化日志
    3. 安装全局异常钩子
    4. 创建数据库连接池
    5. 测试数据库连接性
    6. 初始化所有组件
    7. 记录启动成功日志

    Returns:
        一个包含所有已连接组件的 AppContext 实例。

    Raises:
        SystemExit: 如果配置无效或数据库无法访问。
    """
    # Step 1: 加载并验证配置
    config = load_config_or_exit()

    # Step 2: 配置结构化日志
    configure_logging(default_level=config.log_level)

    # Step 3: 安装全局异常钩子
    install_exception_hook()

    logger.info(
        "Starting Code Factory",
        environment=config.environment.value,
        log_level=config.log_level,
    )

    # Step 4: 创建数据库连接池
    pool = await _create_db_pool(config)

    # Step 5: 测试数据库连接性
    await _test_db_connection(pool)

    # Step 6: 初始化所有组件
    model_router = _initialize_model_router(config)
    vector_store = _initialize_vector_store(pool)
    index_manager = _initialize_index_manager(vector_store, pool)
    rag_pipeline = _initialize_rag_pipeline(vector_store, model_router)
    orchestrator = _initialize_orchestrator()
    review_gate = _initialize_review_gate(pool)

    # Step 7: 记录启动成功日志
    logger.info(
        "Code Factory started successfully",
        environment=config.environment.value,
        database=config.database.database,
        components_initialized=[
            "model_router",
            "vector_store",
            "index_manager",
            "rag_pipeline",
            "orchestrator",
            "review_gate",
        ],
    )

    return AppContext(
        config=config,
        db_pool=pool,
        vector_store=vector_store,
        index_manager=index_manager,
        rag_pipeline=rag_pipeline,
        model_router=model_router,
        orchestrator=orchestrator,
        review_gate=review_gate,
    )
