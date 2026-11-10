"""云部署启动入口：读取 PORT 环境变量（默认 8000），绑定 0.0.0.0。"""
import os

from waitress import serve

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    serve(app, host="0.0.0.0", port=port, threads=8)
