"""
快速初始化API目录数据的脚本。

使用方法:
    python init_folders.py          # 初始化所有项目的目录
    python init_folders.py reset    # 重置所有目录数据（谨慎使用）

作者: yandc
创建时间: 2026-01-16
"""
from app.init_api_data import init_api_folders, reset_api_folders
import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        reset_api_folders()
    else:
        init_api_folders()
