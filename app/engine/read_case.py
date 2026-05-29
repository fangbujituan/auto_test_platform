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

