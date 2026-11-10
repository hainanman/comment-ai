"""初始化演示数据：3 个账号 + 10 条固定演示评论 + 每商品 120 条生成评论。

用法：
    python seed.py
    python seed.py --reset
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from itertools import product as iter_product

from app import create_app
from app.catalog import PRODUCTS
from app.extensions import db
from app.models import AnalysisTrace, Comment, User

# 每个商品 120 条生成评论：好评 / 中评 / 差评数量
DISTRIBUTIONS = {
    "降噪耳机": (65, 35, 20),
    "机械键盘": (85, 25, 10),
    "保温杯": (80, 28, 12),
    "运动鞋": (70, 32, 18),
    "咖啡豆": (88, 22, 10),
    "充电宝": (78, 30, 12),
    "显示器": (90, 20, 10),
    "洗发水": (72, 30, 18),
}

PRODUCT_ISSUES = {
    "降噪耳机": ["断连", "夹耳", "续航衰减"],
    "机械键盘": ["键帽松动", "轴体有弹簧音", "蓝牙延迟"],
    "保温杯": ["杯盖漏水", "保温变差", "内胆有异味"],
    "运动鞋": ["磨脚", "尺码偏小", "鞋底开胶"],
    "咖啡豆": ["香气不足", "苦味太重", "不够新鲜"],
    "充电宝": ["发热明显", "容量虚标", "接口接触不良"],
    "显示器": ["有坏点", "色彩偏冷", "支架不稳"],
    "洗发水": ["头皮发痒", "香味太浓", "控油一般"],
}

SCENES = ["通勤", "办公室", "家里", "出差", "周末", "晚上", "白天", "日常"]
POSITIVE_TAILS = ["整体值这个价", "会继续用", "推荐给朋友", "符合预期", "没有踩雷", "体验还可以"]
NEUTRAL_TAILS = ["暂时没有明显问题", "再用一段时间看看", "符合这个价位", "没有特别惊喜", "日常够用"]

POSITIVE_TEMPLATES = [
    "用了{scene}，{name}的{feature}表现不错，{tail}。",
    "{scene}体验下来，{feature}比预期好，{name}整体满意，{tail}。",
    "{name}的{feature}很稳，{scene}使用没有翻车，{tail}。",
    "给{name}一个好评，{feature}符合描述，{scene}用着很顺手，{tail}。",
]
NEGATIVE_TEMPLATES = [
    "{name}的{feature}没有宣传的那么好，{scene}用了几次就{issue}。",
    "{scene}使用时{issue}，{feature}也一般，{name}不太推荐。",
    "有点失望，{name}的{feature}不如预期，{scene}还{issue}。",
]
NEUTRAL_TEMPLATES = [
    "{name}的{feature}中规中矩，{scene}用着还行，{tail}。",
    "{scene}体验了几天，{feature}符合价位，{name}没有特别惊喜，{tail}。",
    "{name}整体一般，{feature}没有明显短板，{scene}用着凑合，{tail}。",
]




def _user(username: str, password: str, role: str) -> User:
    user = User.query.filter_by(username=username).first()
    if user is None:
        user = User(username=username, role=role, status=1)
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
    return user


def _trace(comment: Comment, decision: str, rule_hits=None, llm_raw: str = "") -> None:
    db.session.add(
        AnalysisTrace(
            comment_id=comment.id,
            rule_hits=rule_hits or [],
            rule_ms=8,
            llm_ms=1800 if decision != "rejected" else 0,
            llm_raw=llm_raw[:2000] if llm_raw else None,
            decision=decision,
            # 与评论时间对齐，避免历史演示数据占用"当日模型调用配额"
            created_at=comment.created_at,
        )
    )


def _add_demo(user: User) -> None:
    demo = [
        {
            "target": "降噪耳机",
            "rating": 5,
            "content": "音质不错，戴了一天也不夹耳朵，物流很快。",
            "status": "published",
            "sentiment": "positive",
            "violation": "none",
            "risk": 0.05,
            "is_sarcasm": False,
            "reason": "用户对音质、佩戴和物流表示满意，无违规内容。",
            "keywords": ["音质", "佩戴", "物流"],
            "engine": "llm",
        },
        {
            "target": "降噪耳机",
            "rating": 2,
            "content": "用了三天就断连，客服也不回消息。",
            "status": "published",
            "sentiment": "negative",
            "violation": "none",
            "risk": 0.08,
            "is_sarcasm": False,
            "reason": "普通差评，表达断连和客服问题，无违规。",
            "keywords": ["断连", "客服"],
            "engine": "llm",
        },
        {
            "target": "降噪耳机",
            "rating": 3,
            "content": "包装一般，功能符合预期。",
            "status": "published",
            "sentiment": "neutral",
            "violation": "none",
            "risk": 0.03,
            "is_sarcasm": False,
            "reason": "中性评价，无违规内容。",
            "keywords": ["包装", "功能"],
            "engine": "llm",
        },
        {
            "target": "降噪耳机",
            "rating": 1,
            "content": "加V：abc123，同款降噪耳机低价，需要的私聊。",
            "status": "rejected",
            "sentiment": "neutral",
            "violation": "ad",
            "risk": 0.96,
            "is_sarcasm": False,
            "reason": "包含微信号和站外引流话术。",
            "keywords": ["微信", "私聊", "耳机"],
            "engine": "llm",
            "appeal_status": "pending",
            "appealed_at": datetime.now() - timedelta(hours=2),
            "rule_hits": [{"kind": "wechat", "value": "微信", "action": "review", "risk": 0.9}],
        },
        {
            "target": "降噪耳机",
            "rating": 1,
            "content": "好评返现 5 元，降噪耳机晒图联系客服。",
            "status": "rejected",
            "sentiment": "neutral",
            "violation": "fraud",
            "risk": 0.93,
            "is_sarcasm": False,
            "reason": "刷单返利话术。",
            "keywords": ["好评返现", "客服", "耳机"],
            "engine": "llm",
            "rule_hits": [{"kind": "word", "value": "好评返现", "action": "review", "risk": 0.6}],
        },
        {
            "target": "降噪耳机",
            "rating": 1,
            "content": "垃圾耳机，客服都是废物。",
            "status": "rejected",
            "sentiment": "negative",
            "violation": "abuse",
            "risk": 0.91,
            "is_sarcasm": False,
            "reason": "包含辱骂性称呼。",
            "keywords": ["垃圾", "客服", "耳机"],
            "engine": "llm",
            "rule_hits": [{"kind": "word", "value": "垃圾", "action": "review", "risk": 0.6}],
        },
        {
            "target": "降噪耳机",
            "rating": 1,
            "content": "戴了一天耳朵就发炎，这耳机真是绝了。",
            "status": "published",
            "sentiment": "negative",
            "violation": "none",
            "risk": 0.12,
            "is_sarcasm": True,
            "reason": "反讽表达，真实态度为负向；无违规。",
            "keywords": ["耳朵", "发炎", "耳机"],
            "engine": "llm",
        },
        {
            "target": "降噪耳机",
            "rating": 2,
            "content": "降噪耳机收到了，今天先来打个卡，使用体验之后再说。",
            "status": "reviewing",
            "sentiment": "neutral",
            "violation": "irrelevant",
            "risk": 0.62,
            "is_sarcasm": False,
            "reason": "内容与商品体验关联较弱，建议人工复核。",
            "keywords": ["耳机", "打卡", "体验"],
            "engine": "llm",
        },
        {
            "target": "降噪耳机",
            "rating": 5,
            "content": "全网最低价，绝对降噪第一，买它！",
            "status": "reviewing",
            "sentiment": "positive",
            "violation": "false_promo",
            "risk": 0.71,
            "is_sarcasm": False,
            "reason": "绝对化、夸大宣传，建议复核。",
            "keywords": ["最低价", "降噪", "第一"],
            "engine": "llm",
        },
        {
            "target": "降噪耳机",
            "rating": 1,
            "content": "加V：def456，降噪耳机渠道价，私聊发链接。",
            "status": "rejected",
            "sentiment": "neutral",
            "violation": "ad",
            "risk": 1.0,
            "is_sarcasm": False,
            "reason": "命中直接拦截词：加V。",
            "keywords": ["微信", "加V", "耳机"],
            "engine": "rule",
            "rule_hits": [{"kind": "word", "value": "加V", "action": "block", "risk": 1.0}],
        },
    ]

    now = datetime.now()
    for index, item in enumerate(demo):
        comment = Comment(
            user_id=user.id,
            target_name=item["target"],
            rating=item["rating"],
            content=item["content"],
            status=item["status"],
            sentiment=item["sentiment"],
            sentiment_confidence=0.9,
            violation_type=item["violation"],
            risk_score=item["risk"],
            is_sarcasm=item["is_sarcasm"],
            reason=item["reason"],
            keywords=item["keywords"],
            engine=item["engine"],
            analysis_ms=1800 + index * 37,
            appeal_status=item.get("appeal_status", "none"),
            appealed_at=item.get("appealed_at"),
            created_at=now - timedelta(days=10 - index, minutes=index * 11),
        )
        db.session.add(comment)
        db.session.flush()
        _trace(
            comment,
            decision=item["status"],
            rule_hits=item.get("rule_hits", []),
            llm_raw='{"sentiment": "%s", "risk_score": %.2f}' % (item["sentiment"], item["risk"]),
        )


def _candidates(product: dict, sentiment: str, rng: random.Random):
    """为单个商品生成不重复的商品专属评论候选。"""
    name = product["name"]
    features = product["features"] + product["keywords"]
    issues = PRODUCT_ISSUES[name]

    if sentiment == "positive":
        combos = list(
            iter_product(POSITIVE_TEMPLATES, features, SCENES, POSITIVE_TAILS)
        )
        rng.shuffle(combos)
        for template, feature, scene, tail in combos:
            yield template.format(name=name, feature=feature, scene=scene, tail=tail)
    elif sentiment == "negative":
        combos = list(iter_product(NEGATIVE_TEMPLATES, features, issues, SCENES))
        rng.shuffle(combos)
        for template, feature, issue, scene in combos:
            yield template.format(name=name, feature=feature, issue=issue, scene=scene)
    else:
        combos = list(
            iter_product(NEUTRAL_TEMPLATES, features, SCENES, NEUTRAL_TAILS)
        )
        rng.shuffle(combos)
        for template, feature, scene, tail in combos:
            yield template.format(name=name, feature=feature, scene=scene, tail=tail)


def _add_generated(user: User) -> None:
    """每个商品生成 120 条评论，保证评论内容不重复。"""
    rng = random.Random(42)
    now = datetime.now()

    for product in PRODUCTS:
        target = product["name"]
        positive, neutral, negative = DISTRIBUTIONS[target]
        labels = ["positive"] * positive + ["neutral"] * neutral + ["negative"] * negative
        rng.shuffle(labels)
        iterators = {
            "positive": _candidates(product, "positive", rng),
            "neutral": _candidates(product, "neutral", rng),
            "negative": _candidates(product, "negative", rng),
        }
        used: set[str] = set()

        for sentiment in labels:
            content = next(
                (text for text in iterators[sentiment] if text not in used),
                None,
            )
            if content is None:
                raise RuntimeError(f"{target} 的{sentiment}评论候选不足")
            used.add(content)

            # 关键词必须是正文中真实出现的词，点击后才能搜到对应评论。
            # 去掉商品名，避免“降噪耳机”让所有评论都命中“降噪”。
            content_without_name = content.replace(target, "")
            candidates = list(
                dict.fromkeys(
                    PRODUCT_ISSUES[target]
                    + product["keywords"]
                    + product["features"]
                )
            )
            keywords = [
                word for word in candidates if word in content_without_name
            ][:3]
            if not keywords:
                keywords = [product["features"][0]]

            if sentiment == "positive":
                rating = rng.choice([4, 5, 5])
                risk = round(rng.uniform(0.01, 0.25), 3)
                reason = "商品相关正向评价，未发现违规内容。"
            elif sentiment == "negative":
                rating = rng.choice([1, 2])
                risk = round(rng.uniform(0.01, 0.35), 3)
                reason = "商品相关负向评价，未发现违规内容。"
            else:
                rating = 3
                risk = round(rng.uniform(0.01, 0.30), 3)
                reason = "商品相关中性评价，未发现违规内容。"

            comment = Comment(
                user_id=user.id,
                target_name=target,
                rating=rating,
                content=content,
                status="published",
                sentiment=sentiment,
                sentiment_confidence=round(rng.uniform(0.65, 0.98), 3),
                violation_type="none",
                risk_score=risk,
                is_sarcasm=False,
                reason=reason,
                keywords=keywords,
                engine="llm",
                analysis_ms=rng.randint(900, 3600),
                appeal_status="none",
                created_at=now
                - timedelta(days=rng.randint(0, 364), minutes=rng.randint(0, 1440)),
            )
            db.session.add(comment)
            db.session.flush()
            _trace(
                comment,
                decision="published",
                rule_hits=[],
                llm_raw='{"sentiment": "%s", "risk_score": %.2f}'
                % (sentiment, risk),
            )

        if len(used) != 120:
            raise RuntimeError(f"{target} 只生成了 {len(used)} 条唯一评论")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="清空三表并重建演示数据")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.reset:
            db.drop_all()
            db.create_all()
            print("已重置三张表。")
        else:
            db.create_all()

        existed = Comment.query.count()
        if existed and not args.reset:
            print(f"已有 {existed} 条评论，跳过初始化。需要重建请执行：python seed.py --reset")
            return

        admin = _user("admin", "admin123", "admin")
        reviewer = _user("reviewer", "reviewer123", "reviewer")
        normal = _user("user", "user123", "user")
        db.session.commit()

        _add_demo(normal)
        _add_generated(normal)
        db.session.commit()

        print("演示数据初始化完成：")
        print(f"  用户：{len(User.query.all())}，评论：{Comment.query.count()}，轨迹：{AnalysisTrace.query.count()}")
        print("  每个商品 120 条生成评论（降噪耳机另含 10 条固定演示）")
        print("  管理员 admin/admin123，审核员 reviewer/reviewer123，普通用户 user/user123")
        print("  申诉待复审：1 条（广告评论 #4）")


if __name__ == "__main__":
    main()
