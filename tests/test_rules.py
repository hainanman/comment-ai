from pathlib import Path

from app.ai.rules import load_matcher, normalize, scan_rules


def _matcher(text: str):
    path = Path(__file__).parent / "_test_sensitive_words.txt"
    path.write_text(text, encoding="utf-8")
    try:
        return load_matcher(path)
    finally:
        path.unlink(missing_ok=True)


def test_normalize_fullwidth_and_zero_width():
    assert normalize("ＡＢＣ\u200b 123") == "ABC 123"


def test_dfa_block_and_review():
    matcher = _matcher("加微信,block\n好评返现,review\n")

    block_result = scan_rules("加微信 abc123", matcher)
    assert block_result.block is True
    assert block_result.risk == 1.0

    review_result = scan_rules("好评返现 5 元", matcher)
    assert review_result.block is False
    assert review_result.force_review is True
    assert review_result.risk == 0.6


def test_phone_regex_forces_review():
    matcher = _matcher("")

    result = scan_rules("联系我 13800000000", matcher)
    assert result.force_review is True
    assert result.risk >= 0.9
    assert any(hit["kind"] == "phone" for hit in result.hits)


def test_normal_comment_has_no_hits():
    matcher = _matcher("加微信,block\n")

    result = scan_rules("音质不错，物流很快", matcher)
    assert result.hits == []
    assert result.risk == 0.0
