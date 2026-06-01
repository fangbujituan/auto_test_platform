"""
业务 Agent 层。

承载继承 :class:`BaseAgent` 的具体业务 Agent，每一个 Agent 是测试链路上
的一个能力节点（意图理解 / 用例生成 / 脚本生成 / 执行解析 / ...）。

公开符号
--------

- :class:`IntentAgent`     意图理解：把用户自然语言转成 ``{test_type, target, assertions}``
- :class:`TestcaseAgent`   测试用例生成：包装 ``services.testcase_generator``
- :class:`UIScriptAgent`   UI 脚本生成：包装根目录 ``ui_automation_agent.make_agent``
- :class:`RecordingAgent`  浏览器录制：包装根目录 ``recording_agent.make_recording_agent``
- :class:`ResultAgent`     执行结果解析 + 自动建 bug：包装 ``services.case_runner``

设计原则
--------

1. **零基础设施重写**：所有业务能力已经在 ``app/services`` 实现，本层
   只是用 BaseAgent 模板包一层，把"调 service"变成"在 DAG 里运行的节点"。
2. **与底层工厂解耦**：根目录 ``ui_automation_agent.py`` / ``recording_agent.py``
   作为 LangGraph deepagents 工厂保留不动，``ai_agent.py`` 等老路由继续
   用它们；本层只是新增一个 BaseAgent 视角的入口，**不取代任何东西**。
3. **支持 mock 模式**：输入 ``state.input_data["mock"] = True`` 时跳过 LLM
   /MCP 调用直接产 fake 数据，便于零 token 烟雾测试。

作者: yandc
"""
from app.agents.business.api_script_agent import ApiScriptAgent
from app.agents.business.intent_agent import IntentAgent
from app.agents.business.persistence_agent import PersistenceAgent
from app.agents.business.recording_agent import RecordingAgent
from app.agents.business.result_agent import ResultAgent
from app.agents.business.review_gate_agent import ReviewGateAgent
from app.agents.business.testcase_agent import TestcaseAgent
from app.agents.business.ui_script_agent import UIScriptAgent

__all__ = [
    "IntentAgent",
    "TestcaseAgent",
    "ReviewGateAgent",
    "PersistenceAgent",
    "UIScriptAgent",
    "RecordingAgent",
    "ApiScriptAgent",
    "ResultAgent",
]
