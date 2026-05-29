"""
应用程序主入口。

作者: yandc
创建时间: 2026-01-13
"""
from app.flask_app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=12048, debug=True)
