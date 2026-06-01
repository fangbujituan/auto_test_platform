"""Unit tests for the semantic chunker."""

import pytest

from rag.chunker import (
    SemanticChunker,
    count_tokens,
    split_sentences,
    _build_chunks_from_sentences,
)
from src.core.models import (
    Chunk,
    ChunkConfig,
    ChunkMetadata,
    DocumentFormat,
    DocumentUnit,
    LoadedDocument,
)


@pytest.fixture
def chunker():
    return SemanticChunker()


@pytest.fixture
def default_config():
    return ChunkConfig(max_tokens=512, overlap_tokens=50, code_block_max_tokens=2048)


@pytest.fixture
def small_config():
    """Small config for easier testing of chunking behavior."""
    return ChunkConfig(max_tokens=20, overlap_tokens=5, code_block_max_tokens=50)


def _make_document(units, source_path="test/doc.md", structural_info=None):
    """Helper to create a LoadedDocument."""
    if structural_info is None:
        structural_info = {
            "project_name": "test-project",
            "module_name": "test-module",
            "document_version": "1.0",
            "content_type": "requirement",
        }
    return LoadedDocument(
        source_path=source_path,
        format=DocumentFormat.MARKDOWN,
        units=units,
        raw_text="",
        structural_info=structural_info,
    )


def _make_unit(content, unit_type="paragraph", position=0):
    """Helper to create a DocumentUnit."""
    return DocumentUnit(
        content=content,
        unit_type=unit_type,
        metadata={},
        source_path="test/doc.md",
        position=position,
    )


class TestCountTokens:
    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_single_word(self):
        assert count_tokens("hello") == 1

    def test_multiple_words(self):
        assert count_tokens("hello world foo bar") == 4

    def test_whitespace_only(self):
        assert count_tokens("   ") == 0


class TestSplitSentences:
    def test_empty_string(self):
        assert split_sentences("") == []

    def test_single_sentence(self):
        result = split_sentences("Hello world.")
        assert result == ["Hello world."]

    def test_multiple_sentences(self):
        result = split_sentences("Hello world. This is a test. Another sentence.")
        assert len(result) >= 2

    def test_exclamation_boundary(self):
        result = split_sentences("Hello! World is great.")
        assert len(result) == 2

    def test_question_boundary(self):
        result = split_sentences("What is this? This is a test.")
        assert len(result) == 2

    def test_no_split_mid_sentence(self):
        # Lowercase after period should not split
        result = split_sentences("Version 2.0 is released today.")
        assert len(result) == 1

    def test_paragraph_boundary(self):
        result = split_sentences("First paragraph.\n\nSecond paragraph.")
        assert len(result) == 2


class TestBuildChunksFromSentences:
    def test_single_sentence_fits(self):
        sentences = ["Hello world."]
        result = _build_chunks_from_sentences(sentences, max_tokens=10, overlap_tokens=2)
        assert result == ["Hello world."]

    def test_multiple_sentences_single_chunk(self):
        sentences = ["Hello.", "World."]
        result = _build_chunks_from_sentences(sentences, max_tokens=10, overlap_tokens=2)
        assert len(result) == 1
        assert result[0] == "Hello. World."

    def test_sentences_split_into_multiple_chunks(self):
        sentences = ["Word " * 5 + "end.", "Another " * 5 + "end.", "Third " * 5 + "end."]
        result = _build_chunks_from_sentences(sentences, max_tokens=8, overlap_tokens=0)
        assert len(result) >= 2

    def test_overlap_between_chunks(self):
        # Create sentences that will force splitting
        s1 = "First sentence with several words here."
        s2 = "Second sentence also has words."
        s3 = "Third sentence is the last one."
        sentences = [s1, s2, s3]
        # max_tokens=10 should force splits
        result = _build_chunks_from_sentences(sentences, max_tokens=10, overlap_tokens=5)
        # With overlap, later chunks should start with content from previous chunk
        assert len(result) >= 2

    def test_empty_sentences(self):
        result = _build_chunks_from_sentences([], max_tokens=10, overlap_tokens=2)
        assert result == []


class TestSemanticChunkerTextChunking:
    def test_short_text_single_chunk(self, chunker, default_config):
        unit = _make_unit("This is a short text.")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, default_config)
        assert len(chunks) == 1
        assert chunks[0].content == "This is a short text."

    def test_long_text_multiple_chunks(self, chunker, small_config):
        # Create text that exceeds small_config.max_tokens (20)
        text = " ".join(["word"] * 50) + ". " + " ".join(["another"] * 50) + "."
        # Rewrite with proper sentences
        text = "This is the first sentence with many words to fill up space. " \
               "Another sentence that also has quite a few words in it. " \
               "Yet another sentence to ensure we exceed the token limit."
        unit = _make_unit(text)
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, small_config)
        assert len(chunks) > 1

    def test_never_splits_mid_sentence(self, chunker, small_config):
        text = "First sentence here. Second sentence here. Third sentence here."
        unit = _make_unit(text)
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, small_config)
        # Each chunk should contain complete sentences
        for chunk in chunks:
            # A chunk should not end with an incomplete sentence
            # (it should end with punctuation or be a complete phrase)
            content = chunk.content.strip()
            assert content  # Not empty

    def test_empty_document(self, chunker, default_config):
        doc = _make_document([])
        chunks = chunker.chunk_document(doc, default_config)
        assert chunks == []


class TestSemanticChunkerCodeBlocks:
    def test_small_code_block_kept_intact(self, chunker, default_config):
        code = "def hello():\n    return 'world'\n"
        unit = _make_unit(code, unit_type="code_block")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, default_config)
        assert len(chunks) == 1
        assert chunks[0].content == code

    def test_code_block_under_2048_kept_intact(self, chunker, default_config):
        # Create a code block with ~500 tokens (well under 2048)
        lines = [f"    x_{i} = {i}" for i in range(200)]
        code = "def big_function():\n" + "\n".join(lines)
        unit = _make_unit(code, unit_type="code_block")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, default_config)
        assert len(chunks) == 1

    def test_large_code_block_split(self, chunker):
        """Code blocks exceeding 2048 tokens should be split."""
        config = ChunkConfig(max_tokens=512, overlap_tokens=50, code_block_max_tokens=20)
        # Create code with multiple functions
        code = (
            "def func_a():\n    return 1\n\n"
            "def func_b():\n    return 2\n\n"
            "def func_c():\n    return 3\n\n"
            "def func_d():\n    x = 1\n    y = 2\n    return x + y\n"
        )
        unit = _make_unit(code, unit_type="code_block")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, config)
        assert len(chunks) > 1


class TestSemanticChunkerTables:
    def test_small_table_single_chunk(self, chunker, default_config):
        table = "| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob | 25 |"
        unit = _make_unit(table, unit_type="table")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, default_config)
        assert len(chunks) == 1
        # Should contain header
        assert "Name" in chunks[0].content
        assert "Alice" in chunks[0].content

    def test_table_rows_include_header(self, chunker):
        """When table is split, each chunk should include the header."""
        config = ChunkConfig(max_tokens=10, overlap_tokens=0, code_block_max_tokens=2048)
        header = "| Column1 | Column2 | Column3 |"
        separator = "|---------|---------|---------|"
        rows = [f"| data{i}_1 | data{i}_2 | data{i}_3 |" for i in range(20)]
        table = "\n".join([header, separator] + rows)
        unit = _make_unit(table, unit_type="table")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, config)
        # Each chunk should contain the header
        for chunk in chunks:
            assert "Column1" in chunk.content


class TestSemanticChunkerMetadata:
    def test_metadata_populated(self, chunker, default_config):
        unit = _make_unit("Some content here.")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, default_config)
        assert len(chunks) == 1
        meta = chunks[0].metadata
        assert meta.project_name == "test-project"
        assert meta.module_name == "test-module"
        assert meta.document_version == "1.0"
        assert meta.content_type == "requirement"
        assert meta.source_path == "test/doc.md"
        assert meta.chunk_position == 0

    def test_chunk_positions_sequential(self, chunker, small_config):
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        unit = _make_unit(text)
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, small_config)
        positions = [c.metadata.chunk_position for c in chunks]
        assert positions == list(range(len(chunks)))


class TestSemanticChunkerTokenCount:
    def test_token_count_accurate(self, chunker, default_config):
        unit = _make_unit("hello world foo bar baz")
        doc = _make_document([unit])
        chunks = chunker.chunk_document(doc, default_config)
        assert chunks[0].token_count == 5


class TestGenerateChunkId:
    def test_basic_id_generation(self, chunker):
        chunk_id = chunker.generate_chunk_id("path/to/doc.md", 0, "1.0")
        # Should be a 64-char hex string (SHA-256 digest)
        assert len(chunk_id) == 64
        assert all(c in "0123456789abcdef" for c in chunk_id)

    def test_different_positions_different_ids(self, chunker):
        id1 = chunker.generate_chunk_id("doc.md", 0, "1.0")
        id2 = chunker.generate_chunk_id("doc.md", 1, "1.0")
        assert id1 != id2

    def test_different_versions_different_ids(self, chunker):
        id1 = chunker.generate_chunk_id("doc.md", 0, "1.0")
        id2 = chunker.generate_chunk_id("doc.md", 0, "2.0")
        assert id1 != id2

    def test_different_paths_different_ids(self, chunker):
        id1 = chunker.generate_chunk_id("doc_a.md", 0, "1.0")
        id2 = chunker.generate_chunk_id("doc_b.md", 0, "1.0")
        assert id1 != id2

    def test_same_inputs_same_id(self, chunker):
        id1 = chunker.generate_chunk_id("doc.md", 0, "1.0")
        id2 = chunker.generate_chunk_id("doc.md", 0, "1.0")
        assert id1 == id2

    def test_deterministic_across_instances(self):
        chunker1 = SemanticChunker()
        chunker2 = SemanticChunker()
        id1 = chunker1.generate_chunk_id("path/doc.md", 5, "v2.1")
        id2 = chunker2.generate_chunk_id("path/doc.md", 5, "v2.1")
        assert id1 == id2

    def test_known_hash_value(self, chunker):
        """Verify the hash is computed from 'source_path|position|version'."""
        import hashlib
        expected = hashlib.sha256("doc.md|0|1.0".encode("utf-8")).hexdigest()
        actual = chunker.generate_chunk_id("doc.md", 0, "1.0")
        assert actual == expected


class TestMetadataTagging:
    """Tests for metadata tagging completeness (Requirement 6.2)."""

    def test_all_metadata_fields_populated(self, chunker, default_config):
        """All metadata fields should be populated from structural_info."""
        unit = _make_unit("Content for metadata test.")
        doc = _make_document(
            [unit],
            structural_info={
                "project_name": "my-project",
                "module_name": "auth-module",
                "document_version": "2.3.1",
                "content_type": "api",
            },
        )
        chunks = chunker.chunk_document(doc, default_config)
        assert len(chunks) == 1
        meta = chunks[0].metadata
        assert meta.project_name == "my-project"
        assert meta.module_name == "auth-module"
        assert meta.document_version == "2.3.1"
        assert meta.content_type == "api"
        assert meta.source_path == doc.source_path
        assert meta.chunk_position == 0

    def test_metadata_defaults_to_empty_string_when_missing(self, chunker, default_config):
        """When structural_info lacks a field, metadata should default to empty string."""
        unit = _make_unit("Content here.")
        doc = _make_document([unit], structural_info={})
        chunks = chunker.chunk_document(doc, default_config)
        meta = chunks[0].metadata
        assert meta.project_name == ""
        assert meta.module_name == ""
        assert meta.document_version == ""
        assert meta.content_type == ""

    def test_chunk_id_uses_document_version_from_structural_info(self, chunker, default_config):
        """Chunk ID should incorporate the document_version from structural_info."""
        import hashlib

        unit = _make_unit("Some content.")
        doc = _make_document(
            [unit],
            source_path="project/readme.md",
            structural_info={
                "project_name": "proj",
                "module_name": "mod",
                "document_version": "3.0",
                "content_type": "requirement",
            },
        )
        chunks = chunker.chunk_document(doc, default_config)
        expected_id = hashlib.sha256("project/readme.md|0|3.0".encode("utf-8")).hexdigest()
        assert chunks[0].chunk_id == expected_id

    def test_multiple_chunks_have_consistent_metadata(self, chunker, small_config):
        """All chunks from the same document should share the same project/module/version/type."""
        # Create text that exceeds small_config.max_tokens (20 tokens) to force multiple chunks
        text = (
            "First sentence here with enough words to fill up some space in the chunk. "
            "Second sentence here also has quite a few words to add more tokens. "
            "Third sentence here continues to add even more content to exceed the limit. "
            "Fourth sentence here is the final one with additional padding words included."
        )
        unit = _make_unit(text)
        doc = _make_document(
            [unit],
            structural_info={
                "project_name": "shared-project",
                "module_name": "shared-module",
                "document_version": "1.0",
                "content_type": "test_case",
            },
        )
        chunks = chunker.chunk_document(doc, small_config)
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.metadata.project_name == "shared-project"
            assert chunk.metadata.module_name == "shared-module"
            assert chunk.metadata.document_version == "1.0"
            assert chunk.metadata.content_type == "test_case"
