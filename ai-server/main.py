from langgraph.prebuilt import create_react_agent
from langchain.agents import create_agent
from llms import get_default_model
from tools import get_weather, get_zhipu_search_mcp_tools, get_tavily_search_tools, \
    get_playwright_mcp_tools, get_chrome_devtools_mcp_tools, get_mcp_server_chart_tools, \
    agent as playwright_agent, make_agent
from tools.playwright.recording_agent import make_recording_agent as recording_agent_factory

# from 父 import 儿子
model = get_default_model(agent_name="web_agent")

# 使用 make_agent，已配置三层中间件和 DOM 清理功能
# 这解决了：
# 1. 页面元素识别不准确问题（通过 DOM 清理中间件）
# 2. Token 超出问题（通过三层 Token 控制机制）
agent = make_agent

# 保留简单的 web_agent 用于非 Playwright 场景
web_agent = create_agent(
    model=model,
    tools=get_chrome_devtools_mcp_tools(),
    system_prompt="You are a helpful assistant"
)

# 录制回放 Agent
# 支持操作录制和脚本回放，用于节省 token 消耗
# 智能登录态加载：
# - 自动检测 playwright_scripts/auth_state/bnp_auth.json 是否存在
# - 存在 → 自动加载登录态（录制登录后操作）
# - 不存在 → 不加载（可用于录制登录流程）
recording_agent = recording_agent_factory
