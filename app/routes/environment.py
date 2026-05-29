"""
环境管理路由。

包含环境分组 CRUD、前置 URL CRUD、全局变量 CRUD、全局参数 CRUD、
环境共享、环境变量（按环境分组）等路由。

作者: yandc
创建时间: 2026-04-03
"""
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.env_variable import (
    Environment, PrefixUrl, GlobalVariable, GlobalParam, EnvironmentVariable
)
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema


# ============================================================
# 环境分组 Blueprint
# ============================================================
environment_blp = Blueprint(
    "environment", __name__,
    url_prefix="/api/projects/<int:project_id>/environments",
    description="环境分组管理"
)


@environment_blp.route("")
class EnvironmentsView(MethodView):
    """环境分组列表与创建"""

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有环境分组。"""
        environments = Environment.query.filter_by(
            project_id=project_id
        ).order_by(Environment.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [env.to_dict() for env in environments]
        })

    @environment_blp.response(200, MessageResponseSchema)
    @environment_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建环境分组。"""
        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "环境名称不能为空"}), 400

        try:
            env = Environment(
                name=name,
                project_id=project_id,
                is_shared=data.get("is_shared", False)
            )
            db.session.add(env)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": env.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@environment_blp.route("/<int:env_id>")
class EnvironmentDetailView(MethodView):
    """环境分组详情、更新与删除"""

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id, env_id):
        """获取单个环境分组详情。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        return jsonify({"code": 0, "data": env.to_dict()})

    @environment_blp.response(200, MessageResponseSchema)
    @environment_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, env_id):
        """更新环境分组。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "环境名称不能为空"}), 400

        try:
            env.name = name
            if "is_shared" in data:
                env.is_shared = data["is_shared"]
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": env.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, env_id):
        """删除环境分组（级联删除前置 URL 和环境变量）。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        try:
            db.session.delete(env)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500


# ============================================================
# 前置 URL Blueprint
# ============================================================
prefix_url_blp = Blueprint(
    "prefix_url", __name__,
    url_prefix="/api/projects/<int:project_id>/environments/<int:env_id>/prefix-urls",
    description="前置URL管理"
)


@prefix_url_blp.route("")
class PrefixUrlsView(MethodView):
    """前置 URL 列表与创建"""

    @prefix_url_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id, env_id):
        """获取环境的所有前置 URL。"""
        # 校验环境归属
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        prefix_urls = PrefixUrl.query.filter_by(
            environment_id=env_id
        ).order_by(PrefixUrl.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [p.to_dict() for p in prefix_urls]
        })

    @prefix_url_blp.response(200, MessageResponseSchema)
    @prefix_url_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('create')
    def post(self, project_id, env_id):
        """创建前置 URL。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        data = request.get_json()

        try:
            prefix_url = PrefixUrl(
                environment_id=env_id,
                module=data.get("module", ""),
                service=data.get("service", ""),
                url=data.get("url", "")
            )
            db.session.add(prefix_url)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": prefix_url.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@prefix_url_blp.route("/<int:prefix_id>")
class PrefixUrlDetailView(MethodView):
    """前置 URL 更新与删除"""

    @prefix_url_blp.response(200, MessageResponseSchema)
    @prefix_url_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, env_id, prefix_id):
        """更新前置 URL。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        prefix_url = PrefixUrl.query.filter_by(
            id=prefix_id, environment_id=env_id
        ).first()
        if not prefix_url:
            return jsonify({"code": 1, "message": "前置URL不存在"}), 404

        data = request.get_json()

        try:
            if "module" in data:
                prefix_url.module = data["module"]
            if "service" in data:
                prefix_url.service = data["service"]
            if "url" in data:
                prefix_url.url = data["url"]
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": prefix_url.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @prefix_url_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, env_id, prefix_id):
        """删除前置 URL。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        prefix_url = PrefixUrl.query.filter_by(
            id=prefix_id, environment_id=env_id
        ).first()
        if not prefix_url:
            return jsonify({"code": 1, "message": "前置URL不存在"}), 404

        try:
            db.session.delete(prefix_url)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500


# ============================================================
# 全局变量 Blueprint
# ============================================================
global_variable_blp = Blueprint(
    "global_variable", __name__,
    url_prefix="/api/projects/<int:project_id>/global-variables",
    description="全局变量管理"
)


@global_variable_blp.route("")
class GlobalVariablesView(MethodView):
    """全局变量列表与创建"""

    @global_variable_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有全局变量。"""
        variables = GlobalVariable.query.filter_by(
            project_id=project_id
        ).order_by(GlobalVariable.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [v.to_dict() for v in variables]
        })

    @global_variable_blp.response(200, MessageResponseSchema)
    @global_variable_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建全局变量。"""
        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "变量名不能为空"}), 400

        # 检查同项目下全局变量名唯一性
        existing = GlobalVariable.query.filter_by(
            project_id=project_id, name=name
        ).first()
        if existing:
            return jsonify({"code": 1, "message": "全局变量名已存在"}), 400

        try:
            variable = GlobalVariable(
                name=name,
                value=data.get("value", ""),
                project_id=project_id
            )
            db.session.add(variable)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": variable.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@global_variable_blp.route("/<int:var_id>")
class GlobalVariableDetailView(MethodView):
    """全局变量更新与删除"""

    @global_variable_blp.response(200, MessageResponseSchema)
    @global_variable_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, var_id):
        """更新全局变量。"""
        variable = GlobalVariable.query.filter_by(
            id=var_id, project_id=project_id
        ).first()
        if not variable:
            return jsonify({"code": 1, "message": "全局变量不存在"}), 404

        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "变量名不能为空"}), 400

        # 检查唯一性（排除自身）
        existing = GlobalVariable.query.filter(
            GlobalVariable.project_id == project_id,
            GlobalVariable.name == name,
            GlobalVariable.id != var_id
        ).first()
        if existing:
            return jsonify({"code": 1, "message": "全局变量名已存在"}), 400

        try:
            variable.name = name
            variable.value = data.get("value", "")
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": variable.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @global_variable_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, var_id):
        """删除全局变量。"""
        variable = GlobalVariable.query.filter_by(
            id=var_id, project_id=project_id
        ).first()
        if not variable:
            return jsonify({"code": 1, "message": "全局变量不存在"}), 404

        try:
            db.session.delete(variable)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500


# ============================================================
# 全局参数 Blueprint（仅 Header 类型）
# ============================================================
global_param_blp = Blueprint(
    "global_param", __name__,
    url_prefix="/api/projects/<int:project_id>/global-params",
    description="全局参数管理（仅Header类型）"
)


@global_param_blp.route("")
class GlobalParamsView(MethodView):
    """全局参数列表与创建"""

    @global_param_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有全局参数（Header 类型）。"""
        params = GlobalParam.query.filter_by(
            project_id=project_id
        ).order_by(GlobalParam.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [p.to_dict() for p in params]
        })

    @global_param_blp.response(200, MessageResponseSchema)
    @global_param_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建全局参数（Header 类型）。"""
        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "参数名不能为空"}), 400

        try:
            param = GlobalParam(
                name=name,
                value=data.get("value", ""),
                description=data.get("description", ""),
                project_id=project_id
            )
            db.session.add(param)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": param.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@global_param_blp.route("/<int:param_id>")
class GlobalParamDetailView(MethodView):
    """全局参数更新与删除"""

    @global_param_blp.response(200, MessageResponseSchema)
    @global_param_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, param_id):
        """更新全局参数。"""
        param = GlobalParam.query.filter_by(
            id=param_id, project_id=project_id
        ).first()
        if not param:
            return jsonify({"code": 1, "message": "全局参数不存在"}), 404

        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "参数名不能为空"}), 400

        try:
            param.name = name
            param.value = data.get("value", "")
            if "description" in data:
                param.description = data["description"]
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": param.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @global_param_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, param_id):
        """删除全局参数。"""
        param = GlobalParam.query.filter_by(
            id=param_id, project_id=project_id
        ).first()
        if not param:
            return jsonify({"code": 1, "message": "全局参数不存在"}), 404

        try:
            db.session.delete(param)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500


# ============================================================
# 环境共享路由（复用 environment_blp）
# ============================================================
@environment_blp.route("/<int:env_id>/share")
class EnvironmentShareView(MethodView):
    """环境共享管理"""

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('update')
    def post(self, project_id, env_id):
        """共享环境配置。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        try:
            env.is_shared = True
            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "共享成功",
                "data": env.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"共享失败: {str(e)}"}), 500

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('update')
    def delete(self, project_id, env_id):
        """取消共享环境配置。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        try:
            env.is_shared = False
            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "取消共享成功",
                "data": env.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"取消共享失败: {str(e)}"}), 500


# ============================================================
# 环境变量路由（按环境分组，复用 environment_blp）
# ============================================================
@environment_blp.route("/<int:env_id>/variables")
class EnvVariablesByEnvironmentView(MethodView):
    """按环境分组的环境变量列表与创建"""

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id, env_id):
        """获取指定环境下的所有环境变量。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        variables = EnvironmentVariable.query.filter_by(
            project_id=project_id, environment_id=env_id
        ).order_by(EnvironmentVariable.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [v.to_dict() for v in variables]
        })

    @environment_blp.response(200, MessageResponseSchema)
    @environment_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('create')
    def post(self, project_id, env_id):
        """在指定环境下创建环境变量。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "变量名不能为空"}), 400

        # 检查同项目下变量名唯一性
        existing = EnvironmentVariable.query.filter_by(
            project_id=project_id, name=name
        ).first()
        if existing:
            return jsonify({"code": 1, "message": "变量名已存在"}), 400

        try:
            variable = EnvironmentVariable(
                name=name,
                value=data.get("value", ""),
                remark=data.get("remark", ""),
                project_id=project_id,
                environment_id=env_id
            )
            db.session.add(variable)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": variable.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@environment_blp.route("/<int:env_id>/variables/<int:variable_id>")
class EnvVariableByEnvironmentDetailView(MethodView):
    """按环境分组的环境变量更新与删除"""

    @environment_blp.response(200, MessageResponseSchema)
    @environment_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, env_id, variable_id):
        """更新指定环境下的环境变量。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        variable = EnvironmentVariable.query.filter_by(
            id=variable_id, project_id=project_id, environment_id=env_id
        ).first()
        if not variable:
            return jsonify({"code": 1, "message": "环境变量不存在"}), 404

        data = request.get_json()
        name = (data.get("name") or "").strip()

        if not name:
            return jsonify({"code": 1, "message": "变量名不能为空"}), 400

        # 检查唯一性（排除自身）
        existing = EnvironmentVariable.query.filter(
            EnvironmentVariable.project_id == project_id,
            EnvironmentVariable.name == name,
            EnvironmentVariable.id != variable_id
        ).first()
        if existing:
            return jsonify({"code": 1, "message": "变量名已存在"}), 400

        try:
            variable.name = name
            variable.value = data.get("value", "")
            variable.remark = data.get("remark", "")
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": variable.to_dict()
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @environment_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, env_id, variable_id):
        """删除指定环境下的环境变量。"""
        env = Environment.query.filter_by(
            id=env_id, project_id=project_id
        ).first()
        if not env:
            return jsonify({"code": 1, "message": "环境不存在"}), 404

        variable = EnvironmentVariable.query.filter_by(
            id=variable_id, project_id=project_id, environment_id=env_id
        ).first()
        if not variable:
            return jsonify({"code": 1, "message": "环境变量不存在"}), 404

        try:
            db.session.delete(variable)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500
