"""
测试用例模型。

作者: yandc
创建时间: 2026-01-13
"""
from app.models.base import db, BaseModel


class TestCase(BaseModel):
    """测试用例模型。"""

    __tablename__ = "test_cases"

    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    
    # API测试字段
    method = db.Column(db.String(10), default="GET", comment="HTTP method")
    url = db.Column(db.String(500), nullable=False)
    headers = db.Column(db.JSON, comment="Request headers")
    params = db.Column(db.JSON, comment="Query parameters")
    body = db.Column(db.JSON, comment="Request body")
    
    # 断言字段
    expected_status = db.Column(db.Integer, default=200)
    expected_response = db.Column(db.JSON, comment="Expected response for validation")
    
    status = db.Column(db.Integer, default=1, comment="1: active, 0: inactive")
    priority = db.Column(db.Integer, default=2, comment="1: high, 2: medium, 3: low")

    results = db.relationship("TestResult", backref="case", lazy="dynamic")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "project_id": self.project_id,
            "method": self.method,
            "url": self.url,
            "headers": self.headers,
            "params": self.params,
            "body": self.body,
            "expected_status": self.expected_status,
            "expected_response": self.expected_response,
            "status": self.status,
            "priority": self.priority,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
