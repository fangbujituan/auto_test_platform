"""需求管理相关 Schema。"""
from marshmallow import Schema, fields


class RequirementCreateSchema(Schema):
    """创建需求请求"""
    title = fields.String(required=True, metadata={"description": "需求名称"})
    description = fields.String(metadata={"description": "需求描述（支持图文HTML格式）"})
    project_id = fields.Integer(required=True, metadata={"description": "关联项目ID"})
    sprint_id = fields.Integer(metadata={"description": "关联冲刺ID"})
    assignee_ids = fields.List(fields.Integer(), load_default=[], metadata={"description": "关联人员ID数组"})
    status = fields.String(load_default="draft", metadata={"description": "状态: draft, pending, approved, in_progress, testing, done, closed, rejected"})
    priority = fields.String(load_default="medium", metadata={"description": "优先级: low, medium, high, critical"})
    tag_ids = fields.List(fields.Integer(), load_default=[], metadata={"description": "标签ID数组"})


class RequirementUpdateSchema(Schema):
    """更新需求请求（所有字段可选）"""
    title = fields.String(metadata={"description": "需求名称"})
    description = fields.String(metadata={"description": "需求描述"})
    sprint_id = fields.Integer(metadata={"description": "关联冲刺ID"}, allow_none=True)
    assignee_ids = fields.List(fields.Integer(), metadata={"description": "关联人员ID数组"})
    status = fields.String(metadata={"description": "状态"})
    priority = fields.String(metadata={"description": "优先级"})
    tag_ids = fields.List(fields.Integer(), metadata={"description": "标签ID数组"})


class RequirementQuerySchema(Schema):
    """查询需求参数"""
    project_id = fields.Integer(required=True, metadata={"description": "项目ID"})
    sprint_id = fields.Integer(metadata={"description": "冲刺ID"})
    status = fields.String(metadata={"description": "状态"})
    priority = fields.String(metadata={"description": "优先级"})
    assignee_id = fields.Integer(metadata={"description": "负责人ID"})
    keyword = fields.String(metadata={"description": "搜索关键词"})
    page = fields.Integer(load_default=1, metadata={"description": "页码"})
    per_page = fields.Integer(load_default=20, metadata={"description": "每页数量"})


class SprintCreateSchema(Schema):
    """创建冲刺请求"""
    name = fields.String(required=True, metadata={"description": "冲刺名称"})
    project_id = fields.Integer(required=True, metadata={"description": "关联项目ID"})
    start_date = fields.DateTime(required=True, metadata={"description": "开始时间"})
    end_date = fields.DateTime(required=True, metadata={"description": "结束时间"})
    goal = fields.String(metadata={"description": "冲刺目标"})
    status = fields.String(load_default="planning", metadata={"description": "状态: planning, active, completed, cancelled"})


class SprintUpdateSchema(Schema):
    """更新冲刺请求"""
    name = fields.String(metadata={"description": "冲刺名称"})
    start_date = fields.DateTime(metadata={"description": "开始时间"})
    end_date = fields.DateTime(metadata={"description": "结束时间"})
    goal = fields.String(metadata={"description": "冲刺目标"})
    status = fields.String(metadata={"description": "状态"})


class SprintQuerySchema(Schema):
    """查询冲刺参数"""
    project_id = fields.Integer(required=True, metadata={"description": "项目ID"})
    status = fields.String(metadata={"description": "状态"})


class TagCreateSchema(Schema):
    """创建标签请求"""
    name = fields.String(required=True, metadata={"description": "标签名称"})
    color = fields.String(load_default="#409EFF", metadata={"description": "标签颜色"})


class OperationLogQuerySchema(Schema):
    """查询操作日志参数"""
    project_id = fields.Integer(metadata={"description": "项目ID"})
    operator_id = fields.Integer(metadata={"description": "操作人ID"})
    target_type = fields.String(metadata={"description": "操作对象类型"})
    page = fields.Integer(load_default=1, metadata={"description": "页码"})
    per_page = fields.Integer(load_default=20, metadata={"description": "每页数量"})
