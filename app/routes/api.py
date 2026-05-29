"""
API接口管理路由。

作者: yandc
创建时间: 2026-01-16
"""
from urllib.parse import urlparse
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.api import Api
from app.utils.permission import login_required, check_project_permission
from app.services.request_factory import get_request_factory
from app.services.variable_replacer import replace_in_request, resolve_prefix_url, merge_global_params
from app.schemas.common import MessageResponseSchema

api_blp = Blueprint(
    "api", __name__,
    url_prefix="/api/projects/<int:project_id>/apis",
    description="API接口管理"
)

# 向后兼容
api_bp = api_blp


@api_blp.route("")
class ApisView(MethodView):
    """API接口列表与创建"""

    @api_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有API接口。"""
        category = request.args.get('category')
        status = request.args.get('status', type=int)
        keyword = request.args.get('keyword')

        query = Api.query.filter_by(project_id=project_id)

        if category:
            query = query.filter_by(category=category)
        if status is not None:
            query = query.filter_by(status=status)
        if keyword:
            query = query.filter(
                db.or_(
                    Api.name.like(f'%{keyword}%'),
                    Api.path.like(f'%{keyword}%'),
                    Api.description.like(f'%{keyword}%')
                )
            )

        apis = query.order_by(Api.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [api.to_dict() for api in apis]
        })

    @api_blp.response(200, MessageResponseSchema)
    @api_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建新的API接口。"""
        data = request.get_json()

        try:
            api = Api(
                name=data.get("name"),
                description=data.get("description"),
                project_id=project_id,
                folder_id=data.get("folder_id"),
                method=data.get("method", "GET"),
                path=data.get("path"),
                base_url=data.get("base_url"),
                headers=data.get("headers", {}),
                params=data.get("params", {}),
                body=data.get("body", {}),
                body_type=data.get("body_type", "json"),
                response_example=data.get("response_example", {}),
                prefix_url_id=data.get("prefix_url_id"),
                status=data.get("status", 1),
                category=data.get("category"),
                tags=data.get("tags", [])
            )

            db.session.add(api)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": api.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}"
            }), 500


@api_blp.route("/<int:api_id>")
class ApiDetailView(MethodView):
    """API接口详情、更新与删除"""

    @api_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id, api_id):
        """获取单个API接口详情。"""
        api = Api.query.filter_by(
            id=api_id, project_id=project_id
        ).first_or_404()
        return jsonify({"code": 0, "data": api.to_dict()})

    @api_blp.response(200, MessageResponseSchema)
    @api_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, api_id):
        """更新API接口。"""
        api = Api.query.filter_by(
            id=api_id, project_id=project_id
        ).first_or_404()
        data = request.get_json()

        try:
            for field in [
                "name", "description", "folder_id", "method", "path",
                "base_url", "headers", "params", "body", "body_type",
                "response_example", "prefix_url_id", "status", "category", "tags"
            ]:
                if field in data:
                    setattr(api, field, data[field])

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": api.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}"
            }), 500

    @api_blp.response(200, MessageResponseSchema)
    @api_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, api_id):
        """删除API接口。"""
        api = Api.query.filter_by(
            id=api_id, project_id=project_id
        ).first_or_404()

        try:
            db.session.delete(api)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}"
            }), 500


@api_blp.route("/categories")
class ApiCategoriesView(MethodView):
    """API分类列表"""

    @api_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目中所有的API分类。"""
        categories = db.session.query(Api.category).filter(
            Api.project_id == project_id,
            Api.category.isnot(None)
        ).distinct().all()

        return jsonify({
            "code": 0,
            "data": [cat[0] for cat in categories if cat[0]]
        })


@api_blp.route("/<int:api_id>/test")
class ApiTestView(MethodView):
    """API接口测试"""

    @api_blp.response(200, MessageResponseSchema)
    @api_blp.alt_response(500, schema=MessageResponseSchema, description="测试失败")
    @login_required
    @check_project_permission('read')
    def post(self, project_id, api_id):
        """测试执行API接口。"""
        api = Api.query.filter_by(
            id=api_id, project_id=project_id
        ).first_or_404()
        data = request.get_json() or {}

        try:
            factory = get_request_factory()

            base_url = data.get('base_url') or api.base_url or ''
            path = data.get('path') or api.path
            headers = data.get('headers') or api.headers or {}
            params = data.get('params') or api.params or {}
            body = data.get('body') or api.body or {}
            body_type = data.get('body_type') or api.body_type or 'json'
            environment_id = data.get('environment_id')
            prefix_url_id = data.get('prefix_url_id') or api.prefix_url_id

            # 当 path 是完整 URL 且 base_url 为空时，拆分出 base_url 和 path
            if not base_url and path and path.startswith(('http://', 'https://')):
                parsed = urlparse(path)
                base_url = f"{parsed.scheme}://{parsed.netloc}"
                path = parsed.path or '/'
                # 保留查询参数（如果有）
                if parsed.query:
                    path = f"{path}?{parsed.query}"

            # 变量替换（支持环境优先级）
            base_url, path, headers, params, body = replace_in_request(
                project_id, base_url, path, headers, params, body, body_type,
                environment_id=environment_id
            )

            # 当 base_url 为空时，优先使用绑定的前置 URL，其次按模块/服务匹配
            if not base_url and prefix_url_id:
                from app.models.env_variable import PrefixUrl as PrefixUrlModel
                bound = PrefixUrlModel.query.get(prefix_url_id)
                if bound and bound.url:
                    base_url = bound.url

            if not base_url:
                base_url = resolve_prefix_url(
                    environment_id=environment_id,
                    module=api.module,
                    service=api.service,
                    base_url=base_url
                )

            # 合并全局参数到请求头
            headers = merge_global_params(project_id, headers)

            if base_url and not base_url.endswith('/') \
                    and not path.startswith('/'):
                full_url = f"{base_url}/{path}"
            else:
                full_url = f"{base_url}{path}"

            result = factory.execute(
                method=data.get('method') or api.method,
                url=full_url,
                headers=headers,
                params=params,
                body=body,
                body_type=body_type
            )

            return jsonify({"code": 0, "data": result})

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"测试失败: {str(e)}"
            }), 500
