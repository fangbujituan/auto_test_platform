"""
SwaggerImportView.post() 增强错误报告的单元测试。

验证失败时返回具体的失败接口索引、路径和错误详情，
以及事务回滚保证。

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**
"""
import sys
import os
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.routes.api_import import parse_swagger


def _make_swagger_data(apis):
    """Build a minimal Swagger 2.0 doc from (method, path, name) tuples."""
    paths = {}
    for method, path, name in apis:
        paths.setdefault(path, {})[method.lower()] = {
            "summary": name,
            "responses": {"200": {"description": "OK"}}
        }
    return {
        "swagger": "2.0",
        "info": {"title": "Test", "version": "1.0"},
        "paths": paths
    }


@pytest.fixture
def app():
    """Create a test Flask app with in-memory SQLite."""
    os.environ['FLASK_ENV'] = 'testing'
    from app.flask_app import create_app
    from app.models.base import db

    application = create_app('testing')

    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def setup_data(app):
    """Create project, folder, user with admin role for auth."""
    from app.models.base import db
    from app.models.api_folder import ApiFolder
    from app.models.project import Project
    from app.models.user import User
    from app.models.role import Role
    from app.models.project_member import ProjectMember

    project = Project(name="TestProject")
    db.session.add(project)
    db.session.flush()

    folder = ApiFolder(
        name="Default",
        description="Default folder",
        project_id=project.id
    )
    db.session.add(folder)
    db.session.flush()

    user = User(username="testuser", password_hash="fakehash", email="t@t.com")
    db.session.add(user)
    db.session.flush()

    role = Role(name="admin", description="Admin")
    db.session.add(role)
    db.session.flush()

    member = ProjectMember(
        project_id=project.id,
        user_id=user.id,
        role_id=role.id
    )
    db.session.add(member)
    db.session.commit()

    return {"project_id": project.id, "folder_id": folder.id}


def _headers():
    return {
        "Authorization": "Bearer test",
        "X-Username": "testuser",
        "Content-Type": "application/json",
    }


class TestSwaggerImportErrorReporting:
    """Test enhanced error reporting in SwaggerImportView.post()."""

    def test_successful_import_returns_created_count(self, app, setup_data):
        """Req 6.4: successful import commits and returns created_count."""
        from app.models.api import Api

        swagger = _make_swagger_data([
            ("GET", "/api/users", "List Users"),
            ("POST", "/api/users", "Create User"),
        ])

        with app.test_client() as client:
            pid = setup_data["project_id"]
            resp = client.post(
                f"/api/projects/{pid}/apis/import/swagger",
                headers=_headers(),
                json={
                    "swagger_data": swagger,
                    "folder_id": setup_data["folder_id"],
                },
            )

        data = resp.get_json()
        assert data["code"] == 0
        assert data["data"]["created_count"] == 2

        with app.app_context():
            count = Api.query.filter_by(project_id=setup_data["project_id"]).count()
            assert count == 2

    def test_failure_returns_detailed_error_fields(self, app, setup_data):
        """Req 6.3: failure response contains failed_index, failed_api, error_detail, created_before_failure."""
        from app.models.base import db
        from app.models.api import Api

        # Use a single API so we know exactly which one fails
        swagger = _make_swagger_data([
            ("PUT", "/api/fail", "Will Fail"),
        ])

        original_flush = db.session.flush

        def fail_flush(*args, **kwargs):
            raise Exception("字段 name 不能为空")

        with app.test_client() as client:
            with patch.object(db.session, 'flush', side_effect=fail_flush):
                pid = setup_data["project_id"]
                resp = client.post(
                    f"/api/projects/{pid}/apis/import/swagger",
                    headers=_headers(),
                    json={
                        "swagger_data": swagger,
                        "folder_id": setup_data["folder_id"],
                    },
                )

        assert resp.status_code == 500
        data = resp.get_json()
        assert data["code"] == 1
        assert "failed_index" in data.get("data", {})
        assert "failed_api" in data["data"]
        assert "error_detail" in data["data"]
        assert "created_before_failure" in data["data"]
        assert data["data"]["failed_api"]["method"] == "PUT"
        assert data["data"]["failed_api"]["path"] == "/api/fail"
        assert "字段 name 不能为空" in data["data"]["error_detail"]
        assert data["data"]["created_before_failure"] == 0

    def test_failure_rolls_back_all_records(self, app, setup_data):
        """Req 6.2: on failure, all records are rolled back."""
        from app.models.base import db
        from app.models.api import Api

        swagger = _make_swagger_data([
            ("GET", "/api/first", "First"),
            ("POST", "/api/second", "Second - will fail"),
        ])

        original_flush = db.session.flush
        flush_count = [0]

        def counting_flush(*args, **kwargs):
            flush_count[0] += 1
            if flush_count[0] == 2:
                raise Exception("DB constraint error")
            return original_flush(*args, **kwargs)

        with app.test_client() as client:
            with patch.object(db.session, 'flush', side_effect=counting_flush):
                pid = setup_data["project_id"]
                resp = client.post(
                    f"/api/projects/{pid}/apis/import/swagger",
                    headers=_headers(),
                    json={
                        "swagger_data": swagger,
                        "folder_id": setup_data["folder_id"],
                    },
                )

        assert resp.status_code == 500

        with app.app_context():
            count = Api.query.filter_by(project_id=setup_data["project_id"]).count()
            assert count == 0, f"Expected 0 records after rollback, found {count}"

    def test_error_message_contains_index_and_path(self, app, setup_data):
        """Req 6.3: error message includes 1-based index and [METHOD path]."""
        from app.models.base import db

        swagger = _make_swagger_data([
            ("DELETE", "/api/broken", "Broken"),
        ])

        original_flush = db.session.flush

        def fail_flush(*args, **kwargs):
            raise RuntimeError("some db error")

        with app.test_client() as client:
            with patch.object(db.session, 'flush', side_effect=fail_flush):
                pid = setup_data["project_id"]
                resp = client.post(
                    f"/api/projects/{pid}/apis/import/swagger",
                    headers=_headers(),
                    json={
                        "swagger_data": swagger,
                        "folder_id": setup_data["folder_id"],
                    },
                )

        data = resp.get_json()
        msg = data["message"]
        assert "第" in msg
        assert "DELETE" in msg
        assert "/api/broken" in msg
        assert "创建出错" in msg
