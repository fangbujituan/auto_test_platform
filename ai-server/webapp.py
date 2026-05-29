"""
自定义 HTTP 路由

通过 graph.json 的 http.app 配置挂载到 LangGraph API Server。
提供 Token 统计 Dashboard API（v1 + v2）。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tools.utils.dashboard import router, router_v2

app = FastAPI(title="Token Stats API", version="2.0.0")

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载 v1 路由（/token-stats/*）
app.include_router(router)

# 挂载 v2 路由（/api/v1/token-stats/*）
app.include_router(router_v2)


@app.get("/ok")
async def health_check():
    """健康检查"""
    return {"status": "ok"}
