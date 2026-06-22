---
name: add-route
description: 在 ATP 后端新增一个 RESTful 接口（flask-smorest MethodView + Marshmallow Schema + login_required + check_project_permission + service 分层），自动按项目目录约定落位并在 flask_app.py 注册蓝图。
---

# 新增 RESTful 接口

## 何时激活

用户说要"新增 / 加 / 写一个接口、API、route"，且接口应当落在 `app/routes/`。
典型触发词：「加一个查询 xxx 的接口」「新增 xxx 路由」「补一个删除 xxx 的 API」。

## 必要输入

接收任务前先确认（缺哪个就向用户问哪个）：

- 资源名（snake_case，单数/复数都可，如 `comment`）
- HTTP 方法（GET / POST / PUT / DELETE / 多个）
- URL 路径模式（项目惯例是项目级前缀 `/api/projects/<int:project_id>/<resource>`，
  全局接口才用 `/api/<resource>`）
- 权限要求（默认 `login_required` + `check_project_permission('read'|'create'|'update'|'delete')`，
  非项目级接口用 `require_permission('resource:action')`）
- 是否需要新建 model（如果是，先调用 `add-model` skill）

## 项目硬约束（必须遵守）

1. 路由文件用 **flask-smorest Blueprint + MethodView**，**不要**写裸 `@bp.route` + 函数。
2. Blueprint 命名固定为 `<resource>_blp`，同时保留 `<resource>_bp = <resource>_blp` 兼容老引用（参考 `app/routes/bug.py`）。
3. 文件顶部必须有 docstring：

   ```
   """
   <资源中文名>路由。

   作者: yandc
   创建时间: YYYY-MM-DD
   """
   ```

4. **响应统一格式**（不要返回裸 dict，不要用其他状态码体）：
   - 成功：`return jsonify({"code": 0, "data": ..., "message": "..."})`
   - 失败：`return jsonify({"code": 1, "message": f"xxx失败: {str(e)}"}), 500`
   - `code == 0` 成功，其余为失败。前端 `client/src/api/request.js` 的拦截器依赖此约定。

5. **装饰器顺序**（自上而下）：

   ```python
   @bug_blp.route("")
   class BugsView(MethodView):
       @bug_blp.response(200, MessageResponseSchema)
       @bug_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
       @login_required
       @check_project_permission('create')
       def post(self, project_id):
           ...
   ```

6. **写库必须 try/except + `db.session.rollback()`**。读库可以裸跑。
7. 取当前用户用 `g.get('current_user')`，不要再次解析 token。
8. 复杂业务逻辑（>30 行 / 多步事务 / 跨表）放 `app/services/<resource>_service.py`，路由层只做参数提取 + 调 service + 拼响应。简单 CRUD 可以直接在路由里 ORM 操作（参考 `bug.py`）。

## 实现步骤

### 1. 读取相邻样例

先读 `app/routes/bug.py` 确认最新风格；如果资源是项目级，照抄 `BugsView / BugDetailView` 结构。

### 2. （如需）新建 / 改动 model

若涉及新表或新字段，先调用 `add-model` skill 完成 model 创建。

### 3. 写 Schema

新建 / 复用 `app/schemas/<resource>.py`：

```python
"""<资源中文名>相关 Schema。"""
from marshmallow import Schema, fields


class <Resource>CreateSchema(Schema):
    """创建 <资源中文名> 请求"""
    name = fields.String(required=True, metadata={"description": "名称"})
    # required=True 必填；可选字段用 load_default=...


class <Resource>UpdateSchema(<Resource>CreateSchema):
    """更新请求（所有字段可选）"""
    name = fields.String(metadata={"description": "名称"})


class <Resource>QuerySchema(Schema):
    """列表查询参数"""
    keyword = fields.String(metadata={"description": "搜索关键词"})
```

约定：
- 必填字段 `required=True`，可选字段用 `load_default=<默认值>`，不要混用 `missing=` / `default=`。
- 每个字段都加 `metadata={"description": "..."}`，会出现在 Swagger 文档里。

### 4. 写 Route

新建 `app/routes/<resource>.py`：

```python
"""
<资源中文名>路由。

作者: yandc
创建时间: YYYY-MM-DD
"""
from flask import request, jsonify, g
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.<resource> import <Resource>
from app.utils.permission import login_required, check_project_permission
from app.schemas.common import MessageResponseSchema

<resource>_blp = Blueprint(
    "<resource>", __name__,
    url_prefix="/api/projects/<int:project_id>/<resources>",
    description="<资源中文名>管理",
)
# 向后兼容
<resource>_bp = <resource>_blp


@<resource>_blp.route("")
class <Resource>sView(MethodView):
    """<资源中文名>列表与创建"""

    @<resource>_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目下的所有<资源中文名>。"""
        items = <Resource>.query.filter_by(project_id=project_id) \
            .order_by(<Resource>.created_at.desc()).all()
        return jsonify({"code": 0, "data": [i.to_dict() for i in items]})

    @<resource>_blp.response(200, MessageResponseSchema)
    @<resource>_blp.alt_response(500, schema=MessageResponseSchema, description="创建失败")
    @login_required
    @check_project_permission('create')
    def post(self, project_id):
        """创建<资源中文名>。"""
        data = request.get_json() or {}
        try:
            current_user = g.get('current_user')
            obj = <Resource>(
                project_id=project_id,
                # 字段一一对应，对引用人字段默认取当前用户
                **{k: v for k, v in data.items() if k != 'project_id'},
            )
            db.session.add(obj)
            db.session.commit()
            return jsonify({"code": 0, "message": "创建成功", "data": obj.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"创建失败: {str(e)}"}), 500


@<resource>_blp.route("/<int:<resource>_id>")
class <Resource>DetailView(MethodView):
    """<资源中文名>详情、更新、删除"""

    @<resource>_blp.response(200, MessageResponseSchema)
    @login_required
    @check_project_permission('read')
    def get(self, project_id, <resource>_id):
        obj = <Resource>.query.filter_by(
            id=<resource>_id, project_id=project_id
        ).first_or_404()
        return jsonify({"code": 0, "data": obj.to_dict()})

    @<resource>_blp.response(200, MessageResponseSchema)
    @<resource>_blp.alt_response(500, schema=MessageResponseSchema, description="更新失败")
    @login_required
    @check_project_permission('update')
    def put(self, project_id, <resource>_id):
        obj = <Resource>.query.filter_by(
            id=<resource>_id, project_id=project_id
        ).first_or_404()
        data = request.get_json() or {}
        try:
            # 仅更新允许字段，禁止覆盖 id / project_id / created_at
            for field in ("name", "description"):  # 按实际字段补全
                if field in data:
                    setattr(obj, field, data[field])
            db.session.commit()
            return jsonify({"code": 0, "message": "更新成功", "data": obj.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"更新失败: {str(e)}"}), 500

    @<resource>_blp.response(200, MessageResponseSchema)
    @<resource>_blp.alt_response(500, schema=MessageResponseSchema, description="删除失败")
    @login_required
    @check_project_permission('delete')
    def delete(self, project_id, <resource>_id):
        obj = <Resource>.query.filter_by(
            id=<resource>_id, project_id=project_id
        ).first_or_404()
        try:
            db.session.delete(obj)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({"code": 1, "message": f"删除失败: {str(e)}"}), 500
```

### 5. 注册蓝图

在 `app/flask_app.py` 的 `create_app()` 中：

```python
from app.routes.<resource> import <resource>_blp
# ...其他蓝图...
api.register_blueprint(<resource>_blp)
```

按字母 / 模块分组就近插入，不要破坏现有顺序。

### 6. 写前端 API（如果用户同时需要前端调用）

新建 `client/src/api/<resource>.js`：

```js
import request from './request'

export function get<Resource>s(projectId, params) {
  return request({ url: `/projects/${projectId}/<resources>`, method: 'get', params })
}

export function get<Resource>(projectId, id) {
  return request({ url: `/projects/${projectId}/<resources>/${id}`, method: 'get' })
}

export function create<Resource>(projectId, data) {
  return request({ url: `/projects/${projectId}/<resources>`, method: 'post', data })
}

export function update<Resource>(projectId, id, data) {
  return request({ url: `/projects/${projectId}/<resources>/${id}`, method: 'put', data })
}

export function delete<Resource>(projectId, id) {
  return request({ url: `/projects/${projectId}/<resources>/${id}`, method: 'delete' })
}
```

`baseURL` 已在 `request.js` 设为 `/api`，路径不要再带 `/api` 前缀。

## 验证

完成后必须：

1. `python -c "from app import create_app; create_app()"` 能跑通（验证蓝图注册没冲突）。
2. 启动服务，访问 `http://localhost:12048/api/docs/swagger`，确认新接口出现且参数 / 响应描述正确。
3. 用 curl 或 Swagger UI 试一条 happy path（带 `Authorization: Bearer xxx` 和 `X-Username: admin` 头）。
4. 不要自己加 README，README 只在用户明确要求时改。

## 反模式（不要做）

- 直接在路由里写 200+ 行业务逻辑——超过 30 行就抽 service。
- 用 `@cross_origin` 等装饰器绕权限——CORS 已在 `flask_app.py` 全局开。
- 返回 `{"success": true, ...}`——前端拦截器只认 `code`。
- 用 alembic—— 项目当前依赖 `db.create_all()`，新加表 / 字段要写一次性 migration 脚本放 `app/migrations/`，详见 `add-model` skill。
