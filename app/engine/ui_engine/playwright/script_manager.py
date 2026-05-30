"""
脚本管理器（简化版）。

迁移自 ai-server/tools/playwright/script_manager.py。

负责录制脚本的存储、加载与匹配（按 URL/关键词）。脚本执行使用同目录的
executor.py。

目录布局：
    playwright_scripts/
        recordings/   — 元数据 .meta.json
        tests/        — 实际脚本 .spec.ts

作者: yandc
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.utils.debug.readlog import logs


# 项目根目录定位：app/engine/ui_engine/playwright/script_manager.py 的上 4 级
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_DEFAULT_RECORDINGS_DIR = _PROJECT_ROOT / "playwright_scripts" / "recordings"
_DEFAULT_SCRIPTS_DIR = _PROJECT_ROOT / "playwright_scripts" / "tests"


@dataclass
class ScriptMetadata:
    """脚本元数据。"""
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
    """脚本管理器（简化版）。

    功能：
    - 保存脚本及其元数据
    - 加载已保存的脚本
    - 根据 URL 和任务描述匹配脚本

    脚本执行交由 executor.py 处理。
    """

    def __init__(
        self,
        recordings_dir: Optional[Path] = None,
        scripts_dir: Optional[Path] = None,
    ):
        self.recordings_dir = recordings_dir or _DEFAULT_RECORDINGS_DIR
        self.scripts_dir = scripts_dir or _DEFAULT_SCRIPTS_DIR
        self._ensure_dirs()
        logs.info("[ScriptManager] 初始化完成")
        logs.info(f"  - 元数据目录: {self.recordings_dir}")
        logs.info(f"  - 脚本目录:   {self.scripts_dir}")

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------
    def _ensure_dirs(self) -> None:
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.scripts_dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, name: str) -> str:
        return name.replace(" ", "_").replace("/", "_")

    def _get_script_path(self, name: str) -> Path:
        safe = self._safe_name(name)
        if not safe.endswith(".spec.ts"):
            safe = f"{safe}.spec"
        return self.scripts_dir / f"{safe}.ts"

    def _get_meta_path(self, name: str) -> Path:
        return self.recordings_dir / f"{self._safe_name(name)}.meta.json"

    # ------------------------------------------------------------------
    # 写
    # ------------------------------------------------------------------
    def save_script(
        self,
        name: str,
        code: str,
        description: str = "",
        url_patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        variables: Optional[List[str]] = None,
    ) -> bool:
        """保存脚本及元数据。"""
        try:
            self._get_script_path(name).write_text(code, encoding="utf-8")

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
            self._get_meta_path(name).write_text(
                json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logs.info(f"[ScriptManager] 脚本已保存: {name}")
            return True
        except Exception as e:
            logs.error(f"[ScriptManager] 保存脚本失败: {e}")
            return False

    def save_metadata(
        self,
        name: str,
        description: str = "",
        url_patterns: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        variables: Optional[List[str]] = None,
    ) -> bool:
        """单独保存元数据，不写脚本代码。"""
        try:
            now = datetime.now().isoformat()
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
                success_rate=success_rate,
            )
            self._get_meta_path(name).write_text(
                json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logs.info(f"[ScriptManager] 元数据已保存: {name}")
            return True
        except Exception as e:
            logs.error(f"[ScriptManager] 保存元数据失败: {e}")
            return False

    def update_usage(self, name: str, success: bool = True) -> None:
        """更新使用统计。"""
        metadata = self.load_metadata(name)
        if not metadata:
            return

        metadata.usage_count += 1
        if metadata.usage_count == 1:
            metadata.success_rate = 1.0 if success else 0.0
        else:
            old_rate = metadata.success_rate
            new_rate = 1.0 if success else 0.0
            metadata.success_rate = (
                old_rate * (metadata.usage_count - 1) + new_rate
            ) / metadata.usage_count
        metadata.updated_at = datetime.now().isoformat()

        self._get_meta_path(name).write_text(
            json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def delete_script(self, name: str) -> bool:
        """删除脚本与元数据。"""
        deleted = False
        for path in (self._get_script_path(name), self._get_meta_path(name)):
            if path.exists():
                path.unlink()
                deleted = True
        if deleted:
            logs.info(f"[ScriptManager] 脚本已删除: {name}")
        return deleted

    # ------------------------------------------------------------------
    # 读
    # ------------------------------------------------------------------
    def load_script(self, name: str) -> Optional[str]:
        """加载脚本代码。"""
        path = self._get_script_path(name)
        return path.read_text(encoding="utf-8") if path.exists() else None

    def load_metadata(self, name: str) -> Optional[ScriptMetadata]:
        """加载脚本元数据。"""
        path = self._get_meta_path(name)
        if not path.exists():
            return None
        try:
            return ScriptMetadata.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except Exception as e:
            logs.warning(f"[ScriptManager] 加载元数据失败: {e}")
            return None

    def list_scripts(self) -> List[str]:
        """列出所有已保存的脚本名称。"""
        return [p.stem.replace(".spec", "") for p in self.scripts_dir.glob("*.spec.ts")]

    # ------------------------------------------------------------------
    # 匹配
    # ------------------------------------------------------------------
    def match_by_url(self, url: str) -> List[str]:
        """根据 URL 匹配脚本。"""
        matches: List[str] = []
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
        """根据任务描述关键词匹配脚本。"""
        scored: List[tuple] = []
        for name in self.list_scripts():
            metadata = self.load_metadata(name)
            if not metadata:
                continue
            score = self._keyword_match_score(
                description.lower(),
                [k.lower() for k in metadata.keywords],
            )
            if score >= threshold:
                scored.append((name, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [n for n, _ in scored]

    def find_best_match(self, url: str, description: str) -> Optional[str]:
        """找到最佳匹配的脚本。优先 URL 命中，再退化为关键词。"""
        url_matches = self.match_by_url(url)
        if url_matches:
            return url_matches[0]
        keyword_matches = self.match_by_keywords(description)
        return keyword_matches[0] if keyword_matches else None

    @staticmethod
    def _url_matches(url: str, pattern: str) -> bool:
        """通配符 / 简单 regex 匹配。失败时退化为子串匹配。"""
        regex_pattern = pattern.replace("*", ".*").replace("?", ".")
        try:
            return bool(re.match(f"^{regex_pattern}$", url, re.IGNORECASE))
        except re.error:
            return pattern.lower() in url.lower()

    @staticmethod
    def _keyword_match_score(description: str, keywords: List[str]) -> float:
        """计算关键词匹配分数（0-1）。"""
        if not keywords:
            return 0.0
        matched = 0.0
        for keyword in keywords:
            if keyword in description:
                matched += 1
            else:
                ratio = SequenceMatcher(None, keyword, description).ratio()
                if ratio > 0.6:
                    matched += ratio
        return matched / len(keywords)


# ----------------------------------------------------------------------
# 单例
# ----------------------------------------------------------------------
_manager_instance: Optional[ScriptManager] = None


def get_manager() -> ScriptManager:
    """获取脚本管理器单例。"""
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = ScriptManager()
    return _manager_instance


__all__ = ["ScriptManager", "ScriptMetadata", "get_manager"]
