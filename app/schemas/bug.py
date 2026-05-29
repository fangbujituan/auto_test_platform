"""Bug 管理相关 Schema。"""
from marshmallow import Schema, fields


class BugCreateSchema(Schema):
    """创建 Bug 请求"""
    title = fields.String(required=True, metadata={"description": "Bug标题"})
    description = fields.String(metadata={"description": "Bug描述"})
    status = fields.String(load_default="open", metadata={"description": "状态"})
    priority = fields.String(load_default="medium", metadata={"description": "优先级"})
    severity = fields.String(load_default="normal", metadata={"description": "严重程度"})
    category = fields.String(metadata={"description": "分类"})
    module = fields.String(metadata={"description": "所属模块"})
    folder_id = fields.Integer(metadata={"description": "所属目录ID"})
    tags = fields.List(fields.String(), load_default=[], metadata={"description": "标签"})
    reporter_id = fields.Integer(metadata={"description": "报告人ID"})
    assignee_id = fields.Integer(metadata={"description": "指派人ID"})
    environment = fields.String(metadata={"description": "测试环境"})
    version = fields.String(metadata={"description": "发现版本"})
    steps_to_reproduce = fields.String(metadata={"description": "复现步骤"})
    expected_result = fields.String(metadata={"description": "预期结果"})
    actual_result = fields.String(metadata={"description": "实际结果"})
    attachments = fields.List(fields.Dict(), load_default=[], metadata={"description": "附件"})
    related_apis = fields.List(fields.Integer(), load_default=[], metadata={"description": "关联API"})
    related_test_cases = fields.List(fields.Integer(), load_default=[], metadata={"description": "关联用例"})


class BugUpdateSchema(BugCreateSchema):
    """更新 Bug 请求（所有字段可选）"""
    title = fields.String(metadata={"description": "Bug标题"})


class BugResolveSchema(Schema):
    """解决 Bug 请求"""
    resolution = fields.String(load_default="fixed", metadata={"description": "解决方案"})
    resolution_note = fields.String(metadata={"description": "解决说明"})


class BugQuerySchema(Schema):
    """查询 Bug 参数"""
    status = fields.String(metadata={"description": "状态"})
    priority = fields.String(metadata={"description": "优先级"})
    severity = fields.String(metadata={"description": "严重程度"})
    folder_id = fields.Integer(metadata={"description": "目录ID"})
    assignee_id = fields.Integer(metadata={"description": "指派人ID"})
    reporter_id = fields.Integer(metadata={"description": "报告人ID"})
    keyword = fields.String(metadata={"description": "搜索关键词"})
