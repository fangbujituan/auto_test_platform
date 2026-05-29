"""
Token 消耗统计器 v2

通过 LangChain 回调机制捕获 LLM 调用的 token 使用情况，
存储到 SQLite 数据库，支持多维度统计分析。

v2 重构：以 thread_id（LangGraph 会话 ID）为核心维度
- threads 表：会话主表（生命周期 + 聚合统计）
- token_records 表：LLM 调用明细记录（含 latency_ms、is_error）
- thread_events 表：会话事件日志（中断、恢复、状态变更等）
- 保留旧表 token_usage / case_usage 兼容
"""

import json
import sqlite3
import threading
import time
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from langchain_core.callbacks import BaseCallbackHandler

from tools.debug.readlog import logs


# ============================================================================
# ContextVar 定义
# ============================================================================

# 当前请求的 Agent 名称
_current_agent: ContextVar[Optional[str]] = ContextVar("current_agent", default=None)

# 当前用例 ID（v1 兼容）
_current_case_id: ContextVar[Optional[str]] = ContextVar("current_case_id", default=None)

# 当前 thread_id（v2 核心维度）
_current_thread_id: ContextVar[Optional[str]] = ContextVar("current_thread_id", default=None)


def set_current_agent(agent_name: str):
    """设置当前请求的 Agent 名称"""
    _current_agent.set(agent_name)


def get_current_agent() -> str:
    """获取当前请求的 Agent 名称"""
    return _current_agent.get() or "unknown"


def set_current_case_id(case_id: str):
    """设置当前用例 ID（v1 兼容）"""
    _current_case_id.set(case_id)


def get_current_case_id() -> Optional[str]:
    """获取当前用例 ID（v1 兼容）"""
    return _current_case_id.get()


def set_current_thread_id(thread_id: str):
    """设置当前 thread_id（v2 核心）"""
    _current_thread_id.set(thread_id)


def get_current_thread_id() -> Optional[str]:
    """获取当前 thread_id"""
    return _current_thread_id.get()


# ============================================================================
# 费率配置（元/千 tokens）— 扩展支持三网关
# ============================================================================

RATE_CONFIG = {
    # AIOP Gateway
    "aiop": {
        "azure/gpt-5.4": {"input": 0.001, "output": 0.002},
        "openai/gpt-4": {"input": 0.03, "output": 0.06},
    },
    # Kiro Gateway
    "kiro": {
        "claude-sonnet-4.5": {"input": 0.003, "output": 0.015},
        "claude-sonnet-4-6": {"input": 0.003, "output": 0.015},
        "deepseek-3.2": {"input": 0.001, "output": 0.002},
    },
    # AIClient2API
    "aiclient": {
        "claude-sonnet-4-6": {"input": 0, "output": 0},  # 免费（OAuth）
        "gemini-2.5-flash": {"input": 0, "output": 0},
    },
    # 旧配置兼容
    "deepseek": {
        "deepseek-chat": {"input": 0.001, "output": 0.002},
        "deepseek-reasoner": {"input": 0.001, "output": 0.002},
    },
    "zhipu": {
        "glm-4-flash": {"input": 0.0001, "output": 0.0001},
        "glm-4": {"input": 0.1, "output": 0.1},
        "glm-4-plus": {"input": 0.05, "output": 0.05},
        "glm-4-air": {"input": 0.001, "output": 0.001},
    },
    "scnet": {
        "Qwen3-30B-A3B": {"input": 0, "output": 0},
    },
}

# Token 统计配置
TOKEN_STATS_CONFIG = {
    "idle_timeout_minutes": 30,
    "max_consecutive_errors": 5,
    "retention_days": 90,
    "event_retention_days": 180,
    "soft_delete_retention_days": 30,
}


@dataclass
class TokenUsage:
    """Token 使用记录"""
    timestamp: datetime
    model_provider: str
    model_name: str
    agent_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    request_id: str
    case_id: Optional[str] = None


@dataclass
class CaseUsage:
    """用例使用记录"""
    id: str
    name: str
    agent_name: str
    thread_id: Optional[str]
    status: str  # active/completed/failed
    start_time: datetime
    end_time: Optional[datetime]
    total_tokens: int
    input_tokens: int
    output_tokens: int
    message_count: int
    estimated_cost_cny: float


class TokenCounter:
    """
    Token 统计器（单例模式）
    
    功能：
    - 通过 LangChain 回调捕获 token 使用
    - 存储到 SQLite 数据库
    - 提供多维度查询统计
    - 支持用例级别的统计和管理
    """
    
    _instance: Optional["TokenCounter"] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str | Path | None = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str | Path | None = None):
        if self._initialized:
            return
        
        # 数据库路径
        if db_path is None:
            data_dir = Path(__file__).parent.parent.parent / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            db_path = data_dir / "token_stats.db"
        
        self.db_path = Path(db_path)
        self._init_db()
        self._initialized = True
        logs.info(f"[TokenCounter] 初始化完成，数据库: {self.db_path}")
    
    def _connect(self) -> sqlite3.Connection:
        """创建数据库连接（统一配置 timeout + WAL）"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    
    def _init_db(self):
        """初始化数据库表（v1 旧表 + v2 新表）"""
        with sqlite3.connect(self.db_path, timeout=30) as conn:
            # 启用 WAL 模式，提升并发读写性能
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            # ==================== v1 旧表（保留兼容） ====================
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    model_provider TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    total_tokens INTEGER NOT NULL,
                    request_id TEXT,
                    case_id TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS case_usage (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    thread_id TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    input_tokens INTEGER NOT NULL DEFAULT 0,
                    output_tokens INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0
                )
            """)
            
            # v1 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON token_usage(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_provider ON token_usage(model_provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON token_usage(agent_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_case_id ON token_usage(case_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_case_status ON case_usage(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_case_start_time ON case_usage(start_time)")
            
            # ==================== v2 新表 ====================
            
            # threads 表 — 会话主表（以 LangGraph thread_id 为主键）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id       TEXT PRIMARY KEY,
                    name            TEXT NOT NULL DEFAULT '',
                    agent_name      TEXT NOT NULL DEFAULT 'unknown',
                    status          TEXT NOT NULL DEFAULT 'active',
                    created_at      TEXT NOT NULL,
                    updated_at      TEXT NOT NULL,
                    completed_at    TEXT,
                    total_tokens    INTEGER NOT NULL DEFAULT 0,
                    input_tokens    INTEGER NOT NULL DEFAULT 0,
                    output_tokens   INTEGER NOT NULL DEFAULT 0,
                    message_count   INTEGER NOT NULL DEFAULT 0,
                    error_count     INTEGER NOT NULL DEFAULT 0,
                    interrupt_count INTEGER NOT NULL DEFAULT 0,
                    is_deleted      INTEGER NOT NULL DEFAULT 0,
                    deleted_at      TEXT,
                    note            TEXT DEFAULT ''
                )
            """)
            
            # token_records 表 — LLM 调用明细记录
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_records (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id       TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    model_provider  TEXT NOT NULL DEFAULT 'unknown',
                    model_name      TEXT NOT NULL DEFAULT 'unknown',
                    input_tokens    INTEGER NOT NULL DEFAULT 0,
                    output_tokens   INTEGER NOT NULL DEFAULT 0,
                    total_tokens    INTEGER NOT NULL DEFAULT 0,
                    agent_name      TEXT NOT NULL DEFAULT 'unknown',
                    request_id      TEXT,
                    is_error        INTEGER NOT NULL DEFAULT 0,
                    error_message   TEXT,
                    latency_ms      INTEGER,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
            """)
            
            # thread_events 表 — 事件日志
            conn.execute("""
                CREATE TABLE IF NOT EXISTS thread_events (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id       TEXT NOT NULL,
                    timestamp       TEXT NOT NULL,
                    event_type      TEXT NOT NULL,
                    detail          TEXT DEFAULT '',
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
            """)
            
            # v2 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_created ON threads(created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_agent ON threads(agent_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_threads_deleted ON threads(is_deleted)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_thread ON token_records(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_timestamp ON token_records(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_provider ON token_records(model_provider)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_records_agent ON token_records(agent_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_thread ON thread_events(thread_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON thread_events(event_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON thread_events(timestamp)")
            
            conn.commit()
    
    # ==================== v2 核心方法 ====================
    
    def _ensure_thread(self, thread_id: str, agent_name: str = "unknown", conn: sqlite3.Connection | None = None):
        """确保 thread 记录存在，不存在则自动创建"""
        def _do(c: sqlite3.Connection):
            cursor = c.execute(
                "SELECT thread_id FROM threads WHERE thread_id = ?",
                (thread_id,)
            )
            if cursor.fetchone() is None:
                now = datetime.now().isoformat()
                auto_name = f"会话_{datetime.now().strftime('%Y%m%d_%H%M')}"
                c.execute(
                    """
                    INSERT INTO threads (thread_id, name, agent_name, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'active', ?, ?)
                    """,
                    (thread_id, auto_name, agent_name, now, now)
                )
                c.execute(
                    """
                    INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                    VALUES (?, ?, 'created', ?)
                    """,
                    (thread_id, now, json.dumps({"agent_name": agent_name}))
                )
                c.commit()
                logs.info(f"[TokenCounter] 自动创建 thread: {thread_id} ({auto_name})")
        
        if conn is not None:
            _do(conn)
        else:
            with self._connect() as c:
                _do(c)
    
    def _record_event(self, thread_id: str, event_type: str, detail: dict | None = None, conn: sqlite3.Connection | None = None):
        """记录会话事件"""
        now = datetime.now().isoformat()
        detail_json = json.dumps(detail or {}, ensure_ascii=False)
        
        def _do(c: sqlite3.Connection):
            c.execute(
                """
                INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                VALUES (?, ?, ?, ?)
                """,
                (thread_id, now, event_type, detail_json)
            )
            c.commit()
        
        if conn is not None:
            _do(conn)
        else:
            with self._connect() as c:
                _do(c)
    
    def migrate_v1_to_v2(self):
        """从 v1 (case_usage + token_usage) 迁移到 v2 (threads + token_records + thread_events)"""
        with self._connect() as conn:
            # 检查旧表是否存在
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='case_usage'"
            )
            if not cursor.fetchone():
                logs.info("[TokenCounter] 无旧表需要迁移")
                return {"migrated_threads": 0, "migrated_records": 0}
            
            # 1. 从 case_usage 迁移到 threads
            conn.execute("""
                INSERT OR IGNORE INTO threads 
                    (thread_id, name, agent_name, status, created_at, updated_at, completed_at,
                     total_tokens, input_tokens, output_tokens, message_count)
                SELECT 
                    COALESCE(thread_id, id) as thread_id,
                    name,
                    agent_name,
                    status,
                    start_time as created_at,
                    COALESCE(end_time, start_time) as updated_at,
                    end_time as completed_at,
                    total_tokens,
                    input_tokens,
                    output_tokens,
                    message_count
                FROM case_usage
            """)
            threads_count = conn.execute("SELECT changes()").fetchone()[0]
            
            # 2. 从 token_usage 迁移到 token_records
            conn.execute("""
                INSERT INTO token_records 
                    (thread_id, timestamp, model_provider, model_name, 
                     input_tokens, output_tokens, total_tokens, agent_name, request_id)
                SELECT 
                    COALESCE(case_id, 'orphan_' || id) as thread_id,
                    timestamp,
                    model_provider,
                    model_name,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    agent_name,
                    request_id
                FROM token_usage
            """)
            records_count = conn.execute("SELECT changes()").fetchone()[0]
            
            # 3. 为没有 case 的 token_usage 记录创建 orphan thread
            conn.execute("""
                INSERT OR IGNORE INTO threads (thread_id, name, agent_name, status, created_at, updated_at)
                SELECT DISTINCT
                    'orphan_' || tu.id,
                    '未关联会话_' || DATE(tu.timestamp),
                    tu.agent_name,
                    'completed',
                    tu.timestamp,
                    tu.timestamp
                FROM token_usage tu
                WHERE tu.case_id IS NULL
            """)
            
            conn.commit()
        
        logs.info(f"[TokenCounter] v1→v2 迁移完成: {threads_count} threads, {records_count} records")
        return {"migrated_threads": threads_count, "migrated_records": records_count}
    
    def check_idle_threads(self, idle_minutes: int = 30):
        """检查并标记超时中断的会话"""
        threshold = (datetime.now() - timedelta(minutes=idle_minutes)).isoformat()
        
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT thread_id FROM threads
                WHERE status = 'active' AND updated_at < ?
                """,
                (threshold,)
            )
            count = 0
            for row in cursor.fetchall():
                thread_id = row[0]
                now = datetime.now().isoformat()
                conn.execute(
                    """
                    UPDATE threads SET status = 'interrupted', 
                        interrupt_count = interrupt_count + 1, updated_at = ?
                    WHERE thread_id = ?
                    """,
                    (now, thread_id)
                )
                conn.execute(
                    """
                    INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                    VALUES (?, ?, 'timeout', ?)
                    """,
                    (thread_id, now, json.dumps({"idle_minutes": idle_minutes}))
                )
                count += 1
            conn.commit()
        
        if count > 0:
            logs.info(f"[TokenCounter] 标记 {count} 个超时中断会话")
        return count
    
    # ==================== Token 记录方法 ====================
    
    def record(
        self,
        model_provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: str | None = None,
        request_id: str | None = None,
        case_id: str | None = None,
        thread_id: str | None = None,
        latency_ms: int | None = None,
        is_error: bool = False,
        error_message: str | None = None,
    ) -> int:
        """
        记录一次 token 使用（同时写入 v1 旧表和 v2 新表）
        
        Args:
            model_provider: 模型提供商
            model_name: 模型名称
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            agent_name: Agent 名称（默认自动获取）
            request_id: 请求 ID
            case_id: 用例 ID（v1 兼容，默认自动获取）
            thread_id: 会话 ID（v2 核心，默认自动获取）
            latency_ms: LLM 响应耗时（毫秒）
            is_error: 是否为错误记录
            error_message: 错误信息
            
        Returns:
            记录 ID
        """
        if agent_name is None:
            agent_name = get_current_agent()
        
        if request_id is None:
            request_id = str(uuid.uuid4())[:8]
        
        if case_id is None:
            case_id = get_current_case_id()
        
        if thread_id is None:
            thread_id = get_current_thread_id()
        
        logs.info(f"[TokenCounter] 📝 record() 被调用 | provider={model_provider} model={model_name} | in={input_tokens} out={output_tokens} | thread_id={thread_id} | agent={agent_name} | case_id={case_id}")
        
        total_tokens = input_tokens + output_tokens
        timestamp = datetime.now().isoformat()
        
        with self._connect() as conn:
            # ---- v1: 写入 token_usage（向后兼容） ----
            cursor = conn.execute(
                """
                INSERT INTO token_usage 
                (timestamp, model_provider, model_name, agent_name, input_tokens, output_tokens, total_tokens, request_id, case_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (timestamp, model_provider, model_name, agent_name, input_tokens, output_tokens, total_tokens, request_id, case_id)
            )
            record_id = cursor.lastrowid
            
            # v1: 更新 case_usage
            if case_id:
                conn.execute(
                    """
                    UPDATE case_usage 
                    SET total_tokens = total_tokens + ?,
                        input_tokens = input_tokens + ?,
                        output_tokens = output_tokens + ?,
                        message_count = message_count + 1
                    WHERE id = ?
                    """,
                    (total_tokens, input_tokens, output_tokens, case_id)
                )
            
            # ---- v2: 写入 token_records + 更新 threads ----
            if thread_id:
                # 确保 thread 存在（复用当前连接，避免嵌套连接死锁）
                self._ensure_thread(thread_id, agent_name, conn=conn)
                
                # 写入明细记录
                conn.execute(
                    """
                    INSERT INTO token_records 
                    (thread_id, timestamp, model_provider, model_name, 
                     input_tokens, output_tokens, total_tokens, agent_name, request_id,
                     is_error, error_message, latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (thread_id, timestamp, model_provider, model_name,
                     input_tokens, output_tokens, total_tokens, agent_name, request_id,
                     1 if is_error else 0, error_message, latency_ms)
                )
                
                # 更新 threads 聚合字段
                error_inc = 1 if is_error else 0
                conn.execute(
                    """
                    UPDATE threads SET
                        total_tokens = total_tokens + ?,
                        input_tokens = input_tokens + ?,
                        output_tokens = output_tokens + ?,
                        message_count = message_count + 1,
                        error_count = error_count + ?,
                        updated_at = ?
                    WHERE thread_id = ?
                    """,
                    (total_tokens, input_tokens, output_tokens, error_inc, timestamp, thread_id)
                )
            
            conn.commit()
        
        logs.info(f"[TokenCounter] 记录: {model_provider}/{model_name} | "
                  f"input={input_tokens}, output={output_tokens}, total={total_tokens} | "
                  f"agent={agent_name}, thread={thread_id}, case={case_id}")
        
        return record_id
    
    # ==================== 用例管理方法 ====================
    
    def create_case(
        self,
        name: str,
        agent_name: str,
        thread_id: str | None = None,
    ) -> dict:
        """
        创建一个新用例
        
        Args:
            name: 用例名称
            agent_name: Agent 名称
            thread_id: LangGraph thread ID
            
        Returns:
            用例信息
        """
        case_id = str(uuid.uuid4())
        start_time = datetime.now().isoformat()
        
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO case_usage (id, name, agent_name, thread_id, status, start_time)
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (case_id, name, agent_name, thread_id, start_time)
            )
            conn.commit()
        
        logs.info(f"[TokenCounter] 创建用例: {name} (id={case_id})")
        
        return {
            "case_id": case_id,
            "name": name,
            "status": "active",
            "start_time": start_time,
            "message": "用例创建成功"
        }
    
    def get_case_current_stats(self, case_id: str) -> dict:
        """
        获取用例的当前统计（供 AI 返回给用户）
        
        Args:
            case_id: 用例 ID
            
        Returns:
            用例统计信息，包含格式化的摘要文本
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM case_usage WHERE id = ?
                """,
                (case_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {
                    "success": False,
                    "error": "用例不存在"
                }
            
            # 获取最近一条记录的 token（当前消息）
            cursor = conn.execute(
                """
                SELECT total_tokens FROM token_usage 
                WHERE case_id = ? 
                ORDER BY timestamp DESC LIMIT 1
                """,
                (case_id,)
            )
            last_record = cursor.fetchone()
            current_message_tokens = last_record["total_tokens"] if last_record else 0
            
            # 计算耗时
            start_time = datetime.fromisoformat(row["start_time"])
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            # 计算费用
            estimated_cost = self._calculate_case_cost(
                row["input_tokens"] or 0,
                row["output_tokens"] or 0,
                row["agent_name"]
            )
            
            return {
                "success": True,
                "case_id": case_id,
                "name": row["name"],
                "status": row["status"],
                "duration_seconds": duration_seconds,
                "message_count": row["message_count"] or 0,
                "current_message_tokens": current_message_tokens,
                "case_total_tokens": row["total_tokens"] or 0,
                "case_input_tokens": row["input_tokens"] or 0,
                "case_output_tokens": row["output_tokens"] or 0,
                "estimated_cost_cny": round(estimated_cost, 4),
                "summary": f"📊 本次消耗: {current_message_tokens:,} tokens\n"
                          f"📋 用例总计: {row['total_tokens'] or 0:,} tokens\n"
                          f"💰 预估费用: ¥{round(estimated_cost, 4)}"
            }
    
    def complete_case(self, case_id: str, status: str = "completed", note: str = "") -> dict:
        """
        完成用例
        
        Args:
            case_id: 用例 ID
            status: 最终状态（completed/failed）
            note: 备注
            
        Returns:
            用例完成统计
        """
        end_time = datetime.now().isoformat()
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            # 获取用例信息
            cursor = conn.execute(
                "SELECT * FROM case_usage WHERE id = ?",
                (case_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {
                    "success": False,
                    "error": "用例不存在"
                }
            
            # 更新用例状态
            conn.execute(
                """
                UPDATE case_usage 
                SET status = ?, end_time = ?
                WHERE id = ?
                """,
                (status, end_time, case_id)
            )
            conn.commit()
            
            # 计算耗时
            start_time = datetime.fromisoformat(row["start_time"])
            duration_seconds = int((datetime.now() - start_time).total_seconds())
            
            # 计算费用
            estimated_cost = self._calculate_case_cost(
                row["input_tokens"] or 0,
                row["output_tokens"] or 0,
                row["agent_name"]
            )
            
            status_icon = "✅" if status == "completed" else "❌"
            
            return {
                "success": True,
                "case_id": case_id,
                "name": row["name"],
                "status": status,
                "start_time": row["start_time"],
                "end_time": end_time,
                "duration_seconds": duration_seconds,
                "message_count": row["message_count"] or 0,
                "total_tokens": row["total_tokens"] or 0,
                "input_tokens": row["input_tokens"] or 0,
                "output_tokens": row["output_tokens"] or 0,
                "estimated_cost_cny": round(estimated_cost, 4),
                "summary": f"{status_icon} 用例完成\n"
                          f"📊 总消耗: {row['total_tokens'] or 0:,} tokens\n"
                          f"⏱️ 耗时: {self._format_duration(duration_seconds)}\n"
                          f"💰 费用: ¥{round(estimated_cost, 3)}\n"
                          f"🔄 对话轮次: {row['message_count'] or 0}"
            }
    
    def get_case(self, case_id: str) -> dict:
        """
        获取用例详情
        
        Args:
            case_id: 用例 ID
            
        Returns:
            用例详情，包含所有 token 记录
        """
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            cursor = conn.execute(
                "SELECT * FROM case_usage WHERE id = ?",
                (case_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "用例不存在"}
            
            # 获取用例下的所有 token 记录
            cursor = conn.execute(
                """
                SELECT timestamp, model_provider, model_name, 
                       input_tokens, output_tokens, total_tokens
                FROM token_usage
                WHERE case_id = ?
                ORDER BY timestamp
                """,
                (case_id,)
            )
            records = []
            for r in cursor.fetchall():
                records.append({
                    "timestamp": r["timestamp"],
                    "model_provider": r["model_provider"],
                    "model_name": r["model_name"],
                    "input_tokens": r["input_tokens"],
                    "output_tokens": r["output_tokens"],
                    "total_tokens": r["total_tokens"]
                })
            
            # 计算耗时
            duration_seconds = 0
            if row["end_time"]:
                start = datetime.fromisoformat(row["start_time"])
                end = datetime.fromisoformat(row["end_time"])
                duration_seconds = int((end - start).total_seconds())
            
            # 计算费用
            estimated_cost = self._calculate_case_cost(
                row["input_tokens"] or 0,
                row["output_tokens"] or 0,
                row["agent_name"]
            )
            
            return {
                "success": True,
                "id": row["id"],
                "name": row["name"],
                "agent_name": row["agent_name"],
                "thread_id": row["thread_id"],
                "status": row["status"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "duration_seconds": duration_seconds,
                "total_tokens": row["total_tokens"] or 0,
                "input_tokens": row["input_tokens"] or 0,
                "output_tokens": row["output_tokens"] or 0,
                "message_count": row["message_count"] or 0,
                "estimated_cost_cny": round(estimated_cost, 4),
                "records": records
            }
    
    def get_cases(
        self,
        status: str | None = None,
        agent: str | None = None,
        date: str | None = None,
        sort_by: str = "date",
        order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        获取用例列表
        
        Args:
            status: 状态筛选
            agent: Agent 筛选
            date: 日期筛选
            sort_by: 排序字段（tokens/time/date）
            order: 排序方向（asc/desc）
            page: 页码
            page_size: 每页条数
            
        Returns:
            用例列表
        """
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        conditions = []
        params = []
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        if agent:
            conditions.append("agent_name = ?")
            params.append(agent)
        if date:
            conditions.append("DATE(start_time) = ?")
            params.append(date)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 排序字段映射
        sort_map = {
            "tokens": "total_tokens",
            "time": "start_time",
            "date": "start_time"
        }
        order_field = sort_map.get(sort_by, "start_time")
        order_dir = "DESC" if order.lower() == "desc" else "ASC"
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            # 获取总数
            cursor = conn.execute(
                f"SELECT COUNT(*) as total FROM case_usage WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()["total"]
            
            # 获取用例列表
            cursor = conn.execute(
                f"""
                SELECT id, name, agent_name, status, start_time, end_time,
                       total_tokens, message_count
                FROM case_usage
                WHERE {where_clause}
                ORDER BY {order_field} {order_dir}
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset]
            )
            
            cases = []
            for row in cursor.fetchall():
                # 计算耗时
                duration_seconds = 0
                if row["end_time"]:
                    start = datetime.fromisoformat(row["start_time"])
                    end = datetime.fromisoformat(row["end_time"])
                    duration_seconds = int((end - start).total_seconds())
                elif row["status"] == "active":
                    start = datetime.fromisoformat(row["start_time"])
                    duration_seconds = int((datetime.now() - start).total_seconds())
                
                # 计算费用
                cursor2 = conn.execute(
                    "SELECT input_tokens, output_tokens FROM case_usage WHERE id = ?",
                    (row["id"],)
                )
                case_row = cursor2.fetchone()
                estimated_cost = self._calculate_case_cost(
                    case_row["input_tokens"] or 0,
                    case_row["output_tokens"] or 0,
                    row["agent_name"]
                ) if case_row else 0
                
                cases.append({
                    "id": row["id"],
                    "name": row["name"],
                    "agent_name": row["agent_name"],
                    "status": row["status"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "duration_seconds": duration_seconds,
                    "total_tokens": row["total_tokens"] or 0,
                    "message_count": row["message_count"] or 0,
                    "estimated_cost_cny": round(estimated_cost, 4)
                })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "cases": cases
        }
    
    def update_case_name(self, case_id: str, name: str) -> dict:
        """
        更新用例名称
        
        Args:
            case_id: 用例 ID
            name: 新名称
            
        Returns:
            更新结果
        """
        with self._connect() as conn:
            cursor = conn.execute(
                "UPDATE case_usage SET name = ? WHERE id = ?",
                (name, case_id)
            )
            conn.commit()
            
            if cursor.rowcount == 0:
                return {"success": False, "error": "用例不存在"}
        
        return {
            "success": True,
            "case_id": case_id,
            "name": name,
            "message": "用例名称更新成功"
        }
    
    # ==================== v2 Thread 管理方法 ====================
    
    def get_thread(self, thread_id: str) -> dict:
        """获取会话详情（v2）"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "会话不存在"}
            
            # 计算时长
            created = datetime.fromisoformat(row["created_at"])
            if row["completed_at"]:
                duration = int((datetime.fromisoformat(row["completed_at"]) - created).total_seconds())
            elif row["status"] == "active":
                duration = int((datetime.now() - created).total_seconds())
            else:
                duration = int((datetime.fromisoformat(row["updated_at"]) - created).total_seconds())
            
            # 模型分布
            cursor = conn.execute(
                """
                SELECT model_provider, model_name, COUNT(*) as call_count,
                       SUM(total_tokens) as total_tokens
                FROM token_records WHERE thread_id = ? AND is_error = 0
                GROUP BY model_provider, model_name ORDER BY total_tokens DESC
                """,
                (thread_id,)
            )
            total_t = row["total_tokens"] or 1
            model_breakdown = []
            for r in cursor.fetchall():
                model_breakdown.append({
                    "provider": r["model_provider"],
                    "model": r["model_name"],
                    "call_count": r["call_count"],
                    "total_tokens": r["total_tokens"] or 0,
                    "percentage": round((r["total_tokens"] or 0) / total_t * 100, 1)
                })
            
            # 平均延迟
            cursor = conn.execute(
                "SELECT AVG(latency_ms) as avg_lat FROM token_records WHERE thread_id = ? AND latency_ms IS NOT NULL",
                (thread_id,)
            )
            avg_lat = cursor.fetchone()["avg_lat"]
            
            # 费用估算
            cost = self._calculate_thread_cost(thread_id)
            
            msg_count = row["message_count"] or 1
            
            return {
                "success": True,
                "thread_id": row["thread_id"],
                "name": row["name"],
                "agent_name": row["agent_name"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "completed_at": row["completed_at"],
                "is_deleted": bool(row["is_deleted"]),
                "stats": {
                    "total_tokens": row["total_tokens"] or 0,
                    "input_tokens": row["input_tokens"] or 0,
                    "output_tokens": row["output_tokens"] or 0,
                    "message_count": row["message_count"] or 0,
                    "error_count": row["error_count"] or 0,
                    "interrupt_count": row["interrupt_count"] or 0,
                    "duration_seconds": duration,
                    "duration_display": self._format_duration(duration),
                    "avg_tokens_per_message": round((row["total_tokens"] or 0) / msg_count),
                    "avg_latency_ms": round(avg_lat) if avg_lat else None,
                    "estimated_cost_cny": cost,
                },
                "model_breakdown": model_breakdown,
            }
    
    def get_thread_records(self, thread_id: str, page: int = 1, page_size: int = 20) -> dict:
        """获取会话的 Token 明细记录"""
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT COUNT(*) as total FROM token_records WHERE thread_id = ?",
                (thread_id,)
            )
            total = cursor.fetchone()["total"]
            cursor = conn.execute(
                """
                SELECT id, timestamp, model_provider, model_name,
                       input_tokens, output_tokens, total_tokens, latency_ms, is_error, error_message
                FROM token_records WHERE thread_id = ?
                ORDER BY timestamp DESC LIMIT ? OFFSET ?
                """,
                (thread_id, page_size, offset)
            )
            records = [dict(r) for r in cursor.fetchall()]
            for r in records:
                r["is_error"] = bool(r["is_error"])
        return {"thread_id": thread_id, "total": total, "page": page, "page_size": page_size, "records": records}
    
    def get_thread_events(self, thread_id: str) -> dict:
        """获取会话事件日志"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, timestamp, event_type, detail FROM thread_events WHERE thread_id = ? ORDER BY timestamp",
                (thread_id,)
            )
            events = []
            for r in cursor.fetchall():
                evt = dict(r)
                try:
                    evt["detail"] = json.loads(evt["detail"]) if evt["detail"] else {}
                except (json.JSONDecodeError, TypeError):
                    evt["detail"] = {}
                events.append(evt)
        return {"thread_id": thread_id, "events": events}
    
    def create_or_get_thread(self, thread_id: str, agent_name: str = "unknown", name: str = "") -> dict:
        """创建或获取会话（前端调用）"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "thread_id": row["thread_id"],
                    "name": row["name"],
                    "agent_name": row["agent_name"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "is_new": False,
                }
            
            now = datetime.now().isoformat()
            if not name:
                name = f"会话_{datetime.now().strftime('%Y%m%d_%H%M')}"
            conn.execute(
                """
                INSERT INTO threads (thread_id, name, agent_name, status, created_at, updated_at)
                VALUES (?, ?, ?, 'active', ?, ?)
                """,
                (thread_id, name, agent_name, now, now)
            )
            conn.execute(
                """
                INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                VALUES (?, ?, 'created', ?)
                """,
                (thread_id, now, json.dumps({"agent_name": agent_name}))
            )
            conn.commit()
        
        return {
            "thread_id": thread_id,
            "name": name,
            "agent_name": agent_name,
            "status": "active",
            "created_at": now,
            "is_new": True,
        }
    
    def update_thread(self, thread_id: str, name: str | None = None, status: str | None = None, note: str | None = None) -> dict:
        """更新会话信息"""
        with self._connect() as conn:
            cursor = conn.execute("SELECT thread_id, name FROM threads WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "会话不存在"}
            
            now = datetime.now().isoformat()
            updates = []
            params = []
            
            if name is not None:
                old_name = row[1]
                updates.append("name = ?")
                params.append(name)
                self._record_event(thread_id, "renamed", {"old_name": old_name, "new_name": name}, conn=conn)
            
            if status is not None:
                updates.append("status = ?")
                params.append(status)
                if status in ("completed", "failed"):
                    updates.append("completed_at = ?")
                    params.append(now)
                    self._record_event(thread_id, status, {"total_tokens": 0}, conn=conn)
            
            if note is not None:
                updates.append("note = ?")
                params.append(note)
            
            updates.append("updated_at = ?")
            params.append(now)
            params.append(thread_id)
            
            conn.execute(f"UPDATE threads SET {', '.join(updates)} WHERE thread_id = ?", params)
            conn.commit()
        
        return {"success": True, "thread_id": thread_id, "message": "更新成功"}
    
    def delete_thread(self, thread_id: str) -> dict:
        """软删除会话"""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute("SELECT thread_id FROM threads WHERE thread_id = ?", (thread_id,))
            if not cursor.fetchone():
                return {"success": False, "error": "会话不存在"}
            conn.execute(
                "UPDATE threads SET is_deleted = 1, deleted_at = ?, updated_at = ? WHERE thread_id = ?",
                (now, now, thread_id)
            )
            conn.execute(
                "INSERT INTO thread_events (thread_id, timestamp, event_type, detail) VALUES (?, ?, 'deleted', ?)",
                (thread_id, now, json.dumps({"deleted_by": "user"}))
            )
            conn.commit()
        return {"success": True, "thread_id": thread_id, "message": "会话已删除（统计数据保留）"}
    
    def restore_thread(self, thread_id: str) -> dict:
        """恢复已删除会话"""
        now = datetime.now().isoformat()
        with self._connect() as conn:
            cursor = conn.execute("SELECT is_deleted FROM threads WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if not row:
                return {"success": False, "error": "会话不存在"}
            if not row[0]:
                return {"success": False, "error": "会话未被删除"}
            conn.execute(
                "UPDATE threads SET is_deleted = 0, deleted_at = NULL, updated_at = ? WHERE thread_id = ?",
                (now, thread_id)
            )
            conn.execute(
                "INSERT INTO thread_events (thread_id, timestamp, event_type, detail) VALUES (?, ?, 'restored', '{}')",
                (thread_id, now)
            )
            conn.commit()
        return {"success": True, "thread_id": thread_id, "message": "会话已恢复"}
    
    def get_threads(
        self,
        status: str | None = None,
        agent: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        keyword: str | None = None,
        include_deleted: bool = False,
        sort_by: str = "created_at",
        order: str = "desc",
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取会话列表（v2）"""
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        conditions = []
        params = []
        
        if not include_deleted:
            conditions.append("is_deleted = 0")
        if status:
            conditions.append("status = ?")
            params.append(status)
        if agent:
            conditions.append("agent_name = ?")
            params.append(agent)
        if date_from:
            conditions.append("DATE(created_at) >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("DATE(created_at) <= ?")
            params.append(date_to)
        if keyword:
            conditions.append("name LIKE ?")
            params.append(f"%{keyword}%")
        
        where = " AND ".join(conditions) if conditions else "1=1"
        
        sort_map = {"created_at": "created_at", "updated_at": "updated_at", "total_tokens": "total_tokens", "duration": "created_at"}
        order_field = sort_map.get(sort_by, "created_at")
        order_dir = "DESC" if order.lower() == "desc" else "ASC"
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT COUNT(*) as total FROM threads WHERE {where}", params)
            total = cursor.fetchone()["total"]
            
            cursor = conn.execute(
                f"""
                SELECT thread_id, name, agent_name, status, created_at, updated_at,
                       total_tokens, message_count, error_count, interrupt_count, is_deleted
                FROM threads WHERE {where}
                ORDER BY {order_field} {order_dir}
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset]
            )
            
            threads = []
            for row in cursor.fetchall():
                created = datetime.fromisoformat(row["created_at"])
                updated = datetime.fromisoformat(row["updated_at"])
                duration = int((updated - created).total_seconds())
                cost = self._calculate_thread_cost(row["thread_id"])
                
                threads.append({
                    "thread_id": row["thread_id"],
                    "name": row["name"],
                    "agent_name": row["agent_name"],
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "total_tokens": row["total_tokens"] or 0,
                    "message_count": row["message_count"] or 0,
                    "error_count": row["error_count"] or 0,
                    "interrupt_count": row["interrupt_count"] or 0,
                    "duration_seconds": duration,
                    "duration_display": self._format_duration(duration),
                    "estimated_cost_cny": cost,
                    "is_deleted": bool(row["is_deleted"]),
                })
        
        return {"total": total, "page": page, "page_size": page_size, "threads": threads}
    
    def get_global_overview(self, period: str = "today") -> dict:
        """获取全局概览统计（v2，基于 threads + token_records）"""
        start_time = self._get_period_start(period)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            # 基于 token_records 的总体统计
            time_filter = "WHERE timestamp >= ?" if start_time else ""
            time_params = [start_time] if start_time else []
            
            cursor = conn.execute(
                f"""
                SELECT SUM(total_tokens) as total_tokens,
                       SUM(input_tokens) as input_tokens,
                       SUM(output_tokens) as output_tokens,
                       COUNT(*) as total_requests,
                       SUM(is_error) as total_errors,
                       AVG(latency_ms) as avg_latency_ms
                FROM token_records {time_filter}
                """,
                time_params
            )
            rec = cursor.fetchone()
            
            # 基于 threads 的会话统计
            thread_filter = "WHERE created_at >= ?" if start_time else ""
            cursor = conn.execute(
                f"""
                SELECT COUNT(*) as total_threads,
                       SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active_threads,
                       SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_threads,
                       SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed_threads,
                       SUM(CASE WHEN status='interrupted' THEN 1 ELSE 0 END) as interrupted_threads,
                       SUM(interrupt_count) as total_interrupts,
                       AVG(message_count) as avg_messages
                FROM threads {thread_filter}
                """,
                time_params
            )
            th = cursor.fetchone()
            
            total_tokens = rec["total_tokens"] or 0
            total_requests = rec["total_requests"] or 0
            total_threads = th["total_threads"] or 0
            total_errors = rec["total_errors"] or 0
            
            # 按 Agent 分布
            cursor = conn.execute(
                f"""
                SELECT agent_name as agent, COUNT(DISTINCT thread_id) as thread_count,
                       SUM(total_tokens) as total_tokens, COUNT(*) as request_count,
                       SUM(is_error) as errors
                FROM token_records {time_filter}
                GROUP BY agent_name ORDER BY total_tokens DESC
                """,
                time_params
            )
            by_agent = []
            for r in cursor.fetchall():
                req = r["request_count"] or 1
                by_agent.append({
                    "agent": r["agent"],
                    "thread_count": r["thread_count"] or 0,
                    "total_tokens": r["total_tokens"] or 0,
                    "request_count": r["request_count"] or 0,
                    "percentage": round((r["total_tokens"] or 0) / max(total_tokens, 1) * 100, 1),
                    "error_rate": round((r["errors"] or 0) / req * 100, 1),
                })
            
            # 按模型分布
            cursor = conn.execute(
                f"""
                SELECT model_provider as provider, model_name as model,
                       COUNT(*) as request_count, SUM(total_tokens) as total_tokens,
                       AVG(latency_ms) as avg_latency_ms
                FROM token_records {time_filter}
                GROUP BY model_provider, model_name ORDER BY total_tokens DESC
                """,
                time_params
            )
            by_model = []
            for r in cursor.fetchall():
                by_model.append({
                    "provider": r["provider"],
                    "model": r["model"],
                    "request_count": r["request_count"] or 0,
                    "total_tokens": r["total_tokens"] or 0,
                    "percentage": round((r["total_tokens"] or 0) / max(total_tokens, 1) * 100, 1),
                    "avg_latency_ms": round(r["avg_latency_ms"]) if r["avg_latency_ms"] else None,
                })
            
            # 费用
            cost = self._calculate_cost_v2(start_time)
            
            return {
                "period": period,
                "period_start": start_time,
                "summary": {
                    "total_tokens": total_tokens,
                    "input_tokens": rec["input_tokens"] or 0,
                    "output_tokens": rec["output_tokens"] or 0,
                    "total_requests": total_requests,
                    "total_threads": total_threads,
                    "active_threads": th["active_threads"] or 0,
                    "completed_threads": th["completed_threads"] or 0,
                    "failed_threads": th["failed_threads"] or 0,
                    "interrupted_threads": th["interrupted_threads"] or 0,
                    "total_errors": total_errors,
                    "total_interrupts": th["total_interrupts"] or 0,
                    "estimated_cost_cny": cost,
                    "avg_tokens_per_thread": round(total_tokens / max(total_threads, 1)),
                    "avg_messages_per_thread": round(th["avg_messages"] or 0, 1),
                    "error_rate": round(total_errors / max(total_requests, 1) * 100, 1),
                },
                "by_agent": by_agent,
                "by_model": by_model,
            }
    
    def get_global_trend(self, days: int = 7, granularity: str = "day") -> dict:
        """获取全局趋势数据（v2，基于 token_records）"""
        start_time = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            if granularity == "hour":
                time_expr = "strftime('%Y-%m-%d %H:00:00', timestamp)"
            else:
                time_expr = "strftime('%Y-%m-%d', timestamp)"
            
            cursor = conn.execute(
                f"""
                SELECT {time_expr} as time_bucket,
                       SUM(total_tokens) as total_tokens,
                       SUM(input_tokens) as input_tokens,
                       SUM(output_tokens) as output_tokens,
                       COUNT(*) as request_count,
                       COUNT(DISTINCT thread_id) as thread_count,
                       SUM(is_error) as error_count,
                       AVG(latency_ms) as avg_latency_ms
                FROM token_records WHERE timestamp >= ?
                GROUP BY time_bucket ORDER BY time_bucket
                """,
                (start_time,)
            )
            trend = []
            for r in cursor.fetchall():
                trend.append({
                    "time_bucket": r["time_bucket"],
                    "total_tokens": r["total_tokens"] or 0,
                    "input_tokens": r["input_tokens"] or 0,
                    "output_tokens": r["output_tokens"] or 0,
                    "request_count": r["request_count"] or 0,
                    "thread_count": r["thread_count"] or 0,
                    "error_count": r["error_count"] or 0,
                    "avg_latency_ms": round(r["avg_latency_ms"]) if r["avg_latency_ms"] else None,
                })
        
        return {"granularity": granularity, "trend": trend}
    
    def get_global_cost(self, period: str = "month") -> dict:
        """获取全局费用报表（v2，基于 token_records）"""
        start_time = self._get_period_start(period)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            time_filter = "WHERE timestamp >= ?" if start_time else ""
            time_params = [start_time] if start_time else []
            
            cursor = conn.execute(
                f"""
                SELECT model_provider, model_name,
                       SUM(input_tokens) as input_tokens,
                       SUM(output_tokens) as output_tokens
                FROM token_records {time_filter}
                GROUP BY model_provider, model_name
                """,
                time_params
            )
            
            breakdown = []
            total_cost = 0.0
            for r in cursor.fetchall():
                rate = self._get_rate(r["model_provider"], r["model_name"])
                inp = r["input_tokens"] or 0
                out = r["output_tokens"] or 0
                ic = (inp / 1000) * rate["input"]
                oc = (out / 1000) * rate["output"]
                mc = ic + oc
                item = {
                    "provider": r["model_provider"],
                    "model": r["model_name"],
                    "input_tokens": inp,
                    "output_tokens": out,
                    "input_rate": rate["input"],
                    "output_rate": rate["output"],
                    "input_cost": round(ic, 4),
                    "output_cost": round(oc, 4),
                    "total_cost": round(mc, 4),
                }
                if rate["input"] == 0 and rate["output"] == 0:
                    item["note"] = "免费额度内"
                breakdown.append(item)
                total_cost += mc
        
        return {"period": period, "currency": "CNY", "breakdown": breakdown, "total_cost": round(total_cost, 4)}
    
    def get_global_records(
        self,
        thread_id: str | None = None,
        date: str | None = None,
        provider: str | None = None,
        agent: str | None = None,
        is_error: bool | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """获取全局明细记录（v2，基于 token_records）"""
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        conditions = []
        params = []
        if thread_id:
            conditions.append("r.thread_id = ?")
            params.append(thread_id)
        if date:
            conditions.append("DATE(r.timestamp) = ?")
            params.append(date)
        if provider:
            conditions.append("r.model_provider = ?")
            params.append(provider)
        if agent:
            conditions.append("r.agent_name = ?")
            params.append(agent)
        if is_error is not None:
            conditions.append("r.is_error = ?")
            params.append(1 if is_error else 0)
        
        where = " AND ".join(conditions) if conditions else "1=1"
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(f"SELECT COUNT(*) as total FROM token_records r WHERE {where}", params)
            total = cursor.fetchone()["total"]
            
            cursor = conn.execute(
                f"""
                SELECT r.id, r.thread_id, r.timestamp, r.model_provider, r.model_name,
                       r.agent_name, r.input_tokens, r.output_tokens, r.total_tokens,
                       r.latency_ms, r.is_error, r.error_message,
                       t.name as thread_name
                FROM token_records r
                LEFT JOIN threads t ON r.thread_id = t.thread_id
                WHERE {where}
                ORDER BY r.timestamp DESC LIMIT ? OFFSET ?
                """,
                params + [page_size, offset]
            )
            records = []
            for r in cursor.fetchall():
                rec = dict(r)
                rec["is_error"] = bool(rec["is_error"])
                records.append(rec)
        
        return {"total": total, "page": page, "page_size": page_size, "records": records}
    
    def get_last_input_tokens(self, thread_id: str) -> int | None:
        """获取该 thread 最近一次 LLM 调用的 input_tokens（即真实的 prompt token 数）"""
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT input_tokens FROM token_records
                WHERE thread_id = ? AND is_error = 0
                ORDER BY timestamp DESC LIMIT 1
                """,
                (thread_id,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def _calculate_thread_cost(self, thread_id: str) -> float:
        """计算单个会话的费用"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT model_provider, model_name,
                       SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                FROM token_records WHERE thread_id = ?
                GROUP BY model_provider, model_name
                """,
                (thread_id,)
            )
            total_cost = 0.0
            for r in cursor.fetchall():
                rate = self._get_rate(r["model_provider"], r["model_name"])
                total_cost += ((r["input_tokens"] or 0) / 1000) * rate["input"]
                total_cost += ((r["output_tokens"] or 0) / 1000) * rate["output"]
        return round(total_cost, 4)
    
    def _calculate_cost_v2(self, start_time: str | None) -> float:
        """计算全局费用（v2，基于 token_records）"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            time_filter = "WHERE timestamp >= ?" if start_time else ""
            time_params = [start_time] if start_time else []
            cursor = conn.execute(
                f"""
                SELECT model_provider, model_name,
                       SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                FROM token_records {time_filter}
                GROUP BY model_provider, model_name
                """,
                time_params
            )
            total_cost = 0.0
            for r in cursor.fetchall():
                rate = self._get_rate(r["model_provider"], r["model_name"])
                total_cost += ((r["input_tokens"] or 0) / 1000) * rate["input"]
                total_cost += ((r["output_tokens"] or 0) / 1000) * rate["output"]
        return round(total_cost, 4)
    
    # ==================== v1 用例统计方法（保留兼容） ====================
    
    def get_case_stats(self, period: str = "today") -> dict:
        """
        获取用例统计
        
        Args:
            period: 统计周期
            
        Returns:
            用例统计信息
        """
        start_time = self._get_period_start(period)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as total_cases,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_cases,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_cases,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_cases,
                        AVG(total_tokens) as avg_tokens,
                        SUM(total_tokens) as total_tokens
                    FROM case_usage
                    WHERE start_time >= ?
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT 
                        COUNT(*) as total_cases,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_cases,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_cases,
                        SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_cases,
                        AVG(total_tokens) as avg_tokens,
                        SUM(total_tokens) as total_tokens
                    FROM case_usage
                    """
                )
            
            row = cursor.fetchone()
            
            total = row["total_cases"] or 0
            completed = row["completed_cases"] or 0
            success_rate = round(completed / total * 100, 1) if total > 0 else 0
            
            # 获取最大消耗用例
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT id, name, total_tokens
                    FROM case_usage
                    WHERE start_time >= ?
                    ORDER BY total_tokens DESC
                    LIMIT 1
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, name, total_tokens
                    FROM case_usage
                    ORDER BY total_tokens DESC
                    LIMIT 1
                    """
                )
            
            max_case = cursor.fetchone()
            max_tokens_case = None
            if max_case:
                max_tokens_case = {
                    "id": max_case["id"],
                    "name": max_case["name"],
                    "total_tokens": max_case["total_tokens"] or 0
                }
            
            return {
                "total_cases": total,
                "completed_cases": completed,
                "failed_cases": row["failed_cases"] or 0,
                "active_cases": row["active_cases"] or 0,
                "success_rate": success_rate,
                "avg_tokens_per_case": round(row["avg_tokens"] or 0, 1),
                "total_tokens": row["total_tokens"] or 0,
                "max_tokens_case": max_tokens_case
            }
    
    # ==================== 统计查询方法 ====================
    
    def get_overview(self, period: str = "today") -> dict:
        """
        获取统计概览
        
        Args:
            period: 统计周期 (today/week/month/all)
        """
        start_time = self._get_period_start(period)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            # 总体统计
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT 
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp >= ?
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT 
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    """
                )
            summary_row = cursor.fetchone()
            
            summary = {
                "total_tokens": summary_row["total_tokens"] or 0,
                "input_tokens": summary_row["input_tokens"] or 0,
                "output_tokens": summary_row["output_tokens"] or 0,
                "request_count": summary_row["request_count"] or 0,
            }
            
            # 计算预估费用
            summary["estimated_cost_cny"] = self._calculate_cost(
                summary["input_tokens"], 
                summary["output_tokens"],
                start_time
            )
            
            # 按提供商统计
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT 
                        model_provider as provider,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp >= ?
                    GROUP BY model_provider
                    ORDER BY total_tokens DESC
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT 
                        model_provider as provider,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    GROUP BY model_provider
                    ORDER BY total_tokens DESC
                    """
                )
            by_provider = []
            total = summary["total_tokens"] or 1
            for row in cursor.fetchall():
                by_provider.append({
                    "provider": row["provider"],
                    "total_tokens": row["total_tokens"] or 0,
                    "input_tokens": row["input_tokens"] or 0,
                    "output_tokens": row["output_tokens"] or 0,
                    "request_count": row["request_count"] or 0,
                    "percentage": round((row["total_tokens"] or 0) / total * 100, 1)
                })
            
            # 按 Agent 统计
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT 
                        agent_name as agent,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp >= ?
                    GROUP BY agent_name
                    ORDER BY total_tokens DESC
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT 
                        agent_name as agent,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    GROUP BY agent_name
                    ORDER BY total_tokens DESC
                    """
                )
            by_agent = []
            for row in cursor.fetchall():
                by_agent.append({
                    "agent": row["agent"],
                    "total_tokens": row["total_tokens"] or 0,
                    "input_tokens": row["input_tokens"] or 0,
                    "output_tokens": row["output_tokens"] or 0,
                    "request_count": row["request_count"] or 0,
                    "percentage": round((row["total_tokens"] or 0) / total * 100, 1)
                })
            
            # 用例统计
            case_stats = self.get_case_stats(period)
            
            # 添加用例统计到 summary
            summary["case_count"] = case_stats["total_cases"]
            summary["completed_cases"] = case_stats["completed_cases"]
            summary["success_rate"] = case_stats["success_rate"]
        
        return {
            "period": period,
            "summary": summary,
            "by_provider": by_provider,
            "by_agent": by_agent,
            "case_stats": case_stats,
        }
    
    def get_trend(self, days: int = 7, granularity: str = "day") -> dict:
        """
        获取趋势数据
        
        Args:
            days: 查询天数
            granularity: 粒度 (hour/day)
        """
        start_time = (datetime.now() - timedelta(days=days)).isoformat()
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            if granularity == "hour":
                # 按小时统计
                cursor = conn.execute(
                    """
                    SELECT 
                        strftime('%Y-%m-%d %H:00:00', timestamp) as time_bucket,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp >= ?
                    GROUP BY time_bucket
                    ORDER BY time_bucket
                    """,
                    (start_time,)
                )
                trend = []
                for row in cursor.fetchall():
                    trend.append({
                        "time": row["time_bucket"],
                        "total_tokens": row["total_tokens"] or 0,
                        "input_tokens": row["input_tokens"] or 0,
                        "output_tokens": row["output_tokens"] or 0,
                        "request_count": row["request_count"] or 0
                    })
            else:
                # 按天统计
                cursor = conn.execute(
                    """
                    SELECT 
                        strftime('%Y-%m-%d', timestamp) as date,
                        SUM(total_tokens) as total_tokens,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens,
                        COUNT(*) as request_count
                    FROM token_usage
                    WHERE timestamp >= ?
                    GROUP BY date
                    ORDER BY date
                    """,
                    (start_time,)
                )
                trend = []
                for row in cursor.fetchall():
                    trend.append({
                        "date": row["date"],
                        "total_tokens": row["total_tokens"] or 0,
                        "input_tokens": row["input_tokens"] or 0,
                        "output_tokens": row["output_tokens"] or 0,
                        "request_count": row["request_count"] or 0
                    })
        
        return {
            "granularity": granularity,
            "trend": trend,
        }
    
    def get_records(
        self,
        date: str | None = None,
        provider: str | None = None,
        agent: str | None = None,
        case_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """
        获取详细记录列表
        
        Args:
            date: 日期筛选 (YYYY-MM-DD)
            provider: 模型提供商筛选
            agent: Agent 筛选
            case_id: 用例 ID 筛选
            page: 页码
            page_size: 每页条数
        """
        page_size = min(page_size, 100)
        offset = (page - 1) * page_size
        
        conditions = []
        params = []
        
        if date:
            conditions.append("DATE(timestamp) = ?")
            params.append(date)
        if provider:
            conditions.append("model_provider = ?")
            params.append(provider)
        if agent:
            conditions.append("agent_name = ?")
            params.append(agent)
        if case_id:
            conditions.append("case_id = ?")
            params.append(case_id)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            # 获取总数
            cursor = conn.execute(
                f"SELECT COUNT(*) as total FROM token_usage WHERE {where_clause}",
                params
            )
            total = cursor.fetchone()["total"]
            
            # 获取记录（关联 case_name）
            cursor = conn.execute(
                f"""
                SELECT 
                    t.id, t.timestamp, t.model_provider, t.model_name, t.agent_name,
                    t.input_tokens, t.output_tokens, t.total_tokens, t.case_id,
                    c.name as case_name
                FROM token_usage t
                LEFT JOIN case_usage c ON t.case_id = c.id
                WHERE {where_clause}
                ORDER BY t.timestamp DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset]
            )
            records = []
            for row in cursor.fetchall():
                records.append({
                    "id": row["id"],
                    "timestamp": row["timestamp"],
                    "model_provider": row["model_provider"],
                    "model_name": row["model_name"],
                    "agent_name": row["agent_name"],
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "total_tokens": row["total_tokens"],
                    "case_id": row["case_id"],
                    "case_name": row["case_name"]
                })
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": records,
        }
    
    def get_cost(self, period: str = "month") -> dict:
        """
        获取费用估算
        
        Args:
            period: 统计周期
        """
        start_time = self._get_period_start(period)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT 
                        model_provider,
                        model_name,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens
                    FROM token_usage
                    WHERE timestamp >= ?
                    GROUP BY model_provider, model_name
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT 
                        model_provider,
                        model_name,
                        SUM(input_tokens) as input_tokens,
                        SUM(output_tokens) as output_tokens
                    FROM token_usage
                    GROUP BY model_provider, model_name
                    """
                )
            
            breakdown = []
            total_cost = 0.0
            
            for row in cursor.fetchall():
                provider = row["model_provider"]
                model = row["model_name"]
                input_tokens = row["input_tokens"] or 0
                output_tokens = row["output_tokens"] or 0
                
                # 获取费率
                rate = self._get_rate(provider, model)
                input_cost = (input_tokens / 1000) * rate["input"]
                output_cost = (output_tokens / 1000) * rate["output"]
                model_total = input_cost + output_cost
                
                item = {
                    "provider": provider,
                    "model": model,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "input_rate": rate["input"],
                    "output_rate": rate["output"],
                    "input_cost": round(input_cost, 4),
                    "output_cost": round(output_cost, 4),
                    "total_cost": round(model_total, 4),
                }
                
                if rate["input"] == 0 and rate["output"] == 0:
                    item["note"] = "免费额度内"
                
                breakdown.append(item)
                total_cost += model_total
        
        return {
            "period": period,
            "currency": "CNY",
            "breakdown": breakdown,
            "total_cost": round(total_cost, 4),
        }
    
    # ==================== 辅助方法 ====================
    
    def _get_period_start(self, period: str) -> str | None:
        """获取周期起始时间"""
        now = datetime.now()
        if period == "today":
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        elif period == "week":
            return (now - timedelta(days=7)).isoformat()
        elif period == "month":
            return (now - timedelta(days=30)).isoformat()
        elif period == "all":
            return None
        else:
            return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    def _get_rate(self, provider: str, model: str) -> dict:
        """获取模型费率"""
        provider_rates = RATE_CONFIG.get(provider, {})
        model_rate = provider_rates.get(model, {"input": 0, "output": 0})
        return model_rate
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, start_time: str | None) -> float:
        """计算费用"""
        total_cost = 0.0
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            if start_time:
                cursor = conn.execute(
                    """
                    SELECT model_provider, model_name,
                           SUM(input_tokens) as input_tokens,
                           SUM(output_tokens) as output_tokens
                    FROM token_usage
                    WHERE timestamp >= ?
                    GROUP BY model_provider, model_name
                    """,
                    (start_time,)
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT model_provider, model_name,
                           SUM(input_tokens) as input_tokens,
                           SUM(output_tokens) as output_tokens
                    FROM token_usage
                    GROUP BY model_provider, model_name
                    """
                )
            
            for row in cursor.fetchall():
                rate = self._get_rate(row["model_provider"], row["model_name"])
                input_cost = ((row["input_tokens"] or 0) / 1000) * rate["input"]
                output_cost = ((row["output_tokens"] or 0) / 1000) * rate["output"]
                total_cost += input_cost + output_cost
        
        return round(total_cost, 4)
    
    def _calculate_case_cost(self, input_tokens: int, output_tokens: int, agent_name: str) -> float:
        """计算用例费用（使用默认模型费率）"""
        # 使用 deepseek-chat 的费率作为默认
        rate = RATE_CONFIG.get("deepseek", {}).get("deepseek-chat", {"input": 0.001, "output": 0.002})
        input_cost = (input_tokens / 1000) * rate["input"]
        output_cost = (output_tokens / 1000) * rate["output"]
        return input_cost + output_cost
    
    def _format_duration(self, seconds: int) -> str:
        """格式化时长"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}分{secs}秒"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours}小时{minutes}分"


class TokenCallbackHandler(BaseCallbackHandler):
    """
    LangChain 回调处理器（v2 增强）
    
    捕获 LLM 调用的 token 使用情况并记录到 TokenCounter。
    v2 新增：
    - on_llm_start: 记录开始时间，用于计算 latency_ms
    - on_llm_error: 捕获错误，记录到 token_records + thread_events
    - latency_ms: LLM 响应耗时
    """
    
    def __init__(self, counter: TokenCounter | None = None, agent_name: str | None = None):
        self.counter = counter or TokenCounter()
        self.default_agent_name = agent_name
        self._start_times: dict[str, float] = {}  # run_id -> start_time
        self._run_agents: dict[str, str] = {}  # run_id -> agent_name
    
    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用开始时触发，记录开始时间"""
        rid = str(run_id)
        self._start_times[rid] = time.monotonic()
        # agent_name 优先级: ContextVar > 构造函数默认值 > "unknown"
        agent_name = get_current_agent()
        if agent_name == "unknown" and self.default_agent_name:
            agent_name = self.default_agent_name
        self._run_agents[rid] = agent_name
        thread_id = get_current_thread_id()
        model_info = kwargs.get("invocation_params", {}) or {}
        model_name = model_info.get("model_name", "") or model_info.get("model", "?")
        logs.info(f"[TokenCallback] 🟢 on_llm_start | run_id={rid[:8]} | model={model_name} | thread_id={thread_id} | agent={agent_name}")
    
    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束时触发"""
        try:
            # 计算延迟
            latency_ms = None
            rid = str(run_id)
            if rid in self._start_times:
                latency_ms = int((time.monotonic() - self._start_times.pop(rid)) * 1000)
            
            thread_id = get_current_thread_id()
            agent_name = get_current_agent()
            
            # 从 on_llm_start 保存的 agent_name 补充
            if agent_name == "unknown" and rid in self._run_agents:
                agent_name = self._run_agents[rid]
            # 构造函数默认值兜底
            if agent_name == "unknown" and self.default_agent_name:
                agent_name = self.default_agent_name
            self._run_agents.pop(rid, None)
            
            # 如果 ContextVar 中没有 thread_id，尝试直接从 langgraph 获取
            if not thread_id:
                try:
                    from langgraph.config import get_config
                    config = get_config()
                    if config and isinstance(config, dict):
                        configurable = config.get("configurable", {})
                        thread_id = configurable.get("thread_id")
                        if thread_id:
                            set_current_thread_id(thread_id)
                            logs.info(f"[TokenCallback] 从 get_config() 补获 thread_id={thread_id}")
                except Exception:
                    pass
            
            logs.info(f"[TokenCallback] 🔵 on_llm_end | run_id={rid[:8]} | latency={latency_ms}ms | thread_id={thread_id} | agent={agent_name}")
            
            # 从响应中提取 token 使用信息
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage", {})
            
            # 调试：打印响应结构
            logs.info(f"[TokenCallback] response type={type(response).__name__}")
            logs.info(f"[TokenCallback] llm_output keys={list(llm_output.keys()) if isinstance(llm_output, dict) else 'N/A'}")
            logs.info(f"[TokenCallback] token_usage from llm_output={token_usage}")
            
            if not token_usage:
                usage_metadata = getattr(response, "usage_metadata", None)
                logs.info(f"[TokenCallback] usage_metadata={usage_metadata} (type={type(usage_metadata).__name__ if usage_metadata else 'None'})")
                if usage_metadata:
                    if isinstance(usage_metadata, dict):
                        token_usage = {
                            "prompt_tokens": usage_metadata.get("input_tokens", 0),
                            "completion_tokens": usage_metadata.get("output_tokens", 0),
                            "total_tokens": usage_metadata.get("total_tokens", 0),
                        }
                    else:
                        token_usage = {
                            "prompt_tokens": getattr(usage_metadata, "input_tokens", 0) or 0,
                            "completion_tokens": getattr(usage_metadata, "output_tokens", 0) or 0,
                            "total_tokens": getattr(usage_metadata, "total_tokens", 0) or 0,
                        }
                    logs.info(f"[TokenCallback] token_usage from usage_metadata={token_usage}")
            
            # 方式 3: 从 generations[0][0].message.usage_metadata 提取
            if not token_usage:
                try:
                    generations = getattr(response, "generations", None)
                    if generations and len(generations) > 0 and len(generations[0]) > 0:
                        gen = generations[0][0]
                        msg = getattr(gen, "message", None)
                        if msg:
                            um = getattr(msg, "usage_metadata", None)
                            logs.info(f"[TokenCallback] generations[0][0].message.usage_metadata={um}")
                            if um:
                                if isinstance(um, dict):
                                    token_usage = {
                                        "prompt_tokens": um.get("input_tokens", 0),
                                        "completion_tokens": um.get("output_tokens", 0),
                                        "total_tokens": um.get("total_tokens", 0),
                                    }
                                else:
                                    token_usage = {
                                        "prompt_tokens": getattr(um, "input_tokens", 0) or 0,
                                        "completion_tokens": getattr(um, "output_tokens", 0) or 0,
                                        "total_tokens": getattr(um, "total_tokens", 0) or 0,
                                    }
                                logs.info(f"[TokenCallback] token_usage from generation.message={token_usage}")
                            else:
                                # 打印 message 和 generation_info 帮助定位
                                gi = getattr(gen, "generation_info", None)
                                logs.info(f"[TokenCallback] generation_info={gi}")
                                msg_type = type(msg).__name__
                                msg_attrs = [a for a in dir(msg) if not a.startswith('_') and a in ('usage_metadata', 'response_metadata', 'additional_kwargs', 'id', 'content')]
                                logs.info(f"[TokenCallback] message type={msg_type}, key attrs={msg_attrs}")
                                resp_meta = getattr(msg, "response_metadata", None)
                                if resp_meta:
                                    logs.info(f"[TokenCallback] message.response_metadata={resp_meta}")
                                    # 某些网关在 response_metadata 中返回 token_usage
                                    if isinstance(resp_meta, dict):
                                        tu = resp_meta.get("token_usage") or resp_meta.get("usage", {})
                                        if tu:
                                            token_usage = {
                                                "prompt_tokens": tu.get("prompt_tokens", 0) or tu.get("input_tokens", 0) or 0,
                                                "completion_tokens": tu.get("completion_tokens", 0) or tu.get("output_tokens", 0) or 0,
                                                "total_tokens": tu.get("total_tokens", 0) or 0,
                                            }
                                            logs.info(f"[TokenCallback] token_usage from response_metadata={token_usage}")
                                add_kwargs = getattr(msg, "additional_kwargs", None)
                                if add_kwargs:
                                    logs.info(f"[TokenCallback] message.additional_kwargs keys={list(add_kwargs.keys()) if isinstance(add_kwargs, dict) else add_kwargs}")
                except Exception as e:
                    logs.warning(f"[TokenCallback] 从 generations 提取失败: {e}")
            
            # 提取模型信息
            invocation_params = kwargs.get("invocation_params", {}) or {}
            model_name = invocation_params.get("model_name", "") or invocation_params.get("model", "")
            
            # 从 response 或 generation 中补充模型名
            if not model_name:
                # 尝试从 generations[0][0].message.response_metadata 获取
                try:
                    generations = getattr(response, "generations", None)
                    if generations and len(generations) > 0 and len(generations[0]) > 0:
                        msg = getattr(generations[0][0], "message", None)
                        if msg:
                            resp_meta = getattr(msg, "response_metadata", None)
                            if isinstance(resp_meta, dict):
                                model_name = resp_meta.get("model_name", "") or resp_meta.get("model", "")
                except Exception:
                    pass
            
            if not model_name:
                model_name = "unknown"
            
            model_provider = self._infer_provider(model_name)
            
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0) or 0
                output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0) or 0
                
                logs.info(f"[TokenCallback] 📊 记录 token | model={model_provider}/{model_name} | in={input_tokens} out={output_tokens} | thread={thread_id}")
                
                self.counter.record(
                    model_provider=model_provider,
                    model_name=model_name,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    agent_name=agent_name,
                    thread_id=thread_id,
                    latency_ms=latency_ms,
                )
            else:
                logs.warning(f"[TokenCallback] ⚠️ 未提取到 token_usage | model={model_name} | run_id={rid[:8]}")
        except Exception as e:
            logs.error(f"[TokenCallback] ❌ on_llm_end 异常: {e}", exc_info=True)
    
    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any | None = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用失败时触发（v2 新增）"""
        try:
            # 清理 start_time
            rid = str(run_id)
            latency_ms = None
            if rid in self._start_times:
                latency_ms = int((time.monotonic() - self._start_times.pop(rid)) * 1000)
            
            thread_id = get_current_thread_id()
            error_msg = str(error)[:500]
            
            if thread_id:
                now = datetime.now().isoformat()
                with self.counter._connect() as conn:
                    # 更新 thread 错误计数
                    conn.execute(
                        "UPDATE threads SET error_count = error_count + 1, updated_at = ? WHERE thread_id = ?",
                        (now, thread_id)
                    )
                    # 记录错误事件
                    conn.execute(
                        """
                        INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                        VALUES (?, ?, 'llm_error', ?)
                        """,
                        (thread_id, now, json.dumps({"error": error_msg}))
                    )
                    # 记录错误的 token_record
                    conn.execute(
                        """
                        INSERT INTO token_records 
                        (thread_id, timestamp, model_provider, model_name, agent_name, is_error, error_message, latency_ms)
                        VALUES (?, ?, 'unknown', 'unknown', ?, 1, ?, ?)
                        """,
                        (thread_id, now, get_current_agent(), error_msg, latency_ms)
                    )
                    conn.commit()
                
                logs.warning(f"[TokenCallbackHandler] LLM 错误已记录: thread={thread_id}, error={error_msg[:100]}")
        except Exception as e:
            logs.warning(f"[TokenCallbackHandler] 处理 LLM 错误时出错: {e}")
    
    def _infer_provider(self, model_name: str) -> str:
        """根据模型名推断提供商"""
        model_lower = model_name.lower()
        if "deepseek" in model_lower:
            return "deepseek"
        elif "glm" in model_lower:
            return "zhipu"
        elif "qwen" in model_lower:
            return "scnet"
        elif "claude" in model_lower:
            return "kiro"
        elif "gpt" in model_lower:
            return "aiop"
        elif "gemini" in model_lower:
            return "aiclient"
        else:
            import os
            provider = os.getenv("LLM_PROVIDER", "deepseek")
            return provider


# 全局实例
_token_counter: TokenCounter | None = None
_token_callback: TokenCallbackHandler | None = None


def get_token_counter() -> TokenCounter:
    """获取 TokenCounter 单例"""
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter


def get_token_callback(agent_name: str | None = None) -> TokenCallbackHandler:
    """获取 TokenCallbackHandler 实例
    
    Args:
        agent_name: Agent 名称。如果提供，创建新实例；否则返回单例。
    """
    if agent_name:
        cb = TokenCallbackHandler(get_token_counter(), agent_name=agent_name)
        logs.info(f"[TokenCallback] 🚀 创建 TokenCallbackHandler | agent={agent_name}")
        return cb
    
    global _token_callback
    if _token_callback is None:
        _token_callback = TokenCallbackHandler(get_token_counter())
        logs.info(f"[TokenCallback] 🚀 TokenCallbackHandler 单例已创建 | db_path={_token_callback.counter.db_path}")
    return _token_callback