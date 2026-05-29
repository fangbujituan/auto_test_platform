"""
环境变量管理路由。

作者: yandc
创建时间: 2026-04-03
"""
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.env_variable import EnvironmentVariable
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema

env_variable_blp = Blueprint(
    "env_variable", __name__,
    url_prefix="/api/projects/<int:project_id>/env-variables",
    description="环境变量管理"
)


@env_variable_blp.route("")
class EnvVariablesView(MethodView):
    """环境变量列表与创建"""

    @env_variable_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有环境变量。"""
        variables = EnvironmentVariable.query.filter_by(
            project_id=project_id
        ).order_by(EnvironmentVariable.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [v.to_dict() for v in variables]
        })

    @env_variable_blp.response(200, MessageResponseSchema)
    @env_variable_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建环境变量。"""
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


@env_variable_blp.route("/<int:variable_id>")
class EnvVariableDetailView(MethodView):
    """环境变量更新与删除"""

    @env_variable_blp.response(200, MessageResponseSchema)
    @env_variable_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, variable_id):
        """更新环境变量。"""
        variable = EnvironmentVariable.query.filter_by(
            id=variable_id, project_id=project_id
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

    @env_variable_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, variable_id):
        """删除环境变量。"""
        variable = EnvironmentVariable.query.filter_by(
            id=variable_id, project_id=project_id
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
