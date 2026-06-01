"""Unit tests for src/main.py application entry point.

Tests the startup validation sequence, component initialization,
and error handling for database connection failures.
"""

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.main import (
    AppContext,
    _initialize_model_router,
    _initialize_orchestrator,
    _initialize_rag_pipeline,
    _initialize_review_gate,
    _initialize_vector_store,
    _initialize_index_manager,
    _test_db_connection,
    create_app,
)


class TestInitializeComponents:
    """Tests for individual component initialization functions."""

    def test_initialize_model_router(self):
        """Model router initializes without errors."""
        from src.core.config import AppConfig, DatabaseConfig, ModelConfig

        config = AppConfig(
            database=DatabaseConfig(
                host="localhost",
                port=5432,
                database="test_db",
                user="test_user",
                password="test_pass",
            ),
            model=ModelConfig(
                local_endpoint="http://localhost:11434",
            ),
        )
        router = _initialize_model_router(config)
        assert router is not None

    def test_initialize_vector_store(self):
        """Vector store initializes with a mock pool."""
        mock_pool = MagicMock()
        store = _initialize_vector_store(mock_pool)
        assert store is not None

    def test_initialize_index_manager(self):
        """Index manager initializes with vector store and pool."""
        mock_pool = MagicMock()
        mock_store = MagicMock()
        manager = _initialize_index_manager(mock_store, mock_pool)
        assert manager is not None

    def test_initialize_rag_pipeline(self):
        """RAG pipeline initializes with vector store and model router."""
        mock_store = MagicMock()
        mock_router = MagicMock()
        pipeline = _initialize_rag_pipeline(mock_store, mock_router)
        assert pipeline is not None

    def test_initialize_orchestrator(self):
        """Orchestrator initializes without errors."""
        orchestrator = _initialize_orchestrator()
        assert orchestrator is not None

    def test_initialize_review_gate(self):
        """Review gate initializes with a mock pool."""
        mock_pool = MagicMock()
        gate = _initialize_review_gate(mock_pool)
        assert gate is not None


class TestDbConnectionTest:
    """Tests for database connection validation."""

    @pytest.mark.asyncio
    async def test_successful_db_connection(self):
        """Successful DB connection test passes without error."""
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)

        mock_pool = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.return_value = mock_conn
        mock_ctx.__aexit__.return_value = False
        mock_pool.acquire.return_value = mock_ctx

        # Should not raise
        await _test_db_connection(mock_pool)

    @pytest.mark.asyncio
    async def test_failed_db_connection_exits(self):
        """Failed DB connection test causes sys.exit(1)."""
        mock_pool = MagicMock()
        mock_ctx = AsyncMock()
        mock_ctx.__aenter__.side_effect = Exception("Connection refused")
        mock_ctx.__aexit__.return_value = False
        mock_pool.acquire.return_value = mock_ctx

        with pytest.raises(SystemExit) as exc_info:
            await _test_db_connection(mock_pool)
        assert exc_info.value.code == 1


class TestAppContext:
    """Tests for AppContext dataclass."""

    @pytest.mark.asyncio
    async def test_close_closes_pool(self):
        """AppContext.close() closes the database pool."""
        mock_pool = AsyncMock()
        mock_vector_store = AsyncMock()

        ctx = AppContext(
            config=MagicMock(),
            db_pool=mock_pool,
            vector_store=mock_vector_store,
            index_manager=MagicMock(),
            rag_pipeline=MagicMock(),
            model_router=MagicMock(),
            orchestrator=MagicMock(),
            review_gate=MagicMock(),
        )

        await ctx.close()
        mock_pool.close.assert_called_once()
        mock_vector_store.close.assert_called_once()


class TestCreateApp:
    """Tests for the create_app function."""

    @pytest.mark.asyncio
    async def test_create_app_exits_on_invalid_config(self):
        """create_app exits when configuration is invalid."""
        with patch.dict(
            "os.environ",
            {"APP_ENV": "development"},
            clear=False,
        ):
            # Without proper env vars and config, load_config_or_exit should exit
            with pytest.raises(SystemExit):
                await create_app()
