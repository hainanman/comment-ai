"""Flask 扩展实例，避免循环导入。

优先使用 Flask-WTF；未安装时使用项目内置 CSRF 兜底，
保证低依赖环境也能启动并校验表单。
"""
try:  # pragma: no cover - 取决于环境是否安装 Flask-WTF
    from flask_wtf.csrf import CSRFError, CSRFProtect
except Exception:  # pragma: no cover
    from .csrf import CSRFError, CSRFProtect

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
csrf = CSRFProtect()

__all__ = ["db", "csrf", "CSRFError"]
