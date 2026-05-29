"""
测试结果模型。

作者: yandc
创建时间: 2026-01-13
"""
from app.models.base import db, BaseModel


class TestResult(BaseModel):
    """测试执行结果模型。"""

    __tablename__ = "test_results"

    case_id = db.Column(db.Integer, db.ForeignKey("test_cases.id"), nullable=False)
    status = db.Column(db.String(20), comment="passed, failed, error, skipped")
    
    actual_status = db.Column(db.Integer, comment="Actual HTTP status code")
    actual_response = db.Column(db.JSON, comment="Actual response")
    
    duration = db.Column(db.Float, comment="Execution time in seconds")
    error_message = db.Column(db.Text, comment="Error message if failed")

    def to_dict(self):
        """转换为字典。"""
        return {
            "id": self.id,
            "case_id": self.case_id,
            "status": self.status,
            "actual_status": self.actual_status,
            "actual_response": self.actual_response,
            "duration": self.duration,
            "error_message": self.error_message,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
