"""
AI 提示词模板 API 单元测试。

验证 CRUD 接口。
"""
import os

import pytest
from cryptography.fernet import Fernet

from app.flask_app import create_app
from app.models.base import db as _db
from app.models.ai_prompt import AIPromptTemplate
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
def clean_prompts(app):
    """Clean up prompt templates after each test."""
    yield
    with app.app_context():
        AIPromptTemplate.query.delete()
        _db.session.commit()


def _create_prompt_data(**overrides):
    """Helper to build valid prompt creation payload."""
    data = {
        "name": "测试用例生成",
        "scene": "test_case_generation",
        "system_prompt": "你是一个测试专家。",
        "user_prompt_template": "请为以下需求生成测试用例：{requirement}",
        "description": "根据需求生成测试用例",
    }
    data.update(overrides)
    return data


# ------------------------------------------------------------------
# Authentication tests
# ------------------------------------------------------------------

class TestAuthRequired:
    def test_list_requires_auth(self, client):
        resp = client.get("/api/ai/prompts")
        assert resp.status_code == 401

    def test_create_requires_auth(self, client):
        resp = client.post("/api/ai/prompts", json=_create_prompt_data())
        assert resp.status_code == 401

    def test_update_requires_auth(self, client):
        resp = client.put("/api/ai/prompts/1", json={"name": "X"})
        assert resp.status_code == 401

    def test_delete_requires_auth(self, client):
        resp = client.delete("/api/ai/prompts/1")
        assert resp.status_code == 401


# ------------------------------------------------------------------
# GET list tests
# ------------------------------------------------------------------

class TestListPrompts:
    def test_empty_list(self, client, auth_headers):
        resp = client.get("/api/ai/prompts", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"] == []

    def test_list_returns_all(self, client, auth_headers):
        client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(name="缺陷分析", scene="bug_analysis"),
            headers=auth_headers,
        )
        resp = client.get("/api/ai/prompts", headers=auth_headers)
        data = resp.get_json()
        assert len(data["data"]) == 2


# ------------------------------------------------------------------
# POST create tests
# ------------------------------------------------------------------

class TestCreatePrompt:
    def test_create_success(self, client, auth_headers):
        resp = client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["message"] == "创建成功"
        assert data["data"]["name"] == "测试用例生成"
        assert data["data"]["scene"] == "test_case_generation"
        assert data["data"]["is_builtin"] is False

    def test_create_without_description(self, client, auth_headers):
        payload = _create_prompt_data()
        del payload["description"]
        resp = client.post(
            "/api/ai/prompts",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["description"] is None

    def test_create_duplicate_scene_fails(self, client, auth_headers):
        client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        resp = client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["code"] == 1


# ------------------------------------------------------------------
# GET detail tests
# ------------------------------------------------------------------

class TestGetPromptDetail:
    def test_get_existing(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.get(f"/api/ai/prompts/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"]["id"] == pid

    def test_get_nonexistent(self, client, auth_headers):
        resp = client.get("/api/ai/prompts/9999", headers=auth_headers)
        assert resp.status_code == 404


# ------------------------------------------------------------------
# PUT update tests
# ------------------------------------------------------------------

class TestUpdatePrompt:
    def test_update_name(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.put(
            f"/api/ai/prompts/{pid}",
            json={"name": "更新后的名称"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["name"] == "更新后的名称"
        assert data["message"] == "更新成功"

    def test_update_nonexistent(self, client, auth_headers):
        resp = client.put(
            "/api/ai/prompts/9999",
            json={"name": "X"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_update_system_prompt(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.put(
            f"/api/ai/prompts/{pid}",
            json={"system_prompt": "你是一个高级测试专家。"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["data"]["system_prompt"] == "你是一个高级测试专家。"


# ------------------------------------------------------------------
# DELETE tests
# ------------------------------------------------------------------

class TestDeletePrompt:
    def test_delete_success(self, client, auth_headers):
        create_resp = client.post(
            "/api/ai/prompts",
            json=_create_prompt_data(),
            headers=auth_headers,
        )
        pid = create_resp.get_json()["data"]["id"]

        resp = client.delete(
            f"/api/ai/prompts/{pid}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.get_json()["message"] == "删除成功"

        # Verify it's gone
        resp = client.get(f"/api/ai/prompts/{pid}", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete(
            "/api/ai/prompts/9999", headers=auth_headers
        )
        assert resp.status_code == 404
