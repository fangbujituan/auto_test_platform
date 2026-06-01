"""
工作流定义集合。

每个文件对外暴露一个 :class:`WorkflowDefinition` 实例 +
配套的 ``register(orchestrator)`` 函数（把所需 Agent + 工作流注册到指定
编排器实例上），方便从路由层一行接入。

公开符号
--------

- :func:`build_testcase_generation_orchestrator`
  搭好"意图 → 用例 → 审核 → 落库 → 执行/结果"工作流的 :class:`LangGraphOrchestrator`
- :func:`build_api_testing_orchestrator`
  搭好"意图 → 用例 → 审核 → 落库 → 脚本生成 → 执行"API 测试工作流

作者: yandc
"""
from app.agents.workflows.api_testing_workflow import (
    api_testing_workflow,
    build_api_testing_orchestrator,
)
from app.agents.workflows.testcase_generation_workflow import (
    build_testcase_generation_orchestrator,
    testcase_generation_workflow,
)

__all__ = [
    "build_testcase_generation_orchestrator",
    "testcase_generation_workflow",
    "build_api_testing_orchestrator",
    "api_testing_workflow",
]
