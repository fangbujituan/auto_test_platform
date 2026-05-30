"""
本平台对外提供的 MCP（Model Context Protocol）Server。

把"质量飞轮"能力暴露给外部 Agent（开发的 IDE Agent / Cursor / Claude Code 等），
让他们能直接调用我们的"生成用例 / 跑用例 / 建 bug"。

设计原则：
1. **服务端复用**：所有 MCP tool 都是对 ``app.services.*`` 的薄封装，
   逻辑只写一份。
2. **传输灵活**：默认 stdio（适合 Cursor/Claude Code 本地接入），
   也支持 SSE / HTTP（适合远程接入）。
3. **不依赖 Flask 进程**：MCP Server 是独立可执行入口（``python -m app.mcp_server``），
   通过 ``create_app()`` 拿到 app context 后操作 ORM。

启动方式：
    # stdio（IDE 本地接入）
    python -m app.mcp_server

    # HTTP / SSE（远程接入）
    python -m app.mcp_server --transport sse --host 0.0.0.0 --port 7800
"""

from app.mcp_server.server import create_mcp_server

__all__ = ["create_mcp_server"]
