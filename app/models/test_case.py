"""
测试用例管理模型。

作者: yandc
创建时间: 2026-01-19
"""
from app.models.base import db, BaseModel


class TestCaseManagement(BaseModel):
    """测试用例管理模型（用于用例管理，区别于API测试用例）。"""

    __tablename__ = "test_case_management"

    case_no = db.Column(db.String(50), nullable=False, unique=True, comment="用例编号（自动生成）")
    title = db.Column(db.String(200), nullable=False, comment="用例标题")
    description = db.Column(db.Text, comment="用例描述")
    precondition = db.Column(db.Text, comment="前置条件")
    steps = db.Column(db.Text, comment="测试步骤")
    expected_result = db.Column(db.Text, comment="预期结果")
    
    # 分类信息
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    module_id = db.Column(db.Integer, db.ForeignKey("modules.id"), nullable=True, comment="所属模块ID（可选）")
    folder_id = db.Column(db.Integer, db.ForeignKey("api_folders.id"), nullable=True, comment="所属目录ID（可选）")
    
    # 用例属性
    priority = db.Column(db.String(10), default="P2", comment="优先级: P0/P1/P2/P3")
    case_type = db.Column(db.String(20), default="功能", comment="用例类型: 功能/性能/安全等")
    case_status = db.Column(db.String(20), default="草稿", comment="用例状态: 草稿/已评审/已废弃")
    
    status = db.Column(db.Integer, default=1, comment="1: 启用, 0: 禁用")

    # 关系
    api_bindings = db.relationship("TestCaseApiBinding", backref="test_case", lazy="dynamic", cascade="all, delete-orphan")

    def to_dict(self, include_apis=False):
        """转换为字典。"""
        result = {
            "id": self.id,
            "case_no": self.case_no,
            "title": self.title,
            "description": self.description,
            "precondition": self.precondition,
            "steps": self.steps,
            "expected_result": self.expected_result,
            "project_id": self.project_id,
            "module_id": self.module_id,
            "folder_id": self.folder_id,
            "priority": self.priority,
            "case_type": self.case_type,
            "case_status": self.case_status,
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

        if include_apis:
            result["api_ids"] = [binding.api_id for binding in self.api_bindings]

        return result


class TestCaseApiBinding(BaseModel):
    """测试用例与API的绑定关系（多对多）。"""

    __tablename__ = "test_case_api_bindings"

    test_case_id = db.Column(db.Integer, db.ForeignKey("test_case_management.id"), nullable=False)
    api_id = db.Column(db.Integer, db.ForeignKey("apis.id"), nullable=False)
    sort_order = db.Column(db.Integer, default=0, comment="执行顺序")
    remark = db.Column(db.String(200), comment="备注")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "test_case_id": self.test_case_id,
            "api_id": self.api_id,
            "sort_order": self.sort_order,
            "remark": self.remark,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
