"""数据模型：三张表 users / comments / analysis_traces。"""
from __future__ import annotations

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def _id_type():
    """MySQL 用 BIGINT，SQLite 用 INTEGER 以支持自增。"""
    return db.BigInteger().with_variant(db.Integer, "sqlite")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(_id_type(), primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(
        db.Enum("user", "reviewer", "admin", name="user_role"),
        nullable=False,
        default="user",
    )
    status = db.Column(db.SmallInteger, nullable=False, default=1)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    comments = db.relationship("Comment", back_populates="user", lazy="dynamic")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self) -> bool:
        return self.status == 1

    @property
    def role_label(self) -> str:
        return {"user": "普通用户", "reviewer": "审核员", "admin": "管理员"}.get(
            self.role, self.role
        )

    def __repr__(self) -> str:
        return f"<User {self.username} ({self.role})>"


class Comment(db.Model):
    __tablename__ = "comments"
    __table_args__ = (
        db.Index("idx_comments_review_queue", "status", "risk_score", "created_at"),
        db.Index("idx_comments_appeal_queue", "status", "appeal_status", "appealed_at"),
        db.Index("idx_comments_created", "created_at"),
        db.Index("idx_comments_sentiment", "sentiment"),
        db.Index("idx_comments_violation", "violation_type"),
        db.Index("idx_comments_user", "user_id"),
        db.Index("idx_comments_target", "target_name"),
        db.CheckConstraint("rating BETWEEN 1 AND 5", name="chk_comments_rating"),
        db.CheckConstraint(
            "sentiment_confidence IS NULL OR "
            "(sentiment_confidence >= 0 AND sentiment_confidence <= 1)",
            name="chk_comments_confidence",
        ),
        db.CheckConstraint(
            "risk_score IS NULL OR (risk_score >= 0 AND risk_score <= 1)",
            name="chk_comments_risk",
        ),
    )

    id = db.Column(_id_type(), primary_key=True)
    user_id = db.Column(_id_type(), db.ForeignKey("users.id"), nullable=False)
    target_name = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.SmallInteger, nullable=False)
    content = db.Column(db.String(500), nullable=False)

    status = db.Column(
        db.Enum("pending", "published", "reviewing", "rejected", name="comment_status"),
        nullable=False,
        default="pending",
    )
    sentiment = db.Column(
        db.Enum("positive", "neutral", "negative", name="sentiment_label"),
        nullable=True,
    )
    sentiment_confidence = db.Column(db.Numeric(4, 3), nullable=True)
    violation_type = db.Column(
        db.Enum(
            "none",
            "ad",
            "fraud",
            "abuse",
            "false_promo",
            "irrelevant",
            "other",
            name="violation_type",
        ),
        nullable=True,
    )
    risk_score = db.Column(db.Numeric(4, 3), nullable=True)
    is_sarcasm = db.Column(db.Boolean, nullable=False, default=False)
    reason = db.Column(db.String(255), nullable=True)
    keywords = db.Column(db.JSON, nullable=True)
    engine = db.Column(
        db.Enum("llm", "rule", "rule_fallback", name="engine_type"),
        nullable=True,
    )
    analysis_ms = db.Column(db.Integer, nullable=True)
    appeal_status = db.Column(
        db.Enum("none", "pending", "handled", name="appeal_status"),
        nullable=False,
        default="none",
    )
    appealed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    user = db.relationship("User", back_populates="comments")
    trace = db.relationship(
        "AnalysisTrace",
        back_populates="comment",
        uselist=False,
    )

    @property
    def status_label(self) -> str:
        return {
            "pending": "待分析",
            "published": "已发布",
            "reviewing": "待复核",
            "rejected": "已驳回",
        }.get(self.status, self.status)

    @property
    def sentiment_label(self) -> str:
        return {"positive": "好评", "neutral": "中评", "negative": "差评"}.get(
            self.sentiment, "暂无评价"
        )

    @property
    def sentiment_tendency_label(self) -> str:
        """商品页使用的好评/中评/差评口径。"""
        return {"positive": "好评", "neutral": "中评", "negative": "差评"}.get(
            self.sentiment, "暂无评价"
        )

    @property
    def violation_label(self) -> str:
        return {
            "none": "无违规",
            "ad": "广告引流",
            "fraud": "刷单返利",
            "abuse": "辱骂攻击",
            "false_promo": "虚假宣传",
            "irrelevant": "无关内容",
            "other": "其他违规",
        }.get(self.violation_type, "未判定")

    @property
    def appeal_label(self) -> str:
        return {
            "none": "未申诉",
            "pending": "申诉待复审",
            "handled": "申诉已处理",
        }.get(self.appeal_status, self.appeal_status)

    @property
    def engine_label(self) -> str:
        return {
            "llm": "大模型",
            "rule": "规则",
            "rule_fallback": "规则兜底",
        }.get(self.engine, "未分析")

    @property
    def product_slug(self) -> str | None:
        """目录内商品返回 slug，未知名称返回 None。"""
        from .catalog import slug_for_name

        return slug_for_name(self.target_name)

    @property
    def is_appealable(self) -> bool:
        return self.status == "rejected" and self.appeal_status == "none"

    @property
    def can_review(self) -> bool:
        return self.status == "reviewing" or (
            self.status == "rejected" and self.appeal_status == "pending"
        )

    @property
    def user_message(self) -> str:
        """只给用户看的友好文案，不直接暴露模型 reason。"""
        if self.status == "published":
            return "评论已发布。"
        if self.status == "reviewing":
            return "评论已提交，正在人工复核，预计 24 小时内完成。"
        if self.appeal_status == "pending":
            return "申诉已提交，等待审核员复审。"
        if self.appeal_status == "handled":
            return "申诉已处理。"
        if self.status == "rejected":
            return {
                "ad": "评论可能包含联系方式或引流信息，请删除后重新提交。",
                "fraud": "评论可能包含刷单、返现等违规内容，请修改后重新提交。",
                "abuse": "评论包含不友善用语，请文明表达。",
                "false_promo": "评论包含夸大宣传，请调整表述后重新提交。",
                "irrelevant": "评论与当前商品/内容无关，请围绕主题发表。",
                "other": "评论未通过审核，请修改后重新提交。",
            }.get(self.violation_type, "评论未通过审核，请修改后重新提交。")
        return "评论处理中。"

    def __repr__(self) -> str:
        return f"<Comment {self.id} {self.status}>"


class AnalysisTrace(db.Model):
    __tablename__ = "analysis_traces"
    __table_args__ = (
        db.UniqueConstraint("comment_id", name="uk_traces_comment"),
    )

    id = db.Column(_id_type(), primary_key=True)
    comment_id = db.Column(
        _id_type(), db.ForeignKey("comments.id"), nullable=False
    )
    rule_hits = db.Column(db.JSON, nullable=True)
    rule_ms = db.Column(db.Integer, nullable=True)
    llm_ms = db.Column(db.Integer, nullable=True)
    llm_raw = db.Column(db.Text, nullable=True)
    decision = db.Column(
        db.Enum("published", "reviewing", "rejected", name="decision_type"),
        nullable=False,
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    comment = db.relationship("Comment", back_populates="trace")

    def __repr__(self) -> str:
        return f"<AnalysisTrace comment={self.comment_id}>"
