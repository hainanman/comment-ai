"""评论创建服务：商品详情页表单与旧调用共用同一套分析/落库逻辑。"""
from __future__ import annotations

from flask import current_app

from ..ai.pipeline import AnalysisResult, analyze_comment
from ..catalog import PRODUCT_NAMES
from ..extensions import db
from ..models import AnalysisTrace, Comment


def validate_comment_form(
    target_name: str, content: str, rating_raw: str
) -> str | None:
    if target_name not in PRODUCT_NAMES:
        return "请从商品页面发表评论。"
    if not rating_raw.isdigit() or not (1 <= int(rating_raw) <= 5):
        return "评分需为 1—5。"
    max_len = current_app.config["MAX_COMMENT_LENGTH"]
    if not (5 <= len(content) <= max_len):
        return f"评论正文需为 5—{max_len} 个字符。"
    return None


def create_comment(
    user_id: int, target_name: str, content: str, rating: int
) -> Comment:
    """先落 pending，再同步分析；分析异常转人工，不向用户抛 500。"""
    comment = Comment(
        user_id=user_id,
        target_name=target_name,
        rating=rating,
        content=content,
        status="pending",
    )
    db.session.add(comment)
    db.session.commit()
    comment_id = comment.id

    try:
        result = analyze_comment(content=content, target_name=target_name)
        _apply_result(comment, result)
        db.session.commit()
    except Exception:
        current_app.logger.exception("评论分析失败，comment_id=%s", comment_id)
        db.session.rollback()
        comment = db.session.get(Comment, comment_id)
        if comment is not None:
            comment.status = "reviewing"
            comment.engine = "rule_fallback"
            comment.reason = "分析异常，转人工复核"
            comment.analysis_ms = 0
            db.session.commit()
    return comment


def flash_category(status: str) -> str:
    return {
        "published": "success",
        "reviewing": "warning",
        "rejected": "danger",
    }.get(status, "info")


def _apply_result(comment: Comment, result: AnalysisResult) -> None:
    comment.sentiment = result.sentiment
    comment.sentiment_confidence = result.sentiment_confidence
    comment.violation_type = result.violation_type
    comment.risk_score = result.risk_score
    comment.is_sarcasm = result.is_sarcasm
    comment.reason = result.reason
    comment.keywords = result.keywords
    comment.engine = result.engine
    comment.analysis_ms = result.analysis_ms
    comment.status = result.status

    trace = AnalysisTrace(
        comment_id=comment.id,
        rule_hits=result.rule_hits,
        rule_ms=result.rule_ms,
        llm_ms=result.llm_ms,
        llm_raw=result.llm_raw[:2000] if result.llm_raw else None,
        decision=result.status,
    )
    db.session.add(trace)
