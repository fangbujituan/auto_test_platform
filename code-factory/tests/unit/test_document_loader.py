"""Unit tests for the Document Loader base implementation.

Tests format detection, unsupported format rejection, and error handling
for corrupted/unreadable files.

Requirements: 5.1, 5.5, 5.6
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rag.document_loader import (
    EXTENSION_FORMAT_MAP,
    SUPPORTED_FORMATS_DESCRIPTION,
    DocumentLoader,
    FormatLoader,
)
from src.core.exceptions import DocumentLoadError, UnsupportedFormatError
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument


class FakeFormatLoader(FormatLoader):
    """A fake format loader for testing delegation."""

    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        return LoadedDocument(
            source_path=file_path,
            format=DocumentFormat.MARKDOWN,
            units=[
                DocumentUnit(
                    content=content.decode("utf-8"),
                    unit_type="heading",
                    metadata={},
                    source_path=file_path,
                    position=0,
                )
            ],
            raw_text=content.decode("utf-8"),
            structural_info={},
        )


class ErrorFormatLoader(FormatLoader):
    """A format loader that raises an exception during parsing."""

    def load(self, file_path: str, content: bytes) -> LoadedDocument:
        raise ValueError("Simulated parsing error")


class TestSupportsFormat:
    """Tests for DocumentLoader.supports_format()"""

    def test_supported_pdf(self):
        loader = DocumentLoader()
        assert loader.supports_format("document.pdf") is True

    def test_supported_markdown_md(self):
        loader = DocumentLoader()
        assert loader.supports_format("readme.md") is True

    def test_supported_markdown_full(self):
        loader = DocumentLoader()
        assert loader.supports_format("notes.markdown") is True

    def test_supported_word(self):
        loader = DocumentLoader()
        assert loader.supports_format("report.docx") is True

    def test_supported_json(self):
        loader = DocumentLoader()
        assert loader.supports_format("api.json") is True

    def test_supported_yaml(self):
        loader = DocumentLoader()
        assert loader.supports_format("openapi.yaml") is True

    def test_supported_yml(self):
        loader = DocumentLoader()
        assert loader.supports_format("spec.yml") is True

    def test_supported_python(self):
        loader = DocumentLoader()
        assert loader.supports_format("module.py") is True

    def test_supported_java(self):
        loader = DocumentLoader()
        assert loader.supports_format("Main.java") is True

    def test_supported_javascript(self):
        loader = DocumentLoader()
        assert loader.supports_format("app.js") is True

    def test_supported_typescript(self):
        loader = DocumentLoader()
        assert loader.supports_format("component.ts") is True

    def test_unsupported_txt(self):
        loader = DocumentLoader()
        assert loader.supports_format("notes.txt") is False

    def test_unsupported_csv(self):
        loader = DocumentLoader()
        assert loader.supports_format("data.csv") is False

    def test_unsupported_no_extension(self):
        loader = DocumentLoader()
        assert loader.supports_format("Makefile") is False

    def test_unsupported_html(self):
        loader = DocumentLoader()
        assert loader.supports_format("page.html") is False

    def test_case_insensitive_extension(self):
        loader = DocumentLoader()
        assert loader.supports_format("README.MD") is True

    def test_path_with_directories(self):
        loader = DocumentLoader()
        assert loader.supports_format("/path/to/docs/readme.md") is True


class TestDetectFormat:
    """Tests for DocumentLoader.detect_format()"""

    def test_detect_pdf(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.pdf") == DocumentFormat.PDF

    def test_detect_markdown(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.md") == DocumentFormat.MARKDOWN

    def test_detect_markdown_full(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.markdown") == DocumentFormat.MARKDOWN

    def test_detect_word(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.docx") == DocumentFormat.WORD

    def test_detect_json(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.json") == DocumentFormat.SWAGGER_JSON

    def test_detect_yaml(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.yaml") == DocumentFormat.SWAGGER_YAML

    def test_detect_yml(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.yml") == DocumentFormat.SWAGGER_YAML

    def test_detect_python(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.py") == DocumentFormat.PYTHON

    def test_detect_java(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.java") == DocumentFormat.JAVA

    def test_detect_javascript(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.js") == DocumentFormat.JAVASCRIPT

    def test_detect_typescript(self):
        loader = DocumentLoader()
        assert loader.detect_format("file.ts") == DocumentFormat.TYPESCRIPT

    def test_detect_unsupported_raises_error(self):
        loader = DocumentLoader()
        with pytest.raises(UnsupportedFormatError) as exc_info:
            loader.detect_format("file.txt")
        assert "file.txt" in str(exc_info.value)
        assert exc_info.value.supported_formats == SUPPORTED_FORMATS_DESCRIPTION

    def test_detect_unsupported_includes_supported_list(self):
        loader = DocumentLoader()
        with pytest.raises(UnsupportedFormatError) as exc_info:
            loader.detect_format("data.csv")
        # Verify the error includes the list of supported formats
        assert exc_info.value.file_path == "data.csv"
        assert len(exc_info.value.supported_formats) > 0


class TestLoad:
    """Tests for DocumentLoader.load()"""

    def test_load_unsupported_format_raises_error(self):
        loader = DocumentLoader()
        with pytest.raises(UnsupportedFormatError) as exc_info:
            loader.load("file.txt")
        assert "file.txt" in str(exc_info.value)

    def test_load_nonexistent_file_raises_document_load_error(self):
        loader = DocumentLoader()
        # Register a loader so format detection passes
        loader.register_format_loader(DocumentFormat.MARKDOWN, FakeFormatLoader())
        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load("/nonexistent/path/file.md")
        assert "Failed to read file" in str(exc_info.value)

    def test_load_directory_raises_document_load_error(self, tmp_path):
        loader = DocumentLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, FakeFormatLoader())
        # tmp_path is a directory, not a file
        dir_path = str(tmp_path / "somedir.md")
        os.makedirs(dir_path)
        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load(dir_path)
        assert "Failed to read file" in str(exc_info.value)

    def test_load_with_registered_loader_succeeds(self, tmp_path):
        # Create a temporary markdown file
        md_file = tmp_path / "test.md"
        md_file.write_text("# Hello World\n\nSome content here.")

        loader = DocumentLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, FakeFormatLoader())

        result = loader.load(str(md_file))

        assert isinstance(result, LoadedDocument)
        assert result.source_path == str(md_file)
        assert result.format == DocumentFormat.MARKDOWN
        assert len(result.units) == 1
        assert "Hello World" in result.raw_text

    def test_load_without_registered_loader_raises_error(self, tmp_path):
        # Create a temporary file with supported extension but no registered loader
        py_file = tmp_path / "module.py"
        py_file.write_text("def hello(): pass")

        loader = DocumentLoader()
        # Don't register any loader for PYTHON format

        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load(str(py_file))
        assert "No loader registered" in str(exc_info.value)

    def test_load_format_loader_raises_exception(self, tmp_path):
        # Create a temporary file
        md_file = tmp_path / "broken.md"
        md_file.write_text("some content")

        loader = DocumentLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, ErrorFormatLoader())

        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load(str(md_file))
        assert "Error parsing file" in str(exc_info.value)
        assert "Simulated parsing error" in str(exc_info.value)

    def test_load_permission_denied(self, tmp_path):
        # Create a file and remove read permissions
        restricted_file = tmp_path / "restricted.md"
        restricted_file.write_text("secret content")
        restricted_file.chmod(0o000)

        loader = DocumentLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, FakeFormatLoader())

        try:
            with pytest.raises(DocumentLoadError) as exc_info:
                loader.load(str(restricted_file))
            assert "Failed to read file" in str(exc_info.value)
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)


class TestRegisterFormatLoader:
    """Tests for DocumentLoader.register_format_loader()"""

    def test_register_and_use_loader(self, tmp_path):
        md_file = tmp_path / "test.md"
        md_file.write_text("# Test")

        loader = DocumentLoader()
        fake_loader = FakeFormatLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, fake_loader)

        result = loader.load(str(md_file))
        assert result.format == DocumentFormat.MARKDOWN

    def test_register_multiple_loaders(self):
        loader = DocumentLoader()
        loader.register_format_loader(DocumentFormat.MARKDOWN, FakeFormatLoader())
        loader.register_format_loader(DocumentFormat.PYTHON, FakeFormatLoader())

        # Both should be registered
        assert DocumentFormat.MARKDOWN in loader._format_loaders
        assert DocumentFormat.PYTHON in loader._format_loaders

    def test_register_overwrites_existing(self):
        loader = DocumentLoader()
        loader1 = FakeFormatLoader()
        loader2 = FakeFormatLoader()

        loader.register_format_loader(DocumentFormat.MARKDOWN, loader1)
        loader.register_format_loader(DocumentFormat.MARKDOWN, loader2)

        assert loader._format_loaders[DocumentFormat.MARKDOWN] is loader2


class TestExtensionFormatMap:
    """Tests for the EXTENSION_FORMAT_MAP constant."""

    def test_all_document_formats_have_at_least_one_extension(self):
        """Every DocumentFormat should be reachable via at least one extension."""
        mapped_formats = set(EXTENSION_FORMAT_MAP.values())
        for fmt in DocumentFormat:
            assert fmt in mapped_formats, f"DocumentFormat.{fmt.name} has no extension mapping"

    def test_extensions_start_with_dot(self):
        """All extension keys should start with a dot."""
        for ext in EXTENSION_FORMAT_MAP:
            assert ext.startswith("."), f"Extension '{ext}' should start with '.'"
