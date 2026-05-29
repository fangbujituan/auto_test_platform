"""
Token 消耗统计 Dashboard API

提供 REST API 接口查询 token 消耗统计数据。

v1 路由：/token-stats/*（保留兼容）
v2 路由：/api/v1/token-stats/*（新增，以 thread_id 为核心）
"""

import json
from typing import Optional

from fastapi import APIRouter, Query, HTTPException, Body
from pydantic import BaseModel

from tools.utils.token_counter import get_token_counter


# ==================== v1 路由（保留兼容） ====================

router = APIRouter(prefix="/token-stats", tags=["Token Statistics (v1)"])


# ==================== 用例管理 API ====================

@router.post("/cases")
async def create_case(
    name: str = Query(default=None, description="用例名称（可选，默认自动生成）"),
    agent: str = Query(default="unknown", description="Agent 名称"),
    thread_id: Optional[str] = Query(default=None, description="LangGraph thread ID"),
):
    """
    创建新用例
    
    创建一个新的用例用于跟踪 token 消耗。用例名称如未指定，将自动生成"未命名_时间戳"格式。
    """
    import datetime
    
    if not name:
        name = f"未命名_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}"
    
    try:
        counter = get_token_counter()
        data = counter.create_case(name=name, agent_name=agent, thread_id=thread_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.get("/cases")
async def get_cases(
    status: Optional[str] = Query(default=None, description="状态筛选: active/completed/failed"),
    agent: Optional[str] = Query(default=None, description="Agent 筛选"),
    date: Optional[str] = Query(default=None, description="日期筛选 (YYYY-MM-DD)"),
    sort_by: str = Query(default="date", description="排序字段: tokens/time/date"),
    order: str = Query(default="desc", description="排序方向: asc/desc"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """
    获取用例列表
    
    返回用例列表，支持状态、Agent、日期筛选，支持按消耗量或时间排序。
    """
    valid_status = ["active", "completed", "failed"]
    if status and status not in valid_status:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"参数 status 必须是 {'/'.join(valid_status)} 之一或为空"
            }
        )
    
    try:
        counter = get_token_counter()
        data = counter.get_cases(
            status=status,
            agent=agent,
            date=date,
            sort_by=sort_by,
            order=order,
            page=page,
            page_size=page_size,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    """
    获取用例详情
    
    返回指定用例的详细信息，包括所有 token 消耗记录。
    """
    try:
        counter = get_token_counter()
        data = counter.get_case(case_id)
        if not data.get("success"):
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NOT_FOUND",
                    "message": "用例不存在"
                }
            )
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.put("/cases/{case_id}")
async def update_case(
    case_id: str,
    name: str = Query(description="新用例名称"),
):
    """
    更新用例名称
    
    更新指定用例的名称。
    """
    try:
        counter = get_token_counter()
        data = counter.update_case_name(case_id, name)
        if not data.get("success"):
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NOT_FOUND",
                    "message": "用例不存在"
                }
            )
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.post("/cases/{case_id}/complete")
async def complete_case(
    case_id: str,
    status: str = Query(default="completed", description="最终状态: completed/failed"),
    note: Optional[str] = Query(default=None, description="备注"),
):
    """
    完成用例
    
    将用例标记为已完成或失败，并返回最终统计信息。
    """
    valid_status = ["completed", "failed"]
    if status not in valid_status:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"参数 status 必须是 {'/'.join(valid_status)} 之一"
            }
        )
    
    try:
        counter = get_token_counter()
        data = counter.complete_case(case_id, status=status, note=note or "")
        if not data.get("success"):
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NOT_FOUND",
                    "message": "用例不存在"
                }
            )
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.get("/cases/stats/overview")
async def get_case_stats(
    period: str = Query(default="today", description="统计周期: today/week/month/all")
):
    """
    获取用例统计
    
    返回指定周期内的用例统计信息，包括：
    - 总用例数、已完成数、失败数、活跃数
    - 成功率、平均 token 消耗
    - 最大消耗用例
    """
    valid_periods = ["today", "week", "month", "all"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"参数 period 必须是 {'/'.join(valid_periods)} 之一"
            }
        )
    
    try:
        counter = get_token_counter()
        data = counter.get_case_stats(period)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


# ==================== Token 统计 API ====================

@router.get("/overview")
async def get_overview(
    period: str = Query(default="today", description="统计周期: today/week/month/all")
):
    """
    获取统计概览
    
    返回指定周期内的 token 消耗总体统计，包括：
    - 总体统计（总 token、输入 token、输出 token、请求数、预估费用）
    - 按模型提供商分布
    - 按 Agent 分布
    """
    valid_periods = ["today", "week", "month", "all"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"参数 period 必须是 {'/'.join(valid_periods)} 之一"
            }
        )
    
    try:
        counter = get_token_counter()
        data = counter.get_overview(period)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.get("/trend")
async def get_trend(
    days: int = Query(default=7, ge=1, le=90, description="查询天数"),
    granularity: str = Query(default="day", description="粒度: hour/day")
):
    """
    获取趋势数据
    
    返回指定时间范围内的 token 消耗趋势，用于绘制图表。
    """
    valid_granularities = ["hour", "day"]
    if granularity not in valid_granularities:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"参数 granularity 必须是 {'/'.join(valid_granularities)} 之一"
            }
        )
    
    try:
        counter = get_token_counter()
        data = counter.get_trend(days, granularity)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.get("/records")
async def get_records(
    date: Optional[str] = Query(default=None, description="日期筛选 (YYYY-MM-DD)"),
    provider: Optional[str] = Query(default=None, description="模型提供商筛选"),
    agent: Optional[str] = Query(default=None, description="Agent 筛选"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页条数"),
):
    """
    获取详细记录列表
    
    返回 token 消耗的详细记录，支持多条件筛选和分页。
    """
    try:
        counter = get_token_counter()
        data = counter.get_records(
            date=date,
            provider=provider,
            agent=agent,
            page=page,
            page_size=page_size,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )


@router.get("/cost")
async def get_cost(
    period: str = Query(default="month", description="统计周期: today/week/month/all")
):
    """
    获取费用估算
    
    返回指定周期内的 token 消耗费用估算，按模型细分。
    """
    valid_periods = ["today", "week", "month", "all"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_PARAMETER",
                "message": f"参数 period 必须是 {'/'.join(valid_periods)} 之一"
            }
        )
    
    try:
        counter = get_token_counter()
        data = counter.get_cost(period)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DATABASE_ERROR",
                "message": str(e)
            }
        )



# ==================== v2 路由（以 thread_id 为核心） ====================

class ThreadCreateRequest(BaseModel):
    thread_id: str
    agent_name: str = "unknown"
    name: str = ""

class ThreadUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    note: Optional[str] = None

router_v2 = APIRouter(prefix="/api/v1/token-stats", tags=["Token Statistics (v2)"])


@router_v2.post("/threads")
async def v2_create_thread(req: ThreadCreateRequest):
    """创建或获取会话"""
    try:
        counter = get_token_counter()
        data = counter.create_or_get_thread(
            thread_id=req.thread_id,
            agent_name=req.agent_name,
            name=req.name,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/threads")
async def v2_get_threads(
    status: Optional[str] = Query(default=None),
    agent: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    include_deleted: bool = Query(default=False),
    sort_by: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取会话列表"""
    try:
        counter = get_token_counter()
        data = counter.get_threads(
            status=status, agent=agent, date_from=date_from, date_to=date_to,
            keyword=keyword, include_deleted=include_deleted,
            sort_by=sort_by, order=order, page=page, page_size=page_size,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/threads/{thread_id}")
async def v2_get_thread(thread_id: str):
    """获取会话详情"""
    try:
        counter = get_token_counter()
        data = counter.get_thread(thread_id)
        if not data.get("success"):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "会话不存在"})
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.patch("/threads/{thread_id}")
async def v2_update_thread(thread_id: str, req: ThreadUpdateRequest):
    """更新会话信息"""
    try:
        counter = get_token_counter()
        data = counter.update_thread(thread_id, name=req.name, status=req.status, note=req.note)
        if not data.get("success"):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": data.get("error", "会话不存在")})
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.delete("/threads/{thread_id}")
async def v2_delete_thread(thread_id: str):
    """软删除会话"""
    try:
        counter = get_token_counter()
        data = counter.delete_thread(thread_id)
        if not data.get("success"):
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": data.get("error", "会话不存在")})
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.post("/threads/{thread_id}/restore")
async def v2_restore_thread(thread_id: str):
    """恢复已删除会话"""
    try:
        counter = get_token_counter()
        data = counter.restore_thread(thread_id)
        if not data.get("success"):
            raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "message": data.get("error")})
        return {"success": True, "data": data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/threads/{thread_id}/records")
async def v2_get_thread_records(
    thread_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """获取会话的 Token 明细记录"""
    try:
        counter = get_token_counter()
        data = counter.get_thread_records(thread_id, page=page, page_size=page_size)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/threads/{thread_id}/events")
async def v2_get_thread_events(thread_id: str):
    """获取会话事件日志"""
    try:
        counter = get_token_counter()
        data = counter.get_thread_events(thread_id)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/overview")
async def v2_get_overview(
    period: str = Query(default="today", description="today/week/month/all"),
):
    """全局概览统计"""
    valid = ["today", "week", "month", "all"]
    if period not in valid:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PARAMETER", "message": f"period 必须是 {'/'.join(valid)} 之一"})
    try:
        counter = get_token_counter()
        data = counter.get_global_overview(period)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/trend")
async def v2_get_trend(
    days: int = Query(default=7, ge=1, le=90),
    granularity: str = Query(default="day"),
):
    """全局趋势数据"""
    if granularity not in ("hour", "day"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_PARAMETER", "message": "granularity 必须是 hour/day"})
    try:
        counter = get_token_counter()
        data = counter.get_global_trend(days, granularity)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/cost")
async def v2_get_cost(
    period: str = Query(default="month"),
):
    """全局费用报表"""
    valid = ["today", "week", "month", "all"]
    if period not in valid:
        raise HTTPException(status_code=400, detail={"code": "INVALID_PARAMETER", "message": f"period 必须是 {'/'.join(valid)} 之一"})
    try:
        counter = get_token_counter()
        data = counter.get_global_cost(period)
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.get("/records")
async def v2_get_records(
    thread_id: Optional[str] = Query(default=None),
    date: Optional[str] = Query(default=None),
    provider: Optional[str] = Query(default=None),
    agent: Optional[str] = Query(default=None),
    is_error: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    """全局明细记录"""
    try:
        counter = get_token_counter()
        data = counter.get_global_records(
            thread_id=thread_id, date=date, provider=provider,
            agent=agent, is_error=is_error, page=page, page_size=page_size,
        )
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


@router_v2.post("/migrate")
async def v2_migrate():
    """执行 v1 到 v2 数据迁移"""
    try:
        counter = get_token_counter()
        data = counter.migrate_v1_to_v2()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "MIGRATION_ERROR", "message": str(e)})


@router_v2.post("/check-idle")
async def v2_check_idle(
    idle_minutes: int = Query(default=30, ge=1),
):
    """检查并标记超时中断的会话"""
    try:
        counter = get_token_counter()
        count = counter.check_idle_threads(idle_minutes)
        return {"success": True, "data": {"interrupted_count": count}}
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "DATABASE_ERROR", "message": str(e)})


# Dashboard HTML 页面
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Token 消耗统计 Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f7fa;
            color: #333;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        .header h1 { font-size: 24px; color: #1a1a1a; }
        .header .date { color: #666; }
        .cards {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 16px;
            margin-bottom: 20px;
        }
        .card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .card-title { font-size: 14px; color: #666; margin-bottom: 8px; }
        .card-value { font-size: 28px; font-weight: 600; color: #1a1a1a; }
        .card-value.cost { color: #e74c3c; }
        .charts {
            display: grid;
            grid-template-columns: 2fr 1fr 1fr;
            gap: 16px;
            margin-bottom: 20px;
        }
        .chart-box {
            background: white;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .chart-title { font-size: 16px; font-weight: 500; margin-bottom: 12px; }
        .table-box {
            background: white;
            border-radius: 8px;
            padding: 16px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }
        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #eee;
        }
        th { font-weight: 500; color: #666; font-size: 13px; }
        td { font-size: 14px; }
        .loading { text-align: center; padding: 40px; color: #666; }
        .error { text-align: center; padding: 40px; color: #e74c3c; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Token 消耗统计 Dashboard</h1>
        <span class="date" id="currentDate"></span>
    </div>
    
    <div class="cards">
        <div class="card">
            <div class="card-title">今日消耗</div>
            <div class="card-value" id="todayTokens">-</div>
        </div>
        <div class="card">
            <div class="card-title">本月消耗</div>
            <div class="card-value" id="monthTokens">-</div>
        </div>
        <div class="card">
            <div class="card-title">预估费用</div>
            <div class="card-value cost" id="estimatedCost">-</div>
        </div>
    </div>
    
    <div class="charts">
        <div class="chart-box">
            <div class="chart-title">消耗趋势（近7天）</div>
            <div id="trendChart" style="height: 280px;"></div>
        </div>
        <div class="chart-box">
            <div class="chart-title">按模型分布</div>
            <div id="providerChart" style="height: 280px;"></div>
        </div>
        <div class="chart-box">
            <div class="chart-title">按 Agent 分布</div>
            <div id="agentChart" style="height: 280px;"></div>
        </div>
    </div>
    
    <div class="table-box">
        <div class="table-header">
            <span class="chart-title">详细记录</span>
            <a href="#" style="color: #3498db; text-decoration: none;">查看更多</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>时间</th>
                    <th>模型</th>
                    <th>Agent</th>
                    <th>输入 Tokens</th>
                    <th>输出 Tokens</th>
                    <th>总计</th>
                </tr>
            </thead>
            <tbody id="recordsTable">
                <tr><td colspan="6" class="loading">加载中...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        // 格式化数字
        function formatNumber(num) {
            if (num >= 1000000) return (num / 1000000).toFixed(2) + 'M';
            if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
            return num.toString();
        }
        
        // 格式化日期时间
        function formatDateTime(str) {
            const d = new Date(str);
            return d.toLocaleString('zh-CN', { 
                month: '2-digit', day: '2-digit', 
                hour: '2-digit', minute: '2-digit' 
            });
        }
        
        // 获取今天日期
        document.getElementById('currentDate').textContent = 
            new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long' }) + '月';
        
        // 加载概览数据
        async function loadOverview() {
            try {
                const [todayRes, monthRes] = await Promise.all([
                    fetch('/token-stats/overview?period=today'),
                    fetch('/token-stats/overview?period=month')
                ]);
                
                const todayData = await todayRes.json();
                const monthData = await monthRes.json();
                
                if (todayData.success) {
                    document.getElementById('todayTokens').textContent = 
                        formatNumber(todayData.data.summary.total_tokens);
                    
                    // 渲染饼图
                    renderPieChart('providerChart', todayData.data.by_provider, 'provider');
                    renderPieChart('agentChart', todayData.data.by_agent, 'agent');
                }
                
                if (monthData.success) {
                    document.getElementById('monthTokens').textContent = 
                        formatNumber(monthData.data.summary.total_tokens);
                    document.getElementById('estimatedCost').textContent = 
                        '¥' + monthData.data.summary.estimated_cost_cny.toFixed(2);
                }
            } catch (e) {
                console.error('加载概览数据失败:', e);
            }
        }
        
        // 加载趋势数据
        async function loadTrend() {
            try {
                const res = await fetch('/token-stats/trend?days=7');
                const data = await res.json();
                
                if (data.success) {
                    const chart = echarts.init(document.getElementById('trendChart'));
                    chart.setOption({
                        tooltip: { trigger: 'axis' },
                        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
                        xAxis: {
                            type: 'category',
                            data: data.data.trend.map(t => t.date.slice(5))
                        },
                        yAxis: { type: 'value' },
                        series: [{
                            name: 'Token 消耗',
                            type: 'bar',
                            data: data.data.trend.map(t => t.total_tokens),
                            itemStyle: { color: '#3498db' }
                        }]
                    });
                }
            } catch (e) {
                console.error('加载趋势数据失败:', e);
            }
        }
        
        // 渲染饼图
        function renderPieChart(id, data, nameField) {
            const chart = echarts.init(document.getElementById(id));
            chart.setOption({
                tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
                series: [{
                    type: 'pie',
                    radius: ['40%', '70%'],
                    label: { show: false },
                    data: data.map(d => ({
                        name: d[nameField],
                        value: d.total_tokens
                    }))
                }]
            });
        }
        
        // 加载详细记录
        async function loadRecords() {
            try {
                const res = await fetch('/token-stats/records?page_size=10');
                const data = await res.json();
                
                if (data.success && data.data.records.length > 0) {
                    const tbody = document.getElementById('recordsTable');
                    tbody.innerHTML = data.data.records.map(r => `
                        <tr>
                            <td>${formatDateTime(r.timestamp)}</td>
                            <td>${r.model_provider}/${r.model_name}</td>
                            <td>${r.agent_name}</td>
                            <td>${formatNumber(r.input_tokens)}</td>
                            <td>${formatNumber(r.output_tokens)}</td>
                            <td><strong>${formatNumber(r.total_tokens)}</strong></td>
                        </tr>
                    `).join('');
                } else {
                    document.getElementById('recordsTable').innerHTML = 
                        '<tr><td colspan="6" style="text-align:center;color:#999;">暂无数据</td></tr>';
                }
            } catch (e) {
                console.error('加载记录失败:', e);
                document.getElementById('recordsTable').innerHTML = 
                    '<tr><td colspan="6" class="error">加载失败</td></tr>';
            }
        }
        
        // 初始化
        loadOverview();
        loadTrend();
        loadRecords();
    </script>
</body>
</html>
"""


@router.get("/dashboard")
async def get_dashboard():
    """
    获取 Dashboard HTML 页面
    
    返回一个完整的 HTML 页面，展示 token 消耗统计图表。
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=DASHBOARD_HTML)
