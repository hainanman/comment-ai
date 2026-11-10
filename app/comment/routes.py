"""评论广场、我的评论、结果页、极简申诉。

发表评论的入口已经收敛到商品详情页，本蓝图不再提供独立发布页。
"""
from __future__ import annotations

from datetime import datetime

from flask import (
    Blueprint,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import or_

from ..auth.decorators import role_required
from ..extensions import db
from ..models import Comment

comment_bp = Blueprint("comment", __name__)

SENTIMENT_VALUES = {"positive", "neutral", "negative"}


@comment_bp.get("/comments")
def index():
    q = (request.args.get("q") or "").strip()
    sentiment = (request.args.get("sentiment") or "").strip()
    page = request.args.get("page", 1, type=int)

    query = Comment.query.filter(Comment.status == "published")
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Comment.content.like(like), Comment.target_name.like(like))
        )
    if sentiment in SENTIMENT_VALUES:
        query = query.filter(Comment.sentiment == sentiment)

    pagination = query.order_by(Comment.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    return render_template(
        "comments/index.html",
        pagination=pagination,
        q=q,
        sentiment=sentiment,
    )


@comment_bp.get("/comments/<int:comment_id>/result")
@role_required("user")
def result(comment_id: int):
    comment = Comment.query.filter_by(
        id=comment_id, user_id=g.user.id
    ).first_or_404()
    return render_template("comments/result.html", comment=comment)


@comment_bp.get("/my/comments")
@role_required("user")
def my_comments():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Comment.query.filter_by(user_id=g.user.id)
        .order_by(Comment.created_at.desc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("comments/my.html", pagination=pagination)


@comment_bp.post("/comments/<int:comment_id>/appeal")
@role_required("user")
def appeal(comment_id: int):
    comment = Comment.query.filter_by(
        id=comment_id, user_id=g.user.id
    ).first_or_404()

    if not comment.is_appealable:
        flash("该评论不可申诉或已经申诉过。", "warning")
        return redirect(url_for("comment.my_comments"))

    comment.appeal_status = "pending"
    comment.appealed_at = datetime.now()
    db.session.commit()
    flash("申诉已提交，等待审核员复审。", "success")
    return redirect(url_for("comment.my_comments"))
