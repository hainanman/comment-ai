"""云部署启动入口：读取 PORT 环境变量（默认 8000），绑定 0.0.0.0。

首次启动（容器/实例被平台重建）时若 SQLite 数据库不存在，自动初始化演示数据，
保证任何平台上冷启动后都能直接访问。
"""
import os
import subprocess
import sys
from pathlib import Path

from waitress import serve

BASE_DIR = Path(__file__).resolve().parent


def sqlite_path() -> Path | None:
    """从 DATABASE_URL 解析出 SQLite 文件路径；非 SQLite 返回 None。"""
    url = os.environ.get("DATABASE_URL", "sqlite:///comment_ai.db")
    if not url.startswith("sqlite"):
        return None
    raw = url.split("sqlite:///", 1)[-1]
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / "instance" / path


def ensure_database() -> None:
    """数据库缺失时自动灌入演示数据。"""
    path = sqlite_path()
    if path is None or path.exists():
        return
    print(f"[init] 数据库不存在，开始初始化演示数据：{path}", flush=True)
    result = subprocess.run(
        [sys.executable, "seed.py", "--reset"],
        cwd=BASE_DIR,
        check=False,
    )
    if result.returncode != 0:
        print("[init] 演示数据初始化失败，应用仍会启动（空库）", flush=True)


if __name__ == "__main__":
    ensure_database()

    from app import create_app

    app = create_app()
    port = int(os.environ.get("PORT", "8000"))
    serve(app, host="0.0.0.0", port=port, threads=8)
