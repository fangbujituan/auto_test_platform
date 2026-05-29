# Agents（基于 LangGraph 的智能体）

这个目录存放基于 **LangGraph** 构建的多 Agent。本 README 配合第一个 demo
（`testcase_agent_demo.py`）一起看，帮助快速理解 LangGraph 是什么、怎么用。

## LangGraph 是什么

一句话：**用"状态图"的方式编排多步骤的 AI 工作流**。

普通脚本是"从上往下一条道走到黑"。但真实的测试用例生成往往需要：
生成 → 评审 → 不满意就改 → 再评审……这种**带循环和分支**的流程，
用普通 if/while 写会越来越乱。LangGraph 把它拆成"节点 + 边"的图，
流程清晰、易扩展、可中断、可加记忆。

### 三个核心概念

| 概念 | 是什么 | 在 demo 里对应 |
|------|--------|---------------|
| **State** | 贯穿全流程的共享数据包 | `AgentState`（需求、用例、评审结果、尝试次数…） |
| **Node** | 一个处理步骤，就是普通函数 `f(state) -> dict` | `generate_node`、`review_node` |
| **Edge** | 节点之间的流向；条件边可实现循环/分支 | `START→generate→review→(条件)→retry/accept` |

## Demo：测试用例生成 Agent

`testcase_agent_demo.py` 实现了一个带"评审循环"的用例生成流程：

```
START → generate → review → (条件判断)
          ▲                    │
          └──── retry ─────────┤   评审不通过且未超次数：带反馈回去重做
                               └── accept → END   通过 或 超过最大次数：结束
```

### 直接运行（零配置）

demo 默认使用内置的 `MockLLM`，**不需要数据库、不需要配置 AI 提供商**，
开箱即跑，方便先把 LangGraph 的运行机制看明白：

```bash
python -m app.agents.testcase_agent_demo
```

你会看到它第一轮生成 2 条用例 → 评审不通过 → 带着反馈重新生成、
补出"边界与异常"用例 → 评审通过 → 结束。

### 接入真实大模型

项目已有一套多提供商 AI 服务（`app/services/ai_service.py`，支持
OpenAI / 通义千问 / Ollama）。`llm_bridge.py` 把它封装成了
`call_real_llm(messages)`。要让 demo 用真实模型，只需：

1. 把节点里的 `mock_llm(messages)` 换成 `call_real_llm(messages)`；
2. 在 Flask app context 内运行（因为要查库取提供商配置）：

```python
from app.flask_app import create_app
from app.agents.testcase_agent_demo import run_demo

app = create_app()
with app.app_context():
    run_demo("用户登录功能")
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `testcase_agent_demo.py` | LangGraph 入门 demo：带评审循环的用例生成 agent |
| `llm_bridge.py` | LLM 桥接层：封装真实 `AIService` + 提供零依赖的 `MockLLM` |

## 依赖

```
langgraph>=0.2.0
```

已加入项目根目录 `requirements.txt`。
