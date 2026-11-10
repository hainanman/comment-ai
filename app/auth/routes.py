"""注册、登录、退出。"""
from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..extensions import db
from ..models import User
from .decorators import safe_next

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        confirm = request.form.get("confirm") or ""

        error = None
        if not (3 <= len(username) <= 50):
            error = "用户名长度需为 3—50 个字符。"
        elif len(password) < 6:
            error = "密码至少 6 位。"
        elif password != confirm:
            error = "两次输入的密码不一致。"
        elif User.query.filter_by(username=username).first():
            error = "用户名已存在。"

        if error:
            flash(error, "danger")
            return render_template("auth/register.html", username=username), 400

        user = User(username=username, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("注册成功，请登录。", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    next_url = safe_next(request.args.get("next") or request.form.get("next"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()

        if user is None or not user.check_password(password):
            flash("用户名或密码错误。", "danger")
            return render_template("auth/login.html", username=username, next_url=next_url), 401
        if not user.is_active:
            flash("账号已停用，请联系管理员。", "danger")
            return render_template("auth/login.html", username=username, next_url=next_url), 403

        session.clear()
        session["user_id"] = user.id
        session.permanent = True
        flash(f"欢迎回来，{user.username}。", "success")
        return redirect(next_url or url_for("product.index"))

    return render_template("auth/login.html", next_url=next_url)


@auth_bp.post("/logout")
def logout():
    session.clear()
    flash("已退出登录。", "info")
    return redirect(url_for("product.index"))
