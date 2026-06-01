"""Unit tests for src/core/config.py."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.config import (
    AppConfig,
    DatabaseConfig,
    Environment,
    ModelConfig,
    _deep_merge,
    load_config,
    load_config_or_exit,
    load_yaml_config,
    validate_config,
)
from src.core.exceptions import MissingConfigError


# =============================================================================
# Fixtures
# =============================================================================

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "config"


@pytest.fixture
def valid_config_dict():
    """A fully valid configuration dictionary."""
    return {
        "environment": "development",
        "database": {
            "host": "localhost",
            "port": 5432,
            "database": "code_factory_test",
            "user": "postgres",
            "password": "secret123",
        },
        "model": {
            "local_endpoint": "http://localhost:11434",
            "cloud_api_keys": {"anthropic": "sk-test"},
            "default_temperature": 0.7,
            "default_max_tokens": 4096,
        },
        "log_level": "INFO",
        "vector_store_collection": "knowledge_base",
        "similarity_threshold": 0.7,
        "review_timeout_seconds": 3600,
    }


@pytest.fixture
def config_environments_dir(tmp_path):
    """Create a temporary config/environments directory with YAML files."""
    env_dir = tmp_path / "config" / "environments"
    env_dir.mkdir(parents=True)

    dev_yaml = env_dir / "development.yaml"
    dev_yaml.write_text(
        """
database:
  host: localhost
  port: 5432
  database: code_factory_dev
  user: postgres

model:
  local_endpoint: "http://localhost:11434"
  default_temperature: 0.7
  default_max_tokens: 4096

log_level: DEBUG
vector_store_collection: knowledge_base_dev
similarity_threshold: 0.7
review_timeout_seconds: 7200
"""
    )

    testing_yaml = env_dir / "testing.yaml"
    testing_yaml.write_text(
        """
database:
  host: localhost
  port: 5432
  database: code_factory_test
  user: postgres

model:
  local_endpoint: "http://localhost:11434"
  default_temperature: 0.0
  default_max_tokens: 2048

log_level: WARNING
vector_store_collection: knowledge_base_test
similarity_threshold: 0.7
review_timeout_seconds: 60
"""
    )

    return env_dir


# =============================================================================
# Tests: validate_config
# =============================================================================


class TestValidateConfig:
    """Tests for the validate_config function."""

    def test_valid_config_returns_no_errors(self, valid_config_dict):
        errors = validate_config(valid_config_dict)
        assert errors == []

    def test_missing_database_section(self, valid_config_dict):
        del valid_config_dict["database"]
        errors = validate_config(valid_config_dict)
        assert any("database" in e for e in errors)

    def test_missing_database_password(self, valid_config_dict):
        del valid_config_dict["database"]["password"]
        errors = validate_config(valid_config_dict)
        assert any("database.password" in e for e in errors)

    def test_missing_database_host(self, valid_config_dict):
        del valid_config_dict["database"]["host"]
        errors = validate_config(valid_config_dict)
        assert any("database.host" in e for e in errors)

    def test_missing_model_section(self, valid_config_dict):
        del valid_config_dict["model"]
        errors = validate_config(valid_config_dict)
        assert any("model" in e for e in errors)

    def test_missing_model_local_endpoint(self, valid_config_dict):
        del valid_config_dict["model"]["local_endpoint"]
        errors = validate_config(valid_config_dict)
        assert any("model.local_endpoint" in e for e in errors)

    def test_invalid_port_out_of_range(self, valid_config_dict):
        valid_config_dict["database"]["port"] = 99999
        errors = validate_config(valid_config_dict)
        assert any("database.port" in e for e in errors)

    def test_invalid_port_not_integer(self, valid_config_dict):
        valid_config_dict["database"]["port"] = "not_a_number"
        errors = validate_config(valid_config_dict)
        assert any("database.port" in e for e in errors)

    def test_invalid_environment(self, valid_config_dict):
        valid_config_dict["environment"] = "staging"
        errors = validate_config(valid_config_dict)
        assert any("environment" in e for e in errors)

    def test_invalid_log_level(self, valid_config_dict):
        valid_config_dict["log_level"] = "VERBOSE"
        errors = validate_config(valid_config_dict)
        assert any("log_level" in e for e in errors)

    def test_invalid_similarity_threshold_too_high(self, valid_config_dict):
        valid_config_dict["similarity_threshold"] = 1.5
        errors = validate_config(valid_config_dict)
        assert any("similarity_threshold" in e for e in errors)

    def test_invalid_temperature_too_high(self, valid_config_dict):
        valid_config_dict["model"]["default_temperature"] = 3.0
        errors = validate_config(valid_config_dict)
        assert any("default_temperature" in e for e in errors)

    def test_reports_all_errors_not_just_first(self):
        """Validates Requirement 9.3: reports ALL issues."""
        config = {
            "database": {
                "host": "",
                "port": -1,
                "database": "",
                "user": "",
                # password missing
            },
            "model": {
                # local_endpoint missing
                "default_temperature": 5.0,
            },
            "log_level": "INVALID",
            "similarity_threshold": 2.0,
        }
        errors = validate_config(config)
        # Should have multiple errors reported
        assert len(errors) >= 5

    def test_empty_string_treated_as_missing(self, valid_config_dict):
        valid_config_dict["database"]["host"] = "   "
        errors = validate_config(valid_config_dict)
        assert any("database.host" in e for e in errors)


# =============================================================================
# Tests: load_yaml_config
# =============================================================================


class TestLoadYamlConfig:
    """Tests for YAML config loading."""

    def test_load_development_yaml(self, config_environments_dir):
        config = load_yaml_config("development", config_dir=config_environments_dir)
        assert config["database"]["host"] == "localhost"
        assert config["log_level"] == "DEBUG"

    def test_load_testing_yaml(self, config_environments_dir):
        config = load_yaml_config("testing", config_dir=config_environments_dir)
        assert config["database"]["database"] == "code_factory_test"
        assert config["log_level"] == "WARNING"

    def test_missing_yaml_raises_error(self, config_environments_dir):
        with pytest.raises(MissingConfigError) as exc_info:
            load_yaml_config("nonexistent", config_dir=config_environments_dir)
        assert "config file" in str(exc_info.value.missing_fields)


# =============================================================================
# Tests: load_config
# =============================================================================


class TestLoadConfig:
    """Tests for the full config loading pipeline."""

    def test_load_config_with_env_vars(self, config_environments_dir):
        """Test that sensitive values come from environment variables."""
        env_vars = {
            "APP_ENV": "development",
            "DB_PASSWORD": "test_password_123",
            "ANTHROPIC_API_KEY": "sk-ant-test",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config(
                config_dir=config_environments_dir,
                env_override="development",
            )
        assert config.database.password == "test_password_123"
        assert config.model.cloud_api_keys.get("anthropic") == "sk-ant-test"
        assert config.environment == Environment.DEVELOPMENT

    def test_load_config_missing_password_raises(self, config_environments_dir):
        """Test that missing DB_PASSWORD raises MissingConfigError."""
        env_vars = {"APP_ENV": "development"}
        # Ensure DB_PASSWORD is not set
        env_clean = {k: v for k, v in os.environ.items() if k != "DB_PASSWORD"}
        with patch.dict(os.environ, env_vars, clear=True):
            # Restore PATH and other essentials but not DB_PASSWORD
            with pytest.raises(MissingConfigError) as exc_info:
                load_config(
                    config_dir=config_environments_dir,
                    env_override="development",
                )
            assert any("password" in e for e in exc_info.value.missing_fields)

    def test_environment_selection_via_env_var(self, config_environments_dir):
        """Test that APP_ENV selects the correct YAML file."""
        env_vars = {
            "APP_ENV": "testing",
            "DB_PASSWORD": "test_pass",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config(
                config_dir=config_environments_dir,
                env_override="testing",
            )
        assert config.environment == Environment.TESTING
        assert config.database.database == "code_factory_test"


# =============================================================================
# Tests: load_config_or_exit
# =============================================================================


class TestLoadConfigOrExit:
    """Tests for the startup entry point."""

    def test_exits_with_nonzero_on_missing_config(self, config_environments_dir):
        """Validates Requirement 9.4: terminate with non-zero exit code."""
        env_vars = {"APP_ENV": "development"}
        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(SystemExit) as exc_info:
                load_config_or_exit(
                    config_dir=config_environments_dir,
                    env_override="development",
                )
            assert exc_info.value.code != 0

    def test_returns_config_on_success(self, config_environments_dir):
        """Test successful config loading returns AppConfig."""
        env_vars = {
            "APP_ENV": "development",
            "DB_PASSWORD": "secret",
            "ANTHROPIC_API_KEY": "sk-test",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            config = load_config_or_exit(
                config_dir=config_environments_dir,
                env_override="development",
            )
        assert isinstance(config, AppConfig)
        assert config.database.password == "secret"


# =============================================================================
# Tests: _deep_merge
# =============================================================================


class TestDeepMerge:
    """Tests for the deep merge utility."""

    def test_simple_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        result = _deep_merge(base, override)
        assert result == {"a": 1, "b": 3, "c": 4}

    def test_nested_merge(self):
        base = {"db": {"host": "localhost", "port": 5432}}
        override = {"db": {"port": 5433}}
        result = _deep_merge(base, override)
        assert result == {"db": {"host": "localhost", "port": 5433}}

    def test_override_replaces_non_dict(self):
        base = {"key": "old"}
        override = {"key": "new"}
        result = _deep_merge(base, override)
        assert result == {"key": "new"}
