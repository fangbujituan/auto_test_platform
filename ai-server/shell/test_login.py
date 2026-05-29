"""
BNP 登录测试脚本
直接运行: python shell/test_login.py
"""

import subprocess
import sys
import os


def run_playwright_test(test_file: str = "tests/bnp_login.spec.ts", headed: bool = True):
    """
    运行 Playwright 测试脚本
    
    Args:
        test_file: 测试文件路径（相对于 playwright_scripts 目录）
        headed: 是否显示浏览器窗口
    """
    # 获取项目根目录（shell 目录的上级目录）
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script_dir = os.path.join(project_root, "playwright_scripts")
    
    # 构建命令
    cmd = ["npx", "playwright", "test", test_file]
    if headed:
        cmd.append("--headed")
    
    print(f"运行命令: {' '.join(cmd)}")
    print(f"工作目录: {script_dir}")
    print("-" * 50)
    
    # 运行测试
    result = subprocess.run(
        " ".join(cmd),
        cwd=script_dir,
        capture_output=False,
        text=True,
        shell=True
    )
    
    return result.returncode


def main():
    print("=" * 50)
    print("BNP 登录测试")
    print("=" * 50)
    
    # 运行测试
    exit_code = run_playwright_test("tests/bnp_login.spec.ts", headed=True)
    
    print("-" * 50)
    if exit_code == 0:
        print("✅ 测试通过！")
    else:
        print(f"❌ 测试失败，退出码: {exit_code}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
