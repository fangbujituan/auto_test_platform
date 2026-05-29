# -*- coding: utf-8 -*-
"""
Kiro IDE 清理工具
清理缓存、日志、全局存储等文件，解决登录问题

用法:
  python kiro_cleaner.py           # 交互模式
  python kiro_cleaner.py -y        # 自动确认清理
  python kiro_cleaner.py --deep    # 深度清理（账户切换）
  python kiro_cleaner.py --full    # 完全清理（重置为初始状态）
"""

import os
import shutil
import argparse
from pathlib import Path


def get_kiro_base_path():
    """获取 Kiro 基础路径"""
    return Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / 'Kiro'


def get_kiro_paths(mode='normal'):
    """获取 Kiro IDE 相关目录路径
    
    mode: 
      normal - 基础缓存清理
      deep - 账户切换清理（清理认证数据）
      full - 完全重置（删除整个 Kiro 目录）
    """
    user_home = Path.home()
    appdata = Path(os.environ.get('APPDATA', user_home / 'AppData' / 'Roaming'))
    kiro_base = appdata / 'Kiro'
    
    if mode == 'full':
        # 完全重置 - 删除整个 Kiro 目录
        return {'Kiro (完整目录)': kiro_base}
    
    paths = {
        # 基础缓存
        'Cache': kiro_base / 'Cache' / 'Cache_Data',
        'CachedData': kiro_base / 'CachedData',
        'CachedExtensions': kiro_base / 'CachedExtensionVSIXs',
        'CodeCache': kiro_base / 'Code Cache',
        'GPUCache': kiro_base / 'GPUCache',
        'DawnGraphiteCache': kiro_base / 'DawnGraphiteCache',
        'DawnWebGPUCache': kiro_base / 'DawnWebGPUCache',
        'Logs': kiro_base / 'logs',
        'Crashpad': kiro_base / 'Crashpad',
        
        # 用户数据
        'GlobalStorage': kiro_base / 'User' / 'globalStorage',
        'KiroConfig': user_home / '.kiro',
    }
    
    if mode == 'deep':
        # 深度清理 - 添加认证相关目录
        auth_paths = {
            # 认证相关（关键）
            'NetworkCookies': kiro_base / 'Network' / 'Cookies',
            'NetworkCookiesJournal': kiro_base / 'Network' / 'Cookies-journal',
            'LocalStorage': kiro_base / 'Local Storage',
            'SessionStorage': kiro_base / 'Session Storage',
            'WebStorage': kiro_base / 'WebStorage',
            'DIPS': kiro_base / 'DIPS',
            'DIPSWal': kiro_base / 'DIPS-wal',
            'SharedStorage': kiro_base / 'SharedStorage',
            
            # 状态文件（认证相关）
            'LocalState': kiro_base / 'Local State',
            'Preferences': kiro_base / 'Preferences',
            
            # 缓存配置
            'CachedProfilesData': kiro_base / 'CachedProfilesData',
            
            # 工作区存储
            'WorkspaceStorage': kiro_base / 'User' / 'workspaceStorage',
        }
        paths.update(auth_paths)
    
    return paths


def get_dir_size(path: Path) -> str:
    """获取目录或文件大小"""
    if not path.exists():
        return "不存在"
    
    if path.is_file():
        try:
            size = path.stat().st_size
        except (OSError, PermissionError):
            return "无法访问"
    else:
        total_size = 0
        try:
            for dirpath, dirnames, filenames in os.walk(path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, PermissionError):
                        pass
        except (OSError, PermissionError):
            return "无法访问"
        size = total_size
    
    # 转换为可读格式
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def clear_path(path: Path) -> tuple[bool, str]:
    """清理目录或文件"""
    if not path.exists():
        return True, "不存在，跳过"
    
    try:
        if path.is_file():
            path.unlink()
        else:
            shutil.rmtree(path)
        return True, "清理成功"
    except PermissionError as e:
        return False, f"权限不足"
    except Exception as e:
        return False, f"失败: {str(e)[:30]}"


def main():
    parser = argparse.ArgumentParser(description='Kiro IDE 清理工具')
    parser.add_argument('-y', '--yes', action='store_true', help='自动确认清理')
    parser.add_argument('--deep', action='store_true', help='深度清理（账户切换）')
    parser.add_argument('--full', action='store_true', help='完全清理（重置为初始状态）')
    args = parser.parse_args()
    
    # 确定清理模式
    if args.full:
        mode = 'full'
        mode_desc = "完全清理（重置为初始状态）"
    elif args.deep:
        mode = 'deep'
        mode_desc = "深度清理（账户切换）"
    else:
        mode = 'normal'
        mode_desc = "基础清理"
    
    print("=" * 70)
    print(f"Kiro IDE 清理工具 - {mode_desc}")
    print("=" * 70)
    print()
    
    paths = get_kiro_paths(mode)
    
    # 显示各目录状态
    print("扫描 Kiro 相关目录:")
    print("-" * 70)
    
    results = []
    for name, path in paths.items():
        size = get_dir_size(path)
        exists = path.exists()
        status = "[OK]" if exists else "[--]"
        is_file = path.is_file() if exists else False
        type_str = "文件" if is_file else "目录"
        print(f"  {name:25} {status:6} {type_str:4} {size:12} {path}")
        results.append((name, path, exists, size))
    
    print("-" * 70)
    print()
    
    # 检查是否有需要清理的目录
    existing_paths = [(n, p, s) for n, p, e, s in results if e]
    
    if not existing_paths:
        print("没有找到需要清理的 Kiro 目录。")
        return
    
    print(f"发现 {len(existing_paths)} 个可清理项")
    
    if mode == 'deep':
        print()
        print("  [!] 深度清理将清除所有登录态和认证信息")
        print("  [!] 清理后需要重新登录")
    elif mode == 'full':
        print()
        print("  [!] 完全清理将删除整个 Kiro 目录")
        print("  [!] Kiro 将恢复到初始安装状态")
    
    print()
    
    # 确认清理
    if args.yes:
        confirm = 'y'
    else:
        confirm = input("确认清理以上所有项目? (y/n): ").strip().lower()
    
    if confirm != 'y':
        print("已取消清理。")
        return
    
    print()
    print("开始清理...")
    print("-" * 70)
    
    success_count = 0
    fail_count = 0
    
    for name, path, size in existing_paths:
        success, msg = clear_path(path)
        status = "[OK]" if success else "[FAIL]"
        print(f"  {status} {name:25} {msg}")
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    print("-" * 70)
    print()
    print(f"清理完成: 成功 {success_count} 个, 失败 {fail_count} 个")
    
    if fail_count > 0:
        print()
        print("[!] 部分项目清理失败，请确保 Kiro IDE 已完全关闭后重试。")
    
    print()
    print("=" * 70)
    print("清理完成！请重新打开 Kiro IDE 并重新登录。")
    if mode == 'deep':
        print("提示: 使用 AWS Identity Center 登录需要 Q Developer Pro 订阅")
        print("      如果 Identity Center 登录失败，请尝试 Builder ID 或 Google/GitHub")
    print("=" * 70)


if __name__ == "__main__":
    main()