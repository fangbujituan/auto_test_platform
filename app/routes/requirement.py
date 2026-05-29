"""
需求管理路由。

作者: yandc
创建时间: 2026-03-12
"""
from flask import request, jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.requirement import Requirement, RequirementStatus
from app.models.tag import Tag
from app.models.operation_log import OperationLog
from app.utils.permission import login_required
from app.schemas.common import MessageResponseSchema

requirement_blp = Blueprint(
    "requirement", __name__,
    url_prefix="/api/requirements",
    description="需求管理"
)

tag_blp = Blueprint(
    "tag", __name__,
    url_prefix="/api/tags",
    description="标签管理"
)

operation_log_blp = Blueprint(
    "operation_log", __name__,
    url_prefix="/api/operation-logs",
    description="操作日志"
)


def log_operation(api_name, action, target_type=None, target_id=None, project_id=None, detail=None):
    """记录操作日志。"""
    current_user = g.get("current_user")
    if not current_user:
        return
    log = OperationLog(
        api_name=api_name,
        action=action,
        operator_id=current_user.id,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.session.add(log)


# ==================== 需求接口 ====================

@requirement_blp.route("")
class RequirementsView(MethodView):
    """需求列表与创建"""

    @requirement_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取需求列表，支持分页和筛选。"""
        project_id = request.args.get("project_id", type=int)
        if not project_id:
            return jsonify({"code": 1, "message": "缺少project_id参数"}), 400

        query = Requirement.query.filter_by(project_id=project_id)

        sprint_id = request.args.get("sprint_id", type=int)
        status = request.args.get("status")
        priority = request.args.get("priority")
        assignee_id = request.args.get("assignee_id", type=int)
        keyword = request.args.get("keyword")

        if sprint_id:
            query = query.filter_by(sprint_id=sprint_id)
        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if assignee_id:
            query = query.filter(db.func.json_contains(Requirement.assignee_ids, str(assignee_id)))
        if keyword:
            kw = f"%{keyword}%"
            query = query.filter(
                db.or_(
                    Requirement.title.like(kw),
                    Requirement.req_number.like(kw),
                    Requirement.description.like(kw),
                )
            )

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        pagination = query.order_by(Requirement.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            "code": 0,
            "data": {
                "items": [r.to_dict() for r in pagination.items],
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
            }
        })

    @requirement_blp.response(201, MessageResponseSchema)
    @requirement_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    def post(self):
        """创建新的需求，自动生成需求编号。"""
        data = request.get_json()
        try:
            current_user = g.get("current_user")
            req = Requirement(
                title=data["title"],
                req_number=Requirement.generate_req_number(),
                description=data.get("description"),
                project_id=data["project_id"],
                sprint_id=data.get("sprint_id"),
                assignee_ids=data.get("assignee_ids", []),
                creator_id=current_user.id,
                status=data.get("status", RequirementStatus.DRAFT.value),
                priority=data.get("priority", "medium"),
            )

            tag_ids = data.get("tag_ids", [])
            if tag_ids:
                tags = Tag.query.filter(Tag.id.in_(tag_ids)).all()
                req.tags = tags

            db.session.add(req)
            db.session.flush()
            log_operation("POST /api/requirements", f"创建需求: {req.title}", "requirement", req.id, req.project_id)
            db.session.commit()
            return jsonify({"code": 0, "message": "创建成功", "data": req.to_dict()}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@requirement_blp.route("/<int:req_id>")
class RequirementDetailView(MethodView):
    """需求详情、更新与删除"""

    @requirement_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self, req_id):
        """获取需求详情。"""
        req = Requirement.query.get_or_404(req_id)
        return jsonify({"code": 0, "data": req.to_dict()})

    @requirement_blp.response(200, MessageResponseSchema)
    @requirement_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    def put(self, req_id):
        """更新需求。"""
        req = Requirement.query.get_or_404(req_id)
        data = request.get_json()
        try:
            for field in ["title", "description", "sprint_id", "assignee_ids", "status", "priority"]:
                if field in data:
                    setattr(req, field, data[field])

            if "tag_ids" in data:
                tags = Tag.query.filter(Tag.id.in_(data["tag_ids"])).all()
                req.tags = tags

            log_operation("PUT /api/requirements", f"更新需求: {req.title}", "requirement", req.id, req.project_id)
            db.session.commit()
            return jsonify({"code": 0, "message": "更新成功", "data": req.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @requirement_blp.response(200, MessageResponseSchema)
    @requirement_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    def delete(self, req_id):
        """删除需求。"""
        req = Requirement.query.get_or_404(req_id)
        try:
            log_operation("DELETE /api/requirements", f"删除需求: {req.title}", "requirement", req.id, req.project_id)
            db.session.delete(req)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500


@requirement_blp.route("/statuses")
class RequirementStatusView(MethodView):
    """需求状态枚举"""

    @requirement_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取所有需求状态枚举值。"""
        statuses = [{"value": s.value, "label": s.name} for s in RequirementStatus]
        return jsonify({"code": 0, "data": statuses})


# ==================== 标签接口 ====================

@tag_blp.route("")
class TagsView(MethodView):
    """标签列表与创建"""

    @tag_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取所有标签。"""
        tags = Tag.query.order_by(Tag.name).all()
        return jsonify({"code": 0, "data": [t.to_dict() for t in tags]})

    @tag_blp.response(201, MessageResponseSchema)
    @tag_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    def post(self):
        """创建新标签。"""
        data = request.get_json()
        try:
            existing = Tag.query.filter_by(name=data["name"]).first()
            if existing:
                return jsonify({"code": 1, "message": "标签名已存在"}), 400
            tag = Tag(name=data["name"], color=data.get("color", "#409EFF"))
            db.session.add(tag)
            db.session.commit()
            return jsonify({"code": 0, "message": "创建成功", "data": tag.to_dict()}), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@tag_blp.route("/<int:tag_id>")
class TagDetailView(MethodView):
    """标签删除"""

    @tag_blp.response(200, MessageResponseSchema)
    @tag_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    def delete(self, tag_id):
        """删除标签。"""
        tag = Tag.query.get_or_404(tag_id)
        try:
            db.session.delete(tag)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500


# ==================== 操作日志接口 ====================

@operation_log_blp.route("")
class OperationLogsView(MethodView):
    """操作日志列表"""

    @operation_log_blp.response(200, MessageResponseSchema)
    @login_required
    def get(self):
        """获取操作日志列表，支持分页。"""
        query = OperationLog.query

        project_id = request.args.get("project_id", type=int)
        operator_id = request.args.get("operator_id", type=int)
        target_type = request.args.get("target_type")

        if project_id:
            query = query.filter_by(project_id=project_id)
        if operator_id:
            query = query.filter_by(operator_id=operator_id)
        if target_type:
            query = query.filter_by(target_type=target_type)

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        pagination = query.order_by(OperationLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            "code": 0,
            "data": {
                "items": [log.to_dict() for log in pagination.items],
                "total": pagination.total,
                "page": pagination.page,
                "per_page": pagination.per_page,
                "pages": pagination.pages,
            }
        })
