"""
录制回放 Agent 工厂。

迁移自 ai-server/tools/playwright/recording_agent.py。

相对原版的简化（取长补短）：
- 移除 BNP 特定的自动登录链路（``bnp_check_auth`` / ``bnp_login_and_save``），
  改为通用的"登录态文件存在则加载"。BNP 特定登录留在 P3 阶段单独迁移。
- 移除依赖 ``ScriptIndexManager`` 高级特性的工具
  （``rebuild_index`` / ``init_script_library`` / ``cleanup_scripts`` /
  ``list_low_quality_scripts``），等索引管理迁移完整后再补回。
- 保留核心录制工作流：check_script / save_current_recording /
  list_scripts / delete_script / reset_recording / get_current_code /
  create_script_with_auth。

环境变量：
    PLAYWRIGHT_LOAD_AUTH_STATE   true|false|auto（默认 auto，文件存在则加载）
    PLAYWRIGHT_AUTH_STATE_PATH   登录态文件路径（默认
                                 playwright_scripts/auth_state/bnp_auth.json）
    UI_RECORDING_AGENT_NAME      Agent 名（默认 recording_agent）
    UI_RECORDING_TRIGGER_TOKENS  Token 摘要触发阈值（默认 100000）
    UI_RECORDING_KEEP_MESSAGES   摘要后保留的最近消息数（默认 50）

使用方式：
    from app.agents.recording_agent import make_recording_agent

    async with make_recording_agent() as agent:
        result = await agent.ainvoke({"messages": [...]})
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, List

import anyio
from deepagents import create_deep_agent
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.pregel import Pregel

from app.agents.prompts import RECORDING_SYSTEM_PROMPT
from app.engine.ui_engine.config import DEFAULT_CONFIG
from app.engine.ui_engine.playwright.executor import create_playwright_executor_tool
from app.engine.ui_engine.playwright.report import create_result_parser_tool
from app.engine.ui_engine.playwright.script_generator import create_script_save_tool
from app.engine.ui_engine.playwright.script_manager import get_manager
from app.services.llm_gateway import get_model
from app.utils.debug.readlog import logs
from app.utils.middleware import (
    Base64FilterMiddleware,
    BeforeAgentMiddleware,
    DOMCleanerMiddleware,
    ThreadContextMiddleware,
    TokenControlMiddleware,
)
from app.utils.middleware.code_collector import get_collector
from app.utils.middleware.semantic_selector import (
    get_semantic_selector,
    reset_semantic_selector,
)


# ============================================================================
# 配置
# ============================================================================

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_AUTH_STATE_PATH = (
    _PROJECT_ROOT / "playwright_scripts" / "auth_state" / "bnp_auth.json"
)

_AGENT_NAME = os.getenv("UI_RECORDING_AGENT_NAME", "recording_agent")
_TRIGGER_TOKENS = int(os.getenv("UI_RECORDING_TRIGGER_TOKENS", "100000"))
_KEEP_MESSAGES = int(os.getenv("UI_RECORDING_KEEP_MESSAGES", "50"))


# ============================================================================
# 录制管理工具（@tool 装饰，挂给 agent 调用）
# ============================================================================

@tool
def check_script(url: str, task_description: str) -> str:
    """检查是否有匹配的录制脚本。

    在执行新任务前调用，看脚本库中是否已有可复用的脚本。

    Args:
        url: 目标 URL
        task_description: 任务描述（如：登录、搜索、填写表单）

    Returns:
        匹配结果，包括脚本名称和描述
    """
    manager = get_manager()
    best_match = manager.find_best_match(url, task_description)

    if best_match:
        metadata = manager.load_metadata(best_match)
        if metadata:
            variables = ", ".join(metadata.variables) if metadata.variables else "无"
            return (
                f"找到匹配脚本：\n"
                f"- 名称: {best_match}\n"
                f"- 描述: {metadata.description}\n"
                f"- 变量: {variables}\n"
                f"- 使用次数: {metadata.usage_count}\n"
                f"- 成功率: {metadata.success_rate * 100:.1f}%\n\n"
                f"使用 run_playwright_script 工具执行此脚本。"
            )

    all_scripts = manager.list_scripts()
    if all_scripts:
        return (
            f"未找到完全匹配的脚本。\n"
            f"可用脚本: {', '.join(all_scripts)}\n\n"
            f"可以使用 Playwright 工具手动操作，完成后用 save_current_recording 保存。"
        )
    return "脚本库为空。可以使用 Playwright 工具手动操作，完成后用 save_current_recording 保存。"


@tool
def save_current_recording(name: str, description: str = "", keywords: str = "") -> str:
    """保存当前录制的脚本。

    将当前会话中收集的 Playwright 操作保存为可复用的脚本。

    Args:
        name: 脚本名称（如：login_github, search_google）
        description: 脚本描述
        keywords: 关键词，多个用逗号分隔（如：登录,login,github）
    """
    collector = get_collector(get_semantic_selector())
    manager = get_manager()

    code = collector.get_collected_code()
    if not code.strip():
        return "错误：没有收集到任何代码。请先执行一些 Playwright 操作。"

    ref_count, semantic_count = collector.get_selector_stats()
    total_selectors = ref_count + semantic_count

    full_script = collector.generate_script(name=name, description=description)

    keyword_list = [k.strip() for k in keywords.split(",") if k.strip()]
    if not manager.save_script(
        name=name,
        code=full_script,
        description=description,
        url_patterns=[],
        keywords=keyword_list,
        variables=[],
    ):
        return "错误：脚本保存失败。"

    # 同步保存到 ui_engine 的 tests/ 目录
    save_tool = create_script_save_tool(DEFAULT_CONFIG)
    file_result = save_tool.invoke({
        "script_content": full_script,
        "script_name": name,
        "language": "typescript",
    })

    # 质量报告
    if total_selectors > 0:
        ratio = semantic_count / total_selectors
        if ratio >= 0.8:
            quality_report = (
                f"✅ 高质量脚本：{semantic_count}/{total_selectors} "
                f"使用语义化选择器 ({ratio:.0%})"
            )
        elif ratio >= 0.5:
            quality_report = (
                f"⚠️ 中等质量：{semantic_count}/{total_selectors} "
                f"使用语义化选择器 ({ratio:.0%})"
            )
        else:
            quality_report = (
                f"❌ 低质量：仅 {semantic_count}/{total_selectors} "
                f"使用语义化选择器 ({ratio:.0%})，建议优化"
            )
    else:
        quality_report = "ℹ️ 无选择器统计信息"

    script_virtual_path = f"/playwright_scripts/tests/{name}.spec.ts"
    collector.reset()

    return (
        f"脚本保存成功！\n"
        f"- 名称: {name}\n"
        f"- 代码行数: {len(code.splitlines())}\n"
        f"- 选择器统计: {quality_report}\n\n"
        f"{file_result}\n\n"
        f"## 📋 运行此脚本\n\n"
        f"使用以下路径运行脚本：\n"
        f"```\nscript_path: \"{script_virtual_path}\"\n```\n"
    )


@tool
def list_scripts() -> str:
    """列出所有已保存的脚本。"""
    manager = get_manager()
    names = manager.list_scripts()
    if not names:
        return "脚本库为空。执行一些操作后使用 save_current_recording 保存。"

    lines: List[str] = ["已保存的脚本：\n"]
    for name in names:
        meta = manager.load_metadata(name)
        if meta:
            lines.append(
                f"- {name}\n"
                f"  描述: {meta.description}\n"
                f"  使用次数: {meta.usage_count} | 成功率: {meta.success_rate * 100:.1f}%\n"
            )
        else:
            lines.append(f"- {name}（无元数据）\n")
    return "\n".join(lines)


@tool
def delete_script(name: str) -> str:
    """删除已保存的脚本。

    Args:
        name: 脚本名称
    """
    manager = get_manager()
    if manager.delete_script(name):
        return f"脚本 '{name}' 已删除。"
    return f"脚本 '{name}' 不存在或删除失败。"


@tool
def reset_recording() -> str:
    """重置当前录制。清空当前会话收集的所有代码和缓存，开始新的录制。"""
    get_collector().reset()
    reset_semantic_selector()
    return "录制已重置，可以开始新的操作录制。"


@tool
def get_current_code() -> str:
    """获取当前录制的代码（查看当前会话已收集的 TypeScript 代码）。"""
    code = get_collector().get_collected_code()
    if not code.strip():
        return "当前没有收集到任何代码。"
    return f"当前收集的代码：\n```typescript\n{code}\n```"


@tool
def create_script_with_auth(
    script_name: str,
    url: str,
    operations: str,
    auth_state_path: str = "auth_state/bnp_auth.json",
) -> str:
    """创建带登录态的 Playwright 脚本框架。

    ⚠️ 此工具只生成脚本框架，不生成实际操作代码！正确流程：先用 browser_*
    工具实际操作，中间件会自动收集代码，再用 save_current_recording 保存。

    Args:
        script_name: 脚本名称
        url: 起始 URL
        operations: 操作步骤描述（仅用于注释）
        auth_state_path: 登录态文件相对路径
    """
    ops_list = [op.strip() for op in operations.split("\\n") if op.strip()]
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    script_content = (
        f"import {{ test, expect }} from '@playwright/test';\n"
        f"\n"
        f"/**\n"
        f" * {script_name}\n"
        f" * ⚠️ 此脚本需要通过录制补充实际操作代码！\n"
        f" * 生成时间: {timestamp}\n"
        f" *\n"
        f" * 运行方式：\n"
        f" * PLAYWRIGHT_AUTH_STATE={auth_state_path} npx playwright test "
        f"tests/{script_name}.spec.ts --project=chromium-auth\n"
        f" */\n"
        f"\n"
        f"test('{script_name}', async ({{ page }}) => {{\n"
        f"  // 公司网络缓慢，导航后必须等待 30 秒\n"
        f"  await page.goto('{url}');\n"
        f"  await page.waitForLoadState('networkidle', {{ timeout: 30000 }});\n"
        f"  await page.waitForTimeout(30000);\n"
        f"\n"
        f"  // ========== 以下是操作步骤（需通过录制补充实际代码）==========\n"
    )
    for i, op in enumerate(ops_list, 1):
        script_content += (
            f"\n  // TODO 步骤 {i}: {op}\n"
            f"  // await page.getByRole('button', {{name: 'xxx'}}).click();\n"
            f"  // await page.waitForTimeout(5000);\n"
        )
    script_content += (
        f"\n  await page.waitForLoadState('networkidle');\n"
        f"  console.log('测试完成！');\n"
        f"}});\n"
    )

    save_tool = create_script_save_tool(DEFAULT_CONFIG)
    file_result = save_tool.invoke({
        "script_content": script_content,
        "script_name": script_name,
        "language": "typescript",
    })

    manager = get_manager()
    manager.save_metadata(
        name=script_name,
        description=f"带登录态脚本: {script_name}（需要补充实际代码）",
        url_patterns=[url],
        keywords=ops_list,
        variables=["auth_state"],
    )

    return (
        f"脚本框架已创建！\n"
        f"\n"
        f"文件: /playwright_scripts/tests/{script_name}.spec.ts\n"
        f"\n"
        f"⚠️ 重要提示：\n"
        f"1. 脚本中的选择器是占位符，需要根据实际页面修改\n"
        f"2. 登录态文件: playwright_scripts/{auth_state_path}\n"
        f"3. 推荐流程：用 browser_* 工具实际操作 → save_current_recording 保存\n\n"
        f"{file_result}"
    )


_RECORDING_TOOLS = [
    check_script,
    save_current_recording,
    list_scripts,
    delete_script,
    reset_recording,
    get_current_code,
    create_script_with_auth,
]


# ============================================================================
# Agent 工厂
# ============================================================================

def _resolve_auth_state() -> tuple[bool, str]:
    """根据环境变量决定是否加载登录态。

    Returns:
        (should_load, abs_path_str)
    """
    mode = os.getenv("PLAYWRIGHT_LOAD_AUTH_STATE", "auto").lower()
    raw_path = os.getenv("PLAYWRIGHT_AUTH_STATE_PATH", "")
    auth_path = Path(raw_path) if raw_path else _DEFAULT_AUTH_STATE_PATH
    if not auth_path.is_absolute():
        auth_path = _PROJECT_ROOT / auth_path
    abs_path_str = str(auth_path).replace("\\", "/")

    if mode == "false":
        logs.info("[recording_agent] ℹ️ 禁用登录态加载（PLAYWRIGHT_LOAD_AUTH_STATE=false）")
        return False, abs_path_str

    if not auth_path.exists():
        msg = (
            "[recording_agent] ⚠️ 登录态文件不存在: %s，将启动无登录态浏览器" % abs_path_str
        )
        if mode == "true":
            logs.error(msg + "（已强制要求加载，请先创建文件）")
        else:
            logs.info(msg)
        return False, abs_path_str

    logs.info(f"[recording_agent] 🔐 加载登录态: {abs_path_str}")
    return True, abs_path_str


@asynccontextmanager
async def make_recording_agent() -> AsyncIterator[Pregel]:
    """创建录制回放 Agent。

    集成能力：
    - **脚本录制**：CodeCollectorMiddleware 从工具调用参数生成 TypeScript
    - **DOM 清理**：DOMCleanerMiddleware 清除多余元素
    - **Token 控制**：TokenControlMiddleware 历史摘要
    - **Base64 过滤**：截图保存到本地，替换为路径
    - **语义选择器**：SemanticSelectorMiddleware 解析快照
    - **本地工具**：脚本保存、执行、结果解析

    登录态：通过 ``PLAYWRIGHT_LOAD_AUTH_STATE`` 环境变量控制。
    """
    config = DEFAULT_CONFIG

    should_load_auth, auth_state_path_str = _resolve_auth_state()

    playwright_args = [
        "-y", "@playwright/mcp@latest",
        "--viewport-size", "1920x1080",
    ]
    if should_load_auth:
        # --storage-state 必须配合 --isolated 才能生效
        playwright_args.append("--isolated")
        playwright_args.append(f"--storage-state={auth_state_path_str}")

    logs.info("=" * 60)
    logs.info("🚀 [MCP Playwright] 启动浏览器（实时 MCP 模式）")
    logs.info(f"   登录态加载: {'是' if should_load_auth else '否'}")
    if should_load_auth:
        logs.info(f"   登录态文件: {auth_state_path_str}")
    logs.info(f"   启动参数: {' '.join(playwright_args)}")
    logs.info("=" * 60)

    playwright_client = MultiServerMCPClient(
        {
            "playwright": {
                "transport": "stdio",
                "command": "npx",
                "args": playwright_args,
            }
        }
    )

    model = get_model(agent_name=_AGENT_NAME)

    # 中间件链（顺序很重要）
    semantic_selector = get_semantic_selector()
    collector = get_collector(semantic_selector=semantic_selector)
    dom_cleaner = DOMCleanerMiddleware()
    base64_filter = Base64FilterMiddleware(config)

    logs.info(f"[recording_agent] 中间件实例 ID: "
              f"semantic={id(semantic_selector)} collector={id(collector)} "
              f"dom={id(dom_cleaner)} base64={id(base64_filter)}")

    middleware = [
        ThreadContextMiddleware(agent_name=_AGENT_NAME),
        BeforeAgentMiddleware(),
        semantic_selector,
        collector,
        # base64 过滤要在 DOM 清理之前，避免大图片被清理逻辑访问
        base64_filter,
        dom_cleaner,
        TokenControlMiddleware(
            model=model,
            trigger_tokens=_TRIGGER_TOKENS,
            keep_messages=_KEEP_MESSAGES,
            max_summary_length=8000,
        ),
    ]

    # 本地（非 MCP）工具
    script_save_tool = create_script_save_tool(config)
    executor_tool = create_playwright_executor_tool(config)
    parser_tool = create_result_parser_tool(config)

    try:
        async with playwright_client.session("playwright") as playwright_session:
            playwright_tools = await load_mcp_tools(playwright_session)

            # 把工具列表传给语义选择器，供其找到 browser_evaluate 做 JS 注入
            semantic_selector.set_tools(playwright_tools)

            all_tools = (
                list(playwright_tools)
                + _RECORDING_TOOLS
                + [script_save_tool, executor_tool, parser_tool]
            )

            logs.info(
                f"[recording_agent] 装配完成 | tools={len(all_tools)} "
                f"| middleware={[type(m).__name__ for m in middleware]}"
            )

            agent = create_deep_agent(
                tools=all_tools,
                system_prompt=RECORDING_SYSTEM_PROMPT,
                model=model,
                middleware=middleware,
            )

            yield agent

    except (anyio.BrokenResourceError, BaseExceptionGroup) as e:
        # MCP 会话在服务关闭时可能抛出这些异常，属于正常关闭流程
        if isinstance(e, BaseExceptionGroup):
            broken = [exc for exc in e.exceptions if isinstance(exc, anyio.BrokenResourceError)]
            if broken or "TaskGroup" in str(e):
                logs.info("[recording_agent] MCP 会话已正常关闭")
            else:
                logs.warning(f"[recording_agent] MCP 会话关闭时出现异常: {e}")
        else:
            logs.info("[recording_agent] MCP 会话资源已释放")
    except Exception as e:
        logs.error(f"[recording_agent] Agent 运行异常: {e}")
        raise


# 别名，便于作为 LangGraph API 的 graph 入口
recording_agent = make_recording_agent


__all__ = ["make_recording_agent", "recording_agent"]
