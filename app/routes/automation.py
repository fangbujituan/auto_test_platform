"""
自动化任务管理路由。

作者: yandc
创建时间: 2026-01-20
"""
import secrets

from flask import request, jsonify
from flask.views import MethodView
from flask_smorest import Blueprint
from app.models.base import db
from app.models.automation import (
    AutomationTask,
    AutomationTaskCase,
    TaskExecution,
    generate_task_no,
)
from app.models.api import Api
from app.models.api_folder import ApiFolder
from app.models.env_variable import Environment
from app.utils.permission import check_project_permission, require_permission
from app.services.scheduler_service import SchedulerService
from app.services.automation_executor import AutomationExecutor, DuplicateExecutionError
from app.schemas.common import MessageResponseSchema

automation_blp = Blueprint(
    "automation",
    __name__,
    url_prefix="/api/projects/<int:project_id>/automations",
    description="自动化任务管理",
)

automation_exec_blp = Blueprint(
    "automation_exec",
    __name__,
    url_prefix="/api/automations",
    description="自动化任务执行",
)

# 向后兼容
automation_bp = automation_blp

scheduler = SchedulerService()


# =============================================================
# 工具函数
# =============================================================

_VALID_FAIL_STRATEGY = {"continue", "stop"}


def _validate_folder(project_id, folder_id):
    """校验 folder 归属与 type=automation。返回 (ok, error_msg)。"""
    if folder_id is None:
        return True, None
    folder = ApiFolder.query.filter_by(
        id=folder_id, project_id=project_id
    ).first()
    if not folder:
        return False, "目录不存在"
    folder_type = folder.type or ApiFolder.TYPE_API
    if folder_type != ApiFolder.TYPE_AUTOMATION:
        return False, f"目录类型不匹配：期望 automation，实际 {folder_type}"
    return True, None


def _coerce_loop_count(value):
    """循环次数：>=1 的整数，缺省为 1。"""
    if value is None or value == "":
        return 1
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 1 else None


def _coerce_interval(value):
    """间隔时间：>=0 的浮点，缺省为 0。"""
    if value is None or value == "":
        return 0.0
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if v >= 0 else None


def _enrich_task_case(tc):
    """task_case → 含关联资源摘要的字典（前端展示用）。"""
    base = tc.to_dict()
    ref = None
    if tc.api_id:
        api = Api.query.get(tc.api_id)
        if api:
            ref = {
                "kind": "api",
                "id": api.id,
                "name": api.name,
                "method": api.method,
                "path": api.path,
                "folder_id": api.folder_id,
            }
        else:
            ref = {"kind": "api", "id": tc.api_id, "missing": True}
    elif tc.case_id:
        # 接口测试用例（test_cases 表）
        try:
            from app.models.case import TestCase
            case = TestCase.query.get(tc.case_id)
            if case:
                ref = {
                    "kind": "case",
                    "id": case.id,
                    "name": case.name,
                    "method": case.method,
                    "url": case.url,
                }
            else:
                ref = {"kind": "case", "id": tc.case_id, "missing": True}
        except Exception:
            ref = {"kind": "case", "id": tc.case_id}
    elif tc.case_mgmt_id:
        ref = {"kind": "case_mgmt", "id": tc.case_mgmt_id}

    base["ref"] = ref
    return base


@automation_blp.route("")
class AutomationsView(MethodView):
    """自动化任务列表与创建"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    @check_project_permission('read')
    def get(self, project_id):
        """获取项目自动化任务列表（分页，按创建时间倒序）。

        支持 query 参数：
        - ``page`` / ``per_page``
        - ``keyword``：模糊匹配 name / task_no
        - ``folder_id``：精确过滤目录；传 ``"null"`` 表示未分类
        """
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 20, type=int)
        keyword = (request.args.get("keyword") or "").strip()
        folder_id_raw = request.args.get("folder_id")

        query = AutomationTask.query.filter_by(
            project_id=project_id, is_deleted=0
        )

        if keyword:
            like = f"%{keyword}%"
            query = query.filter(
                (AutomationTask.name.ilike(like))
                | (AutomationTask.task_no.ilike(like))
            )

        if folder_id_raw is not None and folder_id_raw != "":
            if folder_id_raw in ("null", "0"):
                query = query.filter(AutomationTask.folder_id.is_(None))
            else:
                try:
                    fid = int(folder_id_raw)
                    query = query.filter(AutomationTask.folder_id == fid)
                except ValueError:
                    pass

        query = query.order_by(AutomationTask.created_at.desc())

        pagination = query.paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            "code": 0,
            "data": [t.to_dict() for t in pagination.items],
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
        })

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        500, schema=MessageResponseSchema, description="创建失败"
    )
    @require_permission("automation:create")
    @check_project_permission('create')
    def post(self, project_id):
        """创建自动化任务。"""
        data = request.get_json() or {}

        name = data.get("name")
        if not name:
            return jsonify({
                "code": 1,
                "message": "任务名称不能为空"
            }), 400

        # 校验名称唯一性
        existing = AutomationTask.query.filter_by(
            project_id=project_id, name=name, is_deleted=0
        ).first()
        if existing:
            return jsonify({
                "code": 1,
                "message": "任务名称已存在"
            }), 400

        # 校验环境存在性
        environment_id = data.get("environment_id")
        if environment_id is not None:
            env = Environment.query.get(environment_id)
            if not env:
                return jsonify({
                    "code": 1,
                    "message": "环境不存在"
                }), 404

        # 校验目录存在性 + 类型
        folder_id = data.get("folder_id")
        ok, msg = _validate_folder(project_id, folder_id)
        if not ok:
            return jsonify({"code": 1, "message": msg}), 400

        # 执行配置校验
        loop_count = _coerce_loop_count(data.get("loop_count"))
        if loop_count is None:
            return jsonify({
                "code": 1, "message": "循环次数必须为 >=1 的整数"
            }), 400

        interval_seconds = _coerce_interval(data.get("interval_seconds"))
        if interval_seconds is None:
            return jsonify({
                "code": 1, "message": "间隔时间必须为 >=0 的数字"
            }), 400

        fail_strategy = data.get("fail_strategy") or "continue"
        if fail_strategy not in _VALID_FAIL_STRATEGY:
            return jsonify({
                "code": 1,
                "message": f"失败策略不合法: {fail_strategy}",
            }), 400

        trigger_type = data.get("trigger_type", "manual")

        # Cron 表达式校验
        cron_expression = data.get("cron_expression")
        if trigger_type == "cron":
            if not cron_expression:
                return jsonify({
                    "code": 1,
                    "message": "Cron 表达式不能为空"
                }), 400
            if not SchedulerService.validate_cron(cron_expression):
                return jsonify({
                    "code": 1,
                    "message": "Cron 表达式格式无效"
                }), 400

        # Webhook 令牌生成
        webhook_token = None
        if trigger_type == "webhook":
            webhook_token = secrets.token_urlsafe(32)

        try:
            task = AutomationTask(
                task_no=generate_task_no(project_id),
                name=name,
                description=data.get("description"),
                project_id=project_id,
                folder_id=folder_id,
                trigger_type=trigger_type,
                cron_expression=cron_expression,
                webhook_token=webhook_token,
                environment_id=environment_id,
                loop_count=loop_count,
                fail_strategy=fail_strategy,
                interval_seconds=interval_seconds,
                status=data.get("status", 1),
            )
            db.session.add(task)
            db.session.commit()

            # 注册 cron 调度
            if trigger_type == "cron" and cron_expression:
                scheduler.add_cron_job(task.id, cron_expression)

            return jsonify({
                "code": 0,
                "message": "创建成功",
                "data": task.to_dict(),
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"创建失败: {str(e)}"
            }), 500


@automation_blp.route("/<int:task_id>")
class AutomationDetailView(MethodView):
    """自动化任务详情、更新与删除"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    @check_project_permission('read')
    def get(self, project_id, task_id):
        """获取任务详情（含关联用例/接口信息）。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        task_dict = task.to_dict()
        # 附带关联用例/接口信息
        task_cases = AutomationTaskCase.query.filter_by(
            task_id=task.id
        ).order_by(AutomationTaskCase.sort_order.asc()).all()
        task_dict["cases"] = [_enrich_task_case(tc) for tc in task_cases]

        return jsonify({"code": 0, "data": task_dict})

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        500, schema=MessageResponseSchema, description="更新失败"
    )
    @require_permission("automation:update")
    @check_project_permission('update')
    def put(self, project_id, task_id):
        """更新自动化任务。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        data = request.get_json() or {}

        # 名称唯一性校验（如果更新了名称）
        new_name = data.get("name")
        if new_name and new_name != task.name:
            dup = AutomationTask.query.filter_by(
                project_id=project_id, name=new_name, is_deleted=0
            ).first()
            if dup:
                return jsonify({
                    "code": 1,
                    "message": "任务名称已存在"
                }), 400

        # 校验环境存在性
        environment_id = data.get("environment_id")
        if "environment_id" in data and environment_id is not None:
            env = Environment.query.get(environment_id)
            if not env:
                return jsonify({
                    "code": 1,
                    "message": "环境不存在"
                }), 404

        # 校验目录归属
        if "folder_id" in data:
            ok, msg = _validate_folder(project_id, data.get("folder_id"))
            if not ok:
                return jsonify({"code": 1, "message": msg}), 400

        # 执行配置校验
        if "loop_count" in data:
            lc = _coerce_loop_count(data.get("loop_count"))
            if lc is None:
                return jsonify({
                    "code": 1, "message": "循环次数必须为 >=1 的整数",
                }), 400
            data["loop_count"] = lc

        if "interval_seconds" in data:
            iv = _coerce_interval(data.get("interval_seconds"))
            if iv is None:
                return jsonify({
                    "code": 1, "message": "间隔时间必须为 >=0 的数字",
                }), 400
            data["interval_seconds"] = iv

        if "fail_strategy" in data:
            fs = data.get("fail_strategy") or "continue"
            if fs not in _VALID_FAIL_STRATEGY:
                return jsonify({
                    "code": 1,
                    "message": f"失败策略不合法: {fs}",
                }), 400
            data["fail_strategy"] = fs

        new_trigger = data.get("trigger_type")
        new_cron = data.get("cron_expression")

        # Cron 表达式校验
        effective_trigger = new_trigger or task.trigger_type
        if effective_trigger == "cron":
            effective_cron = (
                new_cron if new_cron is not None
                else task.cron_expression
            )
            if effective_cron and not SchedulerService.validate_cron(
                effective_cron
            ):
                return jsonify({
                    "code": 1,
                    "message": "Cron 表达式格式无效"
                }), 400

        try:
            old_trigger = task.trigger_type

            # 更新简单字段
            for field in [
                "name", "description", "trigger_type",
                "cron_expression", "environment_id", "status",
                "folder_id", "loop_count", "fail_strategy",
                "interval_seconds",
            ]:
                if field in data:
                    setattr(task, field, data[field])

            # Webhook 令牌：切换到 webhook 时生成
            if (
                new_trigger == "webhook"
                and old_trigger != "webhook"
            ):
                task.webhook_token = secrets.token_urlsafe(32)

            # 处理 trigger_type 变更的调度器同步
            effective_trigger = task.trigger_type
            if effective_trigger == "cron" and task.cron_expression:
                scheduler.add_cron_job(
                    task.id, task.cron_expression
                )
            elif old_trigger == "cron" and effective_trigger != "cron":
                scheduler.remove_job(task.id)

            db.session.commit()

            return jsonify({
                "code": 0,
                "message": "更新成功",
                "data": task.to_dict(),
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"更新失败: {str(e)}"
            }), 500

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        500, schema=MessageResponseSchema, description="删除失败"
    )
    @require_permission("automation:delete")
    @check_project_permission('delete')
    def delete(self, project_id, task_id):
        """软删除任务及关联执行历史。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        try:
            task.is_deleted = 1

            # 标记关联的 TaskExecution 为已删除
            TaskExecution.query.filter_by(
                task_id=task.id
            ).update({"status": "deleted"})

            # 如果是 cron 类型，移除调度
            if task.trigger_type == "cron":
                scheduler.remove_job(task.id)

            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "删除成功"
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"删除失败: {str(e)}"
            }), 500


# ---- 用例/接口关联管理 ----


@automation_blp.route("/<int:task_id>/cases")
class AutomationCasesView(MethodView):
    """自动化任务关联用例/接口列表与导入"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:read")
    @check_project_permission('read')
    def get(self, project_id, task_id):
        """获取关联的接口/用例列表（按 sort_order）。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({"code": 1, "message": "自动化任务不存在"}), 404

        task_cases = AutomationTaskCase.query.filter_by(
            task_id=task.id
        ).order_by(AutomationTaskCase.sort_order.asc()).all()

        return jsonify({
            "code": 0,
            "data": [_enrich_task_case(tc) for tc in task_cases],
        })

    @automation_blp.response(200, MessageResponseSchema)
    @automation_blp.alt_response(
        400, schema=MessageResponseSchema, description="参数错误"
    )
    @require_permission("automation:update")
    @check_project_permission('update')
    def post(self, project_id, task_id):
        """批量导入接口/用例到任务。

        请求体示例：
        ```json
        {
          "items": [
            {"kind": "api", "id": 12},
            {"kind": "case", "id": 8}
          ],
          "append": true
        }
        ```
        - ``append=true``（默认）：追加到末尾
        - ``append=false``：先清空再写入
        """
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({"code": 1, "message": "自动化任务不存在"}), 404

        data = request.get_json() or {}
        items = data.get("items") or []
        if not isinstance(items, list) or not items:
            return jsonify({
                "code": 1, "message": "items 不能为空",
            }), 400

        append = bool(data.get("append", True))

        # 计算起始排序
        if append:
            current_max = (
                db.session.query(db.func.max(AutomationTaskCase.sort_order))
                .filter(AutomationTaskCase.task_id == task.id)
                .scalar()
            )
            start_order = (current_max or 0) + 1
        else:
            AutomationTaskCase.query.filter_by(task_id=task.id).delete()
            db.session.flush()
            start_order = 1

        created = []
        try:
            for offset, item in enumerate(items):
                kind = (item.get("kind") or "").lower()
                ref_id = item.get("id")
                if not ref_id:
                    return jsonify({
                        "code": 1,
                        "message": f"items[{offset}].id 不能为空",
                    }), 400

                if kind == "api":
                    api = Api.query.filter_by(
                        id=ref_id, project_id=project_id
                    ).first()
                    if not api:
                        return jsonify({
                            "code": 1,
                            "message": f"接口不存在: id={ref_id}",
                        }), 400
                    tc = AutomationTaskCase(
                        task_id=task.id,
                        api_id=api.id,
                        sort_order=start_order + offset,
                    )
                elif kind == "case":
                    from app.models.case import TestCase
                    case = TestCase.query.filter_by(
                        id=ref_id, project_id=project_id
                    ).first()
                    if not case:
                        return jsonify({
                            "code": 1,
                            "message": f"接口用例不存在: id={ref_id}",
                        }), 400
                    tc = AutomationTaskCase(
                        task_id=task.id,
                        case_id=case.id,
                        sort_order=start_order + offset,
                    )
                elif kind == "case_mgmt":
                    from app.models.test_case import TestCaseManagement
                    cm = TestCaseManagement.query.filter_by(
                        id=ref_id, project_id=project_id
                    ).first()
                    if not cm:
                        return jsonify({
                            "code": 1,
                            "message": f"测试用例不存在: id={ref_id}",
                        }), 400
                    tc = AutomationTaskCase(
                        task_id=task.id,
                        case_mgmt_id=cm.id,
                        sort_order=start_order + offset,
                    )
                else:
                    return jsonify({
                        "code": 1,
                        "message": f"未知 kind: {kind}",
                    }), 400

                db.session.add(tc)
                db.session.flush()
                created.append(tc)

            db.session.commit()
            return jsonify({
                "code": 0,
                "message": f"导入成功，共 {len(created)} 条",
                "data": [_enrich_task_case(tc) for tc in created],
            })

        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"导入失败: {str(e)}",
            }), 500


@automation_blp.route("/<int:task_id>/cases/order")
class AutomationCasesOrderView(MethodView):
    """重新设置任务关联用例的执行顺序"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:update")
    @check_project_permission('update')
    def put(self, project_id, task_id):
        """批量调整 sort_order。

        请求体：``{"order": [{"id": 1, "sort_order": 1}, ...]}``
        """
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({"code": 1, "message": "自动化任务不存在"}), 404

        data = request.get_json() or {}
        order = data.get("order") or []
        if not isinstance(order, list):
            return jsonify({"code": 1, "message": "order 必须为列表"}), 400

        try:
            for item in order:
                tc_id = item.get("id")
                so = item.get("sort_order")
                if not tc_id or so is None:
                    continue
                tc = AutomationTaskCase.query.filter_by(
                    id=tc_id, task_id=task.id
                ).first()
                if tc:
                    tc.sort_order = int(so)
            db.session.commit()
            return jsonify({"code": 0, "message": "排序已更新"})
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1, "message": f"更新失败: {str(e)}",
            }), 500


@automation_blp.route("/<int:task_id>/cases/<int:case_row_id>")
class AutomationCaseDetailView(MethodView):
    """删除单条任务关联用例"""

    @automation_blp.response(200, MessageResponseSchema)
    @require_permission("automation:update")
    @check_project_permission('update')
    def delete(self, project_id, task_id, case_row_id):
        """删除一条任务关联记录。"""
        task = AutomationTask.query.filter_by(
            id=task_id, project_id=project_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({"code": 1, "message": "自动化任务不存在"}), 404

        tc = AutomationTaskCase.query.filter_by(
            id=case_row_id, task_id=task.id
        ).first()
        if not tc:
            return jsonify({"code": 1, "message": "关联记录不存在"}), 404

        try:
            db.session.delete(tc)
            db.session.commit()
            return jsonify({"code": 0, "message": "删除成功"})
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1, "message": f"删除失败: {str(e)}",
            }), 500


# ---- 执行相关路由 (automation_exec_blp) ----

executor = AutomationExecutor()


@automation_exec_blp.route("/<int:task_id>/execute")
class AutomationExecuteView(MethodView):
    """手动触发自动化任务执行"""

    @automation_exec_blp.response(200, MessageResponseSchema)
    @require_permission("automation:execute")
    def post(self, task_id):
        """手动触发执行自动化任务。"""
        task = AutomationTask.query.filter_by(
            id=task_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        data = request.get_json(silent=True) or {}
        environment_id = data.get("environment_id")

        try:
            execution = executor.execute_task(
                task_id, environment_id=environment_id
            )
            return jsonify({
                "code": 0,
                "message": "执行已触发",
                "data": execution.to_dict(),
            })
        except DuplicateExecutionError:
            return jsonify({
                "code": 1,
                "message": "任务正在执行中，请勿重复触发"
            }), 409


@automation_exec_blp.route("/<int:task_id>/cancel")
class AutomationCancelView(MethodView):
    """取消自动化任务执行"""

    @automation_exec_blp.response(200, MessageResponseSchema)
    @require_permission("automation:execute")
    def post(self, task_id):
        """取消正在执行的自动化任务。"""
        task = AutomationTask.query.filter_by(
            id=task_id, is_deleted=0
        ).first()
        if not task:
            return jsonify({
                "code": 1,
                "message": "自动化任务不存在"
            }), 404

        running_execution = TaskExecution.query.filter_by(
            task_id=task_id, status="running"
        ).first()
        if not running_execution:
            return jsonify({
                "code": 1,
                "message": "没有正在执行的任务"
            }), 404

        try:
            running_execution.status = "cancelled"
            db.session.commit()
            return jsonify({
                "code": 0,
                "message": "执行已取消",
                "data": running_execution.to_dict(),
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({
                "code": 1,
                "message": f"取消失败: {str(e)}"
            }), 500
