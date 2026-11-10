"""PythonAnywhere WSGI 入口。

用法：创建 Web 应用时选 Flask，把 Web 标签页里的 WSGI 配置文件内容
整体替换为本文件内容，并把 PROJECT_DIR 改成实际项目路径
（默认 /home/<你的用户名>/comment-ai）。
"""
import os
import sys

PROJECT_DIR = os.path.expanduser("~/comment-ai")
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

# PythonAnywhere 无 MySQL，使用随项目携带的 SQLite
os.environ.setdefault("DATABASE_URL", "sqlite:///" + os.path.join(PROJECT_DIR, "instance", "comment_ai.db"))

from app import create_app  # noqa: E402

application = create_app()
