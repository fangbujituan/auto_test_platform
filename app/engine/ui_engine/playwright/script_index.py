"""
Playwright脚本索引管理器

管理Playwright脚本的索引和执行统计。

作者: yandc
创建时间: 2026-05-30
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class ScriptIndexManager:
    """Playwright脚本索引管理器."""
    
    def __init__(self, db_path: str = None):
        """
        初始化索引管理器.
        
        Args:
            db_path: SQLite数据库路径，默认使用工作区根目录下的 identifier.sqlite
        """
        if db_path is None:
            # 使用工作区根目录下的 identifier.sqlite
            workspace_root = Path(__file__).parent.parent.parent.parent
            db_path = str(workspace_root / "ai-server" / "identifier.sqlite")
        
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化数据库表."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 创建脚本索引表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playwright_scripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                description TEXT,
                tags TEXT,  -- JSON数组格式
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(name)
            )
        """)
        
        # 创建执行统计表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS script_execution_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                script_id INTEGER NOT NULL,
                execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN NOT NULL,
                duration_ms INTEGER,
                browser TEXT,
                headless BOOLEAN,
                FOREIGN KEY (script_id) REFERENCES playwright_scripts (id)
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scripts_name ON playwright_scripts(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_script_id ON script_execution_stats(script_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_stats_time ON script_execution_stats(execution_time)")
        
        conn.commit()
        conn.close()
    
    def add_script(self, name: str, path: str, description: str = "", tags: List[str] = None) -> bool:
        """
        添加或更新脚本.
        
        Args:
            name: 脚本名称
            path: 脚本路径
            description: 脚本描述
            tags: 标签列表
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        tags_json = json.dumps(tags or [])
        
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO playwright_scripts 
                (name, path, description, tags, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (name, path, description, tags_json, datetime.now().isoformat()))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"添加脚本失败: {e}")
            return False
        finally:
            conn.close()
    
    def get_script(self, name: str) -> Optional[Dict]:
        """
        获取脚本信息.
        
        Args:
            name: 脚本名称
            
        Returns:
            脚本信息字典，或None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, path, description, tags, created_at, updated_at
            FROM playwright_scripts
            WHERE name = ?
        """, (name,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "name": row[1],
                "path": row[2],
                "description": row[3],
                "tags": json.loads(row[4]) if row[4] else [],
                "created_at": row[5],
                "updated_at": row[6]
            }
        return None
    
    def list_scripts(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        列出所有脚本.
        
        Args:
            limit: 限制数量
            offset: 偏移量
            
        Returns:
            脚本列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, path, description, tags, created_at, updated_at
            FROM playwright_scripts
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        rows = cursor.fetchall()
        conn.close()
        
        scripts = []
        for row in rows:
            scripts.append({
                "id": row[0],
                "name": row[1],
                "path": row[2],
                "description": row[3],
                "tags": json.loads(row[4]) if row[4] else [],
                "created_at": row[5],
                "updated_at": row[6]
            })
        
        return scripts
    
    def search_scripts(self, keyword: str, limit: int = 50) -> List[Dict]:
        """
        搜索脚本.
        
        Args:
            keyword: 关键词
            limit: 限制数量
            
        Returns:
            匹配的脚本列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        search_pattern = f"%{keyword}%"
        cursor.execute("""
            SELECT id, name, path, description, tags, created_at, updated_at
            FROM playwright_scripts
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY updated_at DESC
            LIMIT ?
        """, (search_pattern, search_pattern, search_pattern, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        scripts = []
        for row in rows:
            scripts.append({
                "id": row[0],
                "name": row[1],
                "path": row[2],
                "description": row[3],
                "tags": json.loads(row[4]) if row[4] else [],
                "created_at": row[5],
                "updated_at": row[6]
            })
        
        return scripts
    
    def update_execution_stats(self, script_name: str, success: bool, 
                              duration_ms: int = None, browser: str = None, 
                              headless: bool = None) -> bool:
        """
        更新脚本执行统计.
        
        Args:
            script_name: 脚本名称
            success: 是否成功
            duration_ms: 执行时长（毫秒）
            browser: 浏览器类型
            headless: 是否无��模式
            
        Returns:
            是否成功
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 先获取脚本ID
        cursor.execute("SELECT id FROM playwright_scripts WHERE name = ?", (script_name,))
        row = cursor.fetchone()
        
        if not row:
            # 脚本不存在，先创建
            script_id = self._create_script_if_not_exists(script_name)
            if not script_id:
                conn.close()
                return False
        else:
            script_id = row[0]
        
        try:
            cursor.execute("""
                INSERT INTO script_execution_stats 
                (script_id, success, duration_ms, browser, headless)
                VALUES (?, ?, ?, ?, ?)
            """, (script_id, success, duration_ms, browser, headless))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"更新执行统计失败: {e}")
            return False
        finally:
            conn.close()
    
    def _create_script_if_not_exists(self, script_name: str) -> Optional[int]:
        """如果脚本不存在则创建."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO playwright_scripts (name, path, description, tags)
                VALUES (?, ?, ?, ?)
            """, (script_name, f"/playwright_scripts/tests/{script_name}.spec.ts", "", "[]"))
            
            script_id = cursor.lastrowid
            conn.commit()
            return script_id
        except Exception as e:
            print(f"创建脚本失败: {e}")
            return None
        finally:
            conn.close()
    
    def get_execution_stats(self, script_name: str, limit: int = 10) -> List[Dict]:
        """
        获取脚本执行统计.
        
        Args:
            script_name: 脚本名称
            limit: 限制数量
            
        Returns:
            执行统计列表
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT s.id, s.name, e.execution_time, e.success, e.duration_ms, e.browser, e.headless
            FROM playwright_scripts s
            LEFT JOIN script_execution_stats e ON s.id = e.script_id
            WHERE s.name = ?
            ORDER BY e.execution_time DESC
            LIMIT ?
        """, (script_name, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        stats = []
        for row in rows:
            stats.append({
                "script_id": row[0],
                "script_name": row[1],
                "execution_time": row[2],
                "success": bool(row[3]),
                "duration_ms": row[4],
                "browser": row[5],
                "headless": bool(row[6]) if row[6] is not None else None
            })
        
        return stats
    
    def get_summary_stats(self) -> Dict:
        """
        获取总体统计信息.
        
        Returns:
            统计信息字典
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总脚本数
        cursor.execute("SELECT COUNT(*) FROM playwright_scripts")
        total_scripts = cursor.fetchone()[0]
        
        # 总执行次数
        cursor.execute("SELECT COUNT(*) FROM script_execution_stats")
        total_executions = cursor.fetchone()[0]
        
        # 成功次数
        cursor.execute("SELECT COUNT(*) FROM script_execution_stats WHERE success = 1")
        success_executions = cursor.fetchone()[0]
        
        # 失败次数
        cursor.execute("SELECT COUNT(*) FROM script_execution_stats WHERE success = 0")
        failed_executions = cursor.fetchone()[0]
        
        # 最近执行时间
        cursor.execute("SELECT MAX(execution_time) FROM script_execution_stats")
        last_execution = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_scripts": total_scripts,
            "total_executions": total_executions,
            "success_executions": success_executions,
            "failed_executions": failed_executions,
            "success_rate": success_executions / total_executions if total_executions > 0 else 0,
            "last_execution": last_execution
        }


# 全局索引管理器实例
_index_manager = None

def get_index_manager() -> ScriptIndexManager:
    """获取全局索引管理器实例."""
    global _index_manager
    if _index_manager is None:
        _index_manager = ScriptIndexManager()
    return _index_manager