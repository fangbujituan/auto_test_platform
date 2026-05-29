"""测试用例管理相关 Schema。"""
from marshmallow import Schema, fields


class TestCaseCreateSchema(Schema):
    """创建测试用例请求"""
    title = fields.String(required=True, metadata={"description": "用例标题"})
    project_id = fields.Integer(required=True, metadata={"description": "项目ID"})
    description = fields.String(metadata={"description": "用例描述"})
    precondition = fields.String(metadata={"description": "前置条件"})
    steps = fields.String(metadata={"description": "测试步骤"})
    expected_result = fields.String(metadata={"description": "预期结果"})
    module_id = fields.Integer(metadata={"description": "模块ID"})
    folder_id = fields.Integer(metadata={"description": "目录ID"})
    priority = fields.String(load_default="P2", metadata={"description": "优先级"})
    case_type = fields.String(load_default="功能", metadata={"description": "用例类型"})
    case_status = fields.String(load_default="草稿", metadata={"description": "用例状态"})
    status = fields.Integer(load_default=1, metadata={"description": "启用状态"})
    api_ids = fields.List(fields.Integer(), load_default=[], metadata={"description": "关联API ID列表"})


class TestCaseUpdateSchema(Schema):
    """更新测试用例请求"""
    title = fields.String(metadata={"description": "用例标题"})
    description = fields.String(metadata={"description": "用例描述"})
    precondition = fields.String(metadata={"description": "前置条件"})
    steps = fields.String(metadata={"description": "测试步骤"})
    expected_result = fields.String(metadata={"description": "预期结果"})
    module_id = fields.Integer(metadata={"description": "模块ID"})
    folder_id = fields.Integer(metadata={"description": "目录ID"})
    priority = fields.String(metadata={"description": "优先级"})
    case_type = fields.String(metadata={"description": "用例类型"})
    case_status = fields.String(metadata={"description": "用例状态"})
    status = fields.Integer(metadata={"description": "启用状态"})
    api_ids = fields.List(fields.Integer(), metadata={"description": "关联API ID列表"})


class TestCaseQuerySchema(Schema):
    """查询测试用例参数"""
    project_id = fields.Integer(metadata={"description": "项目ID"})
    module_id = fields.Integer(metadata={"description": "模块ID"})
    folder_id = fields.Integer(metadata={"description": "目录ID"})
    priority = fields.String(metadata={"description": "优先级"})
    case_type = fields.String(metadata={"description": "用例类型"})
    case_status = fields.String(metadata={"description": "用例状态"})
    page = fields.Integer(load_default=1, metadata={"description": "页码"})
    per_page = fields.Integer(load_default=20, metadata={"description": "每页数量"})


class TestCaseStatsQuerySchema(Schema):
    """测试用例统计查询参数"""
    project_id = fields.Integer(required=True, metadata={"description": "项目ID"})
    module_id = fields.Integer(metadata={"description": "模块ID"})
