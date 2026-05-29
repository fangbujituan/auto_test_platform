"""
AIService 单元测试。

验证提供商解析、模板变量替换、连接测试、set_default 等核心逻辑。
"""
import os
from unittest.mock import patch, MagicMock

import pytest
from cryptography.fernet import Fernet

from app.flask_app import create_app
from app.models.base import db as _db
from app.models.ai_provider import AIProviderConfig
from app.models.ai_prompt import AIPromptTemplate
from app.services.ai_service import AIService


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """Create a Flask app configured for testing."""
    # Generate a valid Fernet key for tests
    test_key = Fernet.generate_key().decode()
    os.environ["AI_ENCRYPTION_KEY"] = test_key

    application = create_app("testing")
    # Ensure testing DB is in-memory SQLite
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    application.config["TESTING"] = True

    with application.app_context():
        _db.create_all()

    yield application

    with application.app_context():
        _db.drop_all()

    os.environ.pop("AI_ENCRYPTION_KEY", None)


@pytest.fixture(autouse=True)
def db_session(app):
    """Provide a clean DB session for each test."""
    with app.app_context():
        yield _db.session
        _db.session.rollback()
        # Clean up all test data
        AIPromptTemplate.query.delete()
        AIProviderConfig.query.delete()
        _db.session.commit()


@pytest.fixture
def service():
    return AIService()


def _create_provider(name="test", provider_type="openai",
                     is_default=False, api_key_enc="enc_key",
                     base_url="https://api.openai.com",
                     model_name="gpt-4o"):
    """Helper to insert a provider config."""
    p = AIProviderConfig(
        name=name,
        provider_type=provider_type,
        api_key_encrypted=api_key_enc,
        base_url=base_url,
        model_name=model_name,
        is_default=is_default,
        is_enabled=True,
    )
    _db.session.add(p)
    _db.session.flush()
    return p


def _create_template(scene="test_scene", name="Test",
                     system_prompt="You are helpful.",
                     user_prompt="Hello {name}, do {task}"):
    t = AIPromptTemplate(
        name=name,
        scene=scene,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt,
    )
    _db.session.add(t)
    _db.session.flush()
    return t


# ------------------------------------------------------------------
# _get_provider_config tests
# ------------------------------------------------------------------

class TestGetProviderConfig:
    def test_returns_default_when_no_id(self, service, db_session):
        p = _create_provider(is_default=True)
        result = service._get_provider_config()
        assert result.id == p.id

    def test_error_when_no_default(self, service, db_session):
        _create_provider(is_default=False)
        result = service._get_provider_config()
        assert result["error_code"] == "NO_DEFAULT_PROVIDER"

    def test_returns_specific_by_id(self, service, db_session):
        p1 = _create_provider(name="p1", is_default=True)
        p2 = _create_provider(name="p2", is_default=False)
        result = service._get_provider_config(provider_id=p2.id)
        assert result.id == p2.id

    def test_error_when_id_not_found(self, service, db_session):
        result = service._get_provider_config(provider_id=9999)
        assert result["error_code"] == "PROVIDER_NOT_FOUND"


# ------------------------------------------------------------------
# set_default tests
# ------------------------------------------------------------------

class TestSetDefault:
    def test_sets_default_and_clears_others(self, service, db_session):
        p1 = _create_provider(name="p1", is_default=True)
        p2 = _create_provider(name="p2", is_default=False)

        result = service.set_default(p2.id)
        assert result["success"] is True

        _db.session.refresh(p1)
        _db.session.refresh(p2)
        assert p1.is_default is False
        assert p2.is_default is True

    def test_error_for_nonexistent_id(self, service, db_session):
        result = service.set_default(9999)
        assert result["error_code"] == "PROVIDER_NOT_FOUND"

    def test_only_one_default_after_set(self, service, db_session):
        p1 = _create_provider(name="a", is_default=True)
        p2 = _create_provider(name="b", is_default=False)
        p3 = _create_provider(name="c", is_default=False)

        service.set_default(p3.id)

        defaults = AIProviderConfig.query.filter_by(
            is_default=True
        ).all()
        assert len(defaults) == 1
        assert defaults[0].id == p3.id


# ------------------------------------------------------------------
# chat tests
# ------------------------------------------------------------------

class TestChat:
    @patch("app.services.ai_service.get_adapter")
    @patch("app.services.ai_service.CryptoUtil.decrypt",
           return_value="plain_key")
    def test_chat_success(self, mock_decrypt, mock_get_adapter,
                          service, db_session):
        p = _create_provider(is_default=True)
        mock_adapter = MagicMock()
        mock_adapter.chat.return_value = {
            "content": "Hello!", "usage": {}
        }
        mock_get_adapter.return_value = mock_adapter

        result = service.chat(
            [{"role": "user", "content": "Hi"}]
        )
        assert result["content"] == "Hello!"
        mock_decrypt.assert_called_once()

    def test_chat_no_default_provider(self, service, db_session):
        result = service.chat(
            [{"role": "user", "content": "Hi"}]
        )
        assert result["error_code"] == "NO_DEFAULT_PROVIDER"


# ------------------------------------------------------------------
# chat_with_template tests
# ------------------------------------------------------------------

class TestChatWithTemplate:
    @patch("app.services.ai_service.get_adapter")
    @patch("app.services.ai_service.CryptoUtil.decrypt",
           return_value="plain_key")
    def test_template_substitution(self, mock_decrypt,
                                   mock_get_adapter,
                                   service, db_session):
        _create_provider(is_default=True)
        _create_template()
        mock_adapter = MagicMock()
        mock_adapter.chat.return_value = {
            "content": "result", "usage": {}
        }
        mock_get_adapter.return_value = mock_adapter

        result = service.chat_with_template(
            "test_scene", {"name": "Alice", "task": "testing"}
        )
        assert result["content"] == "result"

        # Verify the adapter received the substituted message
        call_args = mock_adapter.chat.call_args
        messages = call_args[0][0]
        assert messages[0]["role"] == "system"
        assert messages[1]["content"] == "Hello Alice, do testing"

    def test_template_not_found(self, service, db_session):
        result = service.chat_with_template(
            "nonexistent", {"x": "y"}
        )
        assert result["error_code"] == "TEMPLATE_NOT_FOUND"

    @patch("app.services.ai_service.get_adapter")
    @patch("app.services.ai_service.CryptoUtil.decrypt",
           return_value="plain_key")
    def test_missing_variable(self, mock_decrypt,
                              mock_get_adapter,
                              service, db_session):
        _create_provider(is_default=True)
        _create_template()

        result = service.chat_with_template(
            "test_scene", {"name": "Alice"}  # missing 'task'
        )
        assert result["error_code"] == "TEMPLATE_VARIABLE_MISSING"


# ------------------------------------------------------------------
# test_connection tests
# ------------------------------------------------------------------

class TestTestConnection:
    @patch("app.services.ai_service.get_adapter")
    def test_connection_success(self, mock_get_adapter, service):
        mock_adapter = MagicMock()
        mock_adapter.test_connection.return_value = {
            "success": True, "message": "ok", "latency_ms": 100
        }
        mock_get_adapter.return_value = mock_adapter

        result = service.test_connection(
            "openai", "key", "http://url", "model"
        )
        assert result["success"] is True

    def test_connection_invalid_type(self, service):
        result = service.test_connection(
            "unknown_type", "key", "http://url", "model"
        )
        assert result["success"] is False


# ------------------------------------------------------------------
# chat_stream tests
# ------------------------------------------------------------------

class TestChatStream:
    @patch("app.services.ai_service.get_adapter")
    @patch("app.services.ai_service.CryptoUtil.decrypt",
           return_value="plain_key")
    def test_stream_yields_chunks(self, mock_decrypt,
                                  mock_get_adapter,
                                  service, db_session):
        _create_provider(is_default=True)
        mock_adapter = MagicMock()
        mock_adapter.chat_stream.return_value = iter(
            ["Hello", " world"]
        )
        mock_get_adapter.return_value = mock_adapter

        chunks = list(service.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ))
        assert chunks == ["Hello", " world"]

    def test_stream_no_default_provider(self, service, db_session):
        import json
        chunks = list(service.chat_stream(
            [{"role": "user", "content": "Hi"}]
        ))
        assert len(chunks) == 1
        data = json.loads(chunks[0])
        assert data["error_code"] == "NO_DEFAULT_PROVIDER"
