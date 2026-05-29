"""
脚本索引管理器

提供全局索引机制，支持：
1. 索引构建和增量更新
2. 脚本质量评估
3. 清理和恢复功能
4. 快速脚本查找

索引结构：
{
    "version": "1.0",
    "updated_at": "2026-03-17T10:00:00",
    "scripts": [
        {
            "name": "billing_items_add",
            "description": "添加 Billing Item",
            "keywords": ["billing", "add"],
            "url_patterns": ["https://bnp-test.item.pub/**"],
            "usage_count": 5,
            "success_rate": 0.85,
            "quality_score": 0.8,
            "has_code": true,
            "ref_count": 2,
            "created_at": "...",
            "last_used": "..."
        }
    ]
}
"""

import json
import threading
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from tools.debug.readlog import logs


# 统一脚本目录：playwright_scripts/
# recordings/ 子目录存放元数据和索引
# tests/ 子目录存放实际脚本
DEFAULT_RECORDINGS_DIR = Path(__file__).parent.parent.parent / "playwright_scripts" / "recordings"
DEFAULT_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "playwright_scripts" / "tests"
INDEX_FILE = "index.json"
TRASH_DIR = ".trash"
TRASH_EXPIRE_DAYS = 7  # 回收站文件过期天数


@dataclass
class ScriptIndexEntry:
    """脚本索引条目"""
    name: str
    description: str
    keywords: List[str]
    url_patterns: List[str]
    usage_count: int = 0
    success_rate: float = 1.0
    quality_score: float = 1.0  # 综合质量分数 (0-1)
    has_code: bool = True  # 是否有实际代码文件
    has_metadata: bool = True  # 是否有元数据文件
    ref_count: int = 0  # 代码中 ref 选择器数量
    semantic_count: int = 0  # 语义化选择器数量
    created_at: str = ""
    updated_at: str = ""
    last_used: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptIndexEntry":
        return cls(**data)


@dataclass
class ScriptIndex:
    """脚本索引"""
    version: str = "1.0"
    updated_at: str = ""
    scripts: List[ScriptIndexEntry] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "updated_at": self.updated_at,
            "scripts": [s.to_dict() for s in self.scripts]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptIndex":
        scripts = [ScriptIndexEntry.from_dict(s) for s in data.get("scripts", [])]
        return cls(
            version=data.get("version", "1.0"),
            updated_at=data.get("updated_at", ""),
            scripts=scripts
        )


class ScriptIndexManager:
    """
    脚本索引管理器
    
    功能：
    - 维护全局索引 index.json
    - 索引构建和增量更新
    - 脚本质量评估
    - 清理和恢复功能
    - 定期自动清理（后台异步执行）
    """
    
    # 定期清理配置（改进版：后台异步 + 降低频率）
    AUTO_CLEANUP_INTERVAL = 50  # 每 N 次操作后自动清理（原10次，改为50次）
    AUTO_CLEANUP_QUALITY_THRESHOLD = 0.3  # 自动清理的质量阈值（原0.4，改为0.3只清理很差的）
    
    def __init__(self, recordings_dir: Optional[Path] = None, scripts_dir: Optional[Path] = None):
        self.recordings_dir = recordings_dir or DEFAULT_RECORDINGS_DIR
        self.scripts_dir = scripts_dir or DEFAULT_SCRIPTS_DIR
        self.trash_dir = self.recordings_dir / TRASH_DIR
        self.index_path = self.recordings_dir / INDEX_FILE
        self._index: Optional[ScriptIndex] = None
        # 操作计数器（用于定期清理，后台异步执行）
        self._operation_count: int = 0
        self._last_cleanup_time: Optional[datetime] = None
        self._ensure_dirs()
        logs.info(f"[ScriptIndexManager] 初始化完成")
        logs.info(f"  - 元数据目录: {self.recordings_dir}")
        logs.info(f"  - 脚本目录: {self.scripts_dir}")
        logs.info(f"  - 定期清理间隔: 每 {self.AUTO_CLEANUP_INTERVAL} 次操作（后台异步）")
    
    def _ensure_dirs(self):
        """确保目录存在"""
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_script_path(self, name: str) -> Path:
        """获取脚本文件路径（在 tests/ 目录）"""
        safe_name = name.replace(' ', '_').replace('/', '_')
        # 脚本统一存放于 tests/ 目录，使用 .spec.ts 后缀
        if not safe_name.endswith('.spec.ts'):
            safe_name = f"{safe_name}.spec"
        return self.scripts_dir / f"{safe_name}.ts"
    
    def _get_meta_path(self, name: str) -> Path:
        """获取元数据文件路径"""
        safe_name = name.replace(' ', '_').replace('/', '_')
        return self.recordings_dir / f"{safe_name}.meta.json"
    
    def _count_selectors(self, code: str) -> tuple:
        """
        统计代码中的选择器类型
        
        Returns:
            (ref_count, semantic_count) ref选择器数量和语义化选择器数量
        """
        import re
        
        # 统计 ref 选择器: [ref="e123"] 或 ref="e123"
        ref_pattern = r'\[ref=["\']e?\d+["\']\]|ref=["\']e?\d+["\']'
        ref_count = len(re.findall(ref_pattern, code))
        
        # 统计语义化选择器: getByRole, getByText, getByLabel, getByTestId, getByPlaceholder
        semantic_patterns = [
            r'getByRole\s*\(',
            r'getByText\s*\(',
            r'getByLabel\s*\(',
            r'getByTestId\s*\(',
            r'getByPlaceholder\s*\(',
        ]
        semantic_count = 0
        for pattern in semantic_patterns:
            semantic_count += len(re.findall(pattern, code))
        
        return ref_count, semantic_count
    
    def _calculate_quality_score(self, entry: ScriptIndexEntry) -> float:
        """
        计算脚本质量分数
        
        评分维度：
        - success_rate (40%): 执行成功率
        - semantic_ratio (30%): 语义化选择器比例
        - has_code (20%): 是否有代码文件
        - usage_count (10%): 使用次数（归一化）
        
        🚀 P1-006: 冷启动惩罚 — 使用次数 < 3 时打 70% 折扣
        """
        score = 0.0
        
        # 1. 成功率 (40%)
        score += entry.success_rate * 0.4
        
        # 2. 语义化选择器比例 (30%)
        total_selectors = entry.ref_count + entry.semantic_count
        if total_selectors > 0:
            semantic_ratio = entry.semantic_count / total_selectors
            score += semantic_ratio * 0.3
        elif entry.has_code:
            # 🚀 P1-006: 有代码但无选择器统计时，尝试静态分析
            script_path = self._get_script_path(entry.name)
            if script_path.exists():
                try:
                    code = script_path.read_text(encoding='utf-8')
                    ref_count, semantic_count = self._count_selectors(code)
                    total = ref_count + semantic_count
                    if total > 0:
                        score += (semantic_count / total) * 0.3
                    else:
                        score += 0.15
                except Exception:
                    score += 0.15
            else:
                score += 0.15
        else:
            score += 0.15  # 无选择器时给中等分数
        
        # 3. 有代码文件 (20%)
        if entry.has_code:
            score += 0.2
        
        # 4. 使用次数 (10%) - 使用 log 归一化
        if entry.usage_count > 0:
            usage_score = min(1.0, (entry.usage_count / 10))  # 10次以上满分
            score += usage_score * 0.1
        
        # 🚀 P1-006: 冷启动惩罚 — 新脚本（使用次数 < 3）打折
        # 防止从未执行过的脚本因默认 success_rate=1.0 而分数虚高
        if entry.usage_count < 3:
            score *= 0.7
        
        return round(score, 2)
    
    def load_index(self) -> ScriptIndex:
        """加载索引"""
        if self.index_path.exists():
            try:
                data = json.loads(self.index_path.read_text(encoding='utf-8'))
                self._index = ScriptIndex.from_dict(data)
                logs.info(f"[ScriptIndexManager] 加载索引成功，共 {len(self._index.scripts)} 个脚本")
                return self._index
            except Exception as e:
                logs.warning(f"[ScriptIndexManager] 加载索引失败: {e}")
        
        self._index = ScriptIndex()
        return self._index
    
    def save_index(self):
        """保存索引"""
        if self._index is None:
            return
        
        self._index.updated_at = datetime.now().isoformat()
        self.index_path.write_text(
            json.dumps(self._index.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        logs.info(f"[ScriptIndexManager] 索引已保存，共 {len(self._index.scripts)} 个脚本")
    
    @property
    def index(self) -> ScriptIndex:
        """获取索引（懒加载）"""
        if self._index is None:
            self.load_index()
        return self._index
    
    def rebuild_index(self) -> int:
        """
        重建完整索引
        
        以 tests/ 目录的实际脚本为准，清理孤立的元数据文件
        
        Returns:
            索引的脚本数量
        """
        logs.info("[ScriptIndexManager] 开始重建索引...")
        
        entries = []
        orphaned_meta_count = 0
        
        # 1. 扫描 tests/ 目录下的实际脚本文件（以脚本为准）
        for script_path in self.scripts_dir.glob("*.spec.ts"):
            try:
                # 提取脚本名称
                name = script_path.stem.replace('.spec', '')
                
                # 读取元数据（如果存在）
                meta_path = self._get_meta_path(name)
                metadata = {}
                if meta_path.exists():
                    try:
                        metadata = json.loads(meta_path.read_text(encoding='utf-8'))
                    except Exception as e:
                        logs.warning(f"[ScriptIndexManager] 读取元数据 {meta_path} 失败: {e}")
                
                # 统计选择器
                code = script_path.read_text(encoding='utf-8')
                ref_count, semantic_count = self._count_selectors(code)
                
                entry = ScriptIndexEntry(
                    name=name,
                    description=metadata.get("description", ""),
                    keywords=metadata.get("keywords", []),
                    url_patterns=metadata.get("url_patterns", []),
                    usage_count=metadata.get("usage_count", 0),
                    success_rate=metadata.get("success_rate", 1.0),
                    has_code=True,
                    has_metadata=meta_path.exists(),
                    ref_count=ref_count,
                    semantic_count=semantic_count,
                    created_at=metadata.get("created_at", ""),
                    updated_at=metadata.get("updated_at", ""),
                    last_used=metadata.get("last_used", ""),
                )
                
                # 计算质量分数
                entry.quality_score = self._calculate_quality_score(entry)
                
                entries.append(entry)
                
            except Exception as e:
                logs.warning(f"[ScriptIndexManager] 处理 {script_path} 失败: {e}")
        
        # 2. 清理孤立的元数据文件（脚本不存在但元数据存在）
        for meta_path in self.recordings_dir.glob("*.meta.json"):
            name = meta_path.stem.replace(".meta", "")
            script_path = self._get_script_path(name)
            if not script_path.exists():
                meta_path.unlink()
                orphaned_meta_count += 1
                logs.info(f"[ScriptIndexManager] 清理孤立元数据: {meta_path.name}")
        
        # 更新索引
        self._index = ScriptIndex(
            version="1.0",
            updated_at=datetime.now().isoformat(),
            scripts=entries
        )
        
        self.save_index()
        logs.info(f"[ScriptIndexManager] 索引重建完成，共 {len(entries)} 个脚本，清理 {orphaned_meta_count} 个孤立元数据")
        
        return len(entries)
    
    def update_entry(self, name: str, metadata: Dict[str, Any] = None, code: str = None):
        """
        增量更新单个脚本条目
        
        Args:
            name: 脚本名称
            metadata: 元数据（可选）
            code: 代码内容（可选）
        """
        if self._index is None:
            self.load_index()
        
        # 查找现有条目
        existing = None
        for i, entry in enumerate(self._index.scripts):
            if entry.name == name:
                existing = i
                break
        
        # 获取或创建条目
        if existing is not None:
            entry = self._index.scripts[existing]
        else:
            entry = ScriptIndexEntry(name=name, description="", keywords=[], url_patterns=[])
        
        # 更新元数据
        if metadata:
            entry.description = metadata.get("description", entry.description)
            entry.keywords = metadata.get("keywords", entry.keywords)
            entry.url_patterns = metadata.get("url_patterns", entry.url_patterns)
            entry.usage_count = metadata.get("usage_count", entry.usage_count)
            entry.success_rate = metadata.get("success_rate", entry.success_rate)
            if "created_at" in metadata:
                entry.created_at = metadata["created_at"]
            if "updated_at" in metadata:
                entry.updated_at = metadata["updated_at"]
        
        # 更新代码信息
        if code:
            entry.has_code = True
            entry.ref_count, entry.semantic_count = self._count_selectors(code)
        else:
            # 检查代码文件是否存在
            script_path = self._get_script_path(name)
            entry.has_code = script_path.exists()
            if entry.has_code:
                code = script_path.read_text(encoding='utf-8')
                entry.ref_count, entry.semantic_count = self._count_selectors(code)
        
        # 检查元数据文件
        meta_path = self._get_meta_path(name)
        entry.has_metadata = meta_path.exists()
        
        # 重新计算质量分数
        entry.quality_score = self._calculate_quality_score(entry)
        
        # 更新索引
        if existing is not None:
            self._index.scripts[existing] = entry
        else:
            self._index.scripts.append(entry)
        
        self.save_index()
        logs.info(f"[ScriptIndexManager] 更新条目: {name}, 质量分数: {entry.quality_score}")
        
        # 增加操作计数，触发定期清理（后台异步执行，不阻塞主流程）
        self._increment_operation_count()
    
    def _increment_operation_count(self):
        """
        增加操作计数，达到阈值时后台异步清理
        
        改进点：
        - 使用后台线程执行清理，不阻塞主流程
        - 降低触发频率（每50次操作）
        """
        self._operation_count += 1
        
        if self._operation_count >= self.AUTO_CLEANUP_INTERVAL:
            self._operation_count = 0
            # 后台线程执行，不阻塞主流程
            thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
            thread.start()
    
    def _periodic_cleanup(self):
        """
        后台定期自动清理
        
        在后台线程中执行，不影响主流程性能。
        清理过期回收站和低质量脚本。
        """
        try:
            logs.info("[ScriptIndexManager] 开始后台定期清理...")
            
            # 1. 清理过期回收站
            expired = self.cleanup_expired_trash()
            
            # 2. 自动清理低质量脚本
            result = self.auto_cleanup(keep_best=True, quality_threshold=self.AUTO_CLEANUP_QUALITY_THRESHOLD)
            
            self._last_cleanup_time = datetime.now()
            
            if result['total_removed'] > 0 or expired > 0:
                logs.info(f"[ScriptIndexManager] 后台清理完成: 移除 {result['total_removed']} 个脚本, 清理 {expired} 个过期文件")
            else:
                logs.info("[ScriptIndexManager] 后台清理完成: 无需清理")
                
        except Exception as e:
            logs.warning(f"[ScriptIndexManager] 后台清理失败: {e}")
    
    def remove_entry(self, name: str):
        """从索引中移除条目"""
        if self._index is None:
            return
        
        self._index.scripts = [s for s in self._index.scripts if s.name != name]
        self.save_index()
        logs.info(f"[ScriptIndexManager] 移除条目: {name}")
    
    def get_cleanup_status(self) -> Dict[str, Any]:
        """
        获取清理状态信息
        
        Returns:
            包含操作计数、上次清理时间等信息的字典
        """
        return {
            "operation_count": self._operation_count,
            "cleanup_interval": self.AUTO_CLEANUP_INTERVAL,
            "operations_until_cleanup": self.AUTO_CLEANUP_INTERVAL - self._operation_count,
            "last_cleanup_time": self._last_cleanup_time.isoformat() if self._last_cleanup_time else None,
            "quality_threshold": self.AUTO_CLEANUP_QUALITY_THRESHOLD,
        }
    
    def find_scripts(self, query: str = "", url: str = "", min_quality: float = 0.0) -> List[ScriptIndexEntry]:
        """
        查找脚本
        
        Args:
            query: 搜索关键词
            url: URL 匹配
            min_quality: 最低质量分数
            
        Returns:
            匹配的脚本列表
        """
        results = []
        
        for entry in self.index.scripts:
            # 质量过滤
            if entry.quality_score < min_quality:
                continue
            
            score = 0.0
            
            # URL 匹配
            if url:
                for pattern in entry.url_patterns:
                    if self._url_matches(url, pattern):
                        score += 0.5
                        break
            
            # 关键词匹配
            if query:
                query_lower = query.lower()
                for keyword in entry.keywords:
                    if keyword.lower() in query_lower or query_lower in keyword.lower():
                        score += 0.3
                        break
                
                # 描述匹配
                if query_lower in entry.description.lower():
                    score += 0.2
            
            # 如果没有查询条件，返回所有
            if not query and not url:
                score = 1.0
            
            if score > 0:
                results.append((entry, score))
        
        # 按分数排序
        results.sort(key=lambda x: (x[1], x[0].quality_score), reverse=True)
        
        return [r[0] for r in results]
    
    def get_low_quality_scripts(self, threshold: float = 0.3) -> List[ScriptIndexEntry]:
        """
        获取低质量脚本列表
        
        Args:
            threshold: 质量分数阈值
            
        Returns:
            低质量脚本列表
        """
        return [e for e in self.index.scripts if e.quality_score < threshold]
    
    def get_incomplete_scripts(self) -> List[ScriptIndexEntry]:
        """
        获取不完整的脚本（只有元数据，无代码）
        """
        return [e for e in self.index.scripts if not e.has_code]
    
    def move_to_trash(self, name: str) -> bool:
        """
        将脚本移入回收站
        
        Args:
            name: 脚本名称
            
        Returns:
            是否成功
        """
        try:
            script_path = self._get_script_path(name)
            meta_path = self._get_meta_path(name)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            trash_name = f"{name}_{timestamp}"
            
            moved = False
            
            # 移动代码文件
            if script_path.exists():
                trash_script = self.trash_dir / f"{trash_name}.ts"
                script_path.rename(trash_script)
                moved = True
            
            # 移动元数据文件
            if meta_path.exists():
                trash_meta = self.trash_dir / f"{trash_name}.meta.json"
                meta_path.rename(trash_meta)
                moved = True
            
            # 从索引中移除
            self.remove_entry(name)
            
            if moved:
                logs.info(f"[ScriptIndexManager] 脚本 {name} 已移入回收站")
            
            return moved
            
        except Exception as e:
            logs.error(f"[ScriptIndexManager] 移入回收站失败: {e}")
            return False
    
    def restore_from_trash(self, name: str) -> bool:
        """
        从回收站恢复脚本
        
        Args:
            name: 脚本名称（原始名称，不含时间戳）
            
        Returns:
            是否成功
        """
        try:
            # 查找回收站中最新的匹配文件
            best_match = None
            best_time = None
            
            for trash_file in self.trash_dir.glob(f"{name}_*.ts"):
                # 提取时间戳
                parts = trash_file.stem.split('_')
                if len(parts) >= 3:
                    time_str = '_'.join(parts[-2:])
                    try:
                        file_time = datetime.strptime(time_str, "%Y%m%d_%H%M%S")
                        if best_time is None or file_time > best_time:
                            best_match = trash_file
                            best_time = file_time
                    except ValueError:
                        continue
            
            if not best_match:
                logs.warning(f"[ScriptIndexManager] 回收站中未找到脚本: {name}")
                return False
            
            # 恢复代码文件
            script_path = self._get_script_path(name)
            best_match.rename(script_path)
            
            # 恢复元数据文件
            trash_meta = best_match.with_suffix('.meta.json')
            if trash_meta.exists():
                meta_path = self._get_meta_path(name)
                trash_meta.rename(meta_path)
            
            # 重新索引
            self.update_entry(name)
            
            logs.info(f"[ScriptIndexManager] 脚本 {name} 已从回收站恢复")
            return True
            
        except Exception as e:
            logs.error(f"[ScriptIndexManager] 从回收站恢复失败: {e}")
            return False
    
    def list_trash(self) -> List[Dict[str, Any]]:
        """
        列出回收站中的脚本
        """
        items = []
        
        for trash_file in self.trash_dir.glob("*.ts"):
            # 解析原始名称和时间戳
            stem = trash_file.stem
            
            # 尝试提取时间戳
            parts = stem.rsplit('_', 2)
            if len(parts) == 3:
                original_name = parts[0]
                time_str = f"{parts[1]}_{parts[2]}"
                try:
                    deleted_at = datetime.strptime(time_str, "%Y%m%d_%H%M%S")
                except ValueError:
                    original_name = stem
                    deleted_at = datetime.fromtimestamp(trash_file.stat().st_mtime)
            else:
                original_name = stem
                deleted_at = datetime.fromtimestamp(trash_file.stat().st_mtime)
            
            # 检查是否过期
            is_expired = (datetime.now() - deleted_at).days > TRASH_EXPIRE_DAYS
            
            items.append({
                "original_name": original_name,
                "trash_name": stem,
                "deleted_at": deleted_at.isoformat(),
                "is_expired": is_expired,
            })
        
        return items
    
    def cleanup_expired_trash(self) -> int:
        """
        清理过期的回收站文件
        
        Returns:
            清理的文件数量
        """
        cleaned = 0
        
        for item in self.list_trash():
            if item["is_expired"]:
                trash_file = self.trash_dir / f"{item['trash_name']}.ts"
                trash_meta = self.trash_dir / f"{item['trash_name']}.meta.json"
                
                if trash_file.exists():
                    trash_file.unlink()
                    cleaned += 1
                
                if trash_meta.exists():
                    trash_meta.unlink()
                
                logs.info(f"[ScriptIndexManager] 清理过期文件: {item['original_name']}")
        
        return cleaned
    
    def _url_matches(self, url: str, pattern: str) -> bool:
        """检查 URL 是否匹配模式"""
        import re
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        regex_pattern = f"^{regex_pattern}$"
        
        try:
            return bool(re.match(regex_pattern, url, re.IGNORECASE))
        except re.error:
            return pattern.lower() in url.lower()
    
    def update_execution_stats(self, name: str, success: bool) -> bool:
        """
        更新脚本执行统计
        
        Args:
            name: 脚本名称
            success: 是否执行成功
            
        Returns:
            是否更新成功
        """
        if self._index is None:
            self.load_index()
        
        for entry in self._index.scripts:
            if entry.name == name:
                # 更新使用次数
                entry.usage_count += 1
                
                # 更新成功率（滑动窗口）
                # success_rate = 成功次数 / 总次数
                # 使用指数移动平均
                alpha = 0.3  # 新结果权重
                if success:
                    entry.success_rate = alpha * 1.0 + (1 - alpha) * entry.success_rate
                else:
                    entry.success_rate = alpha * 0.0 + (1 - alpha) * entry.success_rate
                
                # 更新最后使用时间
                entry.last_used = datetime.now().isoformat()
                
                # 重新计算质量分数
                entry.quality_score = self._calculate_quality_score(entry)
                
                self.save_index()
                logs.info(f"[ScriptIndexManager] 更新执行统计: {name}, 成功率: {entry.success_rate:.2f}, 质量: {entry.quality_score:.2f}")
                return True
        
        logs.warning(f"[ScriptIndexManager] 未找到脚本: {name}")
        return False
    
    def find_similar_scripts(self, name: str, url: str = "", keywords: List[str] = None) -> List[ScriptIndexEntry]:
        """
        查找功能相似的脚本
        
        相似度判断：
        1. URL 模式匹配（权重 0.3）
        2. 关键词重叠（权重 0.3）
        3. 操作序列相似度（权重 0.25）
        4. 描述相似度（权重 0.15）
        
        Args:
            name: 当前脚本名称（排除自身）
            url: 目标 URL
            keywords: 关键词列表
            
        Returns:
            相似脚本列表（按相似度排序）
        """
        if keywords is None:
            keywords = []
        
        # 提取当前脚本的操作序列
        current_ops = self._extract_operation_sequence(name)
        
        similar = []
        
        for entry in self.index.scripts:
            # 排除自身
            if entry.name == name:
                continue
            
            similarity_score = 0.0
            
            # URL 匹配（权重 0.3）
            if url:
                for pattern in entry.url_patterns:
                    if self._url_matches(url, pattern):
                        similarity_score += 0.3
                        break
            
            # 关键词重叠（权重 0.3）
            if keywords:
                entry_keywords = set(k.lower() for k in entry.keywords)
                query_keywords = set(k.lower() for k in keywords)
                overlap = len(entry_keywords & query_keywords)
                if overlap > 0:
                    max_overlap = max(len(entry_keywords), len(query_keywords))
                    similarity_score += 0.3 * (overlap / max_overlap)
            
            # 🚀 P3-002: 操作序列相似度（权重 0.25）
            if current_ops:
                entry_ops = self._extract_operation_sequence(entry.name)
                if entry_ops:
                    ops_ratio = SequenceMatcher(None, current_ops, entry_ops).ratio()
                    similarity_score += 0.25 * ops_ratio
            
            # 描述/名称相似度（权重 0.15）
            if entry.description:
                ratio = SequenceMatcher(None, name.lower(), entry.name.lower()).ratio()
                similarity_score += 0.15 * ratio
            
            if similarity_score >= 0.3:  # 相似度阈值
                similar.append((entry, similarity_score))
        
        # 按相似度排序
        similar.sort(key=lambda x: x[1], reverse=True)
        
        return [s[0] for s in similar]
    
    def _extract_operation_sequence(self, name: str) -> List[str]:
        """
        P3-002: 从 .spec.ts 文件中提取操作序列
        
        返回操作类型列表，如 ['goto', 'fill', 'fill', 'click', 'expect']
        """
        script_path = self._get_script_path(name)
        if not script_path.exists():
            return []
        
        try:
            code = script_path.read_text(encoding='utf-8')
        except Exception:
            return []
        
        ops = []
        # 匹配 Playwright 操作
        op_patterns = [
            (r'\.goto\(', 'goto'),
            (r'\.fill\(', 'fill'),
            (r'\.click\(', 'click'),
            (r'\.hover\(', 'hover'),
            (r'\.selectOption\(', 'select'),
            (r'\.press\(', 'press'),
            (r'\.check\(', 'check'),
            (r'\.uncheck\(', 'uncheck'),
            (r'\.waitFor', 'wait'),
            (r'expect\(', 'expect'),
            (r'\.screenshot\(', 'screenshot'),
            (r'\.evaluate\(', 'evaluate'),
        ]
        
        import re as _re
        for line in code.split('\n'):
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*'):
                continue
            for pattern, op_name in op_patterns:
                if _re.search(pattern, stripped):
                    ops.append(op_name)
                    break  # 每行只取第一个操作
        
        return ops
    
    def auto_cleanup(self, keep_best: bool = True, quality_threshold: float = 0.4) -> Dict[str, Any]:
        """
        自动清理脚本库
        
        清理策略：
        1. 移除无代码文件的条目
        2. 对于相似脚本，保留质量最高的
        3. 移除质量分数低于阈值的脚本
        
        Args:
            keep_best: 是否保留相似功能中的最优脚本
            quality_threshold: 质量分数阈值
            
        Returns:
            清理结果统计
        """
        result = {
            "removed_no_code": 0,
            "removed_low_quality": 0,
            "removed_similar": 0,
            "kept_best": 0,
            "total_removed": 0,
            "details": []
        }
        
        if self._index is None:
            self.load_index()
        
        to_remove = []
        
        # 1. 移除无代码文件的条目
        for entry in self.index.scripts:
            if not entry.has_code:
                script_path = self._get_script_path(entry.name)
                if not script_path.exists():
                    to_remove.append((entry.name, "无代码文件"))
                    result["removed_no_code"] += 1
        
        # 2. 移除低质量脚本
        for entry in self.index.scripts:
            if entry.quality_score < quality_threshold and entry.has_code:
                # 检查是否有更好的替代
                similar = self.find_similar_scripts(entry.name)
                better_exists = any(s.quality_score > entry.quality_score for s in similar)
                
                if better_exists or not similar:
                    to_remove.append((entry.name, f"低质量 ({entry.quality_score:.2f})"))
                    result["removed_low_quality"] += 1
        
        # 3. 对于相似脚本，保留最优
        if keep_best:
            processed = set()
            for entry in sorted(self.index.scripts, key=lambda x: x.quality_score, reverse=True):
                if entry.name in processed or entry.name in [r[0] for r in to_remove]:
                    continue
                
                similar = self.find_similar_scripts(entry.name)
                for sim in similar:
                    if sim.name in processed or sim.name in [r[0] for r in to_remove]:
                        continue
                    
                    # 如果当前脚本质量更高，移除相似的
                    if entry.quality_score > sim.quality_score:
                        to_remove.append((sim.name, f"相似但有更优版本 ({entry.name})"))
                        result["removed_similar"] += 1
                        processed.add(sim.name)
                
                processed.add(entry.name)
        
        # 执行清理
        for name, reason in to_remove:
            if self.move_to_trash(name):
                result["details"].append({"name": name, "reason": reason})
        
        result["total_removed"] = len(result["details"])
        
        if result["total_removed"] > 0:
            logs.info(f"[ScriptIndexManager] 自动清理完成: 移除 {result['total_removed']} 个脚本")
            # 重建索引
            self.rebuild_index()
        
        return result


# 单例实例
_index_manager_instance: Optional[ScriptIndexManager] = None


def get_index_manager() -> ScriptIndexManager:
    """获取索引管理器单例"""
    global _index_manager_instance
    if _index_manager_instance is None:
        _index_manager_instance = ScriptIndexManager()
    return _index_manager_instance
