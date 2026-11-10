import pytest

from app.ai.llm import LLMOutputError, parse_llm_output, strip_fence

VALID = """
{
  "sentiment": "negative",
  "sentiment_confidence": 0.93,
  "violation_type": "none",
  "risk_score": 0.08,
  "is_sarcasm": true,
  "reason": "反讽表达，真实态度为负向。"
}
"""


def test_parse_valid_json():
    payload = parse_llm_output(VALID)
    assert payload["sentiment"] == "negative"
    assert payload["is_sarcasm"] is True
    assert payload["risk_score"] == 0.08


def test_parse_code_fence():
    payload = parse_llm_output('```json\n' + VALID + '\n```')
    assert payload["violation_type"] == "none"


def test_strip_fence():
    assert strip_fence('```json\n{"a":1}\n```') == '{"a":1}'


def test_missing_field_raises():
    with pytest.raises(LLMOutputError):
        parse_llm_output('{"sentiment":"positive"}')


def test_invalid_enum_raises():
    bad = VALID.replace('"none"', '"not_a_type"')
    with pytest.raises(LLMOutputError):
        parse_llm_output(bad)


def test_none_with_high_risk_raises():
    bad = VALID.replace('"risk_score": 0.08', '"risk_score": 0.8')
    with pytest.raises(LLMOutputError):
        parse_llm_output(bad)


def test_non_json_raises():
    with pytest.raises(LLMOutputError):
        parse_llm_output("不是 JSON")
