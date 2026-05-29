"""
Bug管理模型。

作者: yandc
创建时间: 2026-01-22
"""
from app.models.base import db, BaseModel


class Bug(BaseModel):
    """Bug模型。"""

    __tablename__ = "bugs"

    title = db.Column(db.String(200), nullable=False, comment="Bug标题")
    description = db.Column(db.Text, comment="Bug描述")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    
    # Bug状态和优先级
    status = db.Column(db.String(20), default="open", comment="状态: open, in_progress, resolved, closed, reopened")
    priority = db.Column(db.String(20), default="medium", comment="优先级: low, medium, high, critical")
    severity = db.Column(db.String(20), default="normal", comment="严重程度: trivial, minor, normal, major, critical")
    
    # Bug分类
    category = db.Column(db.String(50), comment="Bug分类")
    module = db.Column(db.String(100), comment="所属模块")
    folder_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), comment="所属目录ID")
    tags = db.Column(db.JSON, comment="标签")
    
    # 人员信息
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, comment="报告人ID")
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"), comment="指派人ID")
    
    # 环境信息
    environment = db.Column(db.String(100), comment="测试环境")
    version = db.Column(db.String(50), comment="发现版本")
    
    # 复现信息
    steps_to_reproduce = db.Column(db.Text, comment="复现步骤")
    expected_result = db.Column(db.Text, comment="预期结果")
    actual_result = db.Column(db.Text, comment="实际结果")
    
    # 附加信息
    attachments = db.Column(db.JSON, comment="附件列表")
    related_apis = db.Column(db.JSON, comment="关联的API接口ID列表")
    related_test_cases = db.Column(db.JSON, comment="关联的测试用例ID列表")
    
    # 解决信息
    resolution = db.Column(db.String(50), comment="解决方案: fixed, wont_fix, duplicate, cannot_reproduce, by_design")
    resolution_note = db.Column(db.Text, comment="解决说明")
    resolved_at = db.Column(db.DateTime, comment="解决时间")
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"), comment="解决人ID")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "project_id": self.project_id,
            "status": self.status,
            "priority": self.priority,
            "severity": self.severity,
            "category": self.category,
            "module": self.module,
            "folder_id": self.folder_id,
            "tags": self.tags or [],
            "reporter_id": self.reporter_id,
            "assignee_id": self.assignee_id,
            "environment": self.environment,
            "version": self.version,
            "steps_to_reproduce": self.steps_to_reproduce,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "attachments": self.attachments or [],
            "related_apis": self.related_apis or [],
            "related_test_cases": self.related_test_cases or [],
            "resolution": self.resolution,
            "resolution_note": self.resolution_note,
            "resolved_at": self.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
