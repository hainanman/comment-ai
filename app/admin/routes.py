"""管理员：只做用户管理。"""
from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from ..auth.decorators import role_required
from ..extensions import db
from ..models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.get("/users")
@role_required("admin")
def users():
    users_list = User.query.order_by(User.role.asc(), User.id.asc()).all()
    return render_template("admin/users.html", users=users_list)


@admin_bp.post("/users")
@role_required("admin")
def create_user():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not (3 <= len(username) <= 50):
        flash("用户名长度需为 3—50 个字符。", "danger")
    elif len(password) < 6:
        flash("初始密码至少 6 位。", "danger")
    elif User.query.filter_by(username=username).first():
        flash("用户名已存在。", "danger")
    else:
        user = User(username=username, role="reviewer", status=1)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash(f"审核员 {username} 创建成功。", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/reset-password")
@role_required("admin")
def reset_password(user_id: int):
    user = User.query.get_or_404(user_id)
    password = request.form.get("password") or ""
    if len(password) < 6:
        flash("新密码至少 6 位。", "danger")
    else:
        user.set_password(password)
        db.session.commit()
        flash(f"已重置 {user.username} 的密码。", "success")
    return redirect(url_for("admin.users"))


@admin_bp.post("/users/<int:user_id>/toggle")
@role_required("admin")
def toggle_user(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.id == g.user.id:
        flash("不能停用当前登录的管理员账号。", "warning")
    else:
        user.status = 0 if user.status == 1 else 1
        db.session.commit()
        flash(
            f"已{'启用' if user.status == 1 else '停用'}账号 {user.username}。",
            "success",
        )
    return redirect(url_for("admin.users"))
