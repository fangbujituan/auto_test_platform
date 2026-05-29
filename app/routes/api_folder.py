"""
API目录管理路由。

作者: yandc
创建时间: 2026-01-16
"""
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
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
        """获取项目的目录树结构。"""
        root_folders = ApiFolder.query.filter_by(
            project_id=project_id, parent_id=None
        ).order_by(ApiFolder.sort_order).all()

        tree = [
            folder.to_dict(include_children=True)
            for folder in root_folders
        ]

        return jsonify({"code": 0, "data": tree})

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建目录。"""
        data = request.get_json()

        try:
            folder = ApiFolder(
                name=data.get("name"),
                description=data.get("description"),
                project_id=project_id,
                parent_id=data.get("parent_id"),
                sort_order=data.get("sort_order", 0)
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
    """完整目录树（包含接口）"""

    @folder_blp.response(200, MessageResponseSchema)
    @folder_blp.alt_response(500, schema=MessageResponseSchema, description="获取失败")
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取完整的目录树（包含接口），支持多级嵌套。"""

        def build_tree_node(folder):
            """递归构建包含接口的树节点。"""
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

            apis = Api.query.filter_by(
                project_id=project_id,
                folder_id=folder.id,
                status=1
            ).order_by(Api.created_at.desc()).all()

            for api in apis:
                api_node = {
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
                    'created_at': api.created_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    'updated_at': api.updated_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    'children': []
                }
                node['children'].append(api_node)

            return node

        try:
            root_folders = ApiFolder.query.filter_by(
                project_id=project_id, parent_id=None
            ).order_by(
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
                    'is_virtual': True,
                    'project_id': project_id,
                    'parent_id': None,
                    'sort_order': 999,
                    'children': []
                }

                for api in uncategorized_apis:
                    api_node = {
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
                        'created_at': api.created_at.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        'updated_at': api.updated_at.strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        'children': []
                    }
                    uncategorized_node['children'].append(api_node)

                tree.append(uncategorized_node)

            return jsonify({"code": 0, "data": tree})

        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"获取目录树失败: {str(e)}"
            }), 500


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
            # 将目录下的接口和Bug移到未分类
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
