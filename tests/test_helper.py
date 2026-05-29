"""
测试辅助模块

提供测试脚本的通用功能，如路径设置等。
"""
import sys
from pathlib import Path


def setup_project_path():
    """
    将项目根目录添加到 Python 路径。
    
    这样测试脚本就可以正确导入 app 模块，
    无论是从项目根目录还是 tests 目录运行。
    """
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


# 自动执行路径设置
setup_project_path()
