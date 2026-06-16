"""
应用程序主入口。

作者: yandc
创建时间: 2026-01-13
"""
import os
from app.flask_app import create_app

app = create_app()

if __name__ == "__main__":
    # 仅在直接 `python run.py`（本地开发）时进入这里；
    # 生产用 gunicorn `run:app` 启动，本块不会执行。
    # 用 FLASK_ENV 控制 debug，避免生产场景下有人误用 `python run.py`
    # 把交互式调试器 + 完整堆栈暴露给客户端。
    debug = os.getenv("FLASK_ENV", "development").lower() != "production"
    app.run(host="0.0.0.0", port=12048, debug=debug)
