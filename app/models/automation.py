"""
自动化管理模型。

作者: yandc
创建时间: 2026-01-20
"""
from app.models.base import db, BaseModel


def generate_task_no(project_id):
    """生成任务编号（格式：AT-项目ID-序号）。"""
    prefix = f"AT-{project_id}-"
    last_task = AutomationTask.query.filter(
        AutomationTask.project_id == project_id,
        AutomationTask.task_no.like(f"{prefix}%")
    ).order_by(AutomationTask.task_no.desc()).first()

    if last_task:
        try:
            last_no = int(last_task.task_no.split("-")[-1])
            new_no = last_no + 1
        except (ValueError, IndexError):
            new_no = 1
    else:
        new_no = 1

    return f"{prefix}{new_no:04d}"


class AutomationTask(BaseModel):
    """自动化任务模型。"""

    __tablename__ = "automation_tasks"

    task_no = db.Column(db.String(50), nullable=False, unique=True, comment="任务编号")
    name = db.Column(db.String(200), nullable=False, comment="任务名称")
    description = db.Column(db.Text, comment="任务描述")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    trigger_type = db.Column(db.String(20), default="manual", comment="触发类型: manual/cron/webhook")
    cron_expression = db.Column(db.String(100), comment="Cron表达式")
    webhook_token = db.Column(db.String(100), unique=True, comment="Webhook令牌")
    environment_id = db.Column(db.Integer, db.ForeignKey("environments.id"), nullable=True)
    status = db.Column(db.Integer, default=1, comment="1:启用 0:禁用")
    is_deleted = db.Column(db.Integer, default=0, comment="0:正常 1:已删除")

    # 关系
    cases = db.relationship("AutomationTaskCase", backref="task", lazy="dynamic", cascade="all, delete-orphan")
    executions = db.relationship("TaskExecution", backref="task", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        db.UniqueConstraint("project_id", "name", name="uq_automation_task_project_name"),
    )

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "task_no": self.task_no,
            "name": self.name,
            "description": self.description,
            "project_id": self.project_id,
            "trigger_type": self.trigger_type,
            "cron_expression": self.cron_expression,
            "webhook_token": self.webhook_token,
            "environment_id": self.environment_id,
            "status": self.status,
            "is_deleted": self.is_deleted,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class AutomationTaskCase(BaseModel):
    """任务-用例关联模型。"""

    __tablename__ = "automation_task_cases"

    task_id = db.Column(db.Integer, db.ForeignKey("automation_tasks.id"), nullable=False)
    case_id = db.Column(db.Integer, db.ForeignKey("test_cases.id"), nullable=True, comment="API测试用例ID")
    case_mgmt_id = db.Column(db.Integer, db.ForeignKey("test_case_management.id"), nullable=True, comment="测试用例管理ID")
    sort_order = db.Column(db.Integer, default=0, comment="执行顺序")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "case_id": self.case_id,
            "case_mgmt_id": self.case_mgmt_id,
            "sort_order": self.sort_order,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class TaskExecution(BaseModel):
    """任务执行记录模型。"""

    __tablename__ = "task_executions"

    task_id = db.Column(db.Integer, db.ForeignKey("automation_tasks.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", comment="pending/running/completed/failed/cancelled")
    trigger_source = db.Column(db.String(20), comment="触发来源: manual/cron/webhook")
    started_at = db.Column(db.DateTime, comment="开始时间")
    finished_at = db.Column(db.DateTime, comment="结束时间")
    duration = db.Column(db.Float, comment="总耗时(秒)")
    total_cases = db.Column(db.Integer, default=0)
    passed_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    error_message = db.Column(db.Text, comment="执行错误信息")

    # 关系
    details = db.relationship("TaskExecutionDetail", backref="execution", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "status": self.status,
            "trigger_source": self.trigger_source,
            "started_at": self.started_at.strftime("%Y-%m-%d %H:%M:%S") if self.started_at else None,
            "finished_at": self.finished_at.strftime("%Y-%m-%d %H:%M:%S") if self.finished_at else None,
            "duration": self.duration,
            "total_cases": self.total_cases,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "error_count": self.error_count,
            "error_message": self.error_message,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }


class TaskExecutionDetail(BaseModel):
    """任务执行明细模型。"""

    __tablename__ = "task_execution_details"

    execution_id = db.Column(db.Integer, db.ForeignKey("task_executions.id"), nullable=False)
    case_id = db.Column(db.Integer, comment="用例ID")
    case_name = db.Column(db.String(200), comment="用例名称")
    status = db.Column(db.String(20), comment="passed/failed/error/skipped")
    actual_status = db.Column(db.Integer, comment="实际HTTP状态码")
    actual_response = db.Column(db.JSON, comment="实际响应")
    duration = db.Column(db.Float, comment="耗时(秒)")
    error_message = db.Column(db.Text, comment="错误信息")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "case_id": self.case_id,
            "case_name": self.case_name,
            "status": self.status,
            "actual_status": self.actual_status,
            "actual_response": self.actual_response,
            "duration": self.duration,
            "error_message": self.error_message,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
