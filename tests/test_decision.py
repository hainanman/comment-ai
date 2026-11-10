from app.ai.pipeline import decide
from app.ai.rules import RuleResult


def rule(risk: float = 0.1, force_review: bool = False) -> RuleResult:
    return RuleResult(
        normalized="",
        hits=[],
        risk=risk,
        force_review=force_review,
        block=False,
        elapsed_ms=0,
    )


def test_low_risk_published():
    assert decide({"risk_score": 0.1}, rule()) == "published"


def test_medium_risk_reviewing():
    assert decide({"risk_score": 0.6}, rule()) == "reviewing"


def test_high_risk_rejected():
    assert decide({"risk_score": 0.9}, rule()) == "rejected"


def test_force_review_overrides_low_risk():
    assert decide({"risk_score": 0.1}, rule(force_review=True)) == "reviewing"


def test_hard_violation_at_medium_risk_rejected():
    assert decide(
        {"risk_score": 0.6, "violation_type": "fraud"}, rule()
    ) == "rejected"


def test_any_violation_at_low_risk_reviewing():
    assert decide(
        {"risk_score": 0.1, "violation_type": "irrelevant"}, rule()
    ) == "reviewing"


def test_threshold_boundaries():
    assert decide({"risk_score": 0.499}, rule()) == "published"
    assert decide({"risk_score": 0.5}, rule()) == "reviewing"
    assert decide({"risk_score": 0.849}, rule()) == "reviewing"
    assert decide({"risk_score": 0.85}, rule()) == "rejected"
