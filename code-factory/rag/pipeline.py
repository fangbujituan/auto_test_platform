"""RAG 管道实现，支持稠密、稀疏 (BM25) 和混合检索 / RAG Pipeline implementation with dense, sparse (BM25), and hybrid retrieval.

实现 RAGPipelineInterface，提供：
Implements the RAGPipelineInterface providing:
- 通过向量相似度搜索进行稠密检索 / Dense retrieval via vector similarity search
- 通过 BM25 评分进行稀疏检索 / Sparse retrieval via BM25 scoring
- 结合稠密和稀疏的加权评分混合检索 / Hybrid retrieval combining dense and sparse with weighted scoring
- 元数据过滤检索 (项目、模块、内容类型) / Metadata-filtered retrieval (project, module, content_type)
- 相似度阈值检查并标记未落地响应 / Similarity threshold check with ungrounded response marking
- 所有响应中包含 Chunk ID 引用 / Chunk ID citations in all responses

需求 / Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

import math
import re
from collections import Counter
from typing import Any, Optional

from src.core.interfaces import ModelRouterInterface, RAGPipelineInterface, VectorStoreInterface
from src.core.models import (
    LLMRequest,
    RAGContext,
    RAGQuery,
    RAGResponse,
    RetrievalStrategy,
    SearchResult,
    TaskComplexity,
)


class BM25Scorer:
    """简单的内存 BM25 评分器，用于稀疏检索 / Simple in-memory BM25 scorer for sparse retrieval.

    在文档语料库上实现 Okapi BM25 排名函数。
    Implements the Okapi BM25 ranking function over a corpus of documents.
    通过 `add_document` 添加文档，通过 `score` 对查询进行评分。
    Documents are added via `add_document` and scored against a query via `score`.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """Initialize BM25 scorer with tuning parameters.

        Args:
            k1: Term frequency saturation parameter (default 1.5).
            b: Document length normalization parameter (default 0.75).
        """
        self.k1 = k1
        self.b = b
        self._documents: dict[str, list[str]] = {}  # chunk_id -> tokenized terms
        self._doc_lengths: dict[str, int] = {}
        self._avg_doc_length: float = 0.0
        self._doc_count: int = 0
        self._df: Counter = Counter()  # document frequency per term

    def add_document(self, chunk_id: str, content: str) -> None:
        """Add a document to the BM25 index.

        Args:
            chunk_id: Unique identifier for the document chunk.
            content: Text content to index.
        """
        terms = self._tokenize(content)
        self._documents[chunk_id] = terms
        self._doc_lengths[chunk_id] = len(terms)

        # Update document frequency
        unique_terms = set(terms)
        for term in unique_terms:
            self._df[term] += 1

        # Update average document length
        self._doc_count = len(self._documents)
        total_length = sum(self._doc_lengths.values())
        self._avg_doc_length = total_length / self._doc_count if self._doc_count > 0 else 0.0

    def score(self, query: str) -> dict[str, float]:
        """Score all documents against a query using BM25.

        Args:
            query: The search query text.

        Returns:
            Dictionary mapping chunk_id to BM25 score.
        """
        query_terms = self._tokenize(query)
        scores: dict[str, float] = {}

        for chunk_id, doc_terms in self._documents.items():
            score = 0.0
            doc_length = self._doc_lengths[chunk_id]
            term_freqs = Counter(doc_terms)

            for term in query_terms:
                if term not in term_freqs:
                    continue

                tf = term_freqs[term]
                df = self._df.get(term, 0)

                # IDF component: log((N - df + 0.5) / (df + 0.5) + 1)
                idf = math.log(
                    (self._doc_count - df + 0.5) / (df + 0.5) + 1.0
                )

                # TF component with length normalization
                tf_norm = (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * doc_length / self._avg_doc_length)
                )

                score += idf * tf_norm

            scores[chunk_id] = score

        return scores

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into lowercase terms.

        Args:
            text: Input text to tokenize.

        Returns:
            List of lowercase word tokens.
        """
        # Simple whitespace + punctuation tokenization
        return re.findall(r"\b\w+\b", text.lower())


class RAGPipeline(RAGPipelineInterface):
    """RAG 管道，实现稠密、稀疏和混合检索及生成 / RAG Pipeline implementing dense, sparse, and hybrid retrieval with generation.

    将向量相似度搜索（稠密）与 BM25 评分（稀疏）结合，提供
    Combines vector similarity search (dense) with BM25 scoring (sparse) to provide
    灵活的检索策略。支持元数据过滤和相似度阈值检查，
    flexible retrieval strategies. Supports metadata filtering and similarity threshold
    当上下文不足时将响应标记为未落地。
    checks to mark responses as ungrounded when context is insufficient.

    参数 / Args:
        vector_store: 用于稠密检索的 VectorStoreInterface / VectorStoreInterface for dense retrieval.
        model_router: 用于 LLM 生成的 ModelRouterInterface / ModelRouterInterface for LLM generation.
        embedding_fn: 可选的异步可调用对象，用于生成查询嵌入 / Optional async callable to generate query embeddings.
            签名 / Signature: async (text: str) -> list[float]
        dense_weight: 混合检索中稠密分数的权重（默认 0.7）/ Weight for dense scores in hybrid retrieval (default 0.7).
        sparse_weight: 混合检索中稀疏分数的权重（默认 0.3）/ Weight for sparse scores in hybrid retrieval (default 0.3).
    """

    def __init__(
        self,
        vector_store: VectorStoreInterface,
        model_router: ModelRouterInterface,
        embedding_fn: Optional[Any] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ):
        self._vector_store = vector_store
        self._model_router = model_router
        self._embedding_fn = embedding_fn
        self._dense_weight = dense_weight
        self._sparse_weight = sparse_weight
        self._bm25 = BM25Scorer()

    def index_for_bm25(self, chunk_id: str, content: str) -> None:
        """Add a document chunk to the BM25 index for sparse retrieval.

        Args:
            chunk_id: Unique identifier for the chunk.
            content: Text content of the chunk.
        """
        self._bm25.add_document(chunk_id, content)

    async def retrieve(self, query: RAGQuery) -> RAGContext:
        """Retrieve relevant context chunks based on the query strategy.

        Supports three retrieval strategies:
        - DENSE: Vector similarity search via the vector store
        - SPARSE: BM25 scoring over indexed documents
        - HYBRID: Weighted combination of dense and sparse results

        Applies metadata filtering when specified in the query.
        Checks similarity threshold to determine if context is grounded.

        Args:
            query: RAGQuery specifying text, strategy, top_k, threshold, and filters.

        Returns:
            RAGContext with retrieved chunks, grounding status, and citations.
        """
        if query.strategy == RetrievalStrategy.DENSE:
            chunks = await self._dense_retrieve(query)
        elif query.strategy == RetrievalStrategy.SPARSE:
            chunks = await self._sparse_retrieve(query)
        else:  # HYBRID
            chunks = await self._hybrid_retrieve(query)

        # Apply similarity threshold check
        grounded_chunks = [
            chunk for chunk in chunks if chunk.similarity_score >= query.similarity_threshold
        ]

        is_grounded = len(grounded_chunks) > 0
        citations = [chunk.chunk_id for chunk in grounded_chunks]

        # Return grounded chunks if available, otherwise return all retrieved chunks
        # so the generate step can still use them (but mark as ungrounded)
        result_chunks = grounded_chunks if is_grounded else chunks

        return RAGContext(
            chunks=result_chunks,
            is_grounded=is_grounded,
            source_citations=citations,
        )

    async def generate(self, query: RAGQuery, context: RAGContext) -> RAGResponse:
        """Generate a response using the model router with retrieved context.

        Constructs a prompt with the retrieved chunks as context and calls the
        model router for generation. Includes chunk_id citations in the response.

        If context is not grounded, the response is marked as ungrounded and
        includes a notice that insufficient context was available.

        Args:
            query: The original RAG query.
            context: Retrieved context from the retrieve step.

        Returns:
            RAGResponse with generated content, context, grounding status, and citations.
        """
        # Build context text from chunks
        context_text = self._build_context_text(context.chunks)
        citations = context.source_citations

        # Build messages for the model
        messages = self._build_messages(query.query_text, context_text, context.is_grounded)

        # Call model router for generation
        llm_request = LLMRequest(
            messages=messages,
            task_type="rag_generation",
            complexity=TaskComplexity.MEDIUM,
            temperature=0.3,
            max_tokens=4096,
        )

        llm_response = await self._model_router.route(llm_request)

        content = llm_response.content

        # If ungrounded, prepend a notice
        if not context.is_grounded:
            content = (
                "[Notice: Insufficient context available. "
                "This response is based on general knowledge and may not reflect "
                "company-specific standards.]\n\n" + content
            )

        return RAGResponse(
            content=content,
            context=context,
            is_grounded=context.is_grounded,
            citations=citations,
        )

    async def query(self, query: RAGQuery) -> RAGResponse:
        """End-to-end RAG query: retrieve relevant context then generate a response.

        Args:
            query: RAGQuery specifying the full retrieval and generation parameters.

        Returns:
            RAGResponse with generated content, context, grounding status, and citations.
        """
        context = await self.retrieve(query)
        return await self.generate(query, context)

    # =========================================================================
    # Private retrieval methods
    # =========================================================================

    async def _dense_retrieve(self, query: RAGQuery) -> list[SearchResult]:
        """Perform dense retrieval using vector similarity search.

        Args:
            query: RAGQuery with query text, top_k, and optional metadata filter.

        Returns:
            List of SearchResult ordered by similarity score descending.
        """
        query_embedding = await self._get_query_embedding(query.query_text)

        results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=query.top_k,
            metadata_filter=query.metadata_filter,
        )

        return results

    async def _sparse_retrieve(self, query: RAGQuery) -> list[SearchResult]:
        """Perform sparse retrieval using BM25 scoring.

        Scores all indexed documents against the query and returns top_k results.
        Applies metadata filtering if specified.

        Args:
            query: RAGQuery with query text, top_k, and optional metadata filter.

        Returns:
            List of SearchResult ordered by BM25 score descending.
        """
        bm25_scores = self._bm25.score(query.query_text)

        if not bm25_scores:
            return []

        # Normalize BM25 scores to [0, 1] range for consistency
        max_score = max(bm25_scores.values()) if bm25_scores else 1.0
        if max_score == 0:
            max_score = 1.0

        # Get all documents from vector store to access content and metadata
        # For sparse retrieval, we need the stored content/metadata
        # We retrieve more than top_k to allow for metadata filtering
        all_results = await self._get_all_indexed_results(query)

        # Build a lookup from chunk_id to SearchResult
        result_lookup: dict[str, SearchResult] = {r.chunk_id: r for r in all_results}

        # Score and filter
        scored_results: list[SearchResult] = []
        for chunk_id, score in bm25_scores.items():
            if chunk_id not in result_lookup:
                continue

            result = result_lookup[chunk_id]

            # Apply metadata filter
            if query.metadata_filter and not self._matches_metadata_filter(
                result.metadata, query.metadata_filter
            ):
                continue

            normalized_score = score / max_score
            scored_results.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    content=result.content,
                    metadata=result.metadata,
                    similarity_score=normalized_score,
                )
            )

        # Sort by score descending and take top_k
        scored_results.sort(key=lambda r: r.similarity_score, reverse=True)
        return scored_results[: query.top_k]

    async def _hybrid_retrieve(self, query: RAGQuery) -> list[SearchResult]:
        """Perform hybrid retrieval combining dense and sparse results.

        Retrieves from both dense (vector) and sparse (BM25) sources,
        then merges results using weighted scoring:
        final_score = dense_weight * dense_score + sparse_weight * sparse_score

        Args:
            query: RAGQuery with query text, top_k, and optional metadata filter.

        Returns:
            List of SearchResult ordered by combined score descending.
        """
        # Retrieve from both sources (get more than top_k to allow merging)
        expanded_query = RAGQuery(
            query_text=query.query_text,
            strategy=query.strategy,
            top_k=query.top_k * 2,  # Retrieve more for better merging
            similarity_threshold=query.similarity_threshold,
            metadata_filter=query.metadata_filter,
        )

        dense_results = await self._dense_retrieve(expanded_query)
        sparse_results = await self._sparse_retrieve(expanded_query)

        # Merge results with weighted scoring
        merged_scores: dict[str, float] = {}
        result_lookup: dict[str, SearchResult] = {}

        # Add dense scores
        for result in dense_results:
            merged_scores[result.chunk_id] = self._dense_weight * result.similarity_score
            result_lookup[result.chunk_id] = result

        # Add sparse scores
        for result in sparse_results:
            sparse_contribution = self._sparse_weight * result.similarity_score
            if result.chunk_id in merged_scores:
                merged_scores[result.chunk_id] += sparse_contribution
            else:
                merged_scores[result.chunk_id] = sparse_contribution
                result_lookup[result.chunk_id] = result

        # Build final results sorted by combined score
        final_results: list[SearchResult] = []
        for chunk_id, combined_score in merged_scores.items():
            original = result_lookup[chunk_id]
            final_results.append(
                SearchResult(
                    chunk_id=original.chunk_id,
                    content=original.content,
                    metadata=original.metadata,
                    similarity_score=combined_score,
                )
            )

        final_results.sort(key=lambda r: r.similarity_score, reverse=True)
        return final_results[: query.top_k]

    # =========================================================================
    # Helper methods
    # =========================================================================

    async def _get_query_embedding(self, query_text: str) -> list[float]:
        """Get embedding vector for a query text.

        Uses the configured embedding function if available,
        otherwise returns a zero vector (for testing/fallback).

        Args:
            query_text: The text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        if self._embedding_fn is not None:
            return await self._embedding_fn(query_text)
        # Fallback: return a zero vector (should be replaced with real embedding)
        return [0.0] * 1536

    async def _get_all_indexed_results(self, query: RAGQuery) -> list[SearchResult]:
        """Get all indexed results from vector store for BM25 cross-referencing.

        Retrieves a large set of results from the vector store to provide
        content and metadata for BM25-scored chunks.

        Args:
            query: RAGQuery with optional metadata filter.

        Returns:
            List of SearchResult from the vector store.
        """
        # Use a large top_k to get all relevant documents for BM25 matching
        query_embedding = await self._get_query_embedding(query.query_text)
        results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=max(query.top_k * 10, 100),
            metadata_filter=query.metadata_filter,
        )
        return results

    def _matches_metadata_filter(
        self, metadata: dict[str, Any], filter_dict: dict[str, Any]
    ) -> bool:
        """Check if a chunk's metadata matches the specified filter criteria.

        Args:
            metadata: The chunk's metadata dictionary.
            filter_dict: Filter criteria to match against.

        Returns:
            True if all filter criteria are satisfied.
        """
        for key, value in filter_dict.items():
            if key in metadata and metadata[key] != value:
                return False
        return True

    def _build_context_text(self, chunks: list[SearchResult]) -> str:
        """Build a formatted context string from retrieved chunks.

        Args:
            chunks: List of SearchResult chunks to format.

        Returns:
            Formatted context string with chunk citations.
        """
        if not chunks:
            return ""

        context_parts: list[str] = []
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(
                f"[Source: {chunk.chunk_id}]\n{chunk.content}"
            )

        return "\n\n---\n\n".join(context_parts)

    def _build_messages(
        self, query_text: str, context_text: str, is_grounded: bool
    ) -> list[dict[str, str]]:
        """Build LLM messages with context for generation.

        Args:
            query_text: The user's query.
            context_text: Formatted context from retrieved chunks.
            is_grounded: Whether the context meets the similarity threshold.

        Returns:
            List of message dicts for the LLM request.
        """
        system_message = (
            "You are a helpful QA assistant that generates responses based on "
            "the provided context from the company knowledge base. "
            "Always cite your sources using the chunk IDs provided in [Source: ...] markers. "
            "If the context is insufficient, clearly state what information is missing."
        )

        if is_grounded and context_text:
            user_message = (
                f"Context from knowledge base:\n\n{context_text}\n\n"
                f"---\n\nQuestion: {query_text}\n\n"
                "Please answer based on the provided context and cite sources."
            )
        else:
            user_message = (
                f"Question: {query_text}\n\n"
                "Note: No sufficiently relevant context was found in the knowledge base. "
                "Please provide a general answer and clearly indicate this is not based on "
                "company-specific documentation."
            )

        return [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ]
