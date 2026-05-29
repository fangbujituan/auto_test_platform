"""
AI 提供商配置 API 单元测试。

验证 CRUD、连接测试、设置默认等接口。
"""
import os
from unittest.mock import patch, MagicMock

import pytest
from cryptography.fernet import Fernet

from app.flask_app import create_app
from app.models.base import db as _db
from app.models.ai_provider import AIProviderConfig
from app.models.user import User
from app.utils.crypto import CryptoUtil


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
        # Create a test user for authentication
        user = User(username="testuser", email="test@example.com")
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
        "X-Username": "testuser",
        "Content-Type": "application/json",
    }


@pytest.fixture(autouse=True)
def clean_providers(app):
    """Clean up provider configs after each test."""
    yield
    with app.app_context():
        AIProviderConfig.query.delete()
        _db.session.commit()


def _create_provider_data(**overrides):
    """Helper to build valid provider creation payload."""
    data = {
        "name": "Test Provider",
        "provider_type": "openai",
        "api_key": "sk-test1234567890abcdef",
        "base_url": "https://api.openai.com/v1",
        "model_name": "gpt-4o",
        "is_default": False,
        "is_enabled": True,
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------
# Authentication tests
# ------------------------------------------------------------------

class TestAuthRequired:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/ai/providers")
        assert resp.status_code == 401

    def test_create_requires_auth(self, client):
        resp = client.post("/api/ai/providers", json=_create_provider_data())
        assert resp.status_code == 401

    def test_delete_requires_auth(self, client):
        resp = client.delete("/api/ai/providers/1")
        assert resp.status_code == 401

    def test_set_default_requires_auth(self, client):
        resp = client.put("/api/ai/providers/1/default")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# GET list tests
# ------------------------------------------------------------------

class TestListProviders:
    def test_empty_list(self, client, auth_headers):
        resp = client.get("/api/ai/providers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"] == []

    def test_list_with_masked_key(self, client, auth_headers, app):
        # Create a provider first
        client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        resp = client.get("/api/ai/providers", headers=auth_headers)
        data = resp.get_json()
        assert len(data["data"]) == 1
        provider = data["data"][0]
        # API key should be masked, not the raw value
        assert "api_key_masked" in provider
        assert "sk-t" in provider["api_key_masked"]
        assert "****" in provider["api_key_masked"]
        # Should not contain the encrypted key
        assert "api_key_encrypted" not in provider


# ------------------------------------------------------------------
# POST create tests
# ------------------------------------------------------------------

class TestCreateProvider:
    def test_create_success(self, client, auth_headers):
        resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["message"] == "创建成功"
        assert data["data"]["name"] == "Test Provider"
        assert data["data"]["provider_type"] == "openai"

    def test_create_without_api_key(self, client, auth_headers):
        """Ollama providers may not need an API key."""
        resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(
                provider_type="ollama",
                api_key=None,
                base_url="http://localhost:11434",
            ),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"]["api_key_masked"] == ""

    def test_create_as_default_clears_others(self, client, auth_headers, app):
        # Create first as default
        client.post(
            "/api/ai/providers",
            json=_create_provider_data(name="First", is_default=True),
            headers=auth_headers,
        )
        # Create second as default
        client.post(
            "/api/ai/providers",
            json=_create_provider_data(name="Second", is_default=True),
            headers=auth_headers,
        )
        resp = client.get("/api/ai/providers", headers=auth_headers)
        providers = resp.get_json()["data"]
        defaults = [p for p in providers if p["is_default"]]
        assert len(defaults) == 1
        assert defaults[0]["name"] == "Second"


# ------------------------------------------------------------------
# GET detail tests
# ------------------------------------------------------------------

class TestGetProviderDetail:
    def test_get_existing(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.get(f"/api/ai/providers/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"]["id"] == pid

    def test_get_nonexistent(self, client, auth_headers):
        resp = client.get("/api/ai/providers/9999", headers=auth_headers)
        assert resp.status_code == 404


# ------------------------------------------------------------------
# PUT update tests
# ------------------------------------------------------------------

class TestUpdateProvider:
    def test_update_name(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.put(
            f"/api/ai/providers/{pid}",
            json={"name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["name"] == "Updated Name"

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put(
            "/api/ai/providers/9999",
            json={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_api_key(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.put(
            f"/api/ai/providers/{pid}",
            json={"api_key": "sk-newkey1234567890"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        # Verify the masked key changed
        data = resp.get_json()
        assert "sk-n" in data["data"]["api_key_masked"]


# ------------------------------------------------------------------
# DELETE tests
# ------------------------------------------------------------------

class TestDeleteProvider:
    def test_delete_success(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.delete(
            f"/api/ai/providers/{pid}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "删除成功"

        # Verify it's gone
        resp = client.get(f"/api/ai/providers/{pid}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete(
            "/api/ai/providers/9999", headers=auth_headers
        )
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Connection test endpoints
# ------------------------------------------------------------------

class TestConnectionTest:
    @patch("app.routes.ai_provider.ai_service")
    def test_test_saved_provider(self, mock_service, client,
                                 auth_headers, app):
        # Create a provider
        create_resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        mock_service.test_connection.return_value = {
            "success": True, "message": "连接成功", "latency_ms": 150,
        }

        resp = client.post(
            f"/api/ai/providers/{pid}/test", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["success"] is True

    @patch("app.routes.ai_provider.ai_service")
    def test_test_unsaved_provider(self, mock_service, client,
                                   auth_headers):
        mock_service.test_connection.return_value = {
            "success": True, "message": "连接成功", "latency_ms": 100,
        }

        resp = client.post(
            "/api/ai/providers/test",
            json={
                "provider_type": "openai",
                "api_key": "sk-test",
                "base_url": "https://api.openai.com/v1",
                "model_name": "gpt-4o",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["success"] is True

    def test_test_nonexistent_provider(self, client, auth_headers):
        resp = client.post(
            "/api/ai/providers/9999/test", headers=auth_headers
        )
        assert resp.status_code == 404


# ------------------------------------------------------------------
# Set default endpoint
# ------------------------------------------------------------------

class TestSetDefault:
    @patch("app.routes.ai_provider.ai_service")
    def test_set_default_success(self, mock_service, client,
                                 auth_headers, app):
        mock_service.set_default.return_value = {"success": True}

        create_resp = client.post(
            "/api/ai/providers",
            json=_create_provider_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.put(
            f"/api/ai/providers/{pid}/default", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["message"] == "设置默认成功"

    @patch("app.routes.ai_provider.ai_service")
    def test_set_default_nonexistent(self, mock_service, client,
                                     auth_headers):
        mock_service.set_default.return_value = {
            "error_code": "PROVIDER_NOT_FOUND",
            "error_message": "提供商配置不存在",
        }

        resp = client.put(
            "/api/ai/providers/9999/default", headers=auth_headers
        )
        assert resp.status_code == 404
