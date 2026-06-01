"""Unit tests for the custom exception hierarchy."""

import pytest

from src.core.exceptions import (
    AgentExecutionError,
    CodeFactoryError,
    ConfigurationError,
    DocumentLoadError,
    MissingConfigError,
    ModelRoutingError,
    ModelTierExhaustedError,
    SchemaValidationError,
    UnsupportedFormatError,
)


class TestCodeFactoryError:
    def test_basic_message(self):
        err = CodeFactoryError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.correlation_id is None

    def test_with_correlation_id(self):
        err = CodeFactoryError("fail", correlation_id="req-123")
        assert err.correlation_id == "req-123"
        assert str(err) == "fail"

    def test_is_exception(self):
        assert issubclass(CodeFactoryError, Exception)


class TestModelRoutingError:
    def test_inherits_from_base(self):
        assert issubclass(ModelRoutingError, CodeFactoryError)

    def test_with_correlation_id(self):
        err = ModelRoutingError("routing failed", correlation_id="corr-456")
        assert err.correlation_id == "corr-456"


class TestModelTierExhaustedError:
    def test_message_format(self):
        err = ModelTierExhaustedError(tier="local", attempts=3)
        assert "local" in str(err)
        assert "3" in str(err)
        assert err.tier == "local"
        assert err.attempts == 3

    def test_inherits_from_model_routing_error(self):
        assert issubclass(ModelTierExhaustedError, ModelRoutingError)

    def test_with_correlation_id(self):
        err = ModelTierExhaustedError(tier="cloud", attempts=2, correlation_id="corr-789")
        assert err.correlation_id == "corr-789"
        assert err.tier == "cloud"
        assert err.attempts == 2


class TestAgentExecutionError:
    def test_inherits_from_base(self):
        assert issubclass(AgentExecutionError, CodeFactoryError)

    def test_with_correlation_id(self):
        err = AgentExecutionError("agent failed", correlation_id="corr-abc")
        assert err.correlation_id == "corr-abc"


class TestSchemaValidationError:
    def test_message_format(self):
        errors = ["field 'x' missing", "field 'y' invalid"]
        err = SchemaValidationError(agent_name="testcase_agent", errors=errors)
        assert "testcase_agent" in str(err)
        assert err.agent_name == "testcase_agent"
        assert err.validation_errors == errors

    def test_inherits_from_agent_execution_error(self):
        assert issubclass(SchemaValidationError, AgentExecutionError)

    def test_with_correlation_id(self):
        err = SchemaValidationError(
            agent_name="test_agent", errors=["bad"], correlation_id="corr-def"
        )
        assert err.correlation_id == "corr-def"


class TestDocumentLoadError:
    def test_inherits_from_base(self):
        assert issubclass(DocumentLoadError, CodeFactoryError)

    def test_with_correlation_id(self):
        err = DocumentLoadError("load failed", correlation_id="corr-ghi")
        assert err.correlation_id == "corr-ghi"


class TestUnsupportedFormatError:
    def test_message_format(self):
        err = UnsupportedFormatError(
            file_path="/tmp/file.xyz",
            supported_formats=["pdf", "md", "docx"],
        )
        assert "/tmp/file.xyz" in str(err)
        assert err.file_path == "/tmp/file.xyz"
        assert err.supported_formats == ["pdf", "md", "docx"]

    def test_inherits_from_document_load_error(self):
        assert issubclass(UnsupportedFormatError, DocumentLoadError)

    def test_with_correlation_id(self):
        err = UnsupportedFormatError(
            file_path="test.bin",
            supported_formats=["pdf"],
            correlation_id="corr-jkl",
        )
        assert err.correlation_id == "corr-jkl"


class TestConfigurationError:
    def test_inherits_from_base(self):
        assert issubclass(ConfigurationError, CodeFactoryError)

    def test_with_correlation_id(self):
        err = ConfigurationError("config bad", correlation_id="corr-mno")
        assert err.correlation_id == "corr-mno"


class TestMissingConfigError:
    def test_message_format(self):
        err = MissingConfigError(missing_fields=["DB_HOST", "DB_PORT"])
        assert "DB_HOST" in str(err)
        assert "DB_PORT" in str(err)
        assert err.missing_fields == ["DB_HOST", "DB_PORT"]

    def test_inherits_from_configuration_error(self):
        assert issubclass(MissingConfigError, ConfigurationError)

    def test_with_correlation_id(self):
        err = MissingConfigError(
            missing_fields=["API_KEY"], correlation_id="corr-pqr"
        )
        assert err.correlation_id == "corr-pqr"


class TestExceptionHierarchy:
    """Test that the full hierarchy is correct for catch-all patterns."""

    def test_catch_all_with_base(self):
        """All custom exceptions should be catchable via CodeFactoryError."""
        exceptions = [
            ModelRoutingError("x"),
            ModelTierExhaustedError(tier="local", attempts=1),
            AgentExecutionError("x"),
            SchemaValidationError(agent_name="a", errors=["e"]),
            DocumentLoadError("x"),
            UnsupportedFormatError(file_path="f", supported_formats=["pdf"]),
            ConfigurationError("x"),
            MissingConfigError(missing_fields=["f"]),
        ]
        for exc in exceptions:
            assert isinstance(exc, CodeFactoryError)

    def test_model_errors_catchable_by_routing(self):
        err = ModelTierExhaustedError(tier="cloud", attempts=3)
        assert isinstance(err, ModelRoutingError)

    def test_schema_error_catchable_by_agent(self):
        err = SchemaValidationError(agent_name="a", errors=["e"])
        assert isinstance(err, AgentExecutionError)

    def test_unsupported_format_catchable_by_document_load(self):
        err = UnsupportedFormatError(file_path="f", supported_formats=[])
        assert isinstance(err, DocumentLoadError)

    def test_missing_config_catchable_by_configuration(self):
        err = MissingConfigError(missing_fields=["x"])
        assert isinstance(err, ConfigurationError)
