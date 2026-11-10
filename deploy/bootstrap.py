"""容器启动引导脚本：拉取源码 -> 安装依赖 -> 启动服务。

适用场景：用纯 python 基础镜像部署，镜像内不含项目代码。
由平台"启动命令"调用，例如：
    python /app/bootstrap.py
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
import urllib.request

SRC = os.environ.get(
    "BOOT_SOURCE",
    "https://codeload.github.com/hainanman/comment-ai/tar.gz/refs/heads/main",
)
APP_DIR = os.environ.get("BOOT_APP_DIR", "/app")
ROOT = os.path.join(APP_DIR, "comment-ai-main")


def fetch_code() -> None:
    if os.path.isdir(ROOT) and os.path.exists(os.path.join(ROOT, "run_server.py")):
        print("[boot] 源码已存在，跳过下载", flush=True)
        return
    print(f"[boot] 下载源码：{SRC}", flush=True)
    data = urllib.request.urlopen(SRC, timeout=180).read()
    os.makedirs(APP_DIR, exist_ok=True)
    tarfile.open(fileobj=io.BytesIO(data)).extractall(APP_DIR)
    print(f"[boot] 解压完成：{ROOT}", flush=True)


def install() -> None:
    print("[boot] 安装依赖", flush=True)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-cache-dir", "-q", "-r",
         os.path.join(ROOT, "requirements.txt")],
        check=True,
    )


def main() -> None:
    fetch_code()
    install()
    os.chdir(ROOT)
    sys.path.insert(0, ROOT)
    print("[boot] 启动应用", flush=True)
    os.execv(sys.executable, [sys.executable, "run_server.py"])


if __name__ == "__main__":
    main()
