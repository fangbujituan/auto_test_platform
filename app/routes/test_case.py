# -*- coding: utf-8 -*-
"""
测试用例管理API。

作者: yandc
创建时间: 2026-01-19
"""
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.test_case import TestCaseManagement, TestCaseApiBinding
from app.models.module import Module
from app.models.project import Project
from app.models.api import Api
from app.models.api_folder import ApiFolder
from app.utils.permission import require_permission
from app.schemas.common import MessageResponseSchema

test_case_blp = Blueprint(
    "test_case", __name__,
    url_prefix="/api/test-cases",
    description="测试用例管理"
)

# 向后兼容
test_case_bp = test_case_blp


def generate_case_no(project_id):
    """生成用例编号（格式：TC-项目ID-序号）。"""
    prefix = f"TC-{project_id}-"
    last_case = TestCaseManagement.query.filter(
        TestCaseManagement.project_id == project_id,
        TestCaseManagement.case_no.like(f"{prefix}%")
    ).order_by(TestCaseManagement.case_no.desc()).first()

    if last_case:
        try:
            last_no = int(last_case.case_no.split("-")[-1])
            new_no = last_no + 1
        except (ValueError, IndexError):
            new_no = 1
    else:
        new_no = 1

    return f"{prefix}{new_no:04d}"


@test_case_blp.route("/tree/<int:project_id>")
class TestCaseTreeView(MethodView):
    """测试用例目录树"""

    @test_case_blp.response(200, MessageResponseSchema)
    @test_case_blp.alt_response(500, schema=MessageResponseSchema, description="获取失败")
    @require_permission("test_case:read")
    def get(self, project_id):
        """获取测试用例目录树（包含测试用例），支持多级嵌套。"""

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
            ).filter(
                (ApiFolder.type != ApiFolder.TYPE_AUTOMATION)
                | (ApiFolder.type.is_(None))
            ).order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()

            for child_folder in child_folders:
                node['children'].append(build_tree_node(child_folder))

            test_cases = TestCaseManagement.query.filter_by(
                project_id=project_id,
                folder_id=folder.id,
                status=1
            ).order_by(TestCaseManagement.created_at.desc()).all()

            for tc in test_cases:
                case_node = {
                    'id': f'case_{tc.id}',
                    'raw_id': tc.id,
                    'name': tc.title,
                    'case_no': tc.case_no,
                    'description': tc.description,
                    'type': 'case',
                    'priority': tc.priority,
                    'case_type': tc.case_type,
                    'case_status': tc.case_status,
                    'folder_id': tc.folder_id,
                    'module_id': tc.module_id,
                    'created_at': tc.created_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    'updated_at': tc.updated_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    'children': []
                }
                node['children'].append(case_node)

            return node

        try:
            root_folders = ApiFolder.query.filter_by(
                project_id=project_id, parent_id=None
            ).filter(
                (ApiFolder.type != ApiFolder.TYPE_AUTOMATION)
                | (ApiFolder.type.is_(None))
            ).order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()

            tree = [build_tree_node(folder) for folder in root_folders]

            uncategorized_cases = TestCaseManagement.query.filter_by(
                project_id=project_id, folder_id=None, status=1
            ).order_by(TestCaseManagement.created_at.desc()).all()

            if uncategorized_cases:
                uncategorized_node = {
                    'id': 'folder_uncategorized',
                    'raw_id': 0,
                    'name': '未分类',
                    'description': '未分配到目录的测试用例',
                    'type': 'folder',
                    'is_virtual': True,
                    'project_id': project_id,
                    'parent_id': None,
                    'sort_order': 999,
                    'children': []
                }

                for tc in uncategorized_cases:
                    case_node = {
                        'id': f'case_{tc.id}',
                        'raw_id': tc.id,
                        'name': tc.title,
                        'case_no': tc.case_no,
                        'description': tc.description,
                        'type': 'case',
                        'priority': tc.priority,
                        'case_type': tc.case_type,
                        'case_status': tc.case_status,
                        'folder_id': tc.folder_id,
                        'module_id': tc.module_id,
                        'created_at': tc.created_at.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        'updated_at': tc.updated_at.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        'children': []
                    }
                    uncategorized_node['children'].append(case_node)

                tree.append(uncategorized_node)

            return jsonify({"code": 0, "data": tree})

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"获取目录树失败: {str(e)}"
            }), 500


@test_case_blp.route("")
class TestCasesView(MethodView):
    """测试用例列表与创建"""

    @test_case_blp.response(200, MessageResponseSchema)
    @require_permission("test_case:read")
    def get(self):
        """获取测试用例列表。"""
        project_id = request.args.get("project_id", type=int)
        module_id = request.args.get("module_id", type=int)
        folder_id = request.args.get("folder_id", type=int)
        priority = request.args.get("priority")
        case_type = request.args.get("case_type")
        case_status = request.args.get("case_status")
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)

        query = TestCaseManagement.query

        if project_id:
            query = query.filter_by(project_id=project_id)
        if module_id:
            query = query.filter_by(module_id=module_id)
        if folder_id is not None:
            query = query.filter_by(folder_id=folder_id)
        if priority:
            query = query.filter_by(priority=priority)
        if case_type:
            query = query.filter_by(case_type=case_type)
        if case_status:
            query = query.filter_by(case_status=case_status)

        pagination = query.order_by(
            TestCaseManagement.id.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            "items": [
                tc.to_dict(include_apis=True)
                for tc in pagination.items
            ],
            "total": pagination.total,
            "page": page,
            "per_page": per_page,
            "pages": pagination.pages
        })

    @test_case_blp.response(201, MessageResponseSchema)
    @test_case_blp.alt_response(400, schema=MessageResponseSchema, description="参数错误")
    @test_case_blp.alt_response(404, schema=MessageResponseSchema, description="资源不存在")
    @require_permission("test_case:create")
    def post(self):
        """创建测试用例。"""
        data = request.get_json()

        if not data.get("title"):
            return jsonify({"error": "用例标题不能为空"}), 400
        if not data.get("project_id"):
            return jsonify({"error": "项目ID不能为空"}), 400

        project = Project.query.get(data["project_id"])
        if not project:
            return jsonify({"error": "项目不存在"}), 404

        module_id = data.get("module_id")
        if module_id:
            module = Module.query.get(module_id)
            if not module:
                return jsonify({"error": "模块不存在"}), 404
            if module.project_id != data["project_id"]:
                return jsonify({"error": "模块不属于该项目"}), 400

        folder_id = data.get("folder_id")
        if folder_id:
            folder = ApiFolder.query.get(folder_id)
            if not folder:
                return jsonify({"error": "目录不存在"}), 404
            if folder.project_id != data["project_id"]:
                return jsonify({"error": "目录不属于该项目"}), 400

        case_no = generate_case_no(data["project_id"])

        test_case = TestCaseManagement(
            case_no=case_no,
            title=data["title"],
            description=data.get("description"),
            precondition=data.get("precondition"),
            steps=data.get("steps"),
            expected_result=data.get("expected_result"),
            project_id=data["project_id"],
            module_id=module_id,
            folder_id=folder_id,
            priority=data.get("priority", "P2"),
            case_type=data.get("case_type", "功能"),
            case_status=data.get("case_status", "草稿"),
            status=data.get("status", 1)
        )

        db.session.add(test_case)
        db.session.flush()

        api_ids = data.get("api_ids", [])
        if api_ids:
            for idx, api_id in enumerate(api_ids):
                api = Api.query.get(api_id)
                if not api:
                    db.session.rollback()
                    return jsonify({
                        "error": f"API {api_id} 不存在"
                    }), 404
                if api.project_id != data["project_id"]:
                    db.session.rollback()
                    return jsonify({
                        "error": f"API {api_id} 不属于该项目"
                    }), 400

                binding = TestCaseApiBinding(
                    test_case_id=test_case.id,
                    api_id=api_id,
                    sort_order=idx
                )
                db.session.add(binding)

        db.session.commit()

        return jsonify(test_case.to_dict(include_apis=True)), 201


@test_case_blp.route("/<int:case_id>")
class TestCaseDetailView(MethodView):
    """测试用例详情、更新与删除"""

    @test_case_blp.response(200, MessageResponseSchema)
    @require_permission("test_case:read")
    def get(self, case_id):
        """获取测试用例详情。"""
        test_case = TestCaseManagement.query.get(case_id)
        if not test_case:
            return jsonify({"error": "测试用例不存在"}), 404

        return jsonify(test_case.to_dict(include_apis=True))

    @test_case_blp.response(200, MessageResponseSchema)
    @test_case_blp.alt_response(404, schema=MessageResponseSchema, description="不存在")
    @require_permission("test_case:update")
    def put(self, case_id):
        """更新测试用例。"""
        test_case = TestCaseManagement.query.get(case_id)
        if not test_case:
            return jsonify({"error": "测试用例不存在"}), 404

        data = request.get_json()

        # 验证 module_id
        if "module_id" in data and data["module_id"]:
            module = Module.query.get(data["module_id"])
            if not module:
                return jsonify({"error": "模块不存在"}), 404
            if module.project_id != test_case.project_id:
                return jsonify({"error": "模块不属于该项目"}), 400
            test_case.module_id = data["module_id"]

        # 验证 folder_id
        if "folder_id" in data:
            if data["folder_id"]:
                folder = ApiFolder.query.get(data["folder_id"])
                if not folder:
                    return jsonify({"error": "目录不存在"}), 404
                if folder.project_id != test_case.project_id:
                    return jsonify({"error": "目录不属于该项目"}), 400
            test_case.folder_id = data["folder_id"]

        for field in [
            "title", "description", "precondition", "steps",
            "expected_result", "priority", "case_type",
            "case_status", "status"
        ]:
            if field in data:
                setattr(test_case, field, data[field])

        if "api_ids" in data:
            TestCaseApiBinding.query.filter_by(
                test_case_id=case_id
            ).delete()

            for idx, api_id in enumerate(data["api_ids"]):
                api = Api.query.get(api_id)
                if not api:
                    db.session.rollback()
                    return jsonify({
                        "error": f"API {api_id} 不存在"
                    }), 404
                if api.project_id != test_case.project_id:
                    db.session.rollback()
                    return jsonify({
                        "error": f"API {api_id} 不属于该项目"
                    }), 400

                binding = TestCaseApiBinding(
                    test_case_id=case_id,
                    api_id=api_id,
                    sort_order=idx
                )
                db.session.add(binding)

        db.session.commit()

        return jsonify(test_case.to_dict(include_apis=True))

    @test_case_blp.response(200, MessageResponseSchema)
    @require_permission("test_case:delete")
    def delete(self, case_id):
        """删除测试用例。"""
        test_case = TestCaseManagement.query.get(case_id)
        if not test_case:
            return jsonify({"error": "测试用例不存在"}), 404

        db.session.delete(test_case)
        db.session.commit()

        return jsonify({"message": "删除成功"})


@test_case_blp.route("/statistics")
class TestCaseStatisticsView(MethodView):
    """测试用例统计"""

    @test_case_blp.response(200, MessageResponseSchema)
    @require_permission("test_case:read")
    def get(self):
        """获取测试用例统计信息。"""
        project_id = request.args.get("project_id", type=int)
        module_id = request.args.get("module_id", type=int)

        if not project_id:
            return jsonify({"error": "项目ID不能为空"}), 400

        query = TestCaseManagement.query.filter_by(
            project_id=project_id
        )

        if module_id:
            module = Module.query.get(module_id)
            if not module:
                return jsonify({"error": "模块不存在"}), 404

            def get_all_child_ids(mod_id):
                ids = [mod_id]
                children = Module.query.filter_by(
                    parent_id=mod_id
                ).all()
                for child in children:
                    ids.extend(get_all_child_ids(child.id))
                return ids

            module_ids = get_all_child_ids(module_id)
            query = query.filter(
                TestCaseManagement.module_id.in_(module_ids)
            )

        total_cases = query.count()
        automated_cases = query.join(
            TestCaseApiBinding
        ).distinct().count()

        priority_stats = {}
        for p in ["P0", "P1", "P2", "P3"]:
            priority_stats[p] = query.filter_by(priority=p).count()

        status_stats = {}
        for s in ["草稿", "已评审", "已废弃"]:
            status_stats[s] = query.filter_by(case_status=s).count()

        type_stats = {}
        for t in ["功能", "性能", "安全"]:
            type_stats[t] = query.filter_by(case_type=t).count()

        automation_rate = (
            (automated_cases / total_cases * 100)
            if total_cases > 0 else 0
        )

        return jsonify({
            "total_cases": total_cases,
            "automated_cases": automated_cases,
            "automation_rate": round(automation_rate, 2),
            "priority_stats": priority_stats,
            "status_stats": status_stats,
            "type_stats": type_stats
        })
