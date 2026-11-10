"""只读数据概览：登录用户均可访问。"""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, render_template, request
from sqlalchemy import func

from ..auth.decorators import login_required
from ..extensions import db
from ..models import AnalysisTrace, Comment
from .sentiment import build_sentiment_tendency
from .time_range import last_months, month_sequence, range_label, range_start

stats_bp = Blueprint("stats", __name__)


@stats_bp.get("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard/index.html")


def _request_range() -> str:
    value = (request.args.get("range") or "").strip()
    if value in {"all", "365", "180"}:
        return value
    # 兼容旧调用 days=365/180；7/30/90 不再作为页面范围，统一回退到全部
    days = request.args.get("days", type=int)
    if days in (365, 180):
        return str(days)
    return "all"


@stats_bp.get("/api/dashboard/sentiment")
@login_required
def sentiment():
    target = (request.args.get("target") or "").strip()
    return jsonify(
        ok=True,
        data=build_sentiment_tendency(range_key=_request_range(), target=target),
    )


@stats_bp.get("/api/dashboard/summary")
@login_required
def summary():
    range_key = _request_range()
    target = (request.args.get("target") or "").strip()

    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = range_start(range_key, now)

    base = Comment.query
    if start is not None:
        base = base.filter(Comment.created_at >= start)
    if target:
        base = base.filter(Comment.target_name.contains(target))

    total = base.count()
    analyzed = base.filter(Comment.engine.isnot(None)).count()
    reviewing = base.filter(Comment.status == "reviewing").count()
    appeals = base.filter(
        Comment.status == "rejected", Comment.appeal_status == "pending"
    ).count()
    rejected = base.filter(Comment.status == "rejected").count()
    today_count = base.filter(Comment.created_at >= today).count()
    avg_analysis = base.with_entities(func.avg(Comment.analysis_ms)).scalar()

    sentiment = {"positive": 0, "neutral": 0, "negative": 0}
    for label, count in (
        base.with_entities(Comment.sentiment, func.count())
        .group_by(Comment.sentiment)
        .all()
    ):
        if label in sentiment:
            sentiment[label] = int(count)

    status = {"published": 0, "reviewing": 0, "rejected": 0}
    for label, count in (
        base.with_entities(Comment.status, func.count())
        .group_by(Comment.status)
        .all()
    ):
        if label in status:
            status[label] = int(count)

    violations = [
        {"type": label, "count": int(count)}
        for label, count in (
            base.filter(
                Comment.violation_type.isnot(None),
                Comment.violation_type != "none",
            )
            .with_entities(Comment.violation_type, func.count())
            .group_by(Comment.violation_type)
            .order_by(func.count().desc())
            .all()
        )
    ]

    # 月度趋势：全部从最早评论开始，一年/半年按区间起点
    if start is None:
        earliest = base.with_entities(func.min(Comment.created_at)).scalar()
        trend_start = earliest or today
        month_keys = month_sequence(trend_start, today)
    elif range_key == "365":
        trend_start = start
        month_keys = last_months(12, today)
    else:
        trend_start = start
        month_keys = last_months(6, today)
    month_rows = base.with_entities(
        Comment.created_at, Comment.sentiment, Comment.status
    ).all()
    by_month: dict[str, dict[str, int]] = {}
    for created_at, sentiment_label, status_label in month_rows:
        key = created_at.strftime("%Y-%m")
        item = by_month.setdefault(
            key, {"total": 0, "negative": 0, "rejected": 0}
        )
        item["total"] += 1
        if sentiment_label == "negative":
            item["negative"] += 1
        if status_label == "rejected":
            item["rejected"] += 1

    trend = []
    for month in month_keys:
        item = by_month.get(month, {"total": 0, "negative": 0, "rejected": 0})
        total_month = item["total"]
        trend.append(
            {
                "day": month,
                "total": total_month,
                "negative_rate": round(item["negative"] / total_month, 4)
                if total_month
                else 0,
                "reject_rate": round(item["rejected"] / total_month, 4)
                if total_month
                else 0,
            }
        )

    llm_count = base.filter(Comment.engine.in_(("llm", "rule_fallback"))).count()
    llm_avg_query = (
        db.session.query(func.avg(AnalysisTrace.llm_ms))
        .join(Comment, AnalysisTrace.comment_id == Comment.id)
        .filter(
            AnalysisTrace.llm_ms.isnot(None),
            AnalysisTrace.llm_ms > 0,
        )
    )
    if start is not None:
        llm_avg_query = llm_avg_query.filter(Comment.created_at >= start)
    if target:
        llm_avg_query = llm_avg_query.filter(Comment.target_name.contains(target))
    avg_llm_ms = llm_avg_query.scalar()

    data = {
        "range": {"key": range_key, "label": range_label(range_key)},
        "kpi": {
            "total": total,
            "today": today_count,
            "reviewing": reviewing,
            "appeals": appeals,
            "reject_rate": round(rejected / analyzed, 4) if analyzed else 0,
            "ai_coverage": round(analyzed / total, 4) if total else 0,
            "avg_analysis_ms": int(avg_analysis or 0),
            "model_participation": round(llm_count / analyzed, 4) if analyzed else 0,
            "avg_llm_ms": int(avg_llm_ms or 0),
            "estimated_cost": round(llm_count * 0.003, 4),
        },
        "sentiment": sentiment,
        "violations": violations,
        "trend": trend,
        "status": status,
    }
    return jsonify(ok=True, data=data)
