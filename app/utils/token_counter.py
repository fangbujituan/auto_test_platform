"""
Token 消耗统计模块。

整合自 ai-server/tools/utils/token_counter.py。
通过 LangChain 回调机制捕获 LLM 调用的 token 使用情况，
存储到 SQLite 数据库，支持多维度统计分析。

作者: yandc
创建时间: 2026-05-30
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
from typing import Any, Optional, Dict, List

from langchain_core.callbacks import BaseCallbackHandler

from app.utils.debug.readlog import logs


# ========================================
# ContextVar 定义
# ========================================

# 当前请求的 Agent 名称
_current_agent: ContextVar[Optional[str]] = ContextVar("current_agent", default=None)

# 当前用例 ID（v1 兼容）
_current_case_id: ContextVar[Optional[str]] = ContextVar("current_case_id", default=None)

# 当前 thread_id（v2 核心维度）
_current_thread_id: ContextVar[Optional[str]] = ContextVar("current_thread_id", default=None)


def set_current_agent(agent_name: str):
    """设置当前请求的 Agent 名称。"""
    _current_agent.set(agent_name)


def get_current_agent() -> str:
    """获取当前请求的 Agent 名称。"""
    return _current_agent.get() or "unknown"


def set_current_case_id(case_id: str):
    """设置当前用例 ID（v1 兼容）。"""
    _current_case_id.set(case_id)


def get_current_case_id() -> Optional[str]:
    """获取当前用例 ID（v1 兼容）。"""
    return _current_case_id.get()


def set_current_thread_id(thread_id: str):
    """设置当前 thread_id（v2 核心）。"""
    _current_thread_id.set(thread_id)


def get_current_thread_id() -> Optional[str]:
    """获取当前 thread_id。"""
    return _current_thread_id.get()


# ========================================
# 费率配置（元/千 tokens）
# ========================================
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


# ========================================
# 数据类
# ========================================
@dataclass
class TokenUsage:
    """Token 使用记录。"""
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
    """用例使用记录。"""
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


# ========================================
# TokenCounter 主类
# ========================================
class TokenCounter:
    """Token 统计器（单例模式）。
    
    功能：
        - 通过 LangChain 回调捕获 token 使用
        - 存储到 SQLite 数据库
        - 提供多维度查询统计
        - 支持用例级别的统计和管理
    """
    
    _instance: Optional['TokenCounter'] = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: Optional[str] = None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: Optional[str] = None):
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
        """创建数据库连接（统一配置 timeout + WAL）。"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn
    
    def _init_db(self):
        """初始化数据库表（v2 新表 + v1 旧表兼容）。"""
        with self._connect() as conn:
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
    
    def record(
        self,
        model_provider: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        agent_name: Optional[str] = None,
        request_id: Optional[str] = None,
        case_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        latency_ms: Optional[int] = None,
        is_error: bool = False,
        error_message: Optional[str] = None,
    ) -> int:
        """记录一次 token 使用（同时写入 v1 旧表和 v2 新表）。
        
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
        
        logs.info(f"[TokenCounter] 📝 record() | provider={model_provider} model={model_name} | in={input_tokens} out={output_tokens} | thread_id={thread_id} | agent={agent_name} | case_id={case_id}")
        
        total_tokens = input_tokens + output_tokens
        timestamp = datetime.now().isoformat()
        
        with self._connect() as conn:
            # ---- v1: 写入 token_usage（向后兼容） ----
            cursor = conn.execute("""
                INSERT INTO token_usage 
                (timestamp, model_provider, model_name, agent_name, input_tokens, output_tokens, total_tokens, request_id, case_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (timestamp, model_provider, model_name, agent_name, input_tokens, output_tokens, total_tokens, request_id, case_id))
            record_id = cursor.lastrowid
            
            # v1: 更新 case_usage
            if case_id:
                conn.execute("""
                    UPDATE case_usage 
                    SET total_tokens = total_tokens + ?,
                        input_tokens = input_tokens + ?,
                        output_tokens = output_tokens + ?,
                        message_count = message_count + 1
                    WHERE id = ?
                """, (total_tokens, input_tokens, output_tokens, case_id))
            
            # ---- v2: 写入 token_records + 更新 threads ----
            if thread_id:
                # 确保 thread 存在
                self._ensure_thread(thread_id, agent_name, conn=conn)
                
                # 写入明细记录
                conn.execute("""
                    INSERT INTO token_records 
                    (thread_id, timestamp, model_provider, model_name, 
                     input_tokens, output_tokens, total_tokens, agent_name, request_id,
                     is_error, error_message, latency_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (thread_id, timestamp, model_provider, model_name,
                      input_tokens, output_tokens, total_tokens, agent_name, request_id,
                      1 if is_error else 0, error_message, latency_ms))
                
                # 更新 threads 聚合字段
                error_inc = 1 if is_error else 0
                conn.execute("""
                    UPDATE threads SET
                        total_tokens = total_tokens + ?,
                        input_tokens = input_tokens + ?,
                        output_tokens = output_tokens + ?,
                        message_count = message_count + 1,
                        error_count = error_count + ?,
                        updated_at = ?
                    WHERE thread_id = ?
                """, (total_tokens, input_tokens, output_tokens, error_inc, timestamp, thread_id))
            
            conn.commit()
        
        logs.info(f"[TokenCounter] 记录: {model_provider}/{model_name} | in={input_tokens}, out={output_tokens}, total={total_tokens} | agent={agent_name}, thread={thread_id}, case={case_id}")
        
        return record_id
    
    def _ensure_thread(self, thread_id: str, agent_name: str = "unknown", conn: Optional[sqlite3.Connection] = None):
        """确保 thread 记录存在，不存在则自动创建。"""
        def _do(c: sqlite3.Connection):
            cursor = c.execute("SELECT thread_id FROM threads WHERE thread_id = ?", (thread_id,))
            if cursor.fetchone() is None:
                now = datetime.now().isoformat()
                auto_name = f"会话_{datetime.now().strftime('%Y%m%d_%H%M')}"
                c.execute("""
                    INSERT INTO threads (thread_id, name, agent_name, status, created_at, updated_at)
                    VALUES (?, ?, ?, 'active', ?, ?)
                """, (thread_id, auto_name, agent_name, now, now))
                c.execute("""
                    INSERT INTO thread_events (thread_id, timestamp, event_type, detail)
                    VALUES (?, ?, 'created', ?)
                """, (thread_id, now, json.dumps({"agent_name": agent_name})))
                c.commit()
                logs.info(f"[TokenCounter] 自动创建 thread: {thread_id} ({auto_name})")
        
        if conn is not None:
            _do(conn)
        else:
            with self._connect() as c:
                _do(c)
    
    def _get_rate(self, provider: str, model: str) -> Dict[str, float]:
        """获取模型费率。"""
        provider_rates = RATE_CONFIG.get(provider, {})
        return provider_rates.get(model, {"input": 0, "output": 0})
    
    def _calculate_thread_cost(self, thread_id: str) -> float:
        """计算单个会话的费用。"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT model_provider, model_name,
                       SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                FROM token_records WHERE thread_id = ?
                GROUP BY model_provider, model_name
            """, (thread_id,))
            total_cost = 0.0
            for row in cursor.fetchall():
                rate = self._get_rate(row["model_provider"], row["model_name"])
                total_cost += ((row["input_tokens"] or 0) / 1000) * rate["input"]
                total_cost += ((row["output_tokens"] or 0) / 1000) * rate["output"]
        return round(total_cost, 4)
    
    def create_case(self, name: str, agent_name: str, thread_id: Optional[str] = None) -> Dict:
        """创建一个新用例。
        
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
            conn.execute("""
                INSERT INTO case_usage (id, name, agent_name, thread_id, status, start_time)
                VALUES (?, ?, ?, ?, 'active', ?)
            """, (case_id, name, agent_name, thread_id, start_time))
            conn.commit()
        
        logs.info(f"[TokenCounter] 创建用例: {name} (id={case_id})")
        
        return {
            "case_id": case_id,
            "name": name,
            "status": "active",
            "start_time": start_time,
            "message": "用例创建成功"
        }
    
    def complete_case(self, case_id: str, status: str = "completed") -> Dict:
        """完成用例。
        
        Args:
            case_id: 用例 ID
            status: 最终状态（completed/failed）
        
        Returns:
            用例完成统计
        """
        end_time = datetime.now().isoformat()
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM case_usage WHERE id = ?", (case_id,))
            row = cursor.fetchone()
            
            if not row:
                return {"success": False, "error": "用例不存在"}
            
            conn.execute("""
                UPDATE case_usage 
                SET status = ?, end_time = ?
                WHERE id = ?
            """, (status, end_time, case_id))
            conn.commit()
            
            cost = self._calculate_case_cost(
                row["input_tokens"] or 0,
                row["output_tokens"] or 0,
                row["agent_name"]
            )
        
        return {
            "success": True,
            "case_id": case_id,
            "name": row["name"],
            "status": status,
            "start_time": row["start_time"],
            "end_time": end_time,
            "total_tokens": row["total_tokens"] or 0,
            "input_tokens": row["input_tokens"] or 0,
            "output_tokens": row["output_tokens"] or 0,
            "estimated_cost_cny": round(cost, 4),
        }
    
    def _calculate_case_cost(self, input_tokens: int, output_tokens: int, agent_name: str) -> float:
        """计算用例费用（使用默认模型费率）。"""
        rate = RATE_CONFIG.get("deepseek", {}).get("deepseek-chat", {"input": 0.001, "output": 0.002})
        input_cost = (input_tokens / 1000) * rate["input"]
        output_cost = (output_tokens / 1000) * rate["output"]
        return input_cost + output_cost
    
    def get_global_overview(self, period: str = "today") -> Dict:
        """获取全局概览统计。
        
        Args:
            period: 统计周期 (today/week/month/all)
        
        Returns:
            统计概览
        """
        start_time = self._get_period_start(period)
        
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            
            time_filter = "WHERE timestamp >= ?" if start_time else ""
            time_params = [start_time] if start_time else []
            
            cursor = conn.execute(f"""
                SELECT SUM(total_tokens) as total_tokens,
                       SUM(input_tokens) as input_tokens,
                       SUM(output_tokens) as output_tokens,
                       COUNT(*) as total_requests
                FROM token_records {time_filter}
            """, time_params)
            rec = cursor.fetchone()
            
            cursor = conn.execute(f"""
                SELECT COUNT(*) as total_threads,
                       SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) as active_threads,
                       SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed_threads
                FROM threads {time_filter}
            """, time_params)
            th = cursor.fetchone()
            
            total_tokens = rec["total_tokens"] or 0
            total_requests = rec["total_requests"] or 0
            total_threads = th["total_threads"] or 0
            
            cost = self._calculate_cost_v2(start_time)
            
            return {
                "period": period,
                "summary": {
                    "total_tokens": total_tokens,
                    "input_tokens": rec["input_tokens"] or 0,
                    "output_tokens": rec["output_tokens"] or 0,
                    "total_requests": total_requests,
                    "total_threads": total_threads,
                    "active_threads": th["active_threads"] or 0,
                    "completed_threads": th["completed_threads"] or 0,
                    "estimated_cost_cny": cost,
                },
            }
    
    def _calculate_cost_v2(self, start_time: Optional[str]) -> float:
        """计算全局费用（v2，基于 token_records）。"""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            time_filter = "WHERE timestamp >= ?" if start_time else ""
            time_params = [start_time] if start_time else []
            cursor = conn.execute(f"""
                SELECT model_provider, model_name,
                       SUM(input_tokens) as input_tokens, SUM(output_tokens) as output_tokens
                FROM token_records {time_filter}
                GROUP BY model_provider, model_name
            """, time_params)
            total_cost = 0.0
            for row in cursor.fetchall():
                rate = self._get_rate(row["model_provider"], row["model_name"])
                total_cost += ((row["input_tokens"] or 0) / 1000) * rate["input"]
                total_cost += ((row["output_tokens"] or 0) / 1000) * rate["output"]
        return round(total_cost, 4)
    
    def _get_period_start(self, period: str) -> Optional[str]:
        """获取周期起始时间。"""
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


# ========================================
# TokenCallbackHandler 回调处理器
# ========================================
class TokenCallbackHandler(BaseCallbackHandler):
    """LangChain 回调处理器。
    
    捕获 LLM 调用的 token 使用情况并记录到 TokenCounter。
    """
    
    def __init__(self, counter: Optional[TokenCounter] = None, agent_name: Optional[str] = None):
        self.counter = counter or TokenCounter()
        self.default_agent_name = agent_name
        self._start_times: Dict[str, float] = {}  # run_id -> start_time
        self._run_agents: Dict[str, str] = {}  # run_id -> agent_name
    
    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用开始时触发，记录开始时间。"""
        rid = str(run_id)
        self._start_times[rid] = time.monotonic()
        agent_name = get_current_agent()
        if agent_name == "unknown" and self.default_agent_name:
            agent_name = self.default_agent_name
        self._run_agents[rid] = agent_name
        model_info = kwargs.get("invocation_params", {}) or {}
        model_name = model_info.get("model_name", "") or model_info.get("model", "?")
        logs.info(f"[TokenCallback] 🟢 on_llm_start | run_id={rid[:8]} | model={model_name} | agent={agent_name}")
    
    def on_llm_end(
        self,
        response: Any,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用结束时触发。"""
        try:
            latency_ms = None
            rid = str(run_id)
            if rid in self._start_times:
                latency_ms = int((time.monotonic() - self._start_times.pop(rid)) * 1000)
            
            agent_name = get_current_agent()
            if agent_name == "unknown" and rid in self._run_agents:
                agent_name = self._run_agents.pop(rid)
            if agent_name == "unknown" and self.default_agent_name:
                agent_name = self.default_agent_name
            
            thread_id = get_current_thread_id()
            
            logs.info(f"[TokenCallback] 🔵 on_llm_end | run_id={rid[:8]} | latency={latency_ms}ms | thread_id={thread_id} | agent={agent_name}")
            
            llm_output = getattr(response, "llm_output", None) or {}
            token_usage = llm_output.get("token_usage", {})
            
            if not token_usage:
                usage_metadata = getattr(response, "usage_metadata", None)
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
            
            invocation_params = kwargs.get("invocation_params", {}) or {}
            model_name = invocation_params.get("model_name", "") or invocation_params.get("model", "")
            if not model_name:
                model_name = "unknown"
            
            model_provider = self._infer_provider(model_name)
            
            if token_usage:
                input_tokens = token_usage.get("prompt_tokens", 0) or token_usage.get("input_tokens", 0) or 0
                output_tokens = token_usage.get("completion_tokens", 0) or token_usage.get("output_tokens", 0) or 0
                
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
                logs.warning(f"[TokenCallback] ⚠️ 未提取到 token_usage | model={model_name}")
        except Exception as e:
            logs.error(f"[TokenCallback] ❌ on_llm_end 异常: {e}", exc_info=True)
    
    def on_llm_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        """LLM 调用失败时触发。"""
        try:
            rid = str(run_id)
            self._start_times.pop(rid, None)
            logs.error(f"[TokenCallback] ❌ LLM 错误: {str(error)}")
        except Exception as e:
            logs.error(f"[TokenCallback] ❌ 处理 LLM 错误时异常: {e}")
    
    def _infer_provider(self, model_name: str) -> str:
        """根据模型名推断提供商。"""
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
            return "unknown"


# ========================================
# 全局实例
# ========================================
_token_counter: Optional[TokenCounter] = None
_token_callback: Optional[TokenCallbackHandler] = None


def get_token_counter() -> TokenCounter:
    """获取 TokenCounter 单例。"""
    global _token_counter
    if _token_counter is None:
        _token_counter = TokenCounter()
    return _token_counter


def get_token_callback(agent_name: Optional[str] = None) -> TokenCallbackHandler:
    """获取 TokenCallbackHandler 实例。
    
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
        logs.info(f"[TokenCallback] 🚀 TokenCallbackHandler 单例已创建")
    return _token_callback
