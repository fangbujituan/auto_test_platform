"""
UI引擎 - Playwright报告解析工具

解析Playwright测试结果，提供详细的测试报告。

作者: yandc
创建时间: 2026-05-30
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool, BaseTool

from app.engine.ui_engine.config import UIAutomationConfig, DEFAULT_CONFIG


def _resolve_virtual_path(virtual_path: str, workspace_root: str) -> Path:
    """将虚拟路径解析为实际文件系统路径."""
    relative_path = virtual_path.lstrip("/")
    return Path(workspace_root).resolve() / relative_path


def create_result_parser_tool(config: UIAutomationConfig | None = None) -> BaseTool:
    """创建Playwright结果解析工具.

    Args:
        config: UI自动化配置

    Returns:
        结果解析工具
    """
    cfg = config or DEFAULT_CONFIG

    def parse_test_results(
        result_path: str,
        format: str = "summary",
        include_details: bool = False
    ) -> str:
        """解析Playwright测试结果文件.

        Args:
            result_path: 结果文件虚拟路径（如 /playwright_results/result_20250101_120000_abc123.json）
            format: 输出格式，可选：summary（摘要）、detailed（详细）、html（HTML格式）
            include_details: 是否包含详细测试用例信息（仅当format为summary或detailed时有效）

        Returns:
            解析后的结果（JSON格式）
        """
        # 将虚拟路径解析为实际路径
        actual_result_path = _resolve_virtual_path(result_path, cfg.workspace_root)

        if not actual_result_path.exists():
            # 尝试查找最近的结果文件
            results_dir = actual_result_path.parent
            if results_dir.exists():
                # 查找所有JSON结果文件
                result_files = list(results_dir.glob("*.json"))
                if result_files:
                    # 按修改时间排序，取最新的
                    latest_file = max(result_files, key=lambda f: f.stat().st_mtime)
                    actual_result_path = latest_file
                else:
                    return json.dumps({
                        "success": False,
                        "error": f"结果文件不存在: {result_path}",
                        "hint": f"结果目录为空: {results_dir}"
                    }, ensure_ascii=False, indent=2)
            else:
                return json.dumps({
                    "success": False,
                    "error": f"结果文件不存在: {result_path}",
                    "actual_path": str(actual_result_path)
                }, ensure_ascii=False, indent=2)

        try:
            with open(actual_result_path, "r", encoding="utf-8") as f:
                test_results = json.load(f)
        except Exception as e:
            return json.dumps({
                "success": False,
                "error": f"无法读取结果文件: {e}",
                "path": str(actual_result_path)
            }, ensure_ascii=False, indent=2)

        # 解析结果
        parsed = _parse_playwright_results(test_results, format, include_details)
        parsed["result_file"] = result_path
        parsed["actual_path"] = str(actual_result_path)

        return json.dumps(parsed, ensure_ascii=False, indent=2)

    return StructuredTool.from_function(
        name="parse_playwright_results",
        func=parse_test_results,
        description="""解析Playwright测试结果文件。
        
参数：
- result_path: 结果文件虚拟路径（必需，如 /playwright_results/result_20250101_120000_abc123.json）
- format: 输出格式（可选，默认 'summary'，可选：summary/detailed/html）
- include_details: 是否包含详细测试用例信息（可选，默认 False）

返回JSON格式的解析结果，包括测试摘要、通过率、失败详情等。""",
    )


def _parse_playwright_results(
    test_results: Dict[str, Any],
    format: str = "summary",
    include_details: bool = False
) -> Dict[str, Any]:
    """解析Playwright测试结果."""
    
    # 提取基本信息
    parsed = {
        "success": True,
        "format": format,
        "summary": _extract_summary(test_results),
        "suites": [],
        "failed_tests": [],
        "slow_tests": [],
        "warnings": []
    }
    
    # 提取测试套件信息
    if "suites" in test_results:
        for suite in test_results.get("suites", []):
            suite_info = _parse_suite(suite)
            if suite_info:
                parsed["suites"].append(suite_info)
    
    # 提取失败测试
    if include_details or format == "detailed":
        parsed["failed_tests"] = _extract_failed_tests(test_results)
        parsed["slow_tests"] = _extract_slow_tests(test_results)
    
    # 提取警告
    parsed["warnings"] = _extract_warnings(test_results)
    
    # 根据格式调整输出
    if format == "html":
        parsed["html"] = _generate_html_report(parsed)
    
    return parsed


def _extract_summary(test_results: Dict[str, Any]) -> Dict[str, Any]:
    """提取摘要信息."""
    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "success_rate": 0.0
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
    
    # 计算通过率
    if summary["total"] > 0:
        summary["success_rate"] = summary["passed"] / summary["total"]
    
    return summary


def _count_tests(suite: Dict, summary: Dict) -> None:
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


def _parse_suite(suite: Dict[str, Any]) -> Dict[str, Any]:
    """解析测试套件."""
    if not suite.get("specs"):
        return None
    
    suite_info = {
        "title": suite.get("title", "Untitled Suite"),
        "file": suite.get("file", ""),
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "specs": []
    }
    
    # 解析specs
    for spec in suite.get("specs", []):
        spec_info = _parse_spec(spec)
        if spec_info:
            suite_info["specs"].append(spec_info)
            
            # 更新套件统计
            suite_info["total"] += spec_info["total"]
            suite_info["passed"] += spec_info["passed"]
            suite_info["failed"] += spec_info["failed"]
            suite_info["skipped"] += spec_info["skipped"]
            suite_info["duration"] += spec_info["duration"]
    
    return suite_info


def _parse_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """解析测试spec."""
    spec_info = {
        "title": spec.get("title", "Untitled Spec"),
        "file": spec.get("file", ""),
        "line": spec.get("line", 0),
        "column": spec.get("column", 0),
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "tests": []
    }
    
    # 解析tests
    for test in spec.get("tests", []):
        test_info = _parse_test(test)
        if test_info:
            spec_info["tests"].append(test_info)
            
            # 更新spec统计
            spec_info["total"] += 1
            if test_info["status"] == "passed":
                spec_info["passed"] += 1
            elif test_info["status"] == "failed":
                spec_info["failed"] += 1
            elif test_info["status"] == "skipped":
                spec_info["skipped"] += 1
            spec_info["duration"] += test_info["duration"]
    
    return spec_info


def _parse_test(test: Dict[str, Any]) -> Dict[str, Any]:
    """解析单个测试."""
    if not test.get("results"):
        return None
    
    # 取第一个结果（通常只有一个）
    result = test["results"][0] if test["results"] else {}
    
    test_info = {
        "title": test.get("title", "Untitled Test"),
        "status": result.get("status", "unknown"),
        "duration": result.get("duration", 0),
        "retries": result.get("retry", 0),
        "errors": [],
        "steps": []
    }
    
    # 提取错误信息
    if "errors" in result:
        for error in result.get("errors", []):
            error_info = {
                "message": error.get("message", ""),
                "stack": error.get("stack", "")
            }
            test_info["errors"].append(error_info)
    
    # 提取步骤信息
    if "steps" in result:
        for step in result.get("steps", []):
            step_info = {
                "title": step.get("title", ""),
                "duration": step.get("duration", 0),
                "error": step.get("error", "")
            }
            test_info["steps"].append(step_info)
    
    return test_info


def _extract_failed_tests(test_results: Dict[str, Any]) -> List[Dict[str, Any]]:
    """提取失败的测试."""
    failed_tests = []
    
    def _collect_failed(suite: Dict):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    if result.get("status") == "failed":
                        failed_test = {
                            "suite": suite.get("title", ""),
                            "spec": spec.get("title", ""),
                            "test": test.get("title", ""),
                            "errors": result.get("errors", []),
                            "duration": result.get("duration", 0)
                        }
                        failed_tests.append(failed_test)
        
        for sub_suite in suite.get("suites", []):
            _collect_failed(sub_suite)
    
    if "suites" in test_results:
        for suite in test_results.get("suites", []):
            _collect_failed(suite)
    
    return failed_tests


def _extract_slow_tests(test_results: Dict[str, Any], threshold_ms: int = 5000) -> List[Dict[str, Any]]:
    """提取执行缓慢的测试."""
    slow_tests = []
    
    def _collect_slow(suite: Dict):
        for spec in suite.get("specs", []):
            for test in spec.get("tests", []):
                for result in test.get("results", []):
                    duration = result.get("duration", 0)
                    if duration > threshold_ms:
                        slow_test = {
                            "suite": suite.get("title", ""),
                            "spec": spec.get("title", ""),
                            "test": test.get("title", ""),
                            "duration_ms": duration,
                            "status": result.get("status", "")
                        }
                        slow_tests.append(slow_test)
        
        for sub_suite in suite.get("suites", []):
            _collect_slow(sub_suite)
    
    if "suites" in test_results:
        for suite in test_results.get("suites", []):
            _collect_slow(suite)
    
    # 按执行时间降序排序
    slow_tests.sort(key=lambda x: x["duration_ms"], reverse=True)
    
    return slow_tests[:10]  # 返回最慢的10个测试


def _extract_warnings(test_results: Dict[str, Any]) -> List[str]:
    """提取警告信息."""
    warnings = []
    
    # 检查是否有超时测试
    if "suites" in test_results:
        for suite in test_results.get("suites", []):
            for spec in suite.get("specs", []):
                for test in spec.get("tests", []):
                    for result in test.get("results", []):
                        # 检查超时
                        if result.get("status") == "timedOut":
                            warnings.append(f"测试超时: {test.get('title')}")
                        
                        # 检查重试次数过多
                        if result.get("retry", 0) > 2:
                            warnings.append(f"重试次数过多({result.get('retry')}次): {test.get('title')}")
    
    return warnings


def _generate_html_report(parsed: Dict[str, Any]) -> str:
    """生成HTML格式的报告."""
    summary = parsed["summary"]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Playwright Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .summary {{ background: #f5f5f5; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
            .metric {{ display: inline-block; margin-right: 30px; }}
            .metric-value {{ font-size: 24px; font-weight: bold; }}
            .metric-label {{ font-size: 14px; color: #666; }}
            .passed {{ color: #28a745; }}
            .failed {{ color: #dc3545; }}
            .skipped {{ color: #ffc107; }}
            .suite {{ margin-bottom: 20px; border: 1px solid #ddd; padding: 15px; border-radius: 5px; }}
            .suite-title {{ font-size: 18px; font-weight: bold; margin-bottom: 10px; }}
            .spec {{ margin-left: 20px; margin-bottom: 10px; }}
            .test {{ margin-left: 40px; padding: 5px; }}
            .test-failed {{ background: #f8d7da; }}
            .test-slow {{ background: #fff3cd; }}
            .warning {{ background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>Playwright Test Report</h1>
        
        <div class="summary">
            <h2>测试摘要</h2>
            <div class="metric">
                <div class="metric-value">{summary['total']}</div>
                <div class="metric-label">总测试数</div>
            </div>
            <div class="metric">
                <div class="metric-value passed">{summary['passed']}</div>
                <div class="metric-label">通过</div>
            </div>
            <div class="metric">
                <div class="metric-value failed">{summary['failed']}</div>
                <div class="metric-label">失败</div>
            </div>
            <div class="metric">
                <div class="metric-value skipped">{summary['skipped']}</div>
                <div class="metric-label">跳过</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary['success_rate']*100:.1f}%</div>
                <div class="metric-label">通过率</div>
            </div>
            <div class="metric">
                <div class="metric-value">{summary['duration']/1000:.1f}s</div>
                <div class="metric-label">总时长</div>
            </div>
        </div>
    """
    
    # 添加测试套件
    if parsed["suites"]:
        html += "<h2>测试套件</h2>"
        for suite in parsed["suites"]:
            html += f"""
            <div class="suite">
                <div class="suite-title">{suite['title']}</div>
                <div>文件: {suite['file']}</div>
                <div>统计: {suite['passed']}通过, {suite['failed']}失败, {suite['skipped']}跳过, 时长: {suite['duration']/1000:.1f}s</div>
            """
            
            for spec in suite["specs"]:
                html += f"""
                <div class="spec">
                    <strong>{spec['title']}</strong> (行{spec['line']}:{spec['column']})
                """
                
                for test in spec["tests"]:
                    test_class = ""
                    if test["status"] == "failed":
                        test_class = "test-failed"
                    elif test["duration"] > 5000:  # 5秒以上算慢
                        test_class = "test-slow"
                    
                    html += f"""
                    <div class="test {test_class}">
                        {test['title']} - {test['status']} ({test['duration']}ms)
                    </div>
                    """
                
                html += "</div>"
            
            html += "</div>"
    
    # 添加警告
    if parsed["warnings"]:
        html += "<h2>警告</h2>"
        for warning in parsed["warnings"]:
            html += f'<div class="warning">⚠️ {warning}</div>'
    
    html += """
    </body>
    </html>
    """
    
    return html