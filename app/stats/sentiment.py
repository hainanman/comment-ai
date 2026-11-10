"""情感倾向聚合：按时间、商品、负面关键词汇总已发布评论。

情感倾向不调用模型，直接复用 comments.sentiment 字段；
只统计已发布评论，避免广告/刷单等被驳回内容污染用户情绪。
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy import func

from ..catalog import get_product_by_name
from ..models import Comment
from .time_range import (
    last_months,
    month_sequence,
    normalize_range,
    range_label,
    range_start,
)


def _rates(counts: dict[str, int], total: int) -> dict[str, float]:
    if not total:
        return {"positive_rate": 0.0, "neutral_rate": 0.0, "negative_rate": 0.0}
    return {
        "positive_rate": round(counts.get("positive", 0) / total, 4),
        "neutral_rate": round(counts.get("neutral", 0) / total, 4),
        "negative_rate": round(counts.get("negative", 0) / total, 4),
    }


def sentiment_score(counts: dict[str, int], total: int) -> float:
    """RI 分：正面 1 分、中性 0.5 分，负面 0 分。"""
    if not total:
        return 0.0
    return round((counts.get("positive", 0) + counts.get("neutral", 0) * 0.5) / total * 100, 1)


def sentiment_label(score: float, total: int) -> str:
    if total == 0:
        return "暂无评价"
    if total < 5:
        return "样本不足"
    if score >= 70:
        return "好评"
    if score >= 45:
        return "中评"
    return "差评"


def _base_query(start: datetime | None, end: datetime, target: str = ""):
    query = Comment.query.filter(
        Comment.status == "published",
        Comment.sentiment.isnot(None),
        Comment.created_at < end,
    )
    if start is not None:
        query = query.filter(Comment.created_at >= start)
    if target:
        query = query.filter(Comment.target_name.contains(target))
    return query


def _aggregate(query) -> tuple[int, dict[str, int], float]:
    total = query.count()
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for label, count in (
        query.with_entities(Comment.sentiment, func.count(Comment.id))
        .group_by(Comment.sentiment)
        .all()
    ):
        if label in counts:
            counts[label] = int(count)
    average = query.with_entities(func.avg(Comment.rating)).scalar()
    return total, counts, float(average or 0)


def build_sentiment_tendency(range_key: str = "all", target: str = "") -> dict:
    range_key = normalize_range(range_key, "all")
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    start = range_start(range_key, now)
    end = today + timedelta(days=1)

    current_query = _base_query(start, end, target)
    if range_key == "all":
        previous_query = None
        previous_start = None
        days = None
    else:
        days = 365 if range_key == "365" else 180
        previous_start = start - timedelta(days=days)
        previous_query = _base_query(previous_start, start, target)

    total, counts, average = _aggregate(current_query)
    if previous_query is None:
        previous_total, previous_counts = 0, {"positive": 0, "neutral": 0, "negative": 0}
    else:
        previous_total, previous_counts, _ = _aggregate(previous_query)
    rates = _rates(counts, total)
    previous_rates = _rates(previous_counts, previous_total)

    # 月度趋势：全部从最早评论开始；一年/半年按区间起点
    if start is None:
        earliest = current_query.with_entities(func.min(Comment.created_at)).scalar()
        trend_start = earliest or today
        month_keys = month_sequence(trend_start, today)
    elif range_key == "365":
        trend_start = start
        month_keys = last_months(12, today)
    else:
        trend_start = start
        month_keys = last_months(6, today)

    month_rows = (
        current_query.with_entities(Comment.created_at, Comment.sentiment)
        .order_by(Comment.created_at)
        .all()
    )
    by_month: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    for created_at, label in month_rows:
        if label in {"positive", "neutral", "negative"}:
            by_month[created_at.strftime("%Y-%m")][label] += 1

    trend = []
    for month in month_keys:
        item = by_month.get(month, {"positive": 0, "neutral": 0, "negative": 0})
        day_total = sum(item.values())
        trend.append(
            {
                "day": month,
                "total": day_total,
                "positive": item["positive"],
                "neutral": item["neutral"],
                "negative": item["negative"],
                **_rates(item, day_total),
            }
        )

    # 商品维度
    product_rows = (
        current_query.with_entities(
            Comment.target_name,
            Comment.sentiment,
            func.count(Comment.id),
        )
        .group_by(Comment.target_name, Comment.sentiment)
        .all()
    )
    product_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    for name, label, count in product_rows:
        if label in {"positive", "neutral", "negative"}:
            product_counts[name][label] = int(count)

    rating_rows = (
        current_query.with_entities(
            Comment.target_name,
            func.avg(Comment.rating),
        )
        .group_by(Comment.target_name)
        .all()
    )
    product_average = {name: float(avg or 0) for name, avg in rating_rows}

    products = []
    for name, item in product_counts.items():
        product_total = sum(item.values())
        if not product_total:
            continue
        product = get_product_by_name(name)
        products.append(
            {
                "name": name,
                "slug": product["slug"] if product else None,
                "total": product_total,
                "positive": item["positive"],
                "neutral": item["neutral"],
                "negative": item["negative"],
                "average": round(product_average.get(name, 0), 2),
                **_rates(item, product_total),
            }
        )
    products.sort(
        key=lambda item: (item["negative_rate"], item["total"]), reverse=True
    )

    # 负面关键词：低频项目直接在 Python 侧聚合 JSON 数组
    negative_keywords = Counter()
    for (keywords,) in (
        current_query.filter(Comment.sentiment == "negative")
        .with_entities(Comment.keywords)
        .all()
    ):
        if isinstance(keywords, list):
            for word in keywords:
                word = str(word).strip()
                if word:
                    negative_keywords[word] += 1

    recent_negative = []
    for comment in (
        current_query.filter(Comment.sentiment == "negative")
        .order_by(Comment.created_at.desc())
        .limit(8)
        .all()
    ):
        product = get_product_by_name(comment.target_name)
        recent_negative.append(
            {
                "id": comment.id,
                "target_name": comment.target_name,
                "slug": product["slug"] if product else None,
                "content": comment.content[:100],
                "keywords": (comment.keywords or [])[:5],
                "created_at": comment.created_at.strftime("%Y-%m-%d %H:%M"),
            }
        )

    negative_delta = rates["negative_rate"] - previous_rates["negative_rate"]
    if total == 0:
        alert = {"level": "info", "message": "当前筛选范围暂无可统计的已发布评论。"}
    elif total >= 20 and rates["negative_rate"] >= 0.30:
        alert = {
            "level": "warning",
            "message": f"差评率 {rates['negative_rate'] * 100:.1f}%，样本 {total} 条，建议关注近期负面反馈。",
        }
    elif total >= 20 and negative_delta >= 0.10:
        alert = {
            "level": "warning",
            "message": f"差评率较上期上升 {negative_delta * 100:.1f} 个百分点。",
        }
    else:
        alert = {
            "level": "ok",
            "message": f"情感整体平稳（样本 {total} 条，差评率 {rates['negative_rate'] * 100:.1f}%）。",
        }

    return {
        "range": {
            "key": range_key,
            "label": range_label(range_key),
            "days": days,
            "start": trend_start.date().isoformat(),
            "end": date.today().isoformat(),
        },
        "overall": {
            "total": total,
            "positive": counts["positive"],
            "neutral": counts["neutral"],
            "negative": counts["negative"],
            "average": round(average, 2),
            **rates,
        },
        "previous": {
            "total": previous_total,
            "positive": previous_counts["positive"],
            "neutral": previous_counts["neutral"],
            "negative": previous_counts["negative"],
            **previous_rates,
        },
        "delta": {
            "positive_rate": round(
                rates["positive_rate"] - previous_rates["positive_rate"], 4
            ),
            "negative_rate": round(negative_delta, 4),
        },
        "alert": alert,
        "trend": trend,
        "products": products,
        "negative_keywords": [
            {"word": word, "count": count}
            for word, count in negative_keywords.most_common(10)
        ],
        "recent_negative": recent_negative,
    }


def build_product_keyword_groups(product_name: str, limit: int = 10) -> dict:
    """按情感分组的关键词：好评关键词 / 中评关键词 / 差评关键词。

    计数口径与商品页筛选一致：去掉商品名后，正文包含该词才算命中。
    """
    comments = Comment.query.filter(
        Comment.status == "published",
        Comment.target_name == product_name,
        Comment.sentiment.isnot(None),
    ).all()
    by_sentiment: dict[str, list] = {
        "positive": [],
        "neutral": [],
        "negative": [],
    }
    candidates: dict[str, set[str]] = {
        "positive": set(),
        "neutral": set(),
        "negative": set(),
    }
    for comment in comments:
        if comment.sentiment not in by_sentiment:
            continue
        by_sentiment[comment.sentiment].append(comment)
        body = comment.content.replace(product_name, "")
        for word in comment.keywords or []:
            word = str(word).strip()
            if word and word in body:
                candidates[comment.sentiment].add(word)

    result = {}
    for sentiment, words in candidates.items():
        counts = {
            word: sum(
                1
                for comment in by_sentiment[sentiment]
                if word in comment.content.replace(product_name, "")
            )
            for word in words
        }
        result[sentiment] = [
            {"word": word, "count": count}
            for word, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )[:limit]
        ]
    return result


def build_product_sentiment(product_name: str, trend_months: int = 12) -> dict:
    """单个商品的整体情感倾向 + 近 12 个月趋势 + 负向关键词。"""
    base = Comment.query.filter(
        Comment.status == "published",
        Comment.target_name == product_name,
        Comment.sentiment.isnot(None),
    )
    total, counts, average = _aggregate(base)
    rates = _rates(counts, total)
    score = sentiment_score(counts, total)
    label = sentiment_label(score, total)

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    month_keys = last_months(trend_months, today)
    trend_start = datetime.strptime(month_keys[0] + "-01", "%Y-%m-%d")
    month_rows = (
        base.filter(Comment.created_at >= trend_start)
        .with_entities(Comment.created_at, Comment.sentiment)
        .order_by(Comment.created_at)
        .all()
    )
    by_month: dict[str, dict[str, int]] = defaultdict(
        lambda: {"positive": 0, "neutral": 0, "negative": 0}
    )
    for created_at, sentiment_key in month_rows:
        if sentiment_key in {"positive", "neutral", "negative"}:
            by_month[created_at.strftime("%Y-%m")][sentiment_key] += 1

    trend = []
    for month in month_keys:
        item = by_month.get(month, {"positive": 0, "neutral": 0, "negative": 0})
        day_total = sum(item.values())
        trend.append(
            {
                "day": month,
                "total": day_total,
                "positive": item["positive"],
                "neutral": item["neutral"],
                "negative": item["negative"],
                **_rates(item, day_total),
            }
        )

    negative_keywords = Counter()
    for (keywords,) in (
        base.filter(Comment.sentiment == "negative")
        .with_entities(Comment.keywords)
        .all()
    ):
        if isinstance(keywords, list):
            for word in keywords:
                word = str(word).strip()
                if word:
                    negative_keywords[word] += 1

    return {
        "total": total,
        "counts": counts,
        "average": round(average, 2),
        "score": score,
        "label": label,
        "trend": trend,
        "negative_keywords": [
            {"word": word, "count": count}
            for word, count in negative_keywords.most_common(5)
        ],
        **rates,
    }
