"""Unit tests for the Markdown document loader.

Tests structural preservation of headings, code blocks, tables, and paragraphs.
Requirements: 5.1, 5.2
"""

import pytest

from rag.loaders.markdown_loader import MarkdownLoader
from src.core.models import DocumentFormat, DocumentUnit


@pytest.fixture
def loader() -> MarkdownLoader:
    return MarkdownLoader()


class TestMarkdownLoaderBasic:
    """Test basic Markdown loading functionality."""

    def test_load_empty_document(self, loader: MarkdownLoader):
        content = b""
        doc = loader.load("test.md", content)

        assert doc.source_path == "test.md"
        assert doc.format == DocumentFormat.MARKDOWN
        assert doc.units == []
        assert doc.raw_text == ""

    def test_load_simple_paragraph(self, loader: MarkdownLoader):
        content = b"This is a simple paragraph."
        doc = loader.load("test.md", content)

        assert len(doc.units) == 1
        assert doc.units[0].unit_type == "paragraph"
        assert doc.units[0].content == "This is a simple paragraph."
        assert doc.units[0].position == 0

    def test_load_preserves_source_path(self, loader: MarkdownLoader):
        content = b"# Hello"
        doc = loader.load("/path/to/doc.md", content)

        assert doc.source_path == "/path/to/doc.md"
        for unit in doc.units:
            assert unit.source_path == "/path/to/doc.md"


class TestHeadingParsing:
    """Test heading extraction and hierarchy."""

    def test_h1_heading(self, loader: MarkdownLoader):
        content = b"# Main Title"
        doc = loader.load("test.md", content)

        assert len(doc.units) == 1
        unit = doc.units[0]
        assert unit.unit_type == "heading"
        assert unit.content == "# Main Title"
        assert unit.metadata["heading_level"] == 1
        assert unit.metadata["heading_text"] == "Main Title"

    def test_h2_through_h6_headings(self, loader: MarkdownLoader):
        content = b"## Level 2\n### Level 3\n#### Level 4\n##### Level 5\n###### Level 6"
        doc = loader.load("test.md", content)

        assert len(doc.units) == 5
        for i, unit in enumerate(doc.units):
            assert unit.unit_type == "heading"
            assert unit.metadata["heading_level"] == i + 2

    def test_heading_hierarchy_in_structural_info(self, loader: MarkdownLoader):
        content = b"# Title\n## Section 1\n### Subsection 1.1\n## Section 2"
        doc = loader.load("test.md", content)

        hierarchy = doc.structural_info["heading_hierarchy"]
        assert len(hierarchy) == 4
        assert hierarchy[0] == {"level": 1, "text": "Title", "position": 0}
        assert hierarchy[1] == {"level": 2, "text": "Section 1", "position": 1}
        assert hierarchy[2] == {"level": 3, "text": "Subsection 1.1", "position": 2}
        assert hierarchy[3] == {"level": 2, "text": "Section 2", "position": 3}

    def test_heading_with_inline_formatting(self, loader: MarkdownLoader):
        content = b"# Title with **bold** and `code`"
        doc = loader.load("test.md", content)

        assert doc.units[0].unit_type == "heading"
        assert doc.units[0].metadata["heading_text"] == "Title with **bold** and `code`"


class TestCodeBlockParsing:
    """Test fenced code block extraction."""

    def test_simple_code_block(self, loader: MarkdownLoader):
        content = b"```\nprint('hello')\n```"
        doc = loader.load("test.md", content)

        assert len(doc.units) == 1
        unit = doc.units[0]
        assert unit.unit_type == "code_block"
        assert unit.content == "print('hello')"
        assert unit.metadata["language"] == ""

    def test_code_block_with_language(self, loader: MarkdownLoader):
        content = b"```python\ndef hello():\n    return 'world'\n```"
        doc = loader.load("test.md", content)

        assert len(doc.units) == 1
        unit = doc.units[0]
        assert unit.unit_type == "code_block"
        assert unit.metadata["language"] == "python"
        assert "def hello():" in unit.content

    def test_multiple_code_blocks(self, loader: MarkdownLoader):
        content = b"```javascript\nconst x = 1;\n```\n\nSome text\n\n```python\ny = 2\n```"
        doc = loader.load("test.md", content)

        code_blocks = [u for u in doc.units if u.unit_type == "code_block"]
        assert len(code_blocks) == 2
        assert code_blocks[0].metadata["language"] == "javascript"
        assert code_blocks[1].metadata["language"] == "python"

    def test_code_block_preserves_content(self, loader: MarkdownLoader):
        code = "def foo():\n    # A comment\n    if True:\n        pass"
        content = f"```python\n{code}\n```".encode()
        doc = loader.load("test.md", content)

        assert doc.units[0].content == code

    def test_code_block_with_markdown_inside(self, loader: MarkdownLoader):
        """Code blocks should not parse Markdown syntax inside them."""
        content = b"```\n# This is not a heading\n| not | a | table |\n```"
        doc = loader.load("test.md", content)

        assert len(doc.units) == 1
        assert doc.units[0].unit_type == "code_block"
        assert "# This is not a heading" in doc.units[0].content


class TestTableParsing:
    """Test table extraction."""

    def test_simple_table(self, loader: MarkdownLoader):
        content = b"| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob | 25 |"
        doc = loader.load("test.md", content)

        tables = [u for u in doc.units if u.unit_type == "table"]
        assert len(tables) == 1
        table = tables[0]
        assert "| Name | Age |" in table.content
        assert "| Alice | 30 |" in table.content
        assert table.metadata["has_header"] is True
        assert table.metadata["row_count"] == 3  # header + 2 data rows

    def test_table_without_separator(self, loader: MarkdownLoader):
        content = b"| Col1 | Col2 |\n| val1 | val2 |"
        doc = loader.load("test.md", content)

        tables = [u for u in doc.units if u.unit_type == "table"]
        assert len(tables) == 1
        assert tables[0].metadata["has_header"] is False

    def test_table_between_paragraphs(self, loader: MarkdownLoader):
        content = b"Before table\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\nAfter table"
        doc = loader.load("test.md", content)

        types = [u.unit_type for u in doc.units]
        assert "paragraph" in types
        assert "table" in types


class TestParagraphParsing:
    """Test paragraph extraction."""

    def test_multi_line_paragraph(self, loader: MarkdownLoader):
        content = b"Line one of paragraph.\nLine two of paragraph."
        doc = loader.load("test.md", content)

        assert len(doc.units) == 1
        assert doc.units[0].unit_type == "paragraph"
        assert "Line one" in doc.units[0].content
        assert "Line two" in doc.units[0].content

    def test_paragraphs_separated_by_blank_lines(self, loader: MarkdownLoader):
        content = b"First paragraph.\n\nSecond paragraph."
        doc = loader.load("test.md", content)

        paragraphs = [u for u in doc.units if u.unit_type == "paragraph"]
        assert len(paragraphs) == 2
        assert paragraphs[0].content == "First paragraph."
        assert paragraphs[1].content == "Second paragraph."


class TestMixedContent:
    """Test documents with mixed content types."""

    def test_full_document(self, loader: MarkdownLoader):
        content = (
            b"# Project README\n\n"
            b"This is the introduction.\n\n"
            b"## Installation\n\n"
            b"Run the following:\n\n"
            b"```bash\npip install mypackage\n```\n\n"
            b"## API Reference\n\n"
            b"| Method | Path |\n|--------|------|\n| GET | /api/v1 |\n\n"
            b"That's all."
        )
        doc = loader.load("README.md", content)

        types = [u.unit_type for u in doc.units]
        assert "heading" in types
        assert "paragraph" in types
        assert "code_block" in types
        assert "table" in types

        # Check sequential positions
        for i, unit in enumerate(doc.units):
            assert unit.position == i

    def test_sequential_positions(self, loader: MarkdownLoader):
        content = b"# H1\n\nParagraph\n\n```\ncode\n```"
        doc = loader.load("test.md", content)

        positions = [u.position for u in doc.units]
        assert positions == list(range(len(doc.units)))

    def test_structural_info_unit_type_counts(self, loader: MarkdownLoader):
        content = b"# H1\n## H2\n\nPara\n\n```\ncode\n```"
        doc = loader.load("test.md", content)

        counts = doc.structural_info["unit_type_counts"]
        assert counts.get("heading", 0) == 2
        assert counts.get("paragraph", 0) == 1
        assert counts.get("code_block", 0) == 1

    def test_total_units_in_structural_info(self, loader: MarkdownLoader):
        content = b"# Title\n\nParagraph\n\n## Section"
        doc = loader.load("test.md", content)

        assert doc.structural_info["total_units"] == len(doc.units)


class TestEdgeCases:
    """Test edge cases and encoding."""

    def test_utf8_content(self, loader: MarkdownLoader):
        content = "# 中文标题\n\n这是一段中文内容。".encode("utf-8")
        doc = loader.load("test.md", content)

        assert doc.units[0].unit_type == "heading"
        assert doc.units[0].metadata["heading_text"] == "中文标题"

    def test_invalid_utf8_handled_gracefully(self, loader: MarkdownLoader):
        # Invalid UTF-8 bytes should be handled with replacement
        content = b"# Title\n\nSome text with \xff\xfe invalid bytes"
        doc = loader.load("test.md", content)

        assert doc.source_path == "test.md"
        assert len(doc.units) > 0

    def test_only_whitespace(self, loader: MarkdownLoader):
        content = b"   \n\n   \n"
        doc = loader.load("test.md", content)

        assert doc.units == []

    def test_heading_without_space_not_parsed(self, loader: MarkdownLoader):
        """'#NoSpace' should not be treated as a heading."""
        content = b"#NoSpace"
        doc = loader.load("test.md", content)

        # Should be treated as paragraph, not heading
        if doc.units:
            assert doc.units[0].unit_type == "paragraph"
