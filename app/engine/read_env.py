"""
@Author: <yandc>
@Time: 2025/06/07
初始化环境变量
"""

import logging

from app.models.autoer import AutoModel

logger = logging.getLogger(__name__)


class ReadEnv:
    """
    负责初始化自动化测试场景所需的环境变量。
    """

    def __init__(self):
        self.env_variables = {}
        logger.info(f"========= 环境变量容器准备就绪 ==========")

    def read_env(self, env_group_code: str):
        total, env_data = AutoModel().get_env_by_code(1, 5000, env_group_code)
        # logger.info(f"读取到的环境变量env_data列表:{env_data}")
        # 异常处理，判断获取环境变量是否为空
        if env_data is None:
            # 抛出异常
            pass
        # 核心代码：将读取到的环境变量存入字典里
        for env in env_data:
            # logger.info(f"env:{env}")
            self.env_variables[env['env_key']] = env['env_values']
        logger.info(f"本次运行环境变量为: {self.env_variables}")
        # 工作台打印每个变量
        # for k, v in self.env_variables.items():
        #     logger.info(f"key:{k},values:{self.env_variables[k]}")
        logger.info("--- 初始化变量完成 ---")

    def load_base_variables(self, scenario_config: dict):
        """
        根据场景配置加载基础环境变量。
        例如：base_url, common_headers 等。
        :param scenario_config: 从数据库获取的场景配置字典。
        """
        logger.info(
            f"ReadEnv: 正在加载场景 '{scenario_config.get('scenario_name', '未知场景')}' 的基础环境变量。")
        self.env_variables['base_url'] = scenario_config.get('base_url', 'http://localhost:5000')
        self.env_variables['common_headers'] = scenario_config.get('common_headers',
                                                                   {'Content-Type': 'application/json'})
        logger.info(f"ReadEnv: 基础URL设置为: {self.env_variables['base_url']}")
        logger.info(f"ReadEnv: 通用请求头设置为: {self.env_variables['common_headers']}")

    def load_auth_variables(self, user_info: dict):
        """
        加载认证相关的环境变量，例如 token。
        这可能涉及到调用登录接口获取 token。
        :param user_info: 包含用户名和密码等认证信息的字典。
        """
        logger.info(f"ReadEnv: 正在加载用户 '{user_info.get('username', '未知用户')}' 的认证信息。")
        # 实际项目中，这里会调用认证服务或接口来获取token
        # 示例：假设我们直接从配置中获取或模拟一个token
        self.env_variables['auth_token'] = user_info.get('token', 'mock_auth_token_12345')
        logger.info(f"ReadEnv: 认证Token设置为: {self.env_variables['auth_token'][:10]}...")  # 避免打印完整token

    def set_custom_variable(self, key: str, value: any):
        """
        设置自定义环境变量。
        :param key: 变量名。
        :param value: 变量值。
        """
        self.env_variables[key] = value
        logger.info(f"ReadEnv: 设置自定义变量 '{key}' = '{value}'")

    def get_env_variables(self) -> dict:
        """
        获取当前已加载的所有环境变量。
        :return: 包含所有环境变量的字典。
        """
        return self.env_variables

    def clear_env_variables(self):
        """
        清除所有已加载的环境变量。
        """
        self.env_variables = {}
        logger.info("ReadEnv: 已清除所有环境变量。")


if __name__ == '__main__':
    # 示例用法
    initializer = ReadEnv()

    # initializer.read_env_var('env-001')




































    #
    # # 模拟从数据库获取的场景配置
    # mock_scenario_config = {
    #     'scenario_name': '用户登录测试',
    #     'base_url': 'http://localhost:5000/api',
    #     'common_headers': {'X-Custom-Header': 'Test'}
    # }
    # initializer.load_base_variables(mock_scenario_config)
    #
    # # 模拟用户认证信息
    # mock_user_info = {
    #     'username': 'testuser',
    #     'password': 'testpassword',
    #     'token': 'eb16e3d1-8edf-4ad4-b930-2e11c99c8ed5'
    # }
    # initializer.load_auth_variables(mock_user_info)
    #
    # # 设置自定义变量
    # initializer.set_custom_variable('user_id', 123)
    # initializer.set_custom_variable('user_id', 123)
    # initializer.set_custom_variable('product_id', 456)
    #
    # current_env = initializer.get_env_variables()
    # logger.info(f"当前环境变量: {current_env}")
    #
    # initializer.clear_env_variables()
    # logger.info(f"清除后环境变量: {initializer.get_env_variables()}")
