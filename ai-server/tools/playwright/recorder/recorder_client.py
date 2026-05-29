"""
Playwright Codegen Recorder Client

Python 客户端，用于连接 Node.js 录制服务，获取 Codegen 生成的高质量代码。

使用方式：
    from tools.playwright.recorder.recorder_client import CodegenRecorder
    
    async with CodegenRecorder() as recorder:
        # 启动录制
        await recorder.start(url="https://example.com")
        
        # 执行操作（会被 Codegen 录制）
        await recorder.click("button[type='submit']")
        await recorder.fill("#username", "testuser")
        
        # 获取 Codegen 生成的代码
        code = await recorder.get_codegen_code()
        
        # 停止录制
        await recorder.stop()
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import websockets

from tools.debug.readlog import logs


class CodegenRecorder:
    """
    Codegen 录制器客户端
    
    通过 WebSocket 连接到 Node.js 录制服务，
    执行操作并获取 Codegen 生成的高质量代码。
    """
    
    def __init__(
        self,
        port: int = 9223,
        auto_start_server: bool = True,
        server_script: Optional[str] = None
    ):
        """
        初始化录制器
        
        Args:
            port: WebSocket 服务端口
            auto_start_server: 是否自动启动 Node.js 服务
            server_script: 服务脚本路径（默认自动查找）
        """
        self.port = port
        self.auto_start_server = auto_start_server
        self.server_script = server_script or self._find_server_script()
        
        self.ws = None
        self.server_process = None
        self._started = False
    
    def _find_server_script(self) -> str:
        """查找服务脚本路径"""
        current_dir = Path(__file__).parent
        return str(current_dir / "recorder-server.js")
    
    async def _start_server(self):
        """启动 Node.js 录制服务"""
        if not Path(self.server_script).exists():
            raise FileNotFoundError(f"Recorder server script not found: {self.server_script}")
        
        # 检查 node_modules 是否存在
        server_dir = Path(self.server_script).parent
        node_modules = server_dir / "node_modules"
        
        if not node_modules.exists():
            logs.info(f"[CodegenRecorder] Installing dependencies...")
            install_process = await asyncio.create_subprocess_exec(
                "npm", "install",
                cwd=str(server_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await install_process.wait()
            logs.info(f"[CodegenRecorder] Dependencies installed")
        
        # 启动服务
        logs.info(f"[CodegenRecorder] Starting server on port {self.port}...")
        
        env = {"RECORDER_PORT": str(self.port)}
        
        self.server_process = await asyncio.create_subprocess_exec(
            "node", self.server_script,
            cwd=str(server_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**dict(__import__('os').environ), **env}
        )
        
        # 等待服务启动
        await asyncio.sleep(2)
        
        logs.info(f"[CodegenRecorder] Server started")
    
    async def _connect(self):
        """连接到 WebSocket 服务"""
        max_retries = 10
        retry_delay = 0.5
        
        for i in range(max_retries):
            try:
                self.ws = await websockets.connect(
                    f"ws://localhost:{self.port}",
                    ping_interval=None
                )
                logs.info(f"[CodegenRecorder] Connected to server")
                return
            except Exception as e:
                if i < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    raise ConnectionError(f"Failed to connect to recorder server: {e}")
    
    async def _send_command(self, action: str, params: Dict = None) -> Dict:
        """发送命令到服务"""
        if not self.ws:
            raise ConnectionError("Not connected to server")
        
        message = {"action": action, "params": params or {}}
        await self.ws.send(json.dumps(message))
        
        response = await self.ws.recv()
        return json.loads(response)
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        if self.auto_start_server:
            await self._start_server()
        
        await self._connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.ws:
            await self.ws.close()
        
        if self.server_process:
            self.server_process.terminate()
            await self.server_process.wait()
    
    async def start(
        self,
        url: str = "about:blank",
        headless: bool = False,
        viewport: Dict = None,
        storage_state: str = None,
        output_file: str = None
    ) -> Dict:
        """
        启动录制会话
        
        Args:
            url: 初始 URL
            headless: 是否无头模式
            viewport: 视口大小
            storage_state: 登录态文件路径
            output_file: 代码输出文件路径
            
        Returns:
            启动结果
        """
        params = {
            "url": url,
            "headless": headless,
            "viewport": viewport or {"width": 1920, "height": 1080}
        }
        
        if storage_state:
            params["storageState"] = storage_state
        
        if output_file:
            params["outputFile"] = output_file
        
        result = await self._send_command("start", params)
        
        if result.get("success"):
            self._started = True
            logs.info(f"[CodegenRecorder] Recording started: {url}")
        else:
            logs.error(f"[CodegenRecorder] Failed to start: {result.get('error')}")
        
        return result
    
    async def navigate(self, url: str) -> Dict:
        """导航到 URL"""
        result = await self._send_command("navigate", {"url": url})
        
        if result.get("success"):
            logs.info(f"[CodegenRecorder] Navigated to: {url}")
        
        return result
    
    async def click(self, selector: str = None, coordinates: Dict = None) -> Dict:
        """
        点击元素
        
        Args:
            selector: CSS 选择器或 Playwright 选择器
            coordinates: 坐标 {"x": 100, "y": 200}
        """
        params = {}
        if selector:
            params["selector"] = selector
        if coordinates:
            params["coordinates"] = coordinates
        
        result = await self._send_command("click", params)
        
        if result.get("success"):
            target = selector or f"({coordinates['x']}, {coordinates['y']})"
            logs.info(f"[CodegenRecorder] Clicked: {target}")
        
        return result
    
    async def fill(self, selector: str, value: str) -> Dict:
        """填充输入框"""
        result = await self._send_command("fill", {
            "selector": selector,
            "value": value
        })
        
        if result.get("success"):
            logs.info(f"[CodegenRecorder] Filled: {selector}")
        
        return result
    
    async def select(self, selector: str, value: str) -> Dict:
        """下拉选择"""
        result = await self._send_command("select", {
            "selector": selector,
            "value": value
        })
        
        if result.get("success"):
            logs.info(f"[CodegenRecorder] Selected: {selector} = {value}")
        
        return result
    
    async def hover(self, selector: str) -> Dict:
        """悬停"""
        result = await self._send_command("hover", {"selector": selector})
        
        if result.get("success"):
            logs.info(f"[CodegenRecorder] Hovered: {selector}")
        
        return result
    
    async def press(self, key: str) -> Dict:
        """按键"""
        result = await self._send_command("press", {"key": key})
        
        if result.get("success"):
            logs.info(f"[CodegenRecorder] Pressed: {key}")
        
        return result
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> Dict:
        """等待选择器出现"""
        result = await self._send_command("waitForSelector", {
            "selector": selector,
            "timeout": timeout
        })
        
        return result
    
    async def wait_for_timeout(self, timeout: int) -> Dict:
        """等待时间"""
        result = await self._send_command("waitForTimeout", {"timeout": timeout})
        return result
    
    async def screenshot(self, path: str = None) -> Dict:
        """
        截图
        
        Args:
            path: 保存路径（可选）
            
        Returns:
            包含 base64 图片数据的结果
        """
        params = {}
        if path:
            params["path"] = path
        
        return await self._send_command("screenshot", params)
    
    async def get_recorded_actions(self) -> List[Dict]:
        """获取录制的操作列表"""
        result = await self._send_command("getRecordedCode")
        return result.get("actions", [])
    
    async def get_codegen_code(self) -> str:
        """
        获取 Codegen 生成的代码
        
        这是关键方法！返回 Codegen 分析 DOM 后生成的高质量代码。
        """
        result = await self._send_command("getCodegenCode")
        
        if result.get("success"):
            code = result.get("code", "")
            source = result.get("source", "unknown")
            
            if source == "codegen_file":
                logs.info(f"[CodegenRecorder] ✅ Got Codegen-generated code")
            else:
                logs.warning(f"[CodegenRecorder] ⚠️ Using fallback code from: {source}")
            
            return code
        else:
            raise Exception(f"Failed to get code: {result.get('error')}")
    
    async def stop(self) -> Dict:
        """停止录制"""
        result = await self._send_command("stop")
        
        if result.get("success"):
            self._started = False
            logs.info(f"[CodegenRecorder] Recording stopped, actions: {result.get('actionsCount', 0)}")
        
        return result
    
    async def get_status(self) -> Dict:
        """获取当前状态"""
        return await self._send_command("getStatus")


# 同步版本（简化使用）
class CodegenRecorderSync:
    """
    Codegen 录制器同步版本
    
    使用方式：
        from tools.playwright.recorder.recorder_client import CodegenRecorderSync
        
        recorder = CodegenRecorderSync()
        recorder.start(url="https://example.com")
        recorder.click("button[type='submit']")
        code = recorder.get_codegen_code()
        recorder.stop()
    """
    
    def __init__(self, port: int = 9223):
        self.port = port
        self._async_recorder = CodegenRecorder(port=port)
        self._loop = None
    
    def _run_async(self, coro):
        """在事件循环中运行异步函数"""
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(coro)
    
    def __enter__(self):
        self._run_async(self._async_recorder.__aenter__())
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._run_async(self._async_recorder.__aexit__(exc_type, exc_val, exc_tb))
    
    def start(self, **kwargs) -> Dict:
        return self._run_async(self._async_recorder.start(**kwargs))
    
    def navigate(self, url: str) -> Dict:
        return self._run_async(self._async_recorder.navigate(url))
    
    def click(self, selector: str = None, coordinates: Dict = None) -> Dict:
        return self._run_async(self._async_recorder.click(selector, coordinates))
    
    def fill(self, selector: str, value: str) -> Dict:
        return self._run_async(self._async_recorder.fill(selector, value))
    
    def get_codegen_code(self) -> str:
        return self._run_async(self._async_recorder.get_codegen_code())
    
    def stop(self) -> Dict:
        return self._run_async(self._async_recorder.stop())


# 命令行测试
if __name__ == "__main__":
    import sys
    
    async def test():
        async with CodegenRecorder() as recorder:
            # 启动录制
            result = await recorder.start(
                url="https://example.com",
                headless=False
            )
            print(f"Start result: {result}")
            
            # 等待用户操作
            print("\n请在浏览器中手动操作...")
            await asyncio.sleep(10)
            
            # 获取代码
            code = await recorder.get_codegen_code()
            print(f"\n生成的代码:\n{code}")
            
            # 停止
            await recorder.stop()
    
    asyncio.run(test())
