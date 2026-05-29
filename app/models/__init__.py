"""数据库模型模块。"""
from app.models.case import TestCase
from app.models.result import TestResult
from app.models.project import Project
from app.models.user import User
from app.models.role import Role, Permission
from app.models.project_member import ProjectMember
from app.models.api import Api
from app.models.api_folder import ApiFolder
from app.models.module import Module
from app.models.test_case import TestCaseManagement, TestCaseApiBinding
from app.models.bug import Bug
from app.models.sprint import Sprint
from app.models.requirement import Requirement, RequirementStatus
from app.models.tag import Tag, requirement_tags
from app.models.operation_log import OperationLog
from app.models.ai_provider import AIProviderConfig
from app.models.ai_prompt import AIPromptTemplate
from app.models.env_variable import (
    EnvironmentVariable, Environment, PrefixUrl, GlobalVariable, GlobalParam,
)
from app.models.automation import (
    AutomationTask, AutomationTaskCase, TaskExecution, TaskExecutionDetail,
    generate_task_no,
)

__all__ = [
    "TestCase", "TestResult", "Project", "User", "Role", "Permission",
    "ProjectMember", "Api", "ApiFolder", "Module", "TestCaseManagement",
    "TestCaseApiBinding", "Bug", "Sprint", "Requirement", "RequirementStatus",
    "Tag", "requirement_tags", "OperationLog", "AIProviderConfig",
    "AIPromptTemplate", "EnvironmentVariable", "Environment", "PrefixUrl",
    "GlobalVariable", "GlobalParam", "AutomationTask", "AutomationTaskCase",
    "TaskExecution", "TaskExecutionDetail", "generate_task_no",
]
