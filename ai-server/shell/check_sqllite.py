#!/usr/bin/env python3
"""
Token Stats 数据库检查工具

用法：
    python shell/check_sqllite.py          # 查看概览
    python shell/check_sqllite.py <thread_id>  # 查看指定会话详情
"""

import sqlite3
import sys
from pathlib import Path

# 自动定位数据库（相对于脚本位置）
DB_PATH = Path(__file__).parent.parent / "data" / "token_stats.db"

if not DB_PATH.exists():
    print(f"❌ 数据库不存在: {DB_PATH}")
    sys.exit(1)

conn = sqlite3.connect(str(DB_PATH))
conn.row_factory = sqlite3.Row

# 获取所有表
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]

# ============================================================
# 如果传入了 thread_id，查看指定会话详情
# ============================================================
if len(sys.argv) > 1:
    tid = sys.argv[1]
    print(f"=== 查询 thread_id: {tid} ===\n")

    # threads
    row = conn.execute("SELECT * FROM threads WHERE thread_id = ?", (tid,)).fetchone()
    if row:
        d = dict(row)
        print(f"📋 会话信息:")
        print(f"  名称: {d['name']}")
        print(f"  Agent: {d['agent_name']}")
        print(f"  状态: {d['status']}")
        print(f"  创建: {d['created_at']}")
        print(f"  更新: {d['updated_at']}")
        print(f"  总 tokens: {d['total_tokens']:,} (in={d['input_tokens']:,} out={d['output_tokens']:,})")
        print(f"  调用次数: {d['message_count']}")
        print(f"  错误次数: {d['error_count']}")
    else:
        print(f"❌ 未找到该会话")
        conn.close()
        sys.exit(1)

    # token_records
    records = conn.execute(
        "SELECT * FROM token_records WHERE thread_id = ? ORDER BY timestamp ASC", (tid,)
    ).fetchall()
    print(f"\n📊 Token 明细 ({len(records)} 条):")
    for i, r in enumerate(records, 1):
        d = dict(r)
        latency = f"{d['latency_ms']}ms" if d['latency_ms'] else "N/A"
        error = " ❌" if d['is_error'] else ""
        print(f"  [{i}] {d['timestamp'][:19]} | {d['model_provider']}/{d['model_name']} | "
              f"in={d['input_tokens']:,} out={d['output_tokens']:,} | "
              f"latency={latency} | agent={d['agent_name']}{error}")

    # thread_events
    events = conn.execute(
        "SELECT * FROM thread_events WHERE thread_id = ? ORDER BY timestamp ASC", (tid,)
    ).fetchall()
    if events:
        print(f"\n📝 事件日志 ({len(events)} 条):")
        for r in events:
            d = dict(r)
            print(f"  {d['timestamp'][:19]} | {d['event_type']} | {d['detail']}")

    conn.close()
    sys.exit(0)

# ============================================================
# 默认：概览模式
# ============================================================
print("=== 各表记录数 ===")
for t in tables:
    if t == "sqlite_sequence":
        continue
    cnt = conn.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
    print(f"  {t}: {cnt}")

# threads 概览
print("\n=== 会话列表（最近 10 个） ===")
rows = conn.execute("SELECT * FROM threads ORDER BY created_at DESC LIMIT 10").fetchall()
for r in rows:
    d = dict(r)
    status_icon = {"active": "🟢", "completed": "✅", "failed": "❌", "interrupted": "⚠️"}.get(d["status"], "❓")
    deleted = " [已删除]" if d["is_deleted"] else ""
    print(f"  {status_icon} {d['thread_id'][:12]}... | {d['name']} | agent={d['agent_name']} | "
          f"tokens={d['total_tokens']:,} | calls={d['message_count']}{deleted}")

# 最近调用
print("\n=== 最近 LLM 调用（最近 10 条） ===")
rows = conn.execute("SELECT * FROM token_records ORDER BY timestamp DESC LIMIT 10").fetchall()
for r in rows:
    d = dict(r)
    latency = f"{d['latency_ms']}ms" if d['latency_ms'] else "N/A"
    print(f"  {d['timestamp'][:19]} | {d['model_provider']}/{d['model_name']} | "
          f"in={d['input_tokens']:,} out={d['output_tokens']:,} | "
          f"latency={latency} | agent={d['agent_name']} | thread={d['thread_id'][:12]}...")

# 汇总
print("\n=== 汇总统计 ===")
row = conn.execute(
    "SELECT SUM(input_tokens) as total_in, SUM(output_tokens) as total_out, "
    "SUM(total_tokens) as total, COUNT(*) as calls, "
    "COUNT(DISTINCT thread_id) as threads FROM token_records"
).fetchone()
total_in = row["total_in"] or 0
total_out = row["total_out"] or 0
total = row["total"] or 0
print(f"  会话数: {row['threads']}")
print(f"  总调用次数: {row['calls']}")
print(f"  总 input tokens: {total_in:,}")
print(f"  总 output tokens: {total_out:,}")
print(f"  总 tokens: {total:,}")

conn.close()
