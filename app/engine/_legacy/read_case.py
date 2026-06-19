# DEPRECATED: 本模块已废弃，调用方请使用 app.engine.api_engine。
# 保留在 app.engine._legacy 仅作历史参考；任何业务路径都不再引用。
# 归档时间：2026-01-20（api_engine 重构 Phase 5）
"""
@Author: <yandc>
@Time: 2025/06/07
初始化环境变量
"""


class FormattingData:
    """
        数据加工厂，将从数据读取的数据标准化为测试
    """
    def __init__(self, data):
        self.data = data

    def get_case_data(self):
        if self.data[0]['data']:
            print(self.data[0]['data'])
            self.data = self.data[0]['data']
        return self.data

    def read_case(self):
        pass

