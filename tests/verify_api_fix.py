# -*- coding: utf-8 -*-
"""
验证API路径修复

作者: yandc
创建时间: 2026-01-19
"""
import os

def check_file_content(filepath, should_not_contain, description):
    """检查文件内容不应包含某些字符串"""
    if not os.path.exists(filepath):
        print(f"✗ 文件不存在: {filepath}")
        return False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    found_issues = []
    for pattern in should_not_contain:
        if pattern in content:
            found_issues.append(pattern)
    
    if found_issues:
        print(f"✗ {description}: 发现问题")
        for issue in found_issues:
            print(f"  - 仍包含: {issue}")
        return False
    else:
        print(f"✓ {description}: 正确")
        return True

def main():
    print("\n" + "="*60)
    print("验证API路径修复")
    print("="*60 + "\n")
    
    checks = [
        (
            "client/src/api/module.js",
            ["url: '/api/modules", 'url: "/api/modules'],
            "module.js URL路径"
        ),
        (
            "client/src/api/testCase.js",
            ["url: '/api/test-cases", 'url: "/api/test-cases'],
            "testCase.js URL路径"
        ),
        (
            "client/src/views/TestCaseManagement.vue",
            ["res.data.items", "res.data.total", "res.data || []"],
            "TestCaseManagement.vue 数据处理"
        ),
    ]
    
    all_passed = True
    for filepath, patterns, desc in checks:
        if not check_file_content(filepath, patterns, desc):
            all_passed = False
    
    print("\n" + "="*60)
    if all_passed:
        print("✓ 所有检查通过！API路径已正确修复")
        print("\n下一步：")
        print("1. 重启前端服务（如果正在运行）")
        print("2. 清除浏览器缓存")
        print("3. 重新访问测试用例管理页面")
    else:
        print("✗ 发现问题，请检查上述文件")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
