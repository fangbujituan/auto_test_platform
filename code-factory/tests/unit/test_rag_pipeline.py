"""Unit tests for RAG Pipeline implementation.

Tests each retrieval strategy independently, hybrid retrieval combination,
metadata filtering, ungrounded response handling, and citation inclusion.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import pytest

from src.core.interfaces import ModelRouterInterface, VectorStoreInterface
from src.core.models import (
    LLMRequest,
    LLMResponse,
    ModelTier,
    RAGQuery,
    RetrievalStrategy,
    SearchResult,
    TaskComplexity,
    EmbeddingRecord,
)
from rag.pipeline import BM25Scorer, RAGPipeline


# =============================================================================
# Mock implementations
# =============================================================================


class MockVectorStore(VectorStoreInterface):
    """Mock vector store for testing."""

    def __init__(self, results: list[SearchResult] | None = None):
        self._results = results or []

    async def upsert(self, records: list[EmbeddingRecord]) -> int:
        return len(records)

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        metadata_filter: dict | None = None,
    ) -> list[SearchResult]:
        results = self._results

        # Apply metadata filter
        if metadata_filter:
            filtered = []
            for r in results:
                match = True
                for key, value in metadata_filter.items():
                    if key in r.metadata and r.metadata[key] != value:
                        match = False
                        break
                if match:
                    filtered.append(r)
            results = filtered

        # Sort by similarity descending and limit to top_k
        results = sorted(results, key=lambda r: r.similarity_score, reverse=True)
        return results[:top_k]

    async def delete_by_document(self, source_path: str) -> int:
        return 0


class MockModelRouter(ModelRouterInterface):
    """Mock model router for testing."""

    def __init__(self, response_content: str = "Generated response"):
        self._response_content = response_content

    async def route(self, request: LLMRequest) -> LLMResponse:
        return LLMResponse(
            content=self._response_content,
            model_used="mock-model",
            tier=ModelTier.LOCAL,
            token_count={"input": 100, "output": 50},
            latency_ms=10.0,
        )

    def classify_complexity(self, task_type: str, context: dict) -> TaskComplexity:
        return TaskComplexity.MEDIUM


# =============================================================================
# Test fixtures
# =============================================================================


def make_search_results(count: int = 5, base_score: float = 0.9) -> list[SearchResult]:
    """Create a list of mock search results with decreasing scores."""
    results = []
    for i in range(count):
        results.append(
            SearchResult(
                chunk_id=f"chunk_{i}",
                content=f"Content of chunk {i} about testing and quality assurance.",
                metadata={
                    "project_name": "project_a",
                    "module_name": "module_x",
                    "content_type": "requirement",
                    "document_version": "1.0",
                },
                similarity_score=base_score - (i * 0.05),
            )
        )
    return results


async def mock_embedding_fn(text: str) -> list[float]:
    """Mock embedding function returning a simple vector."""
    return [0.1] * 1536


# =============================================================================
# BM25 Scorer Tests
# =============================================================================


class TestBM25Scorer:
    """Tests for the BM25 scoring implementation."""

    def test_empty_corpus_returns_empty_scores(self):
        scorer = BM25Scorer()
        scores = scorer.score("test query")
        assert scores == {}

    def test_single_document_scoring(self):
        scorer = BM25Scorer()
        scorer.add_document("doc1", "the quick brown fox jumps over the lazy dog")
        scores = scorer.score("quick fox")
        assert "doc1" in scores
        assert scores["doc1"] > 0

    def test_relevant_document_scores_higher(self):
        scorer = BM25Scorer()
        scorer.add_document("doc1", "python testing framework pytest unit test")
        scorer.add_document("doc2", "cooking recipes for dinner tonight")
        scores = scorer.score("python unit testing")
        assert scores["doc1"] > scores["doc2"]

    def test_multiple_documents_ranking(self):
        scorer = BM25Scorer()
        scorer.add_document("doc1", "machine learning deep learning neural networks")
        scorer.add_document("doc2", "deep learning transformers attention mechanism")
        scorer.add_document("doc3", "cooking recipes food preparation")
        scores = scorer.score("deep learning")
        # Both doc1 and doc2 should score higher than doc3
        assert scores["doc1"] > scores["doc3"]
        assert scores["doc2"] > scores["doc3"]

    def test_no_matching_terms_scores_zero(self):
        scorer = BM25Scorer()
        scorer.add_document("doc1", "alpha beta gamma delta")
        scores = scorer.score("xyz abc")
        assert scores["doc1"] == 0.0

    def test_tokenization_is_case_insensitive(self):
        scorer = BM25Scorer()
        scorer.add_document("doc1", "Python Testing Framework")
        scores = scorer.score("python testing")
        assert scores["doc1"] > 0


# =============================================================================
# RAG Pipeline - Dense Retrieval Tests
# =============================================================================


class TestDenseRetrieval:
    """Tests for dense (vector similarity) retrieval."""

    @pytest.mark.asyncio
    async def test_dense_retrieval_returns_results(self):
        results = make_search_results(3, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=3,
            similarity_threshold=0.7,
        )
        context = await pipeline.retrieve(query)

        assert len(context.chunks) == 3
        assert context.is_grounded is True

    @pytest.mark.asyncio
    async def test_dense_retrieval_respects_top_k(self):
        results = make_search_results(10, base_score=0.95)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.5,
        )
        context = await pipeline.retrieve(query)

        assert len(context.chunks) <= 5

    @pytest.mark.asyncio
    async def test_dense_retrieval_with_metadata_filter(self):
        results = [
            SearchResult(
                chunk_id="chunk_a",
                content="Project A content",
                metadata={"project_name": "project_a", "content_type": "requirement"},
                similarity_score=0.9,
            ),
            SearchResult(
                chunk_id="chunk_b",
                content="Project B content",
                metadata={"project_name": "project_b", "content_type": "api"},
                similarity_score=0.85,
            ),
        ]
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.5,
            metadata_filter={"project_name": "project_a"},
        )
        context = await pipeline.retrieve(query)

        # Only project_a results should be returned
        for chunk in context.chunks:
            assert chunk.metadata["project_name"] == "project_a"


# =============================================================================
# RAG Pipeline - Sparse Retrieval Tests
# =============================================================================


class TestSparseRetrieval:
    """Tests for sparse (BM25) retrieval."""

    @pytest.mark.asyncio
    async def test_sparse_retrieval_returns_results(self):
        results = make_search_results(5, base_score=0.8)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        # Index documents for BM25
        for r in results:
            pipeline.index_for_bm25(r.chunk_id, r.content)

        query = RAGQuery(
            query_text="testing quality assurance",
            strategy=RetrievalStrategy.SPARSE,
            top_k=3,
            similarity_threshold=0.1,
        )
        context = await pipeline.retrieve(query)

        assert len(context.chunks) > 0

    @pytest.mark.asyncio
    async def test_sparse_retrieval_empty_index(self):
        store = MockVectorStore([])
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.SPARSE,
            top_k=5,
            similarity_threshold=0.7,
        )
        context = await pipeline.retrieve(query)

        assert len(context.chunks) == 0
        assert context.is_grounded is False


# =============================================================================
# RAG Pipeline - Hybrid Retrieval Tests
# =============================================================================


class TestHybridRetrieval:
    """Tests for hybrid (dense + sparse) retrieval."""

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_combines_results(self):
        results = make_search_results(5, base_score=0.85)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        # Index for BM25
        for r in results:
            pipeline.index_for_bm25(r.chunk_id, r.content)

        query = RAGQuery(
            query_text="testing quality",
            strategy=RetrievalStrategy.HYBRID,
            top_k=3,
            similarity_threshold=0.1,
        )
        context = await pipeline.retrieve(query)

        assert len(context.chunks) > 0
        assert len(context.chunks) <= 3

    @pytest.mark.asyncio
    async def test_hybrid_retrieval_default_strategy(self):
        results = make_search_results(3, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        for r in results:
            pipeline.index_for_bm25(r.chunk_id, r.content)

        # Default strategy is HYBRID
        query = RAGQuery(query_text="test query", similarity_threshold=0.1)
        context = await pipeline.retrieve(query)

        assert len(context.chunks) > 0


# =============================================================================
# RAG Pipeline - Similarity Threshold Tests
# =============================================================================


class TestSimilarityThreshold:
    """Tests for similarity threshold and ungrounded response marking."""

    @pytest.mark.asyncio
    async def test_below_threshold_marks_ungrounded(self):
        # All results below threshold
        results = make_search_results(3, base_score=0.5)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.7,
        )
        context = await pipeline.retrieve(query)

        assert context.is_grounded is False
        assert context.source_citations == []

    @pytest.mark.asyncio
    async def test_above_threshold_marks_grounded(self):
        results = make_search_results(3, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.7,
        )
        context = await pipeline.retrieve(query)

        assert context.is_grounded is True
        assert len(context.source_citations) > 0

    @pytest.mark.asyncio
    async def test_mixed_scores_filters_below_threshold(self):
        results = [
            SearchResult(
                chunk_id="high",
                content="High relevance",
                metadata={"project_name": "p"},
                similarity_score=0.9,
            ),
            SearchResult(
                chunk_id="low",
                content="Low relevance",
                metadata={"project_name": "p"},
                similarity_score=0.5,
            ),
        ]
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.7,
        )
        context = await pipeline.retrieve(query)

        assert context.is_grounded is True
        assert "high" in context.source_citations
        assert "low" not in context.source_citations


# =============================================================================
# RAG Pipeline - Citation Tests
# =============================================================================


class TestCitations:
    """Tests for chunk_id citation inclusion in responses."""

    @pytest.mark.asyncio
    async def test_citations_included_in_response(self):
        results = make_search_results(3, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=3,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert len(response.citations) > 0
        # Citations should be chunk_ids
        for citation in response.citations:
            assert citation.startswith("chunk_")

    @pytest.mark.asyncio
    async def test_citations_match_context_source_citations(self):
        results = make_search_results(2, base_score=0.85)
        store = MockVectorStore(results)
        router = MockModelRouter()
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert response.citations == response.context.source_citations


# =============================================================================
# RAG Pipeline - Generation Tests
# =============================================================================


class TestGeneration:
    """Tests for the generate step."""

    @pytest.mark.asyncio
    async def test_generate_returns_content(self):
        results = make_search_results(2, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter(response_content="Test answer based on context")
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="What is the testing strategy?",
            strategy=RetrievalStrategy.DENSE,
            top_k=3,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert response.content is not None
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_ungrounded_response_includes_notice(self):
        # All results below threshold
        results = make_search_results(2, base_score=0.4)
        store = MockVectorStore(results)
        router = MockModelRouter(response_content="General answer")
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=3,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert response.is_grounded is False
        assert "Insufficient context" in response.content or "ungrounded" in response.content.lower()

    @pytest.mark.asyncio
    async def test_grounded_response_no_notice(self):
        results = make_search_results(2, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter(response_content="Grounded answer")
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="test query",
            strategy=RetrievalStrategy.DENSE,
            top_k=3,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert response.is_grounded is True
        assert "[Notice:" not in response.content


# =============================================================================
# RAG Pipeline - End-to-End Query Tests
# =============================================================================


class TestEndToEndQuery:
    """Tests for the end-to-end query method."""

    @pytest.mark.asyncio
    async def test_query_performs_retrieve_and_generate(self):
        results = make_search_results(3, base_score=0.9)
        store = MockVectorStore(results)
        router = MockModelRouter(response_content="Complete answer")
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="How to write unit tests?",
            strategy=RetrievalStrategy.DENSE,
            top_k=3,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert response.content is not None
        assert response.context is not None
        assert response.is_grounded is True
        assert len(response.citations) > 0

    @pytest.mark.asyncio
    async def test_query_with_no_results(self):
        store = MockVectorStore([])
        router = MockModelRouter(response_content="No context available")
        pipeline = RAGPipeline(store, router, embedding_fn=mock_embedding_fn)

        query = RAGQuery(
            query_text="obscure query",
            strategy=RetrievalStrategy.DENSE,
            top_k=5,
            similarity_threshold=0.7,
        )
        response = await pipeline.query(query)

        assert response.is_grounded is False
        assert response.citations == []
