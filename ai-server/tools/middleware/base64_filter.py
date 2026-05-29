# -*- coding: UTF-8 -*-
"""
Base64 图片过滤中间件模块

功能：
- 拦截工具返回的 base64 图片数据
- 将截图保存到本地文件
- 替换消息中的 base64 为文件路径
- 显著减少 token 消耗

使用方式：
    from tools.middleware.base64_filter import Base64FilterMiddleware
    
    middleware = [
        Base64FilterMiddleware(config),
        # ... 其他中间件
    ]
"""

import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage

from tools.debug.readlog import logs


# ============================================================================
# Base64 数据的正则匹配模式（支持多种格式）
# ============================================================================

# 格式1: langchain_mcp_adapters 实际格式 - {'type': 'image', 'id': '...', 'base64': '...', 'mime_type': 'image/png'}
# 这是最常见的格式，langchain_mcp_adapters 转换 MCP Image Content 后的格式
BASE64_PATTERN_LMCA = re.compile(r"'base64'\s*:\s*'([A-Za-z0-9+/=]{50,})'")

# 格式2: MCP Image Content JSON - {"type": "image", "data": "base64...", "mimeType": "..."}
BASE64_PATTERN_MCP_IMAGE = re.compile(r'"type"\s*:\s*"image"\s*,\s*"data"\s*:\s*"([A-Za-z0-9+/=]{50,})"')

# 格式3: "base64Data":"..."
BASE64_PATTERN_JSON = re.compile(r'\\?"base64Data\\?"\s*:\s*\\?"([A-Za-z0-9+/=]{50,}.*?)\\?"')

# 格式4: data:image/png;base64,xxx 或 data:image/jpeg;base64,xxx
BASE64_PATTERN_DATA_URI = re.compile(r'data:image/(png|jpeg|jpg|gif|webp);base64,([A-Za-z0-9+/=]{50,})')

# 格式5: 纯 base64 字符串（长字符串，通常是截图数据）
BASE64_PATTERN_PURE = re.compile(r'([A-Za-z0-9+/=]{200,}={0,2})')


# ============================================================================
# 辅助函数
# ============================================================================

def _save_base64_image(base64_data: str, message_id: str, config) -> str:
    """
    保存 base64 图片到本地并返回文件路径.
    
    Args:
        base64_data: base64 编码的图片数据
        message_id: 消息 ID，用于生成文件名
        config: UIAutomationConfig 配置对象
        
    Returns:
        保存的文件路径
    """
    images_dir = Path(config.workspace_root) / config.base64_images_dir.lstrip("/")
    images_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{message_id}_{timestamp}.png"
    filepath = images_dir / filename

    try:
        image_bytes = base64.b64decode(base64_data)
        filepath.write_bytes(image_bytes)
        logs.info(f"[Base64Filter] 图片已保存: {filepath} ({len(image_bytes)} bytes)")
        return str(filepath.absolute())
    except Exception as e:
        logs.error(f"[Base64Filter] 保存图片失败: {e}")
        return f"[ERROR: Failed to save image - {e}]"


# ============================================================================
# 中间件类
# ============================================================================

class Base64FilterMiddleware(AgentMiddleware):
    """
    Base64 图片过滤中间件，重写 awrap_tool_call 方法拦截工具输出，
    在工具返回后立即处理 base64 数据，确保在存入消息历史之前就完成替换。
    
    这是关键：使用 awrap_tool_call 而不是 before_model，因为：
    - awrap_tool_call: 工具返回后立即执行，此时数据还没进入消息历史
    - before_model: 模型调用前执行，如果 token 已经超限，根本没机会执行
    
    Attributes:
        config: UIAutomationConfig 配置对象
    """

    @property
    def name(self) -> str:
        """中间件名称"""
        return "base64_filter"

    def __init__(self, config):
        """
        初始化中间件
        
        Args:
            config: UIAutomationConfig 配置对象，包含 workspace_root 和 base64_images_dir
        """
        super().__init__()
        self.config = config
        logs.info("[Base64FilterMiddleware] 初始化完成")

    def _contains_base64(self, content: Any) -> bool:
        """检查内容是否包含 base64 数据."""
        if content is None:
            return False

        if isinstance(content, str):
            # 优先检查 langchain_mcp_adapters 格式（最常见）
            if BASE64_PATTERN_LMCA.search(content):
                return True
            if BASE64_PATTERN_MCP_IMAGE.search(content):
                return True
            if BASE64_PATTERN_JSON.search(content):
                return True
            if BASE64_PATTERN_DATA_URI.search(content):
                return True
            if BASE64_PATTERN_PURE.search(content):
                return True
            return False

        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    # 检查 langchain_mcp_adapters 格式: {'type': 'image', 'base64': '...', 'mime_type': '...'}
                    if item.get("type") == "image" and "base64" in item:
                        base64_data = item.get("base64", "")
                        if isinstance(base64_data, str) and len(base64_data) > 50:
                            return True
                    # 检查其他可能的格式
                    if "base64" in item and len(str(item.get("base64", ""))) > 50:
                        base64_data = item.get("base64", "")
                        if isinstance(base64_data, str) and len(base64_data) > 1000:
                            return True
                    # 检查嵌套的 text 字段
                    text = item.get("text", "")
                    if isinstance(text, str) and self._contains_base64(text):
                        return True
                elif isinstance(item, str) and self._contains_base64(item):
                    return True

        if isinstance(content, dict):
            # 检查 langchain_mcp_adapters 格式
            if content.get("type") == "image" and "base64" in content:
                base64_data = content.get("base64", "")
                if isinstance(base64_data, str) and len(base64_data) > 50:
                    return True
            if "base64" in content and len(str(content.get("base64", ""))) > 50:
                base64_data = content.get("base64", "")
                if isinstance(base64_data, str) and len(base64_data) > 1000:
                    return True

        return False

    def _get_base64_stats(self, content: Any) -> dict:
        """获取 base64 数据统计信息"""
        stats = {
            "lmca_format": 0,      # langchain_mcp_adapters 格式 {'type': 'image', 'base64': '...', 'mime_type': '...'}
            "mcp_image_format": 0, # MCP Image Content 格式
            "json_format": 0,
            "data_uri_format": 0,
            "pure_format": 0,
            "total_length": 0,
        }
        
        if isinstance(content, str):
            stats["total_length"] = len(content)
            stats["lmca_format"] = len(BASE64_PATTERN_LMCA.findall(content))
            stats["mcp_image_format"] = len(BASE64_PATTERN_MCP_IMAGE.findall(content))
            stats["json_format"] = len(BASE64_PATTERN_JSON.findall(content))
            stats["data_uri_format"] = len(BASE64_PATTERN_DATA_URI.findall(content))
            pure_matches = BASE64_PATTERN_PURE.findall(content)
            stats["pure_format"] = len(pure_matches)
        
        elif isinstance(content, dict):
            # 检查 langchain_mcp_adapters 格式 {'type': 'image', 'base64': '...', 'mime_type': '...'}
            if content.get("type") == "image" and "base64" in content:
                base64_data = content.get("base64", "")
                if isinstance(base64_data, str) and len(base64_data) > 50:
                    stats["lmca_format"] = 1
                    stats["total_length"] = len(base64_data)
            # 检查 MCP Image Content 格式
            elif content.get("type") == "image" and "data" in content:
                stats["mcp_image_format"] = 1
                stats["total_length"] = len(content.get("data", ""))
        
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    # langchain_mcp_adapters 格式
                    if item.get("type") == "image" and "base64" in item:
                        base64_data = item.get("base64", "")
                        if isinstance(base64_data, str) and len(base64_data) > 50:
                            stats["lmca_format"] += 1
                            stats["total_length"] += len(base64_data)
                    # MCP Image Content 格式
                    elif item.get("type") == "image" and "data" in item:
                        stats["mcp_image_format"] += 1
                        stats["total_length"] += len(item.get("data", ""))
        
        return stats

    def _replace_base64_in_content(self, content: Any, message_id: str) -> Any:
        """将内容中的 base64 数据保存到本地并替换为文件路径."""
        config = self.config
        
        def replace_lmca(match: re.Match) -> str:
            """处理 langchain_mcp_adapters 格式的 base64 数据"""
            base64_data = match.group(1)
            saved_path = _save_base64_image(base64_data, message_id, config)
            return f"'base64': '[BASE64_IMAGE_SAVED: {saved_path}]'"
        
        def replace_mcp_image(match: re.Match) -> str:
            """处理 MCP Image Content 格式的 base64 数据"""
            base64_data = match.group(1)
            saved_path = _save_base64_image(base64_data, message_id, config)
            return f'"type": "image", "data": "[BASE64_IMAGE_SAVED: {saved_path}]"'

        def replace_json(match: re.Match) -> str:
            base64_data = match.group(1)
            saved_path = _save_base64_image(base64_data, message_id, config)
            return f'"base64Data": "[BASE64_IMAGE_SAVED: {saved_path}]"'

        def replace_data_uri(match: re.Match) -> str:
            image_type = match.group(1)
            base64_data = match.group(2)
            saved_path = _save_base64_image(base64_data, message_id, config)
            return f'[BASE64_IMAGE_SAVED: {saved_path}] (原格式: data:image/{image_type};base64,...)'
        
        def replace_pure(match: re.Match) -> str:
            base64_data = match.group(1)
            if len(base64_data) > 1000:
                saved_path = _save_base64_image(base64_data, message_id, config)
                return f'[BASE64_IMAGE_SAVED: {saved_path}]'
            return match.group(0)

        # 处理字典格式 - langchain_mcp_adapters: {'type': 'image', 'base64': '...', 'mime_type': 'image/png'}
        if isinstance(content, dict):
            if content.get("type") == "image" and "base64" in content:
                base64_data = content.get("base64", "")
                if isinstance(base64_data, str) and len(base64_data) > 50:
                    saved_path = _save_base64_image(base64_data, message_id, config)
                    new_content = content.copy()
                    new_content["base64"] = f"[BASE64_IMAGE_SAVED: {saved_path}]"
                    logs.info(f"[Base64Filter] LMCA Image Content 已替换: {len(base64_data)} chars -> {saved_path}")
                    return new_content
            # MCP Image Content 格式
            if content.get("type") == "image" and "data" in content:
                base64_data = content["data"]
                saved_path = _save_base64_image(base64_data, message_id, config)
                new_content = content.copy()
                new_content["data"] = f"[BASE64_IMAGE_SAVED: {saved_path}]"
                logs.info(f"[Base64Filter] MCP Image Content 已替换: {len(base64_data)} chars -> {saved_path}")
                return new_content
            return content

        if isinstance(content, str):
            original_length = len(content)
            
            # 优先处理 langchain_mcp_adapters 格式（最常见）
            new_content = BASE64_PATTERN_LMCA.sub(replace_lmca, content)
            new_content = BASE64_PATTERN_MCP_IMAGE.sub(replace_mcp_image, new_content)
            new_content = BASE64_PATTERN_JSON.sub(replace_json, new_content)
            new_content = BASE64_PATTERN_DATA_URI.sub(replace_data_uri, new_content)
            
            if len(new_content) > 5000:
                new_content = BASE64_PATTERN_PURE.sub(replace_pure, new_content)
            
            new_length = len(new_content)
            if original_length != new_length:
                reduction = (original_length - new_length) / original_length * 100
                logs.info(f"[Base64Filter] 内容长度: {original_length} -> {new_length} (减少 {reduction:.1f}%)")
            
            return new_content

        if isinstance(content, list):
            new_content = []
            for item in content:
                if isinstance(item, dict):
                    # 检查 langchain_mcp_adapters 格式 {'type': 'image', 'base64': '...', 'mime_type': '...'}
                    if item.get("type") == "image" and "base64" in item:
                        base64_data = item.get("base64", "")
                        if isinstance(base64_data, str) and len(base64_data) > 50:
                            saved_path = _save_base64_image(base64_data, message_id, config)
                            new_item = item.copy()
                            new_item["base64"] = f"[BASE64_IMAGE_SAVED: {saved_path}]"
                            new_content.append(new_item)
                            logs.info(f"[Base64Filter] LMCA Image Content 列表项已替换: {len(base64_data)} chars -> {saved_path}")
                            continue
                    # 检查 MCP Image Content 格式
                    if item.get("type") == "image" and "data" in item:
                        base64_data = item["data"]
                        saved_path = _save_base64_image(base64_data, message_id, config)
                        new_item = item.copy()
                        new_item["data"] = f"[BASE64_IMAGE_SAVED: {saved_path}]"
                        new_content.append(new_item)
                        logs.info(f"[Base64Filter] MCP Image Content 列表项已替换: {len(base64_data)} chars -> {saved_path}")
                        continue
                    if "text" in item:
                        new_item = item.copy()
                        if isinstance(item["text"], str):
                            new_item["text"] = self._replace_base64_in_content(item["text"], message_id)
                        new_content.append(new_item)
                    else:
                        new_content.append(item)
                else:
                    new_content.append(item)
            return new_content

        return content

    def _clean_result(self, result, tool_name: str = "unknown"):
        """
        清理结果数据中的 base64 内容
        
        Args:
            result: 工具返回结果
            tool_name: 工具名称
            
        Returns:
            清理后的结果
        """
        if isinstance(result, ToolMessage):
            original_content = result.content
            logs.info(f"[Base64Filter] 检查 ToolMessage (工具: {result.name if hasattr(result, 'name') else tool_name})")
            
            if isinstance(original_content, str):
                stats = self._get_base64_stats(original_content)
                if stats["lmca_format"] > 0 or stats["mcp_image_format"] > 0 or stats["json_format"] > 0 or stats["data_uri_format"] > 0 or stats["pure_format"] > 0:
                    logs.info(f"  - LMCA格式: {stats['lmca_format']} 个")
                    logs.info(f"  - MCP Image格式: {stats['mcp_image_format']} 个")
                    logs.info(f"  - JSON格式: {stats['json_format']} 个")
                    logs.info(f"  - Data URI格式: {stats['data_uri_format']} 个")
                    logs.info(f"  - 纯Base64格式: {stats['pure_format']} 个")
                    logs.info(f"  - 内容总长度: {stats['total_length']} 字符")
                    
                    message_id = result.tool_call_id or result.id or "unknown"
                    cleaned_content = self._replace_base64_in_content(original_content, message_id)
                    
                    return ToolMessage(
                        content=cleaned_content,
                        name=result.name,
                        tool_call_id=result.tool_call_id,
                        status=result.status,
                        artifact=result.artifact,
                    )
            
            elif isinstance(original_content, list):
                logs.info(f"  - content 是列表，长度: {len(original_content)}")
                cleaned_content = []
                has_base64 = False
                for item in original_content:
                    if isinstance(item, dict):
                        # 检查 langchain_mcp_adapters 格式: {'type': 'image', 'base64': '...', 'mime_type': '...'}
                        if item.get("type") == "image" and "base64" in item:
                            base64_data = item.get("base64", "")
                            if isinstance(base64_data, str) and len(base64_data) > 50:
                                has_base64 = True
                                message_id = result.tool_call_id or result.id or "unknown"
                                saved_path = _save_base64_image(base64_data, message_id, self.config)
                                new_item = item.copy()
                                new_item["base64"] = f"[BASE64_IMAGE_SAVED: {saved_path}]"
                                cleaned_content.append(new_item)
                                logs.info(f"  - LMCA Image Content 发现并替换: {len(base64_data)} chars -> {saved_path}")
                                continue
                        # 检查 MCP Image Content 格式
                        if item.get("type") == "image" and "data" in item:
                            has_base64 = True
                            base64_data = item["data"]
                            message_id = result.tool_call_id or result.id or "unknown"
                            saved_path = _save_base64_image(base64_data, message_id, self.config)
                            new_item = item.copy()
                            new_item["data"] = f"[BASE64_IMAGE_SAVED: {saved_path}]"
                            cleaned_content.append(new_item)
                            logs.info(f"  - MCP Image Content 发现并替换: {len(base64_data)} chars")
                            continue
                        if 'text' in item:
                            original_text = item['text']
                            stats = self._get_base64_stats(original_text)
                            if stats["lmca_format"] > 0 or stats["mcp_image_format"] > 0 or stats["json_format"] > 0 or stats["data_uri_format"] > 0 or stats["pure_format"] > 0:
                                has_base64 = True
                                logs.info(f"  - 列表项中发现 base64:")
                                logs.info(f"    LMCA: {stats['lmca_format']}, MCP: {stats['mcp_image_format']}, JSON: {stats['json_format']}, Data URI: {stats['data_uri_format']}, 纯Base64: {stats['pure_format']}")
                                message_id = result.tool_call_id or result.id or "unknown"
                                cleaned_text = self._replace_base64_in_content(original_text, message_id)
                                cleaned_content.append({**item, 'text': cleaned_text})
                            else:
                                cleaned_content.append(item)
                        else:
                            cleaned_content.append(item)
                
                if has_base64:
                    return ToolMessage(
                        content=cleaned_content,
                        name=result.name,
                        tool_call_id=result.tool_call_id,
                        status=result.status,
                        artifact=result.artifact,
                    )
            
            return result
        
        if isinstance(result, str):
            stats = self._get_base64_stats(result)
            if stats["lmca_format"] > 0 or stats["mcp_image_format"] > 0 or stats["json_format"] > 0 or stats["data_uri_format"] > 0 or stats["pure_format"] > 0:
                logs.info(f"[Base64Filter] 字符串结果中发现 base64:")
                logs.info(f"  - LMCA格式: {stats['lmca_format']} 个")
                logs.info(f"  - MCP Image格式: {stats['mcp_image_format']} 个")
                logs.info(f"  - JSON格式: {stats['json_format']} 个")
                logs.info(f"  - Data URI格式: {stats['data_uri_format']} 个")
                logs.info(f"  - 纯Base64格式: {stats['pure_format']} 个")
                return self._replace_base64_in_content(result, "str_result")
            return result
        
        elif isinstance(result, list):
            return [self._clean_result(item, tool_name) for item in result]
        
        elif isinstance(result, dict):
            return {k: self._clean_result(v, tool_name) for k, v in result.items()}
        
        return result

    async def awrap_tool_call(self, request, handler):
        """
        异步拦截工具执行，在工具返回后立即处理 base64 数据
        
        这是关键：使用 awrap_tool_call 而不是 before_model
        - 工具返回后立即执行，此时数据还没进入消息历史
        - 确保 base64 在存入消息历史之前就被替换
        """
        # 获取工具信息
        tool_call = getattr(request, 'tool_call', None)
        if tool_call:
            tool_name = tool_call.get('name', 'unknown')
            tool_id = tool_call.get('id', 'unknown')
        else:
            tool_name = 'unknown'
            tool_id = 'unknown'
        
        # 🚀 P0-004: 跳过内部自动注入的工具调用
        if tool_call and isinstance(tool_call, dict) and tool_call.get('_internal'):
            return await handler(request)
        
        # 特别关注截图工具
        is_screenshot_tool = 'screenshot' in tool_name.lower() or 'browser' in tool_name.lower()
        
        logs.info("=" * 80)
        logs.info(f"[Base64Filter] awrap_tool_call 被调用")
        logs.info(f"  - 工具名称: {tool_name}")
        logs.info(f"  - 工具 ID: {tool_id}")
        logs.info(f"  - 可能包含图片: {is_screenshot_tool}")
        logs.info("=" * 80)
        
        # 调用原始工具
        result = await handler(request)
        
        # 调试日志：显示原始结果
        logs.info(f"[Base64Filter] 工具返回结果:")
        logs.info(f"  - 结果类型: {type(result).__name__}")
        if isinstance(result, str):
            logs.info(f"  - 字符串长度: {len(result)}")
        elif isinstance(result, list):
            logs.info(f"  - 列表长度: {len(result)}")
        elif isinstance(result, ToolMessage):
            logs.info(f"  - ToolMessage, name: {result.name}")
            if isinstance(result.content, str):
                logs.info(f"  - content 字符串长度: {len(result.content)}")
            elif isinstance(result.content, list):
                logs.info(f"  - content 列表长度: {len(result.content)}")

        # 清理结果中的 base64
        cleaned_result = self._clean_result(result, tool_name)
        
        logs.info("-" * 40)
        logs.info(f"[Base64Filter] 处理完成")
        logs.info("=" * 80)
        
        return cleaned_result
