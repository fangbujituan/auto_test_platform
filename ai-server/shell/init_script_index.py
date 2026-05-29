"""
脚本索引初始化工具

用于部署时手动初始化脚本索引，清除旧元数据并重建索引。

使用方法：
    python init_script_index.py [--clean-all]

选项：
    --clean-all    清除所有元数据（包括回收站）后重建索引
"""

import argparse
import sys
from pathlib import Path

# 添加项目根目录到路径（脚本在 shell/ 子目录，需要往上一级）
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.playwright.script_index import get_index_manager
from loguru import logger


def init_index(clean_all: bool = False) -> dict:
    """初始化脚本索引.
    
    Args:
        clean_all: 是否清除所有元数据（包括回收站）
    
    Returns:
        初始化结果统计
    """
    index_manager = get_index_manager()
    
    result = {
        "scripts_found": 0,
        "index_rebuilt": False,
        "trash_cleaned": 0,
        "recordings_cleared": False,
    }
    
    # 1. 清除元数据目录（如果指定）
    if clean_all:
        recordings_dir = index_manager.recordings_dir
        trash_dir = recordings_dir / ".trash"
        
        # 清除回收站
        if trash_dir.exists():
            import shutil
            shutil.rmtree(trash_dir)
            trash_dir.mkdir(parents=True, exist_ok=True)
            result["trash_cleaned"] = -1  # 表示已清空
            logger.info("✅ 回收站已清空")
        
        # 清除旧索引文件
        index_file = recordings_dir / "index.json"
        if index_file.exists():
            index_file.unlink()
            result["recordings_cleared"] = True
            logger.info("✅ 旧索引文件已删除")
    
    # 2. 重建索引
    count = index_manager.rebuild_index()
    result["scripts_found"] = count
    result["index_rebuilt"] = True
    
    # 3. 显示结果
    entries = index_manager.index.scripts
    logger.info(f"✅ 索引重建完成，共 {count} 个脚本")
    
    if entries:
        logger.info("\n📋 脚本列表：")
        for entry in entries:
            logger.info(f"  - {entry.name}: 质量={entry.quality_score:.2f}, 关键词={entry.keywords}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="脚本索引初始化工具 - 用于部署时初始化脚本索引",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
    python init_script_index.py              # 重建索引（保留回收站）
    python init_script_index.py --clean-all  # 清除所有元数据后重建索引
        """
    )
    parser.add_argument(
        "--clean-all",
        action="store_true",
        help="清除所有元数据（包括回收站）后重建索引"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("📦 脚本索引初始化工具")
    print("=" * 50)
    
    if args.clean_all:
        print("\n⚠️  模式: 完全清理 + 重建索引")
    else:
        print("\n⚠️  模式: 重建索引（保留回收站）")
    
    print("-" * 50)
    
    result = init_index(clean_all=args.clean_all)
    
    print("-" * 50)
    print("\n📊 初始化结果：")
    print(f"  - 发现脚本: {result['scripts_found']} 个")
    print(f"  - 索引重建: {'✅ 成功' if result['index_rebuilt'] else '❌ 失败'}")
    
    if args.clean_all:
        print(f"  - 回收站清理: {'✅ 已清空' if result['trash_cleaned'] == -1 else '无需清理'}")
        print(f"  - 旧索引删除: {'✅ 已删除' if result['recordings_cleared'] else '无需删除'}")
    
    print("\n" + "=" * 50)
    print("✅ 初始化完成！")
    print("=" * 50)


if __name__ == "__main__":
    main()
