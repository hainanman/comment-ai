"""轻量 CSRF 兜底：当环境没有 Flask-WTF 时使用。

只实现本项目需要的两个能力：
- 生成/复用 session 中的 csrf_token
- 校验所有非安全方法的表单 token
"""
from __future__ import annotations

import hmac
import secrets

from flask import request, session

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


class CSRFError(Exception):
    """CSRF 校验失败。"""


class CSRFProtect:
    def init_app(self, app) -> None:
        app.jinja_env.globals["csrf_token"] = self.generate_token
        app.before_request(self.protect)

    def generate_token(self) -> str:
        token = session.get("_csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    def protect(self):
        if request.method in SAFE_METHODS:
            return None
        expected = session.get("_csrf_token")
        provided = request.form.get("csrf_token") or request.headers.get("X-CSRFToken")
        if not expected or not provided or not hmac.compare_digest(
            str(expected), str(provided)
        ):
            raise CSRFError("CSRF token 缺失或无效")
        return None

    def exempt(self, view):
        """兼容 Flask-WTF 的接口；本项目当前不需要豁免。"""
        return view
