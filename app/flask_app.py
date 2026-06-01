"""
Flask应用工厂。

作者: yandc
创建时间: 2026-01-13
"""
import json
import os
import time
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件（在读取任何环境变量之前）
load_dotenv()

from flask import Flask, g, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS
from flask_smorest import Api
import logging

from app.config.settings import config
from app.models.base import db
from app.utils.logger_config import setup_logging  # 触发日志系统初始化

setup_logging()

# 请求/响应日志记录器
api_logger = logging.getLogger("api.access")


class CustomJSONProvider(DefaultJSONProvider):
    """自定义JSON提供器，确保中文正常显示。"""
    ensure_ascii = False


def _register_request_logging(app):
    """注册 before/after_request 钩子，记录入参和出参。"""

    @app.before_request
    def _log_request_start():
        g._req_start = time.time()

        # 跳过静态资源 / swagger 文档
        if request.path.startswith(("/static", "/api/docs")):
            return

    @app.after_request
    def _log_request_end(response):
        if request.path.startswith(("/static", "/api/docs")):
            return response

        duration_ms = (time.time() - getattr(g, "_req_start", time.time())) * 1000

        # 获取客户端真实IP（支持反向代理）
        client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if client_ip and ',' in client_ip:
            client_ip = client_ip.split(',')[0].strip()

        log_parts = [
            f"{request.method} {request.full_path.rstrip('?')}",
            f"ip={client_ip}",
            f"status={response.status_code}",
            f"duration={duration_ms:.1f}ms",
        ]

        # 入参：仅 POST/PUT/PATCH/DELETE 打印 body，跳过文件上传
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if request.content_type and "multipart/form-data" not in request.content_type:
                try:
                    body = request.get_json(silent=True)
                    if body is not None:
                        log_parts.append(
                            f"入参={json.dumps(body, ensure_ascii=False, separators=(',', ':'))}"
                        )
                except Exception:
                    pass

        # 出参：仅 JSON 响应
        content_type = response.content_type or ""
        if "application/json" in content_type:
            try:
                resp_data = response.get_data(as_text=True)
                log_parts.append(f"出参={resp_data}")
            except Exception:
                pass

        api_logger.info(" | ".join(log_parts))
        return response


def create_app(config_name=None):
    """创建并配置Flask应用。"""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # 确保 JSON 返回中文而不是 Unicode 转义
    app.config['JSON_AS_ASCII'] = False
    # 关闭键排序
    app.config['JSON_SORT_KEYS'] = False
    app.json = CustomJSONProvider(app)

    # flask-smorest / OpenAPI 配置
    app.config['API_TITLE'] = 'ATP 测试平台 API'
    app.config['API_VERSION'] = 'v1'
    app.config['OPENAPI_VERSION'] = '3.0.3'
    app.config['OPENAPI_URL_PREFIX'] = '/api/docs'
    app.config['OPENAPI_SWAGGER_UI_PATH'] = '/swagger'
    app.config['OPENAPI_SWAGGER_UI_URL'] = (
        'https://cdn.jsdelivr.net/npm/swagger-ui-dist/'
    )
    app.config['OPENAPI_REDOC_PATH'] = '/redoc'
    app.config['OPENAPI_REDOC_URL'] = (
        'https://cdn.jsdelivr.net/npm/redoc@latest/'
        'bundles/redoc.standalone.js'
    )

    # 初始化扩展
    db.init_app(app)
    CORS(app)
    api = Api(app)

    # 注册请求/响应日志中间件
    _register_request_logging(app)

    # 注册所有 flask-smorest 蓝图
    from app.routes.auth import auth_blp
    from app.routes.project import project_blp
    from app.routes.project_member import member_blp
    from app.routes.case import case_blp
    from app.routes.result import result_blp
    from app.routes.execute import execute_blp
    from app.routes.role import role_blp
    from app.routes.api import api_blp
    from app.routes.api_folder import folder_blp
    from app.routes.test_case import test_case_blp
    from app.routes.bug import bug_blp
    from app.routes.toolbox import toolbox_blp
    from app.routes.dashboard import dashboard_blp
    from app.routes.api_import import import_blp
    from app.routes.sprint import sprint_blp
    from app.routes.requirement import requirement_blp, tag_blp, operation_log_blp
    from app.routes.ai_provider import ai_provider_blp
    from app.routes.ai_chat import ai_chat_blp
    from app.routes.ai_prompt import ai_prompt_blp
    from app.routes.ai_agent import ai_agent_blp
    from app.routes.env_variable import env_variable_blp
    from app.routes.environment import (
        environment_blp, prefix_url_blp,
        global_variable_blp, global_param_blp
    )
    from app.routes.automation import automation_blp, automation_exec_blp
    from app.routes.webhook import webhook_blp
    from app.routes.execution_history import execution_history_blp
    from app.routes.agent_workflow import agent_workflow_blp
    from app.routes.quality_dashboard import quality_dashboard_blp

    api.register_blueprint(auth_blp)
    api.register_blueprint(project_blp)
    api.register_blueprint(member_blp)
    api.register_blueprint(case_blp)
    api.register_blueprint(result_blp)
    api.register_blueprint(execute_blp)
    api.register_blueprint(role_blp)
    api.register_blueprint(api_blp)
    api.register_blueprint(folder_blp)
    api.register_blueprint(test_case_blp)
    api.register_blueprint(bug_blp)
    api.register_blueprint(toolbox_blp)
    api.register_blueprint(dashboard_blp)
    api.register_blueprint(import_blp)
    api.register_blueprint(sprint_blp)
    api.register_blueprint(requirement_blp)
    api.register_blueprint(tag_blp)
    api.register_blueprint(operation_log_blp)
    api.register_blueprint(ai_provider_blp)
    api.register_blueprint(ai_chat_blp)
    api.register_blueprint(ai_prompt_blp)
    api.register_blueprint(ai_agent_blp)
    api.register_blueprint(env_variable_blp)
    api.register_blueprint(environment_blp)
    api.register_blueprint(prefix_url_blp)
    api.register_blueprint(global_variable_blp)
    api.register_blueprint(global_param_blp)
    api.register_blueprint(automation_blp)
    api.register_blueprint(automation_exec_blp)
    api.register_blueprint(webhook_blp)
    api.register_blueprint(execution_history_blp)
    api.register_blueprint(agent_workflow_blp)
    api.register_blueprint(quality_dashboard_blp)

    # 创建数据表
    with app.app_context():
        db.create_all()

    # 初始化 Cron 调度服务
    from app.services.scheduler_service import SchedulerService
    scheduler = SchedulerService()
    scheduler.init_app(app)

    return app
