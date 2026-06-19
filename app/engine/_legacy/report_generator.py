# DEPRECATED: 本模块已废弃，调用方请使用 app.engine.api_engine。
# 保留在 app.engine._legacy 仅作历史参考；任何业务路径都不再引用。
# 归档时间：2026-01-20（api_engine 重构 Phase 5）
"""
@Author: <yandc>
@Time: 2025/06/07
测试报告生成
"""
import json
import os
import logging
from datetime import datetime
from typing import List, Tuple

logger = logging.getLogger(__name__)
from app.engine._legacy.liu_shui_xian import TestCaseStepResult  # 引入 TestCaseStepResult 用于类型提示


class TestReportGenerator:
    """
    生成自动化测试报告。
    """
    def __init__(self, report_dir: str = None):
        """
        :param report_dir: 报告文件存放的目录。如果为None，则默认为 auto-flask/reports。
        """
        self.report_dir = report_dir if report_dir else os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../reports')
        self.case_name = ""
        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)
        logger.info(f"TestReportGenerator: 报告将生成到目录: {self.report_dir}")

    def generate_json_report(self, test_case_results: List[Tuple[List[TestCaseStepResult], bool]], report_name: str = "automation_report"):
        """
        生成 JSON 格式的测试报告。
        :param test_case_results: 包含所有测试用例执行结果的列表，每个元素是一个元组 (list[TestCaseStepResult], bool)。
        :param report_name: 报告文件的基础名称。
        :return: 生成的报告文件的路径。
        """
        report_data = {
            "report_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_test_cases": len(test_case_results),
            "passed_test_cases": 0,
            "failed_test_cases": 0,
            "test_cases": []
        }

        for case_idx, (steps_results, case_passed) in enumerate(test_case_results):
            self.case_name = f"用例 {case_idx + 1}"
            if steps_results and steps_results[0].step_name: # 尝试从第一个步骤获取用例名
                # 从步骤名中提取用例名，例如 "步骤 1: 用户注册" -> "用户注册"
                # 这里可能需要更智能的用例名获取方式，目前简单处理
                if len(steps_results[0].step_name.split(':')) > 1:
                    self.case_name = steps_results[0].step_name.split(':')[0].strip().replace('步骤 1', self.case_name)

            case_data = {
                "case_name": self.case_name,
                "passed": case_passed,
                "steps": [step.to_dict() for step in steps_results]
            }
            report_data["test_cases"].append(case_data)

            if case_passed:
                report_data["passed_test_cases"] += 1
            else:
                report_data["failed_test_cases"] += 1

        file_name = f"{report_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_file_path = os.path.join(self.report_dir, file_name)

        try:
            with open(report_file_path, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=4, ensure_ascii=False)
            logger.info(f"TestReportGenerator: JSON 报告已生成: {report_file_path}")
            return report_file_path
        except IOError as e:
            logger.error(f"TestReportGenerator: 生成JSON报告失败: {e}", exc_info=True)
            return None

    def generate_console_summary(self, test_case_results: List[Tuple[List[TestCaseStepResult], bool]]):
        """
        在控制台打印测试报告摘要。
        :param test_case_results: 包含所有测试用例执行结果的列表。
        """
        logger.info("\n========== 测试报告摘要 ==========")
        total_cases = len(test_case_results)
        passed_cases = 0
        failed_cases = 0

        for case_idx, (steps_results, case_passed) in enumerate(test_case_results):
            self.case_name = f"用例 {case_idx + 1}"
            if steps_results and steps_results[0].step_name:
                if len(steps_results[0].step_name.split(':')) > 1:
                    self.case_name = steps_results[0].step_name.split(':')[0].strip().replace('步骤 1', self.case_name)

            status = "通过" if case_passed else "失败"
            logger.info(f"用例: {self.case_name} - 状态: {status}")
            if case_passed:
                passed_cases += 1
            else:
                failed_cases += 1
                for step_res in steps_results:
                    if not step_res.passed:
                        logger.info(f"  └── 失败步骤: {step_res.step_name} - 消息: {step_res.message}")
                        for assertion in step_res.assertions:
                            if not assertion.passed:
                                logger.info(f"      └── 失败断言: {assertion.message}")

        logger.info(f"\n总结:")
        logger.info(f"  总用例数: {total_cases}")
        logger.info(f"  通过用例数: {passed_cases}")
        logger.info(f"  失败用例数: {failed_cases}")
        logger.info("==================================\n")


if __name__ == '__main__':
    # 模拟一些测试结果
    from app.engine._legacy.liu_shui_xian import TestCaseStepResult
    from app.engine._legacy.assertion_handler import AssertionResult

    # 模拟第一个用例结果
    step1_results_case1 = TestCaseStepResult(
        step_name="登录",
        passed=True,
        message="登录成功",
        details={'status_code': 200},
        assertions=[
            AssertionResult(True, "状态码断言成功"),
            AssertionResult(True, "JSON包含token断言成功")
        ]
    )
    step2_results_case1 = TestCaseStepResult(
        step_name="获取用户信息",
        passed=False,
        message="状态码断言失败",
        details={'status_code': 404, 'response_text': 'Not Found'},
        assertions=[
            AssertionResult(False, "状态码断言：期望 200, 实际 404."),
            AssertionResult(True, "JSON包含username断言成功")
        ]
    )
    case1_results = ([step1_results_case1, step2_results_case1], False)

    # 模拟第二个用例结果
    step1_results_case2 = TestCaseStepResult(
        step_name="注册新用户",
        passed=True,
        message="注册成功",
        details={'status_code': 201},
        assertions=[
            AssertionResult(True, "状态码断言成功"),
            AssertionResult(True, "JSON包含id断言成功")
        ]
    )
    step2_results_case2 = TestCaseStepResult(
        step_name="验证邮箱",
        passed=True,
        message="验证成功",
        details={'status_code': 200},
        assertions=[
            AssertionResult(True, "状态码断言成功"),
            AssertionResult(True, "文本包含'verified'断言成功")
        ]
    )
    case2_results = ([step1_results_case2, step2_results_case2], True)

    all_mock_test_results = [case1_results, case2_results]

    report_generator = TestReportGenerator()
    report_generator.generate_console_summary(all_mock_test_results)
    json_report_path = report_generator.generate_json_report(all_mock_test_results)
    if json_report_path:
        logger.info(f"JSON报告已生成并可查看: {json_report_path}")