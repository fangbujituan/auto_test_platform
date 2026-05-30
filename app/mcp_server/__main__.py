"""
MCP Server CLI 入口。

外部 Agent 接入方式：

1. **stdio**（推荐用于 Cursor / Claude Code 等本地 IDE Agent 接入）::

       python -m app.mcp_server

   配置示例（Claude Code / Cursor 的 ``mcp.json``）::

       {
         "mcpServers": {
           "auto-test-platform": {
             "command": "/path/to/venv/bin/python",
             "args": ["-m", "app.mcp_server"],
             "cwd": "/path/to/auto_test_platform"
           }
         }
       }

2. **SSE / HTTP**（用于远程 Agent 接入，例如另一个微服务）::

       python -m app.mcp_server --transport sse --host 0.0.0.0 --port 7800
"""

from __future__ import annotations

import argparse
import logging
import sys

from dotenv import load_dotenv

# 加载 .env，确保 LLM 网关、MySQL、MCP Key 等都生效
load_dotenv(override=False)

from app.mcp_server.server import create_mcp_server


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m app.mcp_server",
        description="自动化测试平台 MCP Server",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP 传输协议（默认 stdio，IDE Agent 接入用）",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址（仅 sse / streamable-http 模式生效）",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7800,
        help="监听端口（仅 sse / streamable-http 模式生效）",
    )
    parser.add_argument(
        "--name",
        default="auto-test-platform",
        help="MCP Server 名称",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    # stdio 模式日志必须走 stderr，否则会污染 MCP 协议消息
    log_handler = logging.StreamHandler(stream=sys.stderr)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[log_handler],
        force=True,
    )

    server = create_mcp_server(name=args.name)

    if args.transport == "stdio":
        # FastMCP 默认 stdio
        server.run(transport="stdio")
    elif args.transport == "sse":
        # FastMCP 0.4+ 支持的 SSE 传输
        server.settings.host = args.host
        server.settings.port = args.port
        server.run(transport="sse")
    else:
        server.settings.host = args.host
        server.settings.port = args.port
        server.run(transport="streamable-http")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
