"""Unit tests for the SwaggerLoader.

Tests cover:
- JSON and YAML format parsing
- Endpoint extraction as separate DocumentUnits
- API info extraction as heading unit
- Parameter, request body, and response schema formatting
- Structural info extraction (title, version, base path)
- Error handling for invalid specs
"""

import json

import pytest
import yaml

from rag.loaders.swagger_loader import SwaggerLoader
from src.core.exceptions import DocumentLoadError
from src.core.models import DocumentFormat, DocumentUnit


@pytest.fixture
def loader():
    """Create a SwaggerLoader instance."""
    return SwaggerLoader()


@pytest.fixture
def openapi3_spec():
    """A minimal OpenAPI 3.0 spec with two endpoints."""
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Pet Store API",
            "version": "1.0.0",
            "description": "A sample pet store API",
        },
        "servers": [{"url": "https://api.petstore.com/v1"}],
        "paths": {
            "/pets": {
                "get": {
                    "operationId": "listPets",
                    "summary": "List all pets",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                            "description": "Max number of pets to return",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "A list of pets",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Pet"},
                                    }
                                }
                            },
                        }
                    },
                },
                "post": {
                    "operationId": "createPet",
                    "summary": "Create a pet",
                    "tags": ["pets"],
                    "requestBody": {
                        "required": True,
                        "description": "Pet to create",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "tag": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {"description": "Pet created"},
                        "400": {"description": "Invalid input"},
                    },
                },
            },
            "/pets/{petId}": {
                "get": {
                    "operationId": "getPet",
                    "summary": "Get a pet by ID",
                    "tags": ["pets"],
                    "parameters": [
                        {
                            "name": "petId",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "The pet ID",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "A pet",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Pet"}
                                }
                            },
                        },
                        "404": {"description": "Pet not found"},
                    },
                }
            },
        },
    }


@pytest.fixture
def swagger2_spec():
    """A minimal Swagger 2.0 spec."""
    return {
        "swagger": "2.0",
        "info": {
            "title": "Legacy API",
            "version": "2.0.0",
            "description": "A legacy Swagger 2.0 API",
        },
        "host": "api.example.com",
        "basePath": "/v2",
        "schemes": ["https"],
        "paths": {
            "/users": {
                "get": {
                    "operationId": "getUsers",
                    "summary": "Get all users",
                    "tags": ["users"],
                    "parameters": [
                        {
                            "name": "page",
                            "in": "query",
                            "type": "integer",
                            "required": False,
                            "description": "Page number",
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "List of users",
                            "schema": {
                                "type": "array",
                                "items": {"$ref": "#/definitions/User"},
                            },
                        }
                    },
                }
            }
        },
    }


class TestSwaggerLoaderJSON:
    """Tests for loading JSON OpenAPI specs."""

    def test_load_openapi3_json(self, loader, openapi3_spec):
        """Test loading a valid OpenAPI 3.0 JSON spec."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        assert result.source_path == "api.json"
        assert result.format == DocumentFormat.SWAGGER_JSON

    def test_extracts_info_as_heading(self, loader, openapi3_spec):
        """Test that API info is extracted as a heading unit."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        heading_units = [u for u in result.units if u.unit_type == "heading"]
        assert len(heading_units) == 1
        assert "Pet Store API" in heading_units[0].content
        assert "1.0.0" in heading_units[0].content
        assert heading_units[0].metadata["title"] == "Pet Store API"
        assert heading_units[0].metadata["version"] == "1.0.0"

    def test_extracts_each_endpoint_as_separate_unit(self, loader, openapi3_spec):
        """Test that each endpoint is a separate DocumentUnit."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        # 3 endpoints: GET /pets, POST /pets, GET /pets/{petId}
        assert len(endpoint_units) == 3

    def test_endpoint_metadata(self, loader, openapi3_spec):
        """Test that endpoint metadata contains method, path, operation_id, tags."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]

        # Find GET /pets
        get_pets = next(
            u for u in endpoint_units
            if u.metadata["method"] == "GET" and u.metadata["path"] == "/pets"
        )
        assert get_pets.metadata["operation_id"] == "listPets"
        assert get_pets.metadata["tags"] == ["pets"]
        assert get_pets.metadata["summary"] == "List all pets"

    def test_endpoint_content_includes_method_and_path(self, loader, openapi3_spec):
        """Test that endpoint content includes method and path."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        get_pets = next(
            u for u in endpoint_units
            if u.metadata["method"] == "GET" and u.metadata["path"] == "/pets"
        )
        assert "GET /pets" in get_pets.content

    def test_endpoint_content_includes_parameters(self, loader, openapi3_spec):
        """Test that endpoint content includes parameter info."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        get_pets = next(
            u for u in endpoint_units
            if u.metadata["method"] == "GET" and u.metadata["path"] == "/pets"
        )
        assert "limit" in get_pets.content
        assert "query" in get_pets.content

    def test_endpoint_content_includes_responses(self, loader, openapi3_spec):
        """Test that endpoint content includes response info."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        get_pets = next(
            u for u in endpoint_units
            if u.metadata["method"] == "GET" and u.metadata["path"] == "/pets"
        )
        assert "200" in get_pets.content
        assert "A list of pets" in get_pets.content

    def test_positions_are_sequential(self, loader, openapi3_spec):
        """Test that positions are assigned sequentially."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        positions = [u.position for u in result.units]
        assert positions == list(range(len(result.units)))

    def test_structural_info(self, loader, openapi3_spec):
        """Test that structural_info contains API title, version, base path."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        assert result.structural_info["api_title"] == "Pet Store API"
        assert result.structural_info["api_version"] == "1.0.0"
        assert result.structural_info["base_path"] == "https://api.petstore.com/v1"
        assert result.structural_info["endpoint_count"] == 3
        assert result.structural_info["openapi_version"] == "3.0.3"


class TestSwaggerLoaderYAML:
    """Tests for loading YAML OpenAPI specs."""

    def test_load_openapi3_yaml(self, loader, openapi3_spec):
        """Test loading a valid OpenAPI 3.0 YAML spec."""
        content = yaml.dump(openapi3_spec).encode("utf-8")
        result = loader.load("api.yaml", content)

        assert result.source_path == "api.yaml"
        assert result.format == DocumentFormat.SWAGGER_YAML

    def test_load_yml_extension(self, loader, openapi3_spec):
        """Test that .yml extension is detected as SWAGGER_YAML."""
        content = yaml.dump(openapi3_spec).encode("utf-8")
        result = loader.load("api.yml", content)

        assert result.format == DocumentFormat.SWAGGER_YAML

    def test_yaml_extracts_endpoints(self, loader, openapi3_spec):
        """Test that YAML format extracts endpoints correctly."""
        content = yaml.dump(openapi3_spec).encode("utf-8")
        result = loader.load("api.yaml", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        assert len(endpoint_units) == 3


class TestSwagger2:
    """Tests for Swagger 2.0 format."""

    def test_load_swagger2(self, loader, swagger2_spec):
        """Test loading a Swagger 2.0 spec."""
        content = json.dumps(swagger2_spec).encode("utf-8")
        result = loader.load("api.json", content)

        assert result.source_path == "api.json"
        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        assert len(endpoint_units) == 1

    def test_swagger2_base_path(self, loader, swagger2_spec):
        """Test that Swagger 2.0 base path is extracted correctly."""
        content = json.dumps(swagger2_spec).encode("utf-8")
        result = loader.load("api.json", content)

        assert "api.example.com" in result.structural_info["base_path"]
        assert "/v2" in result.structural_info["base_path"]

    def test_swagger2_parameter_type(self, loader, swagger2_spec):
        """Test that Swagger 2.0 parameter types are extracted."""
        content = json.dumps(swagger2_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        get_users = endpoint_units[0]
        assert "page" in get_users.content
        assert "integer" in get_users.content

    def test_swagger2_response_schema(self, loader, swagger2_spec):
        """Test that Swagger 2.0 response schemas are included."""
        content = json.dumps(swagger2_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        get_users = endpoint_units[0]
        assert "$ref" in get_users.content or "User" in get_users.content


class TestSwaggerLoaderRequestBody:
    """Tests for request body handling (OpenAPI 3.x)."""

    def test_request_body_in_content(self, loader, openapi3_spec):
        """Test that request body info is included in endpoint content."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        post_pets = next(
            u for u in endpoint_units
            if u.metadata["method"] == "POST" and u.metadata["path"] == "/pets"
        )
        assert "Request Body" in post_pets.content
        assert "application/json" in post_pets.content


class TestSwaggerLoaderErrors:
    """Tests for error handling."""

    def test_invalid_json(self, loader):
        """Test that invalid JSON raises DocumentLoadError."""
        content = b"not valid json or yaml: {{{"
        with pytest.raises(DocumentLoadError):
            loader.load("api.json", content)

    def test_valid_json_but_not_openapi(self, loader):
        """Test that valid JSON without OpenAPI fields raises DocumentLoadError."""
        content = json.dumps({"name": "not an api"}).encode("utf-8")
        with pytest.raises(DocumentLoadError, match="does not appear to be a valid"):
            loader.load("api.json", content)

    def test_valid_yaml_but_not_openapi(self, loader):
        """Test that valid YAML without OpenAPI fields raises DocumentLoadError."""
        content = yaml.dump({"name": "not an api"}).encode("utf-8")
        with pytest.raises(DocumentLoadError, match="does not appear to be a valid"):
            loader.load("api.yaml", content)

    def test_empty_paths(self, loader):
        """Test loading a spec with no paths still works."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Empty API", "version": "0.1.0"},
            "paths": {},
        }
        content = json.dumps(spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        assert len(endpoint_units) == 0

    def test_spec_without_paths_key(self, loader):
        """Test loading a spec without paths key (e.g., webhooks only)."""
        spec = {
            "openapi": "3.1.0",
            "info": {"title": "Webhooks API", "version": "1.0.0"},
            "webhooks": {
                "newPet": {
                    "post": {
                        "summary": "New pet webhook",
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        content = json.dumps(spec).encode("utf-8")
        # Should not raise - webhooks-only spec is valid
        result = loader.load("api.json", content)
        assert result.source_path == "api.json"


class TestSwaggerLoaderEdgeCases:
    """Tests for edge cases."""

    def test_source_path_preserved(self, loader, openapi3_spec):
        """Test that source_path is set on all units."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("/path/to/api.json", content)

        for unit in result.units:
            assert unit.source_path == "/path/to/api.json"

    def test_no_info_section(self, loader):
        """Test loading a spec with minimal info."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Minimal", "version": "0.0.1"},
            "paths": {
                "/health": {
                    "get": {
                        "responses": {"200": {"description": "OK"}}
                    }
                }
            },
        }
        content = json.dumps(spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        assert len(endpoint_units) == 1
        assert endpoint_units[0].metadata["method"] == "GET"
        assert endpoint_units[0].metadata["path"] == "/health"

    def test_non_method_keys_in_path_item_ignored(self, loader):
        """Test that non-HTTP-method keys in path items are ignored."""
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Test", "version": "1.0.0"},
            "paths": {
                "/items": {
                    "parameters": [
                        {"name": "shared", "in": "query", "schema": {"type": "string"}}
                    ],
                    "get": {
                        "responses": {"200": {"description": "OK"}}
                    },
                }
            },
        }
        content = json.dumps(spec).encode("utf-8")
        result = loader.load("api.json", content)

        endpoint_units = [u for u in result.units if u.unit_type == "api_endpoint"]
        # Only GET should be extracted, not "parameters"
        assert len(endpoint_units) == 1
        assert endpoint_units[0].metadata["method"] == "GET"

    def test_raw_text_is_concatenation_of_units(self, loader, openapi3_spec):
        """Test that raw_text is built from unit contents."""
        content = json.dumps(openapi3_spec).encode("utf-8")
        result = loader.load("api.json", content)

        assert len(result.raw_text) > 0
        # raw_text should contain content from all units
        for unit in result.units:
            assert unit.content in result.raw_text
