"""
@Author: <yandc>
@Time: 2025/06/07
测试工厂：集成测试执行的动作，引用相关工具类
这是一个独立的脚本，用于启动自动化测试控制集合
控制器，将各个部件组装在一起
"""
import logging

from app.services.api_service import ApiService

logger = logging.getLogger(__name__)
from app.engine.read_env import ReadEnv
from app.engine.read_case import FormattingData
from app.engine.assertion_handler import AssertionHandler
from app.engine.liu_shui_xian import LiuShuiXian
from app.engine.report_generator import TestReportGenerator


# 假设从数据库获取用例数据，这里用模拟数据代替
def get_mock_test_data_from_db(scenario_id: int = 1, include_failing_case: bool = False):
    """
    模拟从数据库获取测试场景和测试用例数据。
    在实际项目中，这里会连接MySQL数据库查询。
    """
    logger.info(f"正在模拟从数据库获取场景ID为 {scenario_id} 的测试数据...")

    # 模拟-场景配置
    scenario_config = {
        'scenario_name': '用户模块自动化测试',
        'base_url': 'http://jsonplaceholder.typicode.com',  # 使用免费API测试服务
        'common_headers': {'X-Api-Key': 'your_api_key_here'}
    }

    # 模拟-测试用例数据
    test_cases_data = [
        {
            "case_name": "获取所有帖子并断言",
            "steps": [
                {
                    "step_name": "获取所有帖子",
                    "method": "GET",
                    "path": "/posts",
                    "expected_status_code": 200,
                    "assertions": [
                        {"type": "text_contains", "value": "sunt aut facere"},
                        {"type": "json_contains", "key": "0.userId", "value": 1}  # 检查第一个元素的userId
                    ]
                }
            ]
        }
    ]
    return test_cases_data


class TestFactory:
    def __init__(self, terminate_on_failure: bool = True, number_of_cycles: int = 1, env_group_code: str = 'env-'):
        """
        自动化平台的执行入口。主要维护执行过程配置信息
        :param terminate_on_failure: 断言失败时是否终止用例执行。
        :number_of_cycles: 循环次数。
        :env_group_code：环境变量code
        """
        self.terminate_on_failure = terminate_on_failure
        self.number_of_cycles = number_of_cycles
        self.env_group_code = env_group_code
        # logger.info(f"变量值：{self.terminate_on_failure}{self.number_of_cycles}{self.env_group_code}")

    def run_automation(self, ids):
        logger.info("========= 欢迎使用《方步自动化》测试 =========")

        # 1. 初始化环境变量，从数据库中提取，根据环境组code查询
        read_env = ReadEnv().read_env(self.env_group_code)
        # 测试代码，用于调试，无数据库时使用
        # 获取环境变量集、测试用例集
        # all_test_cases_data = get_mock_test_data_from_db(include_failing_case=True)

        # 2、获取测试用例集-源数据
        # （当前数据无法直接执行，需要对数据进行处理，类型有case，cases，api，apis，Scene，scenes
        all_test_cases_data = ApiService.get_api_list_service(page=1, size=99999, project_id=1, search=ids)
        logger.info(f"{type(all_test_cases_data)}, 源数据-all_test_cases_data:{all_test_cases_data}")

        # 模拟加载认证信息 (如果需要)
        # read_env.load_auth_variables({'username': 'admin', 'token': 'mock_admin_token'})

        # 模拟设置自定义变量
        # read_env.set_custom_variable('dynamic_param_value', 'test_dynamic')

        # 3. 数据加工——>字典格式
        all_test_cases_data = FormattingData(all_test_cases_data).get_case_data()
        logger.info(f"{type(all_test_cases_data)}, all_test_cases_data:{all_test_cases_data}")

        # 3. 初始化断言处理器
        assertion_handler = AssertionHandler(terminate_on_failure=self.terminate_on_failure)

        # 4. 初始化执行用例驱动
        leader = LiuShuiXian(read_env, assertion_handler)

        # 5. 初始化报告生成器
        report_generator = TestReportGenerator()

        # 存储所有用例的执行结果 (list[list[TestCaseStepResult], bool])
        overall_case_results = []

        # 6. 遍历并执行所有测试用例
        for test_case_data in all_test_cases_data:
            case_steps_results, case_passed = leader.execute_test_case(test_case_data)
            overall_case_results.append((case_steps_results, case_passed))

        # 7. 生成并输出测试报告
        report_generator.generate_console_summary(overall_case_results)
        json_report_path = report_generator.generate_json_report(overall_case_results)
        if json_report_path:
            logger.info(f"完整的JSON测试报告已生成到: {json_report_path}")

        logger.info("========= 自动化平台执行结束ok1 =========")
        # return {"message": "操作成功"}, None


if __name__ == '__main__':
    # 你可以通过修改这里的参数来控制断言失败时的行为
    # True: 遇到第一个断言失败立即终止当前用例的后续步骤
    # False: 即使断言失败也会继续执行当前用例的所有步骤
    TestFactory().run_automation()
    # TestFactory(terminate_on_failure=False).run_automation()
