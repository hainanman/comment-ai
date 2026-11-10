"""情感判别模块测试。"""
from __future__ import annotations

import pytest

from app import create_app
from app.ai.pipeline import analyze_comment
from app.ai.sentiment import analyze_sentiment, rule_sentiment


@pytest.fixture(scope="module")
def app():
    app = create_app()
    app.config.update(TESTING=True)
    with app.app_context():
        yield app


def test_positive_sentiment(app):
    result = analyze_sentiment("音质不错，戴了一天也不夹耳朵，物流很快。")
    assert result.label == "positive"
    assert result.confidence >= 0.6
    assert result.positive_hits


def test_negative_sentiment(app):
    result = analyze_sentiment("用了三天就断连，客服也不回消息。")
    assert result.label == "negative"
    assert result.negative_hits


def test_neutral_sentiment(app):
    result = analyze_sentiment("包装一般，功能符合预期。")
    assert result.label == "neutral"
    assert result.confidence < 0.6


def test_negation_flips_positive(app):
    result = analyze_sentiment("音质不好，戴着不舒服。")
    assert result.label == "negative"
    assert result.negations
    assert any(hit["negated"] for hit in result.positive_hits)


def test_degree_intensifies(app):
    normal = analyze_sentiment("满意")
    strong = analyze_sentiment("非常满意")
    assert strong.label == "positive"
    assert strong.score > normal.score
    assert "非常" in strong.intensifiers


def test_sarcasm_with_negative_context(app):
    result = analyze_sentiment("戴了一天耳朵就发炎，这耳机真是绝了。")
    assert result.label == "negative"
    assert result.is_sarcasm is True


def test_sarcasm_positive_words_with_bad_result(app):
    result = analyze_sentiment("质量真好，用一天就坏。")
    assert result.label == "negative"
    assert result.is_sarcasm is True


def test_wireless_is_not_negation(app):
    result = analyze_sentiment("无线耳机音质很好。")
    assert result.label == "positive"
    assert not result.negations


def test_rule_sentiment_compat(app):
    label, confidence = rule_sentiment("有点失望")
    assert label == "negative"
    assert 0 <= confidence <= 1


def test_pipeline_uses_rule_sentiment_when_ai_disabled(app):
    old = app.config["AI_ENABLED"]
    app.config["AI_ENABLED"] = False
    try:
        result = analyze_comment("非常满意，物流也很快。", "降噪耳机")
    finally:
        app.config["AI_ENABLED"] = old
    assert result.engine == "rule"
    assert result.sentiment == "positive"
    assert result.sentiment_confidence > 0.6
