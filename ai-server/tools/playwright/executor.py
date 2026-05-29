"""Playwright脚本执行工具."""

import json
import os
import platform
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.tools import StructuredTool, BaseTool

from tools.debug.readlog import logs
from tools.playwright.config import UIAutomationConfig, DEFAULT_CONFIG
from tools.playwright.script_index import get_index_manager


def _resolve_virtual_path(virtual_path: str, workspace_root: str) -> Path:
    """将虚拟路径解析为实际文件系统路径."""
    relative_path = virtual_path.lstrip("/")
    return Path(workspace_root).resolve() / relative_path


def _to_virtual_path(results_dir: str, result_name: str) -> str:
    """生成虚拟路径."""
    if not results_dir.startswith("/"):
        results_dir = "/" + results_dir
    results_dir = results_dir.rstrip("/")
    return f"{results_dir}/{result_name}"


def create_playwright_executor_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """创建Playwright脚本执行工具.

    Args:
        config: UI自动化配置

    Returns:
        Playwright执行工具
    """
    cfg = config or DEFAULT_CONFIG

    def run_playwright_script(
        script_path: str,
        browser: str = "",
        headless: bool | None = None,
        reporter: str = "html,json",
        auth_state: str = "",
        project: str = "",
    ) -> str:
        """运行Playwright测试脚本."""
        # 默认加载 bnp_auth.json 登录态
        default_auth_state = "auth_state/bnp_auth.json"
        default_auth_path = Path(cfg.workspace_root) / "playwright_scripts" / default_auth_state
        
        if not auth_state and default_auth_path.exists():
            auth_state = default_auth_state
            logs.info(f"🔑 自动加载默认登录态: {auth_state}")
        
        # 🚀 启动日志：区分 MCP 浏览器 vs 脚本执行浏览器
        logs.info("=" * 60)
        logs.info("🚀 [run_playwright_script] 启动浏览器（脚本执行模式）")
        logs.info("=" * 60)
        logs.info(f"   脚本路径: {script_path}")
        logs.info(f"   登录态文件: {auth_state if auth_state else '未指定'}")
        logs.info(f"   无头模式: {headless if headless is not None else '默认'}")
        logs.info(f"   项目/浏览器: {project if project else browser if browser else '默认'}")
        logs.info("=" * 60)
        """执行Playwright测试脚本.

        Args:
            script_path: Playwright脚本虚拟路径（以 / 开头，如 /playwright_scripts/tests/test.spec.ts）
            browser: 浏览器类型（chromium/firefox/webkit），默认使用配置中的浏览器
            headless: 是否无头模式，默认使用配置中的设置
            reporter: 报告格式（html/json/list/dot/line），可以组合使用，用逗号分隔
            auth_state: 认证状态文件路径（如 auth_state/bnp_auth.json），用于加载已保存的登录态
            project: 项目名称（如 chromium-auth），用于指定带登录态的项目配置

        Returns:
            测试结果（JSON格式）
        """
        # 将虚拟路径解析为实际路径
        actual_script_path = _resolve_virtual_path(script_path, cfg.workspace_root)

        if not actual_script_path.exists():
            # 智能查找：尝试在 tests 目录中查找相似名称的脚本
            tests_dir = Path(cfg.workspace_root) / "playwright_scripts" / "tests"
            script_name = Path(script_path).stem  # 获取脚本名（不含扩展名）
            
            # 查找所有可用的脚本
            available_scripts = []
            if tests_dir.exists():
                available_scripts = [f.name for f in tests_dir.glob("*.spec.ts")]
            
            # 尝试模糊匹配
            matched_script = None
            for script_file in available_scripts:
                # 精确匹配（去掉 .spec.ts 后缀）
                if script_file.replace(".spec.ts", "") == script_name:
                    matched_script = script_file
                    break
                # 模糊匹配（包含关系）
                if script_name in script_file or script_file.replace(".spec.ts", "") in script_name:
                    matched_script = script_file
            
            if matched_script:
                # 找到匹配的脚本，自动修正路径
                actual_script_path = tests_dir / matched_script
            else:
                # 没找到，返回错误和可用脚本列表
                return json.dumps({
                    "success": False,
                    "error": f"脚本文件不存在: {script_path}",
                    "actual_path": str(actual_script_path),
                    "available_scripts": available_scripts,
                    "hint": f"可用的脚本: {', '.join(available_scripts[:10])}" if available_scripts else "tests 目录为空"
                }, ensure_ascii=False, indent=2)

        # 确定 Playwright 项目的工作目录
        # 如果脚本在 playwright_scripts 目录下，使用该目录作为工作目录
        playwright_cwd = Path(cfg.workspace_root).resolve()
        if "playwright_scripts" in actual_script_path.parts:
            # 找到 playwright_scripts 目录
            for i, part in enumerate(actual_script_path.parts):
                if part == "playwright_scripts":
                    playwright_cwd = Path(*actual_script_path.parts[:i+1])
                    break

        # 确保结果目录存在
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_id = str(uuid.uuid4())[:8]
        
        # JSON结果文件
        json_result_name = f"result_{timestamp}_{result_id}.json"
        virtual_json_path = _to_virtual_path(cfg.results_dir, json_result_name)
        actual_json_path = _resolve_virtual_path(virtual_json_path, cfg.workspace_root)
        actual_json_path.parent.mkdir(parents=True, exist_ok=True)

        # HTML报告目录
        html_report_name = f"report_{timestamp}_{result_id}"
        virtual_html_path = _to_virtual_path(cfg.reports_dir, html_report_name)
        actual_html_path = _resolve_virtual_path(virtual_html_path, cfg.workspace_root)
        actual_html_path.mkdir(parents=True, exist_ok=True)

        # 构建Playwright命令
        # 在 Windows 上，如果使用 npx，需要使用 npx.cmd
        playwright_binary = cfg.playwright_binary
        if platform.system() == "Windows" and playwright_binary == "npx":
            playwright_binary = "npx.cmd"

        cmd = [playwright_binary] + cfg.playwright_args
        
        # 添加超时参数
        cmd.extend(["--timeout", str(cfg.default_timeout)])
        
        # 添加项目/浏览器参数
        # 如果指定了 project（如 chromium-auth），优先使用
        # 否则使用 browser 参数
        browser_type = browser or cfg.default_browser
        if project:
            cmd.extend(["--project", project])
        else:
            cmd.extend(["--project", browser_type])
        
        # 添加headless参数
        is_headless = headless if headless is not None else cfg.default_headless
        if not is_headless:
            cmd.append("--headed")
        
        # 准备环境变量用于 reporter 输出路径和认证状态
        env = os.environ.copy()
        
        # 设置认证状态环境变量（用于加载已保存的登录态）
        if auth_state:
            env["PLAYWRIGHT_AUTH_STATE"] = auth_state

        # 添加reporter参数
        # 使用环境变量设置输出路径（Playwright 官方支持的方式）
        reporters = reporter.split(",")
        for rep in reporters:
            rep = rep.strip()
            if rep == "html":
                # HTML reporter 使用环境变量 PLAYWRIGHT_HTML_OUTPUT_FOLDER
                try:
                    relative_html_path = os.path.relpath(actual_html_path, playwright_cwd)
                    relative_html_path = relative_html_path.replace("\\", "/")
                    env["PLAYWRIGHT_HTML_OUTPUT_FOLDER"] = relative_html_path
                except ValueError:
                    abs_path = str(actual_html_path).replace("\\", "/")
                    env["PLAYWRIGHT_HTML_OUTPUT_FOLDER"] = abs_path
                cmd.extend(["--reporter", "html"])
            elif rep == "json":
                # JSON reporter 使用环境变量 PLAYWRIGHT_JSON_OUTPUT_FILE
                try:
                    relative_json_path = os.path.relpath(actual_json_path, playwright_cwd)
                    relative_json_path = relative_json_path.replace("\\", "/")
                    env["PLAYWRIGHT_JSON_OUTPUT_FILE"] = relative_json_path
                except ValueError:
                    abs_path = str(actual_json_path).replace("\\", "/")
                    env["PLAYWRIGHT_JSON_OUTPUT_FILE"] = abs_path
                cmd.extend(["--reporter", "json"])
            else:
                cmd.extend(["--reporter", rep])

        # 添加脚本路径（相对于工作目录）
        try:
            relative_script_path = actual_script_path.relative_to(playwright_cwd)
            # 转换为正斜杠格式（Playwright 在 Windows 上也接受）
            script_path_str = str(relative_script_path).replace("\\", "/")
            cmd.append(script_path_str)
        except ValueError:
            # 如果无法计算相对路径，使用绝对路径并转换为正斜杠
            script_path_str = str(actual_script_path).replace("\\", "/")
            cmd.append(script_path_str)

        try:
            # 执行Playwright（使用 playwright_cwd 作为工作目录）
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',  # 在 Windows 上使用 UTF-8 编码
                errors='replace',  # 遇到无法解码的字符时替换
                timeout=600,  # 10分钟超时
                cwd=str(playwright_cwd),
                env=env,  # 传递环境变量（包含 PLAYWRIGHT_JSON_OUTPUT_FILE）
            )

            # 解析结果
            output = {
                "success": result.returncode == 0,
                "script_path": script_path,
                "browser": browser_type,
                "project": project if project else None,
                "auth_state": auth_state if auth_state else None,
                "headless": is_headless,
                "json_result": virtual_json_path if actual_json_path.exists() else None,
                "html_report": virtual_html_path if actual_html_path.exists() else None,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }

            # 如果有JSON结果文件，读取并解析
            if actual_json_path.exists():
                try:
                    with open(actual_json_path, "r", encoding="utf-8") as f:
                        test_results = json.load(f)
                        output["summary"] = _extract_summary(test_results)
                except Exception as e:
                    output["parse_error"] = str(e)
            
            # 更新脚本执行统计
            try:
                # 从脚本路径提取名称
                script_name = actual_script_path.stem
                if script_name.endswith('.spec'):
                    script_name = script_name[:-5]
                
                index_manager = get_index_manager()
                index_manager.update_execution_stats(script_name, result.returncode == 0)
            except Exception as e:
                # 统计更新失败不影响返回结果
                pass

            return json.dumps(output, ensure_ascii=False, indent=2)

        except subprocess.TimeoutExpired:
            return json.dumps({
                "success": False,
                "error": "Playwright执行超时（>10分钟）",
                "script_path": script_path,
            }, ensure_ascii=False, indent=2)
        except FileNotFoundError:
            return json.dumps({
                "success": False,
                "error": f"Playwright未安装或路径错误: {cfg.playwright_binary}",
                "script_path": script_path,
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": str(e),
                "script_path": script_path,
            }, ensure_ascii=False, indent=2)

    return StructuredTool.from_function(
        name="run_playwright_script",
        func=run_playwright_script,
        description="""执行Playwright测试脚本。
参数：
- script_path: 脚本虚拟路径（必需，如 /playwright_scripts/test.spec.ts）
- browser: 浏览器类型（可选，chromium/firefox/webkit，默认chromium）
- headless: 是否无头模式（可选，默认True）
- reporter: 报告格式（可选，默认 'html,json'，可选 html/json/list/dot/line）
- auth_state: 认证状态文件路径（可选，相对于 playwright_scripts 目录，如 auth_state/bnp_auth.json）
- project: 项目名称（可选，如 chromium-auth，用于指定带登录态的项目配置）

认证状态使用：
1. 先运行登录脚本保存登录态（脚本中使用 context.storageState() 保存）
2. 后续脚本设置 auth_state 参数加载登录态，跳过登录步骤

返回JSON格式的测试结果，包括成功状态、结果文件路径、测试摘要等。""",
    )


def _extract_summary(test_results: dict[str, Any]) -> dict[str, Any]:
    """从Playwright JSON结果中提取摘要信息."""
    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
    }
    
    # Playwright JSON格式解析
    if "suites" in test_results:
        for suite in test_results.get("suites", []):
            _count_tests(suite, summary)
    
    if "stats" in test_results:
        stats = test_results["stats"]
        summary.update({
            "total": stats.get("expected", 0) + stats.get("unexpected", 0) + stats.get("skipped", 0),
            "passed": stats.get("expected", 0),
            "failed": stats.get("unexpected", 0),
            "skipped": stats.get("skipped", 0),
            "duration": stats.get("duration", 0),
        })
    
    return summary


def _count_tests(suite: dict, summary: dict) -> None:
    """递归统计测试用例."""
    for spec in suite.get("specs", []):
        for test in spec.get("tests", []):
            summary["total"] += 1
            for result in test.get("results", []):
                status = result.get("status", "")
                if status == "passed":
                    summary["passed"] += 1
                elif status == "failed":
                    summary["failed"] += 1
                elif status == "skipped":
                    summary["skipped"] += 1
                summary["duration"] += result.get("duration", 0)
    
    # 递归处理子suite
    for sub_suite in suite.get("suites", []):
        _count_tests(sub_suite, summary)
