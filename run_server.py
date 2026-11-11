"""云部署启动入口：读取 PORT 环境变量（默认 8000），绑定 0.0.0.0。

冷启动（容器/实例被平台重建）时若 SQLite 数据库不存在，优先从仓库内的
deploy/seed_demo.db.gz 解压（秒级），解压不可用时退回执行 seed.py 现场生成，
保证任何平台上第一次访问就能看到完整的演示数据。
"""
import gzip
import os
import shutil
import subprocess
import sys
from pathlib import Path

from waitress import serve

BASE_DIR = Path(__file__).resolve().parent
SEED_GZ = BASE_DIR / "deploy" / "seed_demo.db.gz"


def sqlite_path() -> Path | None:
    """从 DATABASE_URL 解析出 SQLite 文件路径；非 SQLite 返回 None。"""
    url = os.environ.get("DATABASE_URL", "sqlite:///comment_ai.db")
    if not url.startswith("sqlite"):
        return None
    raw = url.split("sqlite:///", 1)[-1]
    path = Path(raw)
    return path if path.is_absolute() else BASE_DIR / "instance" / path


def ensure_database() -> None:
    """数据库缺失时准备好演示数据。"""
    path = sqlite_path()
    if path is None or path.exists():
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    # 首选：解压仓库内置的演示库（约 600KB，毫秒级完成）
    if SEED_GZ.exists():
        try:
            with gzip.open(SEED_GZ, "rb") as src, open(path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            print(f"[init] 已从内置演示库恢复数据：{path}", flush=True)
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[init] 解压内置演示库失败：{exc}", flush=True)

    # 兜底：现场生成演示数据（耗时较久，但不至于空库）
    print("[init] 开始现场生成演示数据", flush=True)
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
    print(f"[serve] listening on 0.0.0.0:{port}", flush=True)
    serve(app, host="0.0.0.0", port=port, threads=8)
