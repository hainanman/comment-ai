"""审核员：待复核、申诉复审、复核详情。"""
from __future__ import annotations

from flask import (
    Blueprint,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..auth.decorators import role_required
from ..extensions import db
from ..models import Comment

review_bp = Blueprint("review", __name__, url_prefix="/review")


@review_bp.get("/")
@role_required("reviewer")
def queue():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Comment.query.filter(Comment.status == "reviewing")
        .order_by(Comment.risk_score.desc(), Comment.created_at.asc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("review/queue.html", pagination=pagination)


@review_bp.get("/appeals")
@role_required("reviewer")
def appeals():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Comment.query.filter(
            Comment.status == "rejected",
            Comment.appeal_status == "pending",
        )
        .order_by(Comment.appealed_at.asc())
        .paginate(page=page, per_page=10, error_out=False)
    )
    return render_template("review/appeals.html", pagination=pagination)


@review_bp.get("/<int:comment_id>")
@role_required("reviewer")
def detail(comment_id: int):
    comment = Comment.query.get_or_404(comment_id)
    if not comment.can_review:
        flash("该评论当前不在待复核/申诉复审队列。", "warning")
        return redirect(url_for("review.queue"))
    return render_template("review/detail.html", comment=comment)


@review_bp.post("/<int:comment_id>")
@role_required("reviewer")
def action(comment_id: int):
    comment = Comment.query.get_or_404(comment_id)
    if not comment.can_review:
        flash("该评论已经被处理或不在复核队列。", "warning")
        return redirect(url_for("review.queue"))

    action = (request.form.get("action") or "").strip()
    if action not in {"approve", "reject"}:
        flash("无效的审核动作。", "danger")
        return redirect(url_for("review.detail", comment_id=comment.id))

    from_appeal = (
        comment.status == "rejected" and comment.appeal_status == "pending"
    )
    comment.status = "published" if action == "approve" else "rejected"
    if from_appeal:
        comment.appeal_status = "handled"

    db.session.commit()
    flash("已通过该评论。" if action == "approve" else "已驳回该评论。", "success")
    return redirect(
        url_for("review.appeals") if from_appeal else url_for("review.queue")
    )
