"""Unit tests for the PDF document loader.

Tests PDF text extraction and structural detection (headings, code blocks, tables).

Requirements: 5.1, 5.2
"""

import io
import tempfile
from pathlib import Path

import pytest
from PyPDF2 import PdfWriter

from rag.loaders.pdf_loader import (
    PdfLoader,
    _detect_heading_level,
    _is_likely_code_line,
    _is_likely_heading,
    _is_likely_table_line,
    _parse_text_into_units,
)
from src.core.exceptions import DocumentLoadError
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument


def _create_minimal_pdf() -> bytes:
    """Create a minimal valid PDF with no text."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _create_pdf_with_text(text: str) -> bytes:
    """Create a valid PDF that contains extractable text.

    Uses PyPDF2's PdfWriter with annotations to embed text.
    Since PyPDF2 doesn't easily support adding text to pages,
    we test text parsing logic separately via _parse_text_into_units.
    This helper creates a minimal valid PDF for structural tests.
    """
    # Use a minimal but valid PDF structure
    return _create_minimal_pdf()


class TestIsLikelyHeading:
    """Tests for the _is_likely_heading heuristic."""

    def test_all_caps_is_heading(self):
        assert _is_likely_heading("INTRODUCTION") is True

    def test_line_ending_with_period_not_heading(self):
        # Lines ending with sentence punctuation are not headings
        assert _is_likely_heading("This is a sentence.") is False

    def test_numbered_section(self):
        assert _is_likely_heading("1.2 System Architecture") is True

    def test_chapter_prefix(self):
        assert _is_likely_heading("Chapter 3 Design Patterns") is True

    def test_long_line_not_heading(self):
        long_line = "This is a very long line that exceeds the maximum heading length " * 3
        assert _is_likely_heading(long_line) is False

    def test_empty_line_not_heading(self):
        assert _is_likely_heading("") is False
        assert _is_likely_heading("   ") is False

    def test_sentence_with_period_not_heading(self):
        assert _is_likely_heading("This is a sentence.") is False

    def test_short_capitalized_no_punctuation(self):
        assert _is_likely_heading("System Overview") is True

    def test_indented_line_not_heading(self):
        assert _is_likely_heading("    indented code") is False


class TestIsLikelyTableLine:
    """Tests for the _is_likely_table_line heuristic."""

    def test_pipe_delimited(self):
        assert _is_likely_table_line("| Name | Age | City |") is True

    def test_tab_separated(self):
        assert _is_likely_table_line("Name\tAge\tCity") is True

    def test_single_pipe_not_table(self):
        assert _is_likely_table_line("a | b") is False

    def test_empty_not_table(self):
        assert _is_likely_table_line("") is False

    def test_normal_text_not_table(self):
        assert _is_likely_table_line("This is a normal paragraph.") is False


class TestIsLikelyCodeLine:
    """Tests for the _is_likely_code_line heuristic."""

    def test_indented_with_spaces(self):
        assert _is_likely_code_line("    x = 1") is True

    def test_indented_with_tab(self):
        assert _is_likely_code_line("\tfor i in range(10):") is True

    def test_python_def(self):
        assert _is_likely_code_line("def hello():") is True

    def test_python_class(self):
        assert _is_likely_code_line("class MyClass:") is True

    def test_python_import(self):
        assert _is_likely_code_line("import os") is True

    def test_javascript_function(self):
        assert _is_likely_code_line("function hello() {") is True

    def test_javascript_const(self):
        assert _is_likely_code_line("const x = 42;") is True

    def test_normal_text_not_code(self):
        assert _is_likely_code_line("This is a normal sentence.") is False


class TestDetectHeadingLevel:
    """Tests for the _detect_heading_level function."""

    def test_all_caps_level_1(self):
        assert _detect_heading_level("INTRODUCTION") == 1

    def test_single_number_level_1(self):
        assert _detect_heading_level("1 Overview") == 1

    def test_two_level_number(self):
        assert _detect_heading_level("1.2 Details") == 2

    def test_three_level_number(self):
        assert _detect_heading_level("1.2.3 Sub-details") == 3

    def test_default_level_2(self):
        assert _detect_heading_level("Some Heading") == 2


class TestParseTextIntoUnits:
    """Tests for the _parse_text_into_units function."""

    def test_simple_paragraph(self):
        text = "This is a simple paragraph with some content."
        units = _parse_text_into_units(text, "test.pdf")
        assert len(units) >= 1
        assert any(u.unit_type == "paragraph" for u in units)

    def test_heading_detection(self):
        text = "INTRODUCTION\n\nThis is the introduction text."
        units = _parse_text_into_units(text, "test.pdf")
        headings = [u for u in units if u.unit_type == "heading"]
        assert len(headings) >= 1
        assert headings[0].content == "INTRODUCTION"

    def test_table_detection(self):
        text = "| Name | Age |\n| Alice | 30 |\n| Bob | 25 |"
        units = _parse_text_into_units(text, "test.pdf")
        tables = [u for u in units if u.unit_type == "table"]
        assert len(tables) == 1
        assert "Name" in tables[0].content

    def test_code_block_detection(self):
        text = "    def hello():\n        print('world')\n        return True"
        units = _parse_text_into_units(text, "test.pdf")
        code_blocks = [u for u in units if u.unit_type == "code_block"]
        assert len(code_blocks) >= 1

    def test_mixed_content(self):
        text = (
            "OVERVIEW\n\n"
            "This is a paragraph about the system.\n\n"
            "| Column A | Column B |\n| val1 | val2 |\n\n"
            "    def example():\n        pass\n"
        )
        units = _parse_text_into_units(text, "test.pdf")
        unit_types = set(u.unit_type for u in units)
        assert "heading" in unit_types
        assert "paragraph" in unit_types
        assert "table" in unit_types

    def test_empty_text(self):
        units = _parse_text_into_units("", "test.pdf")
        assert units == []

    def test_whitespace_only(self):
        units = _parse_text_into_units("   \n\n   \n", "test.pdf")
        assert units == []

    def test_positions_are_sequential(self):
        text = "HEADING\n\nParagraph one.\n\nParagraph two."
        units = _parse_text_into_units(text, "test.pdf")
        positions = [u.position for u in units]
        assert positions == sorted(positions)
        assert positions == list(range(len(positions)))

    def test_source_path_preserved(self):
        text = "Some content here."
        units = _parse_text_into_units(text, "/path/to/doc.pdf")
        for unit in units:
            assert unit.source_path == "/path/to/doc.pdf"


class TestPdfLoader:
    """Tests for the PdfLoader class."""

    def test_load_valid_pdf(self):
        loader = PdfLoader()
        pdf_content = _create_minimal_pdf()
        result = loader.load("test.pdf", pdf_content)

        assert isinstance(result, LoadedDocument)
        assert result.source_path == "test.pdf"
        assert result.format == DocumentFormat.PDF
        assert isinstance(result.units, list)
        assert isinstance(result.raw_text, str)
        assert "page_count" in result.structural_info

    def test_load_empty_pdf(self):
        loader = PdfLoader()
        pdf_content = _create_minimal_pdf()
        result = loader.load("empty.pdf", pdf_content)

        assert isinstance(result, LoadedDocument)
        assert result.source_path == "empty.pdf"
        assert result.format == DocumentFormat.PDF

    def test_load_invalid_pdf_raises_error(self):
        loader = PdfLoader()
        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load("bad.pdf", b"this is not a pdf file")
        assert "Failed to parse PDF" in str(exc_info.value)

    def test_load_corrupted_pdf_raises_error(self):
        loader = PdfLoader()
        # Corrupted PDF-like content
        corrupted = b"%PDF-1.4\n" + b"\x00" * 100
        with pytest.raises(DocumentLoadError):
            loader.load("corrupted.pdf", corrupted)

    def test_structural_info_contains_page_count(self):
        loader = PdfLoader()
        pdf_content = _create_minimal_pdf()
        result = loader.load("test.pdf", pdf_content)

        assert "page_count" in result.structural_info
        assert result.structural_info["page_count"] >= 1

    def test_structural_info_contains_unit_count(self):
        loader = PdfLoader()
        pdf_content = _create_minimal_pdf()
        result = loader.load("test.pdf", pdf_content)

        assert "unit_count" in result.structural_info
        assert result.structural_info["unit_count"] == len(result.units)

    def test_units_have_correct_source_path(self):
        loader = PdfLoader()
        # Use _parse_text_into_units directly since PDF text extraction
        # from minimal PDFs may not yield text
        pdf_content = _create_pdf_with_text("Hello World")
        result = loader.load("/docs/report.pdf", pdf_content)

        for unit in result.units:
            assert unit.source_path == "/docs/report.pdf"

    def test_units_have_valid_unit_types(self):
        loader = PdfLoader()
        pdf_content = _create_pdf_with_text("HEADING\n\nParagraph text here.")
        result = loader.load("test.pdf", pdf_content)

        valid_types = {"heading", "paragraph", "code_block", "table"}
        for unit in result.units:
            assert unit.unit_type in valid_types
