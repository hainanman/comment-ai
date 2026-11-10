"""登录与角色装饰器。"""
from __future__ import annotations

from functools import wraps
from urllib.parse import urlparse

from flask import abort, g, redirect, request, url_for


def safe_next(target: str | None) -> str | None:
    """只允许站内相对路径，防止开放重定向。"""
    if not target:
        return None
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        return None
    if "\\" in target:
        return None
    if not target.startswith("/") or target.startswith("//"):
        return None
    return target


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if getattr(g, "user", None) is None:
            return redirect(url_for("auth.login", next=request.path))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles: str):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            user = getattr(g, "user", None)
            if user is None or user.role not in roles:
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    return decorator
