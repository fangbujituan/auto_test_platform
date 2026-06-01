"""Unit tests for the SourceCodeLoader.

Tests extraction of functions, classes, and docstrings from
Python, Java, JavaScript, and TypeScript source files.

Requirements: 5.1, 5.4
"""

import pytest

from rag.loaders.source_code_loader import SourceCodeLoader
from src.core.exceptions import DocumentLoadError
from src.core.models import DocumentFormat, DocumentUnit, LoadedDocument


@pytest.fixture
def loader():
    return SourceCodeLoader()


class TestPythonExtraction:
    """Tests for Python AST-based extraction."""

    def test_extract_simple_function(self, loader):
        source = b'def hello():\n    """Say hello."""\n    print("hello")\n'
        result = loader.load("test.py", source)

        assert isinstance(result, LoadedDocument)
        assert result.format == DocumentFormat.PYTHON
        assert result.structural_info["language"] == "python"
        assert result.structural_info["num_functions"] == 1

        # Should have function + docstring
        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) == 1
        assert func_units[0].metadata["function_name"] == "hello"

    def test_extract_async_function(self, loader):
        source = b"async def fetch_data():\n    pass\n"
        result = loader.load("test.py", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) == 1
        assert func_units[0].metadata["function_name"] == "fetch_data"
        assert func_units[0].metadata["is_async"] is True

    def test_extract_class(self, loader):
        source = b"class MyClass(Base):\n    pass\n"
        result = loader.load("test.py", source)

        assert result.structural_info["num_classes"] == 1
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert class_units[0].metadata["class_name"] == "MyClass"
        assert "Base" in class_units[0].metadata["bases"]

    def test_extract_module_docstring(self, loader):
        source = b'"""Module docstring."""\n\ndef foo():\n    pass\n'
        result = loader.load("test.py", source)

        doc_units = [u for u in result.units if u.unit_type == "docstring"]
        assert len(doc_units) >= 1
        module_docs = [u for u in doc_units if u.metadata.get("parent") == "module"]
        assert len(module_docs) == 1
        assert "Module docstring" in module_docs[0].content

    def test_extract_function_docstring(self, loader):
        source = b'def greet(name):\n    """Greet someone by name."""\n    return f"Hello {name}"\n'
        result = loader.load("test.py", source)

        doc_units = [u for u in result.units if u.unit_type == "docstring"]
        func_docs = [
            u for u in doc_units if u.metadata.get("parent") == "function:greet"
        ]
        assert len(func_docs) == 1
        assert "Greet someone by name" in func_docs[0].content

    def test_extract_class_docstring(self, loader):
        source = b'class Animal:\n    """Represents an animal."""\n    pass\n'
        result = loader.load("test.py", source)

        doc_units = [u for u in result.units if u.unit_type == "docstring"]
        class_docs = [
            u for u in doc_units if u.metadata.get("parent") == "class:Animal"
        ]
        assert len(class_docs) == 1
        assert "Represents an animal" in class_docs[0].content

    def test_extract_class_methods(self, loader):
        source = (
            b"class Calculator:\n"
            b"    def add(self, a, b):\n"
            b"        return a + b\n"
            b"\n"
            b"    def subtract(self, a, b):\n"
            b"        return a - b\n"
        )
        result = loader.load("test.py", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) == 2
        func_names = {u.metadata["function_name"] for u in func_units}
        assert func_names == {"add", "subtract"}

        # Methods should reference parent class
        for u in func_units:
            assert u.metadata.get("parent_class") == "Calculator"

    def test_extract_decorated_function(self, loader):
        source = b"@staticmethod\ndef helper():\n    pass\n"
        result = loader.load("test.py", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) == 1
        assert "staticmethod" in func_units[0].metadata["decorators"]

    def test_sequential_positions(self, loader):
        source = (
            b'"""Module doc."""\n\n'
            b"def foo():\n    pass\n\n"
            b"class Bar:\n    pass\n"
        )
        result = loader.load("test.py", source)

        positions = [u.position for u in result.units]
        # Positions should be sequential (0, 1, 2, ...)
        assert positions == sorted(positions)
        assert positions[0] == 0

    def test_syntax_error_raises_document_load_error(self, loader):
        source = b"def broken(\n"
        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load("broken.py", source)
        assert "Failed to parse Python file" in str(exc_info.value)

    def test_empty_python_file(self, loader):
        source = b""
        result = loader.load("empty.py", source)

        assert result.format == DocumentFormat.PYTHON
        assert result.units == []
        assert result.structural_info["num_functions"] == 0
        assert result.structural_info["num_classes"] == 0

    def test_multiple_base_classes(self, loader):
        source = b"class Multi(Base1, Base2):\n    pass\n"
        result = loader.load("test.py", source)

        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert "Base1" in class_units[0].metadata["bases"]
        assert "Base2" in class_units[0].metadata["bases"]


class TestJavaExtraction:
    """Tests for Java regex-based extraction."""

    def test_extract_java_class(self, loader):
        source = b"public class UserService {\n    // body\n}\n"
        result = loader.load("UserService.java", source)

        assert result.format == DocumentFormat.JAVA
        assert result.structural_info["language"] == "java"
        assert result.structural_info["num_classes"] == 1

        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert class_units[0].metadata["class_name"] == "UserService"

    def test_extract_java_class_with_extends(self, loader):
        source = b"public class Dog extends Animal {\n}\n"
        result = loader.load("Dog.java", source)

        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert class_units[0].metadata["extends"] == "Animal"

    def test_extract_java_method(self, loader):
        source = (
            b"public class Service {\n"
            b"    public String getName() {\n"
            b'        return "name";\n'
            b"    }\n"
            b"}\n"
        )
        result = loader.load("Service.java", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "getName" in func_names

    def test_extract_java_javadoc(self, loader):
        source = (
            b"/**\n"
            b" * A user service class.\n"
            b" */\n"
            b"public class UserService {\n"
            b"}\n"
        )
        result = loader.load("UserService.java", source)

        doc_units = [u for u in result.units if u.unit_type == "docstring"]
        assert len(doc_units) >= 1
        assert any("user service" in u.content.lower() for u in doc_units)

    def test_empty_java_file(self, loader):
        source = b""
        result = loader.load("Empty.java", source)

        assert result.format == DocumentFormat.JAVA
        assert result.structural_info["num_functions"] == 0
        assert result.structural_info["num_classes"] == 0


class TestJavaScriptExtraction:
    """Tests for JavaScript regex-based extraction."""

    def test_extract_js_function(self, loader):
        source = b"function greet(name) {\n    return 'Hello ' + name;\n}\n"
        result = loader.load("app.js", source)

        assert result.format == DocumentFormat.JAVASCRIPT
        assert result.structural_info["language"] == "javascript"
        assert result.structural_info["num_functions"] >= 1

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "greet" in func_names

    def test_extract_js_arrow_function(self, loader):
        source = b"const add = (a, b) => {\n    return a + b;\n};\n"
        result = loader.load("utils.js", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "add" in func_names

    def test_extract_js_class(self, loader):
        source = (
            b"class Animal {\n"
            b"    constructor(name) {\n"
            b"        this.name = name;\n"
            b"    }\n"
            b"}\n"
        )
        result = loader.load("animal.js", source)

        assert result.structural_info["num_classes"] == 1
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert class_units[0].metadata["class_name"] == "Animal"

    def test_extract_js_class_extends(self, loader):
        source = b"class Dog extends Animal {\n}\n"
        result = loader.load("dog.js", source)

        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert class_units[0].metadata["extends"] == "Animal"

    def test_extract_jsdoc_comment(self, loader):
        source = (
            b"/**\n"
            b" * Adds two numbers.\n"
            b" * @param {number} a\n"
            b" * @param {number} b\n"
            b" */\n"
            b"function add(a, b) {\n"
            b"    return a + b;\n"
            b"}\n"
        )
        result = loader.load("math.js", source)

        doc_units = [u for u in result.units if u.unit_type == "docstring"]
        assert len(doc_units) >= 1
        assert any("Adds two numbers" in u.content for u in doc_units)

    def test_extract_async_function(self, loader):
        source = b"async function fetchData() {\n    return await fetch('/api');\n}\n"
        result = loader.load("api.js", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "fetchData" in func_names

    def test_extract_export_function(self, loader):
        source = b"export function helper() {\n    return true;\n}\n"
        result = loader.load("helpers.js", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "helper" in func_names


class TestTypeScriptExtraction:
    """Tests for TypeScript regex-based extraction."""

    def test_extract_ts_function(self, loader):
        source = b"function greet(name: string): string {\n    return `Hello ${name}`;\n}\n"
        result = loader.load("app.ts", source)

        assert result.format == DocumentFormat.TYPESCRIPT
        assert result.structural_info["language"] == "typescript"

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "greet" in func_names

    def test_extract_ts_class(self, loader):
        source = (
            b"export class UserService {\n"
            b"    private name: string;\n"
            b"\n"
            b"    constructor(name: string) {\n"
            b"        this.name = name;\n"
            b"    }\n"
            b"}\n"
        )
        result = loader.load("service.ts", source)

        assert result.structural_info["num_classes"] == 1
        class_units = [u for u in result.units if u.unit_type == "class"]
        assert len(class_units) == 1
        assert class_units[0].metadata["class_name"] == "UserService"

    def test_extract_ts_arrow_function(self, loader):
        source = b"const multiply = (a: number, b: number) => {\n    return a * b;\n};\n"
        result = loader.load("math.ts", source)

        func_units = [u for u in result.units if u.unit_type == "function"]
        assert len(func_units) >= 1
        func_names = {u.metadata["function_name"] for u in func_units}
        assert "multiply" in func_names


class TestStructuralInfo:
    """Tests for structural_info in LoadedDocument."""

    def test_structural_info_contains_language(self, loader):
        source = b"def foo(): pass\n"
        result = loader.load("test.py", source)
        assert "language" in result.structural_info
        assert result.structural_info["language"] == "python"

    def test_structural_info_contains_counts(self, loader):
        source = (
            b"def foo(): pass\n\n"
            b"def bar(): pass\n\n"
            b"class Baz: pass\n"
        )
        result = loader.load("test.py", source)
        assert result.structural_info["num_functions"] == 2
        assert result.structural_info["num_classes"] == 1

    def test_structural_info_java(self, loader):
        source = b"public class Main {\n    public void run() {\n    }\n}\n"
        result = loader.load("Main.java", source)
        assert result.structural_info["language"] == "java"
        assert result.structural_info["num_classes"] >= 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unsupported_extension_raises_error(self, loader):
        source = b"some content"
        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load("file.rb", source)
        assert "Unsupported source code extension" in str(exc_info.value)

    def test_non_utf8_content_raises_error(self, loader):
        # Invalid UTF-8 bytes
        source = b"\xff\xfe\x00\x01"
        with pytest.raises(DocumentLoadError) as exc_info:
            loader.load("test.py", source)
        assert "Failed to decode" in str(exc_info.value)

    def test_raw_text_preserved(self, loader):
        source = b"def hello():\n    pass\n"
        result = loader.load("test.py", source)
        assert result.raw_text == "def hello():\n    pass\n"

    def test_source_path_preserved(self, loader):
        source = b"def foo(): pass\n"
        result = loader.load("/path/to/module.py", source)
        assert result.source_path == "/path/to/module.py"
        for unit in result.units:
            assert unit.source_path == "/path/to/module.py"
