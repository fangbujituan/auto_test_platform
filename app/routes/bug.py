"""
Bug管理路由。

作者: yandc
创建时间: 2026-01-22
"""
from datetime import datetime
from flask import request, jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.bug import Bug
from app.models.api_folder import ApiFolder
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema

bug_blp = Blueprint(
    "bug", __name__,
    url_prefix="/api/projects/<int:project_id>/bugs",
    description="Bug管理"
)

# 向后兼容
bug_bp = bug_blp


@bug_blp.route("/tree")
class BugTreeView(MethodView):
    """Bug目录树"""

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="获取失败")
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取Bug目录树（包含Bug），支持多级嵌套。"""

        def build_tree_node(folder):
            node = {
                'id': f'folder_{folder.id}',
                'raw_id': folder.id,
                'name': folder.name,
                'description': folder.description,
                'type': 'folder',
                'project_id': folder.project_id,
                'parent_id': folder.parent_id,
                'sort_order': folder.sort_order,
                'created_at': folder.created_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                'updated_at': folder.updated_at.strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                'children': []
            }

            child_folders = ApiFolder.query.filter_by(
                project_id=project_id, parent_id=folder.id
            ).order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()

            for child_folder in child_folders:
                node['children'].append(build_tree_node(child_folder))

            bugs = Bug.query.filter_by(
                project_id=project_id, folder_id=folder.id
            ).order_by(Bug.created_at.desc()).all()

            for bug in bugs:
                bug_node = {
                    'id': f'bug_{bug.id}',
                    'raw_id': bug.id,
                    'name': bug.title,
                    'description': bug.description,
                    'type': 'bug',
                    'status': bug.status,
                    'priority': bug.priority,
                    'severity': bug.severity,
                    'folder_id': bug.folder_id,
                    'created_at': bug.created_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    'updated_at': bug.updated_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    'children': []
                }
                node['children'].append(bug_node)

            return node

        try:
            root_folders = ApiFolder.query.filter_by(
                project_id=project_id, parent_id=None
            ).order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()

            tree = [build_tree_node(folder) for folder in root_folders]

            uncategorized_bugs = Bug.query.filter_by(
                project_id=project_id, folder_id=None
            ).order_by(Bug.created_at.desc()).all()

            if uncategorized_bugs:
                uncategorized_node = {
                    'id': 'folder_uncategorized',
                    'raw_id': 0,
                    'name': '未分类',
                    'description': '未分配到目录的Bug',
                    'type': 'folder',
                    'is_virtual': True,
                    'project_id': project_id,
                    'parent_id': None,
                    'sort_order': 999,
                    'children': []
                }

                for bug in uncategorized_bugs:
                    bug_node = {
                        'id': f'bug_{bug.id}',
                        'raw_id': bug.id,
                        'name': bug.title,
                        'description': bug.description,
                        'type': 'bug',
                        'status': bug.status,
                        'priority': bug.priority,
                        'severity': bug.severity,
                        'folder_id': bug.folder_id,
                        'created_at': bug.created_at.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        'updated_at': bug.updated_at.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        'children': []
                    }
                    uncategorized_node['children'].append(bug_node)

                tree.append(uncategorized_node)

            return jsonify({"code": 0, "data": tree})

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"获取目录树失败: {str(e)}"
            }), 500


@bug_blp.route("")
class BugsView(MethodView):
    """Bug列表与创建"""

    @bug_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的所有Bug。"""
        status = request.args.get('status')
        priority = request.args.get('priority')
        severity = request.args.get('severity')
        folder_id = request.args.get('folder_id', type=int)
        assignee_id = request.args.get('assignee_id', type=int)
        reporter_id = request.args.get('reporter_id', type=int)
        keyword = request.args.get('keyword')

        query = Bug.query.filter_by(project_id=project_id)

        if status:
            query = query.filter_by(status=status)
        if priority:
            query = query.filter_by(priority=priority)
        if severity:
            query = query.filter_by(severity=severity)
        if folder_id is not None:
            query = query.filter_by(folder_id=folder_id)
        if assignee_id:
            query = query.filter_by(assignee_id=assignee_id)
        if reporter_id:
            query = query.filter_by(reporter_id=reporter_id)
        if keyword:
            query = query.filter(
                db.or_(
                    Bug.title.like(f'%{keyword}%'),
                    Bug.description.like(f'%{keyword}%'),
                    Bug.module.like(f'%{keyword}%')
                )
            )

        bugs = query.order_by(Bug.created_at.desc()).all()

        return jsonify({
            "code": 0,
            "data": [bug.to_dict() for bug in bugs]
        })

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建新的Bug。"""
        data = request.get_json()

        try:
            current_user = g.get('current_user')

            bug = Bug(
                title=data.get("title"),
                description=data.get("description"),
                project_id=project_id,
                status=data.get("status", "open"),
                priority=data.get("priority", "medium"),
                severity=data.get("severity", "normal"),
                category=data.get("category"),
                module=data.get("module"),
                folder_id=data.get("folder_id"),
                tags=data.get("tags", []),
                reporter_id=data.get(
                    "reporter_id",
                    current_user.id if current_user else None
                ),
                assignee_id=data.get("assignee_id"),
                environment=data.get("environment"),
                version=data.get("version"),
                steps_to_reproduce=data.get("steps_to_reproduce"),
                expected_result=data.get("expected_result"),
                actual_result=data.get("actual_result"),
                attachments=data.get("attachments", []),
                related_apis=data.get("related_apis", []),
                related_test_cases=data.get("related_test_cases", [])
            )

            db.session.add(bug)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": bug.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}"
            }), 500


@bug_blp.route("/<int:bug_id>")
class BugDetailView(MethodView):
    """Bug详情、更新与删除"""

    @bug_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id, bug_id):
        """获取单个Bug详情。"""
        bug = Bug.query.filter_by(
            id=bug_id, project_id=project_id
        ).first_or_404()
        return jsonify({"code": 0, "data": bug.to_dict()})

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, bug_id):
        """更新Bug。"""
        bug = Bug.query.filter_by(
            id=bug_id, project_id=project_id
        ).first_or_404()
        data = request.get_json()

        try:
            for field in [
                "title", "description", "status", "priority", "severity",
                "category", "module", "folder_id", "tags", "assignee_id",
                "environment", "version", "steps_to_reproduce",
                "expected_result", "actual_result", "attachments",
                "related_apis", "related_test_cases"
            ]:
                if field in data:
                    setattr(bug, field, data[field])

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": bug.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}"
            }), 500

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, bug_id):
        """删除Bug。"""
        bug = Bug.query.filter_by(
            id=bug_id, project_id=project_id
        ).first_or_404()

        try:
            db.session.delete(bug)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}"
            }), 500


@bug_blp.route("/<int:bug_id>/resolve")
class BugResolveView(MethodView):
    """解决Bug"""

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="操作失败")
    @login_required
    @check_project_permission('update')
    def post(self, project_id, bug_id):
        """解决Bug。"""
        bug = Bug.query.filter_by(
            id=bug_id, project_id=project_id
        ).first_or_404()
        data = request.get_json()

        try:
            current_user = g.get('current_user')

            bug.status = "resolved"
            bug.resolution = data.get("resolution", "fixed")
            bug.resolution_note = data.get("resolution_note")
            bug.resolved_at = datetime.now()
            bug.resolved_by = (
                current_user.id if current_user else None
            )

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "Bug已解决",
                "data": bug.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"操作失败: {str(e)}"
            }), 500


@bug_blp.route("/<int:bug_id>/reopen")
class BugReopenView(MethodView):
    """重新打开Bug"""

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="操作失败")
    @login_required
    @check_project_permission('update')
    def post(self, project_id, bug_id):
        """重新打开Bug。"""
        bug = Bug.query.filter_by(
            id=bug_id, project_id=project_id
        ).first_or_404()

        try:
            bug.status = "reopened"
            bug.resolution = None
            bug.resolution_note = None
            bug.resolved_at = None
            bug.resolved_by = None

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "Bug已重新打开",
                "data": bug.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"操作失败: {str(e)}"
            }), 500


@bug_blp.route("/statistics")
class BugStatisticsView(MethodView):
    """Bug统计"""

    @bug_blp.response(200, MessageResponseSchema)
    @bug_blp.alt_response(500, schema=MessageResponseSchema, description="获取失败")
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取Bug统计信息。"""
        try:
            status_stats = db.session.query(
                Bug.status, db.func.count(Bug.id)
            ).filter_by(
                project_id=project_id
            ).group_by(Bug.status).all()

            priority_stats = db.session.query(
                Bug.priority, db.func.count(Bug.id)
            ).filter_by(
                project_id=project_id
            ).group_by(Bug.priority).all()

            severity_stats = db.session.query(
                Bug.severity, db.func.count(Bug.id)
            ).filter_by(
                project_id=project_id
            ).group_by(Bug.severity).all()

            return jsonify({
                "code": 0,
                "data": {
                    "by_status": {
                        s: c for s, c in status_stats
                    },
                    "by_priority": {
                        p: c for p, c in priority_stats
                    },
                    "by_severity": {
                        s: c for s, c in severity_stats
                    },
                    "total": Bug.query.filter_by(
                        project_id=project_id
                    ).count()
                }
            })

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"获取统计信息失败: {str(e)}"
            }), 500
