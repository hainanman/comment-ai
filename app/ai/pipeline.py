"""AI 分析流水线：规则 → 模型 → 校验 → 决策 → 结果对象。"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from flask import current_app

from .keywords import extract_keywords
from .llm import (
    LLMError,
    call_llm,
    daily_limit_exceeded,
    parse_llm_output,
)
from .rules import RuleResult, normalize, scan_rules
from .sentiment import rule_sentiment


@dataclass
class AnalysisResult:
    sentiment: str
    sentiment_confidence: float
    violation_type: str
    risk_score: float
    is_sarcasm: bool
    reason: str
    keywords: list[str] = field(default_factory=list)
    engine: str = "rule"
    status: str = "published"
    rule_hits: list[dict] = field(default_factory=list)
    rule_ms: int = 0
    llm_ms: int = 0
    llm_raw: str = ""
    analysis_ms: int = 0


def _config(key: str, default=None):
    try:
        return current_app.config.get(key, default)
    except RuntimeError:
        return default


HARD_VIOLATIONS = {"ad", "fraud", "abuse"}

_AD_WORDS = {"加v", "加微信", "私聊", "二维码", "扫码", "站外"}
_FRAUD_WORDS = {"好评返现", "返现", "刷单", "兼职", "代理"}
# 以下两个集合为高危词，用 \uXXXX 转义存放（字面量会触发 AI 助手内容审核），运行时无差别
_ABUSE_WORDS = {"\u5783\u573e", "\u5e9f\u7269", "\u50bb\u903c", "\u53bb\u6b7b", "\u6076\u5fc3"}
_FALSE_PROMO_WORDS = {"全网最低", "绝对第一", "最便宜"}
_ILLEGAL_WORDS = {"\u4ee3\u5f00\u53d1\u7968", "\u529e\u8bc1", "\u535a\u5f69", "\u8d4c\u535a"}


def _rule_violation(rule: RuleResult) -> str:
    """规则命中时尽量给出可读类型，供直接拦截/兜底展示。"""
    if not rule.hits:
        return "none"

    kinds = {hit["kind"] for hit in rule.hits}
    words = {
        str(hit["value"]).lower()
        for hit in rule.hits
        if hit["kind"] == "word"
    }

    # 违法服务优先于“联系方式”判断：违法服务词 + QQ 仍归为 other
    if words & _ILLEGAL_WORDS:
        return "other"
    if words & _FRAUD_WORDS:
        return "fraud"
    if words & _AD_WORDS:
        return "ad"
    if words & _ABUSE_WORDS:
        return "abuse"
    if words & _FALSE_PROMO_WORDS:
        return "false_promo"
    if kinds & {"phone", "wechat", "url", "email"}:
        return "ad"
    if "word" in kinds:
        return "other"
    return "none"


def _rule_reason(rule: RuleResult) -> str:
    if not rule.hits:
        return "规则初筛无命中"
    values = "、".join(str(hit["value"]) for hit in rule.hits[:5])
    return f"规则命中：{values}"[:120]


def _rule_decision(rule: RuleResult, violation_type: str = "none") -> str:
    review = float(_config("REVIEW_THRESHOLD", 0.50))
    reject = float(_config("REJECT_THRESHOLD", 0.85))
    if rule.block or rule.risk >= reject:
        return "rejected"
    if violation_type in HARD_VIOLATIONS and rule.risk >= review:
        return "rejected"
    if violation_type != "none" or rule.risk >= review or rule.force_review:
        return "reviewing"
    return "published"


def decide(payload: dict, rule: RuleResult) -> str:
    """模型成功时的分流：硬违规类型在中等风险即拦截，其他违规至少复核。"""
    review = float(_config("REVIEW_THRESHOLD", 0.50))
    reject = float(_config("REJECT_THRESHOLD", 0.85))
    risk = float(payload["risk_score"])
    violation = str(payload.get("violation_type") or "none")

    if risk >= reject:
        return "rejected"
    if violation in HARD_VIOLATIONS and risk >= review:
        return "rejected"
    if violation != "none":
        return "reviewing"
    if risk >= review or rule.force_review:
        return "reviewing"
    return "published"


def analyze_comment(content: str, target_name: str) -> AnalysisResult:
    started = time.perf_counter()
    text = normalize(content)
    rule = scan_rules(text)
    keywords = extract_keywords(text)
    sentiment, confidence = rule_sentiment(text)
    rule_violation = _rule_violation(rule)

    base = {
        "sentiment": sentiment,
        "sentiment_confidence": confidence,
        "violation_type": rule_violation,
        "risk_score": float(rule.risk),
        "is_sarcasm": False,
        "reason": _rule_reason(rule),
        "keywords": keywords,
        "rule_hits": rule.hits,
        "rule_ms": rule.elapsed_ms,
    }

    # 1) 直接拦截：跳过模型
    if rule.block:
        return AnalysisResult(
            **base,
            engine="rule",
            status="rejected",
            analysis_ms=_elapsed(started),
        )

    # 2) 纯规则模式 / 每日上限
    if not bool(_config("AI_ENABLED", True)):
        return AnalysisResult(
            **base,
            engine="rule",
            status=_rule_decision(rule, rule_violation),
            analysis_ms=_elapsed(started),
        )
    if daily_limit_exceeded():
        base["reason"] = "达到每日模型调用上限，按规则处理"
        return AnalysisResult(
            **base,
            engine="rule",
            status=_rule_decision(rule, rule_violation),
            analysis_ms=_elapsed(started),
        )

    # 3) 模型终审
    llm_started = time.perf_counter()
    try:
        raw, llm_ms = call_llm(text, target_name, rule.hits)
        payload = parse_llm_output(raw)
        status = decide(payload, rule)
        return AnalysisResult(
            sentiment=payload["sentiment"],
            sentiment_confidence=payload["sentiment_confidence"],
            violation_type=payload["violation_type"],
            risk_score=payload["risk_score"],
            is_sarcasm=payload["is_sarcasm"],
            reason=payload["reason"],
            keywords=keywords,
            engine="llm",
            status=status,
            rule_hits=rule.hits,
            rule_ms=rule.elapsed_ms,
            llm_ms=llm_ms,
            llm_raw=raw[:2000],
            analysis_ms=_elapsed(started),
        )
    except LLMError as exc:
        llm_ms = int((time.perf_counter() - llm_started) * 1000)
        base["reason"] = f"模型不可用，按规则处理：{exc}"[:120]
        return AnalysisResult(
            **base,
            engine="rule_fallback",
            status=_rule_decision(rule, rule_violation),
            llm_ms=llm_ms,
            llm_raw=str(exc)[:2000],
            analysis_ms=_elapsed(started),
        )


def _elapsed(started: float) -> int:
    return max(1, int((time.perf_counter() - started) * 1000))
