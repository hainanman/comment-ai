"""商品列表、商品详情、商品页发表评论。"""
from __future__ import annotations

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from sqlalchemy import func

from ..auth.decorators import role_required
from ..catalog import CATEGORIES, PRODUCTS, get_product
from ..comment.service import create_comment, flash_category, validate_comment_form
from ..extensions import db
from ..models import Comment
from ..stats.sentiment import (
    build_product_keyword_groups,
    build_product_sentiment,
    sentiment_label,
    sentiment_score,
)

product_bp = Blueprint("product", __name__, url_prefix="/products")


@product_bp.get("/")
def index():
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()

    products = PRODUCTS
    if q:
        keyword = q.lower()
        products = [
            product
            for product in products
            if keyword in product["name"].lower()
            or keyword in product["tagline"].lower()
            or keyword in product["description"].lower()
            or any(keyword in word.lower() for word in product["keywords"])
        ]
    if category in CATEGORIES:
        products = [product for product in products if product["category"] == category]

    rating_rows = (
        db.session.query(
            Comment.target_name,
            func.count(Comment.id),
            func.avg(Comment.rating),
        )
        .filter(Comment.status == "published")
        .group_by(Comment.target_name)
        .all()
    )
    sentiment_rows = (
        db.session.query(
            Comment.target_name,
            Comment.sentiment,
            func.count(Comment.id),
        )
        .filter(Comment.status == "published")
        .group_by(Comment.target_name, Comment.sentiment)
        .all()
    )
    sentiment_by_target: dict[str, dict[str, int]] = {}
    for target, label, count in sentiment_rows:
        bucket = sentiment_by_target.setdefault(
            target, {"positive": 0, "neutral": 0, "negative": 0}
        )
        if label in bucket:
            bucket[label] = int(count)

    stats = {}
    for target, count, avg in rating_rows:
        counts = sentiment_by_target.get(
            target, {"positive": 0, "neutral": 0, "negative": 0}
        )
        sentiment_total = sum(counts.values())
        score = sentiment_score(counts, sentiment_total)
        stats[target] = {
            "count": int(count),
            "rating": float(avg or 0),
            "score": score,
            "label": sentiment_label(score, sentiment_total),
            "positive_rate": round(counts["positive"] / sentiment_total, 4)
            if sentiment_total
            else 0,
            "neutral_rate": round(counts["neutral"] / sentiment_total, 4)
            if sentiment_total
            else 0,
            "negative_rate": round(counts["negative"] / sentiment_total, 4)
            if sentiment_total
            else 0,
        }

    return render_template(
        "products/list.html",
        products=products,
        stats=stats,
        categories=CATEGORIES,
        q=q,
        category=category,
    )


@product_bp.get("/<slug>")
def detail(slug: str):
    product = get_product(slug)
    if product is None:
        abort(404)
    page = request.args.get("page", 1, type=int)
    sentiment_filter = (request.args.get("sentiment") or "").strip()
    if sentiment_filter not in {"positive", "neutral", "negative"}:
        sentiment_filter = ""
    keyword = (request.args.get("keyword") or "").strip()[:40]
    return render_template(
        "products/detail.html",
        **_detail_context(product, page, sentiment_filter, keyword),
    )


@product_bp.post("/<slug>/comments")
@role_required("user")
def submit_comment(slug: str):
    """商品详情页内联表单：校验 → 分析 → 结果页。"""
    product = get_product(slug)
    if product is None:
        abort(404)

    content = (request.form.get("content") or "").strip()
    rating_raw = (request.form.get("rating") or "").strip()
    error = validate_comment_form(product["name"], content, rating_raw)
    if error:
        context = _detail_context(product, 1)
        return (
            render_template(
                "products/detail.html",
                **context,
                form_error=error,
                form_content=content,
                form_rating=rating_raw,
            ),
            400,
        )

    comment = create_comment(
        user_id=g.user.id,
        target_name=product["name"],
        content=content,
        rating=int(rating_raw),
    )
    if comment is None:
        flash("评论提交失败，请稍后重试。", "danger")
        return redirect(url_for("product.detail", slug=slug))

    flash(comment.user_message, flash_category(comment.status))
    return redirect(url_for("comment.result", comment_id=comment.id))


def _detail_context(
    product: dict,
    page: int,
    sentiment_filter: str = "",
    keyword: str = "",
) -> dict:
    query = Comment.query.filter(
        Comment.target_name == product["name"],
        Comment.status == "published",
    )
    if sentiment_filter:
        query = query.filter(Comment.sentiment == sentiment_filter)
    if keyword:
        # 去掉商品名后再搜索，避免“降噪耳机”把“降噪”关键词全部命中
        query = query.filter(
            func.replace(Comment.content, product["name"], "").contains(keyword)
        )
    pagination = query.order_by(Comment.created_at.desc()).paginate(
        page=page, per_page=8, error_out=False
    )

    sentiment = build_product_sentiment(product["name"])
    return {
        "product": product,
        "pagination": pagination,
        "sentiment": sentiment,
        "sentiment_counts": sentiment["counts"],
        "total": sentiment["total"],
        "average": sentiment["average"],
        "positive_rate": sentiment["positive_rate"],
        "sentiment_filter": sentiment_filter,
        "keyword": keyword,
        "keyword_groups": build_product_keyword_groups(product["name"]),
    }
