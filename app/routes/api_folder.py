"""
API目录管理路由。

作者: yandc
创建时间: 2026-01-16
"""
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from sqlalchemy import and_, or_
from app.models.base import db
from app.models.api_folder import ApiFolder
from app.models.api import Api
from app.models.bug import Bug
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema

folder_blp = Blueprint(
    "api_folder", __name__,
    url_prefix="/api/projects/<int:project_id>/folders",
    description="API目录管理"
)

# 向后兼容
folder_bp = folder_blp


_VALID_FOLDER_TYPES = {
    ApiFolder.TYPE_API,
    ApiFolder.TYPE_TESTCASE,
    ApiFolder.TYPE_BUG,
    ApiFolder.TYPE_AUTOMATION,
}


def _resolve_folder_type(raw, default=ApiFolder.TYPE_API):
    """规范化前端传入的 type 参数，无效值落回默认。"""
    if raw is None or raw == "":
        return default
    raw = str(raw).strip().lower()
    if raw in _VALID_FOLDER_TYPES:
        return raw
    return default


def _folder_type_filter(query, folder_type):
    """给 ApiFolder 查询追加 type 过滤；老数据 type 为空时按 'api' 处理。"""
    if folder_type == ApiFolder.TYPE_API:
        return query.filter(
            or_(ApiFolder.type == ApiFolder.TYPE_API, ApiFolder.type.is_(None))
        )
    return query.filter(ApiFolder.type == folder_type)


@folder_blp.route("/init")
class FolderInitView(MethodView):
    """初始化项目目录"""

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(400, schema=MessageResponseSchema, description="已有目录")
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="初始化失败")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """为项目初始化默认目录结构。"""
        try:
            existing_count = ApiFolder.query.filter_by(
                project_id=project_id
            ).count()
            if existing_count > 0:
                return jsonify({
                    "code": 1,
                    "message": f"项目已有 {existing_count} 个目录，无需初始化"
                }), 400

            default_folders = [
                {"name": "用户模块", "description": "用户相关接口",
                 "sort_order": 1},
                {"name": "系统模块", "description": "系统相关接口",
                 "sort_order": 2},
                {"name": "业务模块", "description": "业务相关接口",
                 "sort_order": 3},
            ]

            created_folders = []
            for folder_data in default_folders:
                folder = ApiFolder(
                    name=folder_data["name"],
                    description=folder_data["description"],
                    project_id=project_id,
                    parent_id=None,
                    sort_order=folder_data["sort_order"]
                )
                db.session.add(folder)
                db.session.flush()
                created_folders.append(folder)

            # 智能分配现有接口到目录
            apis = Api.query.filter_by(
                project_id=project_id, folder_id=None
            ).all()
            folder_map = {f.name: f for f in created_folders}

            for api in apis:
                folder = None

                if api.category:
                    cat = api.category.lower()
                    if '用户' in cat or 'user' in cat:
                        folder = folder_map.get("用户模块")
                    elif '系统' in cat or 'system' in cat:
                        folder = folder_map.get("系统模块")
                    else:
                        folder = folder_map.get("业务模块")

                if not folder:
                    name_lower = api.name.lower()
                    path_lower = api.path.lower()

                    if any(k in name_lower or k in path_lower
                           for k in ['user', '用户']):
                        folder = folder_map.get("用户模块")
                    elif any(k in name_lower
                             for k in ['auth', 'login', 'register']):
                        folder = folder_map.get("用户模块")
                    elif any(k in name_lower or k in path_lower
                             for k in ['system', 'config', '系统']):
                        folder = folder_map.get("系统模块")
                    else:
                        folder = folder_map.get("业务模块")

                if folder:
                    api.folder_id = folder.id

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": (
                    f"初始化成功，创建了 {len(created_folders)} 个目录，"
                    f"分配了 {len(apis)} 个接口"
                ),
                "data": {
                    "folders": [f.to_dict() for f in created_folders],
                    "assigned_apis": len(apis)
                }
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"初始化失败: {str(e)}"
            }), 500


@folder_blp.route("")
class FoldersView(MethodView):
    """目录列表与创建"""

    @folder_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目的目录树结构（按 type 过滤）。"""
        folder_type = _resolve_folder_type(request.args.get("type"))

        query = ApiFolder.query.filter_by(
            project_id=project_id, parent_id=None
        )
        query = _folder_type_filter(query, folder_type)
        root_folders = query.order_by(ApiFolder.sort_order).all()

        # to_dict 的 include_children 没有 type 过滤；这里直接收集子目录是同 type 的
        # 对于 type=api（老数据全是 api 类型），等价于现状
        def _walk(folder):
            node = folder.to_dict()
            children = (
                ApiFolder.query
                .filter_by(project_id=project_id, parent_id=folder.id)
            )
            children = _folder_type_filter(children, folder_type)
            node["children"] = [
                _walk(c) for c in children.order_by(ApiFolder.sort_order).all()
            ]
            return node

        tree = [_walk(f) for f in root_folders]
        return jsonify({"code": 0, "data": tree})

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建目录。"""
        data = request.get_json() or {}
        folder_type = _resolve_folder_type(data.get("type"))

        # 父目录归属与类型一致性校验
        parent_id = data.get("parent_id")
        if parent_id:
            parent = ApiFolder.query.filter_by(
                id=parent_id, project_id=project_id
            ).first()
            if not parent:
                return jsonify({
                    "code": 1, "message": "父目录不存在"
                }), 404
            parent_type = parent.type or ApiFolder.TYPE_API
            if parent_type != folder_type:
                return jsonify({
                    "code": 1,
                    "message": f"父目录类型不匹配: 父={parent_type}, 当前={folder_type}",
                }), 400

        try:
            folder = ApiFolder(
                name=data.get("name"),
                description=data.get("description"),
                project_id=project_id,
                parent_id=parent_id,
                sort_order=data.get("sort_order", 0),
                type=folder_type,
            )

            db.session.add(folder)
            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": folder.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}"
            }), 500


@folder_blp.route("/tree")
class FolderTreeView(MethodView):
    """完整目录树（默认含接口；type=automation 时含自动化任务）"""

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="获取失败")
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取完整的目录树。

        Query 参数：
        - ``type`` ：api(默认) / automation
        """
        folder_type = _resolve_folder_type(request.args.get("type"))

        if folder_type == ApiFolder.TYPE_AUTOMATION:
            return self._build_automation_tree(project_id)

        # 默认：接口目录树（与历史行为完全一致，并加 type=api 过滤）
        return self._build_api_tree(project_id)

    # ------------------------------------------------------------------
    # 接口目录树（原实现，仅追加 type 过滤）
    # ------------------------------------------------------------------

    def _build_api_tree(self, project_id):
        """构建接口目录树（type=api）。"""

        def build_tree_node(folder):
            """递归构建包含接口的树节点。"""
            node = {
                'id': f'folder_{folder.id}',
                'raw_id': folder.id,
                'name': folder.name,
                'description': folder.description,
                'type': 'folder',
                'folder_type': folder.type or ApiFolder.TYPE_API,
                'project_id': folder.project_id,
                'parent_id': folder.parent_id,
                'sort_order': folder.sort_order,
                'created_at': folder.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'updated_at': folder.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                'children': []
            }

            child_query = _folder_type_filter(
                ApiFolder.query.filter_by(
                    project_id=project_id, parent_id=folder.id
                ),
                ApiFolder.TYPE_API,
            )
            child_folders = child_query.order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()

            for child_folder in child_folders:
                node['children'].append(build_tree_node(child_folder))

            apis = Api.query.filter_by(
                project_id=project_id,
                folder_id=folder.id,
                status=1
            ).order_by(Api.created_at.desc()).all()

            for api in apis:
                node['children'].append(self._api_to_node(api))

            return node

        try:
            root_query = _folder_type_filter(
                ApiFolder.query.filter_by(
                    project_id=project_id, parent_id=None
                ),
                ApiFolder.TYPE_API,
            )
            root_folders = root_query.order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()

            tree = [build_tree_node(folder) for folder in root_folders]

            uncategorized_apis = Api.query.filter_by(
                project_id=project_id, folder_id=None, status=1
            ).order_by(Api.created_at.desc()).all()

            if uncategorized_apis:
                uncategorized_node = {
                    'id': 'folder_uncategorized',
                    'raw_id': 0,
                    'name': '未分类',
                    'description': '未分配到目录的接口',
                    'type': 'folder',
                    'folder_type': ApiFolder.TYPE_API,
                    'is_virtual': True,
                    'project_id': project_id,
                    'parent_id': None,
                    'sort_order': 999,
                    'children': [self._api_to_node(api) for api in uncategorized_apis]
                }
                tree.append(uncategorized_node)

            return jsonify({"code": 0, "data": tree})

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"获取目录树失败: {str(e)}"
            }), 500

    @staticmethod
    def _api_to_node(api):
        """API ORM → 树节点字典。"""
        return {
            'id': f'api_{api.id}',
            'raw_id': api.id,
            'name': api.name,
            'description': api.description,
            'type': 'api',
            'method': api.method,
            'path': api.path,
            'base_url': api.base_url,
            'folder_id': api.folder_id,
            'category': api.category,
            'status': api.status,
            'headers': api.headers or {},
            'params': api.params or {},
            'body': api.body or {},
            'body_type': api.body_type or 'json',
            'response_example': api.response_example or {},
            'created_at': api.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': api.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            'children': []
        }

    # ------------------------------------------------------------------
    # 自动化目录树（type=automation）
    # ------------------------------------------------------------------

    def _build_automation_tree(self, project_id):
        """构建自动化任务目录树。每个目录节点的 children 包含子目录与自动化任务节点。"""
        from app.models.automation import AutomationTask

        try:
            def build_node(folder):
                node = {
                    'id': f'folder_{folder.id}',
                    'raw_id': folder.id,
                    'name': folder.name,
                    'description': folder.description,
                    'type': 'folder',
                    'folder_type': ApiFolder.TYPE_AUTOMATION,
                    'project_id': folder.project_id,
                    'parent_id': folder.parent_id,
                    'sort_order': folder.sort_order,
                    'created_at': folder.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'updated_at': folder.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    'children': []
                }
                child_folders = ApiFolder.query.filter_by(
                    project_id=project_id, parent_id=folder.id,
                    type=ApiFolder.TYPE_AUTOMATION,
                ).order_by(
                    ApiFolder.sort_order, ApiFolder.created_at
                ).all()
                for cf in child_folders:
                    node['children'].append(build_node(cf))

                tasks = AutomationTask.query.filter_by(
                    project_id=project_id, folder_id=folder.id, is_deleted=0,
                ).order_by(AutomationTask.created_at.desc()).all()
                for t in tasks:
                    node['children'].append(self._task_to_node(t))
                return node

            root_folders = ApiFolder.query.filter_by(
                project_id=project_id, parent_id=None,
                type=ApiFolder.TYPE_AUTOMATION,
            ).order_by(
                ApiFolder.sort_order, ApiFolder.created_at
            ).all()
            tree = [build_node(f) for f in root_folders]

            uncategorized_tasks = AutomationTask.query.filter_by(
                project_id=project_id, folder_id=None, is_deleted=0,
            ).order_by(AutomationTask.created_at.desc()).all()
            if uncategorized_tasks:
                tree.append({
                    'id': 'folder_uncategorized_automation',
                    'raw_id': 0,
                    'name': '未分类',
                    'description': '未分配到目录的自动化任务',
                    'type': 'folder',
                    'folder_type': ApiFolder.TYPE_AUTOMATION,
                    'is_virtual': True,
                    'project_id': project_id,
                    'parent_id': None,
                    'sort_order': 999,
                    'children': [self._task_to_node(t) for t in uncategorized_tasks],
                })

            return jsonify({"code": 0, "data": tree})

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"获取自动化目录树失败: {str(e)}"
            }), 500

    @staticmethod
    def _task_to_node(task):
        """AutomationTask ORM → 树节点字典。"""
        return {
            'id': f'automation_{task.id}',
            'raw_id': task.id,
            'name': task.name,
            'task_no': task.task_no,
            'description': task.description,
            'type': 'automation',
            'trigger_type': task.trigger_type,
            'status': task.status,
            'folder_id': task.folder_id,
            'environment_id': task.environment_id,
            'created_at': task.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'updated_at': task.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
            'children': []
        }


@folder_blp.route("/<int:folder_id>")
class FolderDetailView(MethodView):
    """目录更新与删除"""

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, folder_id):
        """更新目录。"""
        folder = ApiFolder.query.filter_by(
            id=folder_id, project_id=project_id
        ).first_or_404()

        data = request.get_json()

        try:
            for field in ["name", "description", "parent_id", "sort_order"]:
                if field in data:
                    setattr(folder, field, data[field])

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": folder.to_dict()
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}"
            }), 500

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(400, schema=MessageResponseSchema, description="目录非空")
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, folder_id):
        """删除目录。"""
        folder = ApiFolder.query.filter_by(
            id=folder_id, project_id=project_id
        ).first_or_404()

        if folder.children.count() > 0:
            return jsonify({
                "code": 1,
                "message": "该目录下有子目录，无法删除"
            }), 400

        try:
            folder_type = folder.type or ApiFolder.TYPE_API

            if folder_type == ApiFolder.TYPE_AUTOMATION:
                # 自动化目录：把目录下任务移到未分类
                from app.models.automation import AutomationTask
                AutomationTask.query.filter_by(
                    folder_id=folder_id
                ).update({"folder_id": None})
            else:
                # 接口/Bug 共用 api_folders（老数据 type='api'）
                Api.query.filter_by(folder_id=folder_id).update(
                    {"folder_id": None}
                )
                Bug.query.filter_by(folder_id=folder_id).update(
                    {"folder_id": None}
                )

            db.session.delete(folder)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}"
            }), 500
