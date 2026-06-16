# 后端 Dockerfile
FROM python:3.13-slim

WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_ENV=production

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制后端代码
COPY app/ ./app/
COPY run.py .
# COPY .env .env

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 暴露端口
EXPOSE 12048

# 启动命令
# 注意：APScheduler 调度器是进程内的，多 worker 会让每个 worker 各自启动一份
# 调度器，同一个 cron 任务会被并发触发 N 次（_check_running 只是 SQL 查询，
# 没有原子锁）。这里用单 worker + 多线程：
#   - 单 worker 保证调度器只有一份；
#   - --threads 8 + gthread 让 I/O 密集型 HTTP 请求仍能并发处理；
#   - --worker-class gthread 显式指定线程模型；
# 如果将来要扩到多 worker，请把 SchedulerService 拆成独立进程，
# 或在 _execute_task 里加分布式锁（Redis / MySQL GET_LOCK 等）。
CMD ["gunicorn", "--bind", "0.0.0.0:12048", "--worker-class", "gthread", "--workers", "1", "--threads", "8", "--timeout", "120", "--access-logfile", "-", "--error-logfile", "-", "run:app"]
