"""
API接口管理路由。

作者: yandc
创建时间: 2026-01-16
"""
from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.api import Api
from app.utils.permission import login_required, check_project_permission
from app.engine.api_engine import (
    ApiEngineError,
    InvalidRequestSpecError,
    LoaderError,
    StepResult,
    get_api_engine,
)
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
                tags=data.get("tags", []),
                # api_engine 引擎能力字段（Phase 2 新增）
                assertions=data.get("assertions") or None,
                extracts=data.get("extracts") or None,
                timeout=data.get("timeout"),
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
                "response_example", "prefix_url_id", "status", "category", "tags",
                # api_engine 引擎能力字段（Phase 2 新增）
                "assertions", "extracts", "timeout",
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


@api_blp.route("/run-sequence")
class ApiSequenceRunView(MethodView):
    """多接口顺序执行（编排）。

    body:
        {
          "api_ids":        [1, 2, 3],            # 必填，按数组顺序执行
          "environment_id": 5,                    # 可选
          "fail_strategy":  "continue" | "fail_fast",   # 可选，默认 continue
          "name":           "登录到下单流程",       # 可选，仅用于日志/报告
          "per_api_overrides": {1: {...}, 2: {...}},   # 可选，按 api_id 局部覆盖
          "initial_variables": {"foo": "bar"},    # 可选，初始变量
        }

    返回 ``CollectionResult.to_dict()`` 完整结构（含每步 StepResult）。
    """

    @api_blp.response(200, MessageResponseSchema)
    @api_blp.alt_response(400, schema=MessageResponseSchema, description="参数非法")
    @api_blp.alt_response(404, schema=MessageResponseSchema, description="接口不存在")
    @api_blp.alt_response(500, schema=MessageResponseSchema, description="执行失败")
    @login_required
    @check_project_permission('read')
    def post(self, project_id):
        """按顺序执行多接口；前一步抽取的字段可被后续步骤通过 {{var}} 引用。"""
        data = request.get_json() or {}
        api_ids = data.get('api_ids') or []
        if not isinstance(api_ids, list) or not api_ids:
            return jsonify({
                "code": 1,
                "message": "api_ids 必填且为非空数组",
            }), 400

        # per_api_overrides 在 JSON 中 key 是字符串，转回 int
        raw_overrides = data.get('per_api_overrides') or {}
        per_api_overrides = {}
        if isinstance(raw_overrides, dict):
            for k, v in raw_overrides.items():
                try:
                    per_api_overrides[int(k)] = v
                except (TypeError, ValueError):
                    return jsonify({
                        "code": 1,
                        "message": f"per_api_overrides key 必须能转为 int: {k!r}",
                    }), 400

        try:
            engine = get_api_engine()
            collection_result = engine.run_api_sequence(
                api_ids=[int(i) for i in api_ids],
                project_id=project_id,
                environment_id=data.get('environment_id'),
                fail_strategy=str(data.get('fail_strategy') or "continue"),
                name=str(data.get('name') or "api-sequence"),
                per_api_overrides=per_api_overrides or None,
                initial_variables=data.get('initial_variables') or None,
            )
            return jsonify({"code": 0, "data": collection_result.to_dict()})

        except LoaderError as exc:
            return jsonify({"code": 1, "message": exc.message, "details": exc.details}), 404
        except InvalidRequestSpecError as exc:
            return jsonify({
                "code": 1,
                "message": f"参数非法: {exc.message}",
                "details": exc.details,
            }), 400
        except ApiEngineError as exc:
            return jsonify({
                "code": 1,
                "message": f"引擎异常: {exc.message}",
                "details": exc.details,
            }), 500
        except Exception as e:
            return jsonify({
                "code": 1,
                "message": f"执行失败: {str(e)}"
            }), 500


@api_blp.route("/<int:api_id>/test")
class ApiTestView(MethodView):
    """API接口测试。

    内部委托给 ``app.engine.api_engine.ApiEngine.run_single_api``，再把
    引擎产出的 ``StepResult`` 翻译成与历史前端契约一致的 JSON 结构，
    并附加引擎独有字段（``assertions / extracts / warnings / run_id`` 等）。
    """

    @api_blp.response(200, MessageResponseSchema)
    @api_blp.alt_response(500, schema=MessageResponseSchema, description="测试失败")
    @login_required
    @check_project_permission('read')
    def post(self, project_id, api_id):
        """测试执行API接口。"""
        # 路径合法性校验保留（404 by 老语义）
        Api.query.filter_by(
            id=api_id, project_id=project_id
        ).first_or_404()
        data = request.get_json() or {}

        try:
            engine = get_api_engine()
            step = engine.run_single_api(
                api_id=api_id,
                project_id=project_id,
                environment_id=data.get('environment_id'),
                overrides=_extract_overrides(data),
            )
            return jsonify({"code": 0, "data": _step_to_legacy_response(step)})

        except LoaderError as exc:
            return jsonify({"code": 1, "message": exc.message}), 404
        except InvalidRequestSpecError as exc:
            return jsonify({
                "code": 1,
                "message": f"接口配置非法: {exc.message}",
                "details": exc.details,
            }), 400
        except ApiEngineError as exc:
            return jsonify({
                "code": 1,
                "message": f"引擎异常: {exc.message}",
                "details": exc.details,
            }), 500
        except Exception as e:
            # 兜底：与老路由完全相同的错误格式
            return jsonify({
                "code": 1,
                "message": f"测试失败: {str(e)}"
            }), 500


# ----------------------------------------------------------------------
# 引擎结果 → 老前端响应结构的翻译层
# ----------------------------------------------------------------------

# 前端"调试时临时改 X"的字段白名单，转成 ApiModelLoader.overrides 的 key
_OVERRIDE_FIELDS = (
    "method", "path", "base_url", "headers", "params", "body", "body_type",
    "timeout", "prefix_url_id", "name",
)


def _extract_overrides(data: dict) -> dict:
    """从前端请求体里挑出会覆盖 apis 表字段的部分。"""
    overrides: dict = {}
    for field in _OVERRIDE_FIELDS:
        if field in data:
            overrides[field] = data[field]
    return overrides


def _step_to_legacy_response(step: StepResult) -> dict:
    """把 ``StepResult`` 翻译成老路由 ``ApiTestView.post`` 的响应字段。

    保证字段名/类型完全一致：``success / request / response / error / duration / timestamp``，
    再附加引擎独有的 ``assertions / extracts / warnings / passed / run_id``。
    """
    request_payload = step.request.to_dict() if step.request else {
        "method": "", "url": "", "headers": {}, "params": {}, "body": None, "body_type": "json",
    }

    # 老 RequestFactory.execute 的 response 字段不含 elapsed_ms；为了向后兼容剔除掉
    response_payload = None
    if step.response is not None:
        response_payload = step.response.to_dict()
        response_payload.pop("elapsed_ms", None)

    error_payload = None
    if step.error:
        error_payload = {"type": step.error_type, "message": step.error}

    legacy = {
        "success": step.error is None,
        "request": request_payload,
        "response": response_payload,
        "error": error_payload,
        "duration": round(step.duration, 3),
        "timestamp": step.started_at.strftime("%Y-%m-%d %H:%M:%S"),
        # === 新引擎能力字段（前端可选消费）===
        "passed": step.passed,
        "assertions": [a.to_dict() for a in step.assertions],
        "extracts": [e.to_dict() for e in step.extracts],
        "warnings": list(step.warnings),
    }
    return legacy
