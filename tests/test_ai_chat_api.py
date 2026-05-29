"""
AI 对话 API 单元测试。

验证同步对话、流式对话、认证、空消息校验等接口。
"""
import os
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.flask_app import create_app
from app.models.base import db as _db
from app.models.user import User


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def app():
    """Create a Flask app configured for testing."""
    test_key = Fernet.generate_key().decode()
    os.environ["AI_ENCRYPTION_KEY"] = test_key

    application = create_app("testing")
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    application.config["TESTING"] = True

    with application.app_context():
        _db.create_all()
        user = User(username="chatuser", email="chat@example.com")
        user.set_password("test123")
        _db.session.add(user)
        _db.session.commit()

    yield application

    with application.app_context():
        _db.drop_all()

    os.environ.pop("AI_ENCRYPTION_KEY", None)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers():
    """Headers that simulate an authenticated user."""
    return {
        "Authorization": "Bearer mock_token",
        "X-Username": "chatuser",
        "Content-Type": "application/json",
    }


def _chat_payload(**overrides):
    """Helper to build a valid chat request payload."""
    data = {
        "messages": [
            {"role": "user", "content": "Hello, AI!"}
        ],
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------
# Authentication tests
# ------------------------------------------------------------------

class TestChatAuthRequired:
    def test_sync_requires_auth(self, client):
        resp = client.post("/api/ai/chat", json=_chat_payload())
        assert resp.status_code == 401

    def test_stream_requires_auth(self, client):
        resp = client.post("/api/ai/chat/stream", json=_chat_payload())
        assert resp.status_code == 401


# ------------------------------------------------------------------
# Empty message validation tests
# ------------------------------------------------------------------

class TestEmptyMessageValidation:
    def test_empty_messages_list(self, client, auth_headers):
        resp = client.post(
            "/api/ai/chat",
            json=_chat_payload(messages=[]),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "消息内容不能为空" in data["message"]

    def test_whitespace_only_content(self, client, auth_headers):
        resp = client.post(
            "/api/ai/chat",
            json=_chat_payload(messages=[{"role": "user", "content": "   "}]),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "消息内容不能为空" in data["message"]

    def test_empty_string_content(self, client, auth_headers):
        resp = client.post(
            "/api/ai/chat",
            json=_chat_payload(messages=[{"role": "user", "content": ""}]),
            headers=auth_headers,
        )
        assert resp.status_code == 400
        data = resp.get_json()
        assert "消息内容不能为空" in data["message"]

    def test_stream_empty_messages(self, client, auth_headers):
        resp = client.post(
            "/api/ai/chat/stream",
            json=_chat_payload(messages=[]),
            headers=auth_headers,
        )
        assert resp.status_code == 400

    def test_stream_whitespace_content(self, client, auth_headers):
        resp = client.post(
            "/api/ai/chat/stream",
            json=_chat_payload(messages=[{"role": "user", "content": "  \t\n  "}]),
            headers=auth_headers,
        )
        assert resp.status_code == 400


# ------------------------------------------------------------------
# Sync chat tests
# ------------------------------------------------------------------

class TestSyncChat:
    @patch("app.routes.ai_chat.ai_service")
    def test_chat_success(self, mock_service, client, auth_headers):
        mock_service.chat.return_value = {
            "content": "Hello! How can I help?",
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
        }

        resp = client.post(
            "/api/ai/chat",
            json=_chat_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"]["content"] == "Hello! How can I help?"
        assert "usage" in data["data"]

    @patch("app.routes.ai_chat.ai_service")
    def test_chat_service_error(self, mock_service, client, auth_headers):
        mock_service.chat.return_value = {
            "error_code": "SERVICE_ERROR",
            "error_message": "AI 服务错误: timeout",
        }

        resp = client.post(
            "/api/ai/chat",
            json=_chat_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 502
        data = resp.get_json()
        assert data["code"] == 1

    @patch("app.routes.ai_chat.ai_service")
    def test_chat_with_provider_id(self, mock_service, client, auth_headers):
        mock_service.chat.return_value = {
            "content": "Response from specific provider",
            "usage": {"prompt_tokens": 5, "completion_tokens": 5, "total_tokens": 10},
        }

        resp = client.post(
            "/api/ai/chat",
            json=_chat_payload(provider_id=1),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        mock_service.chat.assert_called_once()
        call_kwargs = mock_service.chat.call_args
        assert call_kwargs[1]["provider_id"] == 1 or call_kwargs.kwargs.get("provider_id") == 1


# ------------------------------------------------------------------
# Stream chat tests
# ------------------------------------------------------------------

class TestStreamChat:
    @patch("app.routes.ai_chat.ai_service")
    def test_stream_success(self, mock_service, client, auth_headers):
        mock_service.chat_stream.return_value = iter(["Hello", " world", "!"])

        resp = client.post(
            "/api/ai/chat/stream",
            json=_chat_payload(),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.content_type
        body = resp.get_data(as_text=True)
        assert "Hello" in body
        assert "[DONE]" in body
