"""
AI 内置提示词模板初始化逻辑的单元测试。
"""
import os

import pytest
from cryptography.fernet import Fernet

from app.flask_app import create_app
from app.models.base import db as _db
from app.models.ai_prompt import AIPromptTemplate
from app.init_ai_data import init_ai_templates, BUILTIN_TEMPLATES


@pytest.fixture(scope="module")
def app():
    test_key = Fernet.generate_key().decode()
    os.environ["AI_ENCRYPTION_KEY"] = test_key

    application = create_app("testing")
    application.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    application.config["TESTING"] = True

    with application.app_context():
        _db.create_all()

    yield application

    with application.app_context():
        _db.drop_all()

    os.environ.pop("AI_ENCRYPTION_KEY", None)


@pytest.fixture(autouse=True)
def clean_templates(app):
    yield
    with app.app_context():
        AIPromptTemplate.query.delete()
        _db.session.commit()


class TestInitAiTemplates:
    def test_creates_all_builtin_templates(self, app):
        """首次运行应创建全部三个内置模板。"""
        with app.app_context():
            init_ai_templates()
            templates = AIPromptTemplate.query.all()
            assert len(templates) == 3

    def test_templates_have_correct_scenes(self, app):
        """创建的模板应包含正确的场景标识。"""
        with app.app_context():
            init_ai_templates()
            scenes = {t.scene for t in AIPromptTemplate.query.all()}
            assert scenes == {"test_case_generation", "bug_analysis", "requirement_review"}

    def test_all_templates_are_builtin(self, app):
        """所有创建的模板 is_builtin 应为 True。"""
        with app.app_context():
            init_ai_templates()
            for t in AIPromptTemplate.query.all():
                assert t.is_builtin is True

    def test_idempotent_no_duplicates(self, app):
        """多次运行不应创建重复模板。"""
        with app.app_context():
            init_ai_templates()
            init_ai_templates()
            assert AIPromptTemplate.query.count() == 3

    def test_skips_existing_template(self, app):
        """已存在的模板应被跳过，缺失的模板仍会创建。"""
        with app.app_context():
            # 手动插入一个模板
            existing = AIPromptTemplate(
                name="测试用例生成",
                scene="test_case_generation",
                system_prompt="已有模板",
                user_prompt_template="已有模板",
                is_builtin=True,
            )
            _db.session.add(existing)
            _db.session.commit()

            init_ai_templates()

            assert AIPromptTemplate.query.count() == 3
            # 已有模板内容不应被覆盖
            kept = AIPromptTemplate.query.filter_by(scene="test_case_generation").first()
            assert kept.system_prompt == "已有模板"

    def test_template_content_matches_definition(self, app):
        """创建的模板内容应与 BUILTIN_TEMPLATES 定义一致。"""
        with app.app_context():
            init_ai_templates()
            for defn in BUILTIN_TEMPLATES:
                t = AIPromptTemplate.query.filter_by(scene=defn["scene"]).first()
                assert t is not None
                assert t.name == defn["name"]
                assert t.system_prompt == defn["system_prompt"]
                assert t.user_prompt_template == defn["user_prompt_template"]
                assert t.description == defn["description"]
