"""
脚本管理器（简化版）

管理录制脚本的存储、加载、匹配。
脚本执行使用 tools/playwright/executor.py
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from difflib import SequenceMatcher

from tools.debug.readlog import logs


# 统一脚本目录：playwright_scripts/
# recordings/ 子目录存放元数据
# tests/ 子目录存放实际脚本
DEFAULT_RECORDINGS_DIR = Path(__file__).parent.parent.parent / "playwright_scripts" / "recordings"
DEFAULT_SCRIPTS_DIR = Path(__file__).parent.parent.parent / "playwright_scripts" / "tests"


@dataclass
class ScriptMetadata:
    """脚本元数据"""
    name: str
    description: str
    url_patterns: List[str]
    keywords: List[str]
    variables: List[str]
    created_at: str
    updated_at: str
    usage_count: int = 0
    success_rate: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScriptMetadata":
        return cls(**data)


class ScriptManager:
    """
    脚本管理器（简化版）
    
    功能：
    - 保存脚本及其元数据
    - 加载已保存的脚本
    - 根据 URL 和任务描述匹配脚本
    
    注意：脚本执行使用 tools/playwright/executor.py
    """
    
    def __init__(self, recordings_dir: Optional[Path] = None, scripts_dir: Optional[Path] = None):
        self.recordings_dir = recordings_dir or DEFAULT_RECORDINGS_DIR
        self.scripts_dir = scripts_dir or DEFAULT_SCRIPTS_DIR
        self._ensure_dirs()
        logs.info(f"[ScriptManager] 初始化完成")
        logs.info(f"  - 元数据目录: {self.recordings_dir}")
        logs.info(f"  - 脚本目录: {self.scripts_dir}")
    
    def _ensure_dirs(self):
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_script_path(self, name: str) -> Path:
        safe_name = name.replace(' ', '_').replace('/', '_')
        # 脚本统一存放于 tests/ 目录，使用 .spec.ts 后缀
        if not safe_name.endswith('.spec.ts'):
            safe_name = f"{safe_name}.spec"
        return self.scripts_dir / f"{safe_name}.ts"
    
    def _get_meta_path(self, name: str) -> Path:
        safe_name = name.replace(' ', '_').replace('/', '_')
        return self.recordings_dir / f"{safe_name}.meta.json"
    
    def save_script(
        self,
        name: str,
        code: str,
        description: str = "",
        url_patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        variables: Optional[List[str]] = None
    ) -> bool:
        """保存脚本"""
        try:
            script_path = self._get_script_path(name)
            script_path.write_text(code, encoding='utf-8')
            
            now = datetime.now().isoformat()
            metadata = ScriptMetadata(
                name=name,
                description=description,
                url_patterns=url_patterns or [],
                keywords=keywords or [],
                variables=variables or [],
                created_at=now,
                updated_at=now,
            )
            
            meta_path = self._get_meta_path(name)
            meta_path.write_text(
                json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            logs.info(f"[ScriptManager] 脚本已保存: {name}")
            return True
            
        except Exception as e:
            logs.error(f"[ScriptManager] 保存脚本失败: {e}")
            return False
    
    def load_script(self, name: str) -> Optional[str]:
        """加载脚本代码"""
        script_path = self._get_script_path(name)
        if script_path.exists():
            return script_path.read_text(encoding='utf-8')
        return None
    
    def save_metadata(
        self,
        name: str,
        description: str = "",
        url_patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        variables: Optional[List[str]] = None
    ) -> bool:
        """单独保存元数据（不保存脚本代码）"""
        try:
            now = datetime.now().isoformat()
            
            # 尝试加载已有元数据，保留创建时间和统计数据
            existing = self.load_metadata(name)
            if existing:
                created_at = existing.created_at
                usage_count = existing.usage_count
                success_rate = existing.success_rate
            else:
                created_at = now
                usage_count = 0
                success_rate = 1.0
            
            metadata = ScriptMetadata(
                name=name,
                description=description,
                url_patterns=url_patterns or [],
                keywords=keywords or [],
                variables=variables or [],
                created_at=created_at,
                updated_at=now,
                usage_count=usage_count,
                success_rate=success_rate
            )
            
            meta_path = self._get_meta_path(name)
            meta_path.write_text(
                json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
                encoding='utf-8'
            )
            
            logs.info(f"[ScriptManager] 元数据已保存: {name}")
            return True
            
        except Exception as e:
            logs.error(f"[ScriptManager] 保存元数据失败: {e}")
            return False
    
    def load_metadata(self, name: str) -> Optional[ScriptMetadata]:
        """加载脚本元数据"""
        meta_path = self._get_meta_path(name)
        if meta_path.exists():
            try:
                data = json.loads(meta_path.read_text(encoding='utf-8'))
                return ScriptMetadata.from_dict(data)
            except Exception as e:
                logs.warning(f"[ScriptManager] 加载元数据失败: {e}")
        return None
    
    def list_scripts(self) -> List[str]:
        """列出所有已保存的脚本名称"""
        scripts = []
        # 从 tests/ 目录扫描 .spec.ts 文件
        for path in self.scripts_dir.glob("*.spec.ts"):
            # 移除 .spec.ts 后缀得到名称
            name = path.stem.replace('.spec', '')
            scripts.append(name)
        return scripts
    
    def delete_script(self, name: str) -> bool:
        """删除脚本"""
        script_path = self._get_script_path(name)
        meta_path = self._get_meta_path(name)
        
        deleted = False
        if script_path.exists():
            script_path.unlink()
            deleted = True
        
        if meta_path.exists():
            meta_path.unlink()
            deleted = True
        
        if deleted:
            logs.info(f"[ScriptManager] 脚本已删除: {name}")
        return deleted
    
    def match_by_url(self, url: str) -> List[str]:
        """根据 URL 匹配脚本"""
        matches = []
        
        for name in self.list_scripts():
            metadata = self.load_metadata(name)
            if not metadata:
                continue
            
            for pattern in metadata.url_patterns:
                if self._url_matches(url, pattern):
                    matches.append(name)
                    break
        
        return matches
    
    def match_by_keywords(self, description: str, threshold: float = 0.3) -> List[str]:
        """根据任务描述关键词匹配脚本"""
        matches = []
        
        for name in self.list_scripts():
            metadata = self.load_metadata(name)
            if not metadata:
                continue
            
            score = self._keyword_match_score(
                description.lower(),
                [k.lower() for k in metadata.keywords]
            )
            
            if score >= threshold:
                matches.append((name, score))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matches]
    
    def find_best_match(self, url: str, description: str) -> Optional[str]:
        """找到最佳匹配的脚本"""
        url_matches = self.match_by_url(url)
        if url_matches:
            return url_matches[0]
        
        keyword_matches = self.match_by_keywords(description)
        if keyword_matches:
            return keyword_matches[0]
        
        return None
    
    def update_usage(self, name: str, success: bool = True):
        """更新脚本使用统计"""
        metadata = self.load_metadata(name)
        if not metadata:
            return
        
        metadata.usage_count += 1
        
        if metadata.usage_count == 1:
            metadata.success_rate = 1.0 if success else 0.0
        else:
            old_rate = metadata.success_rate
            new_rate = 1.0 if success else 0.0
            metadata.success_rate = (old_rate * (metadata.usage_count - 1) + new_rate) / metadata.usage_count
        
        metadata.updated_at = datetime.now().isoformat()
        
        meta_path = self._get_meta_path(name)
        meta_path.write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
    
    def _url_matches(self, url: str, pattern: str) -> bool:
        """检查 URL 是否匹配模式"""
        import re
        regex_pattern = pattern.replace('*', '.*').replace('?', '.')
        regex_pattern = f"^{regex_pattern}$"
        
        try:
            return bool(re.match(regex_pattern, url, re.IGNORECASE))
        except re.error:
            return pattern.lower() in url.lower()
    
    def _keyword_match_score(self, description: str, keywords: List[str]) -> float:
        """计算关键词匹配分数"""
        if not keywords:
            return 0.0
        
        matched = 0
        for keyword in keywords:
            if keyword in description:
                matched += 1
            else:
                ratio = SequenceMatcher(None, keyword, description).ratio()
                if ratio > 0.6:
                    matched += ratio
        
        return matched / len(keywords)


_manager_instance: Optional[ScriptManager] = None


def get_manager() -> ScriptManager:
    """获取脚本管理器单例"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ScriptManager()
    return _manager_instance
