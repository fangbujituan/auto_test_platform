"""自动化管理相关 Schema。"""
from marshmallow import Schema, fields


class AutomationTaskCreateSchema(Schema):
    """创建自动化任务请求"""
    name = fields.String(
        required=True, metadata={"description": "任务名称"}
    )
    description = fields.String(
        metadata={"description": "任务描述"}
    )
    trigger_type = fields.String(
        load_default="manual",
        metadata={"description": "触发类型: manual/cron/webhook"},
    )
    cron_expression = fields.String(
        metadata={"description": "Cron表达式"}
    )
    environment_id = fields.Integer(
        metadata={"description": "环境ID"}
    )
    case_ids = fields.List(
        fields.Integer(),
        required=True,
        metadata={"description": "测试用例ID列表"},
    )


class AutomationTaskUpdateSchema(Schema):
    """更新自动化任务请求（所有字段可选）"""
    name = fields.String(metadata={"description": "任务名称"})
    description = fields.String(
        metadata={"description": "任务描述"}
    )
    trigger_type = fields.String(
        metadata={"description": "触发类型: manual/cron/webhook"}
    )
    cron_expression = fields.String(
        metadata={"description": "Cron表达式"}
    )
    environment_id = fields.Integer(
        metadata={"description": "环境ID"}
    )
    case_ids = fields.List(
        fields.Integer(),
        metadata={"description": "测试用例ID列表"},
    )
    status = fields.Integer(
        metadata={"description": "状态: 1启用 0禁用"}
    )


class AutomationTaskExecuteSchema(Schema):
    """手动触发执行请求"""
    environment_id = fields.Integer(
        metadata={"description": "环境ID（可选，覆盖任务默认环境）"}
    )
