"""规则情感判别：词典 + 否定 + 程度副词 + 反讽 + 表情。

主链路仍由 qwen-plus 给出最终情感；本模块用于：
- AI 关闭/失败时的兜底
- 规则直接拦截时的情感兜底
- 评测脚本中的“纯规则”基线

设计目标是小而可解释：不训练模型，不引入额外服务。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from flask import current_app

from .rules import normalize, unescape_text

_END = "__end__"
_PUNCT = "，。！？；、,.!?;:：\n\r"
_WINDOW = 6

_NEGATIONS = (
    "不是",
    "没有",
    "并没",
    "并未",
    "并不",
    "毫不",
    "从未",
    "毫无",
    "不太",
    "不够",
    "不怎么",
    "不再",
    "不会",
    "不能",
    "不",
    "没",
    "无",
    "未",
    "别",
    "莫",
    "勿",
)

# “无线/无比/不过/不得不”等不是否定，先剔除再判断
_NON_NEGATING = (
    "无线",
    "无人机",
    "无感",
    "无缝",
    "无论",
    "无法",
    "无聊",
    "无理由",
    "无货",
    "无门槛",
    "无广告",
    "无比",
    "不过",
    "不仅",
    "不但",
    "不光",
    "不少",
    "不得不",
    "是不是",
)

_DEGREES = {
    "极其": 1.6,
    "非常": 1.5,
    "超级": 1.5,
    "特别": 1.4,
    "十分": 1.4,
    "最": 1.35,
    "太": 1.3,
    "很": 1.25,
    "真": 1.2,
    "挺": 1.15,
    "更": 1.15,
    "比较": 1.1,
    "有点": 0.7,
    "有些": 0.75,
    "稍微": 0.6,
    "略": 0.6,
}

_POSITIVE_EMOJI = {
    "😊": 1.2,
    "😄": 1.2,
    "😍": 1.3,
    "👍": 1.3,
    "❤": 1.2,
    "❤️": 1.2,
    "🔥": 1.1,
    "👏": 1.1,
    "✅": 1.0,
}
_NEGATIVE_EMOJI = {
    "😞": 1.1,
    "😡": 1.3,
    "😤": 1.2,
    "👎": 1.3,
    "💔": 1.2,
    "🤮": 1.4,
    "❌": 1.1,
}

_SARCASM_PATTERNS = (
    "真是绝了",
    "呵呵",
    "真棒",
    "真好",
    "太好了",
    "好一个",
    "真是谢谢",
    "厉害了",
    "真不错",
    "好家伙",
)
_NEGATIVE_CONTEXT = (
    "发炎",
    "断连",
    "坏了",
    "坏",
    "难用",
    "失望",
    "退货",
    "故障",
    "差",
    "漏",
    "卡顿",
    "异味",
    "磨脚",
    "疼",
    "裂",
    "掉",
    "假",
    "慢",
    "贵",
    "吵",
    "硬",
)
_NEUTRAL_PHRASES = (
    "一般",
    "中规中矩",
    "符合预期",
    "还行",
    "还可以",
    "普通",
    "没什么惊喜",
    "不好说",
    "看情况",
    "因人而异",
    "凑合",
)


@dataclass(frozen=True)
class SentimentHit:
    word: str
    polarity: str
    weight: float
    start: int
    end: int
    negated: bool = False
    degree: float = 1.0
    source: str = "word"
    degree_word: str | None = None
    negation_word: str | None = None

    @property
    def signed(self) -> float:
        value = self.weight * self.degree
        if self.polarity == "negative":
            value = -value
        if self.negated:
            value = -value
        return value

    @property
    def value(self) -> float:
        return self.signed

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "polarity": self.polarity,
            "weight": round(self.weight, 3),
            "degree": round(self.degree, 3),
            "negated": self.negated,
            "value": round(self.signed, 3),
            "source": self.source,
        }


@dataclass
class SentimentResult:
    label: str
    score: float
    confidence: float
    positive_hits: list[dict] = field(default_factory=list)
    negative_hits: list[dict] = field(default_factory=list)
    negations: list[str] = field(default_factory=list)
    intensifiers: list[str] = field(default_factory=list)
    is_sarcasm: bool = False
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 3),
            "positive_hits": self.positive_hits,
            "negative_hits": self.negative_hits,
            "negations": self.negations,
            "intensifiers": self.intensifiers,
            "is_sarcasm": self.is_sarcasm,
            "reason": self.reason,
        }


@lru_cache(maxsize=8)
def _load_lexicon(path_str: str) -> dict[str, float]:
    """加载词表；支持 `词` 或 `词,权重` 两种格式。"""
    path = Path(path_str)
    if not path.exists():
        return {}
    lexicon: dict[str, float] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = unescape_text(line.strip())
        if not line or line.startswith("#"):
            continue
        word, _, raw_weight = line.partition(",")
        word = word.strip()
        if not word:
            continue
        try:
            weight = float(raw_weight) if raw_weight.strip() else 1.0
        except ValueError:
            weight = 1.0
        lexicon[word] = max(0.1, min(2.0, weight))
    return lexicon


class SentimentAnalyzer:
    def __init__(self, positive_path: str, negative_path: str):
        self.positive = _load_lexicon(positive_path)
        self.negative = _load_lexicon(negative_path)
        self.root: dict = {}
        for word, weight in self.positive.items():
            self._add(word, "positive", weight)
        for word, weight in self.negative.items():
            self._add(word, "negative", weight)

    def _add(self, word: str, polarity: str, weight: float) -> None:
        node = self.root
        for ch in word:
            node = node.setdefault(ch, {})
        node[_END] = (word, polarity, weight)

    def _match_at(self, text: str, start: int):
        node = self.root
        best = None
        end = start
        while end < len(text) and text[end] in node:
            node = node[text[end]]
            end += 1
            if _END in node:
                best = (end, node[_END])
        return best

    @staticmethod
    def _context(text: str, start: int) -> str:
        before = text[max(0, start - _WINDOW):start]
        for sep in _PUNCT:
            idx = before.rfind(sep)
            if idx >= 0:
                before = before[idx + 1:]
        for phrase in _NON_NEGATING:
            before = before.replace(phrase, "")
        return before

    @staticmethod
    def _detect_negation(before: str) -> str | None:
        for word in _NEGATIONS:
            if word in before:
                return word
        return None

    @staticmethod
    def _detect_degree(before: str) -> tuple[str | None, float]:
        for word in sorted(_DEGREES, key=len, reverse=True):
            if word in before:
                return word, _DEGREES[word]
        return None, 1.0

    def _word_hits(self, text: str) -> list[SentimentHit]:
        hits: list[SentimentHit] = []
        index = 0
        while index < len(text):
            match = self._match_at(text, index)
            if not match:
                index += 1
                continue
            end, (word, polarity, weight) = match
            before = self._context(text, index)
            negation = self._detect_negation(before)
            degree_word, degree = self._detect_degree(before)
            hits.append(
                SentimentHit(
                    word=word,
                    polarity=polarity,
                    weight=weight,
                    start=index,
                    end=end,
                    negated=bool(negation),
                    degree=degree,
                    source="word",
                    degree_word=degree_word,
                    negation_word=negation,
                )
            )
            index = end
        return hits

    @staticmethod
    def _emoji_hits(text: str) -> list[SentimentHit]:
        hits: list[SentimentHit] = []
        for index, char in enumerate(text):
            if char in _POSITIVE_EMOJI:
                hits.append(
                    SentimentHit(
                        word=char,
                        polarity="positive",
                        weight=_POSITIVE_EMOJI[char],
                        start=index,
                        end=index + 1,
                        source="emoji",
                    )
                )
            elif char in _NEGATIVE_EMOJI:
                hits.append(
                    SentimentHit(
                        word=char,
                        polarity="negative",
                        weight=_NEGATIVE_EMOJI[char],
                        start=index,
                        end=index + 1,
                        source="emoji",
                    )
                )
        return hits

    def analyze(self, text: str) -> SentimentResult:
        text = normalize(text)
        hits = self._word_hits(text) + self._emoji_hits(text)
        hits.sort(key=lambda item: item.start)

        raw = sum(hit.signed for hit in hits)
        has_neutral_phrase = any(phrase in text for phrase in _NEUTRAL_PHRASES)
        if has_neutral_phrase and abs(raw) < 1.5:
            raw *= 0.5

        sarcasm_pattern = next(
            (pattern for pattern in _SARCASM_PATTERNS if pattern in text), None
        )
        sarcasm = bool(
            sarcasm_pattern
            and (sarcasm_pattern == "呵呵" or any(word in text for word in _NEGATIVE_CONTEXT))
        )
        if sarcasm:
            raw = -max(1.0, abs(raw))

        emphasis = 1.0 + min(
            0.2, 0.04 * (text.count("!") + text.count("！"))
        )
        raw *= emphasis

        score = max(-1.0, min(1.0, raw / 3.0))
        if abs(score) < 0.12:
            score = 0.0
        if score >= 0.12:
            label = "positive"
        elif score <= -0.12:
            label = "negative"
        else:
            label = "neutral"

        if not hits:
            confidence = 0.35
        else:
            confidence = 0.55 + min(
                0.35,
                abs(raw) * 0.10 + min(0.12, (len(hits) - 1) * 0.04),
            )
            if label == "neutral":
                confidence = min(confidence, 0.62)
            if sarcasm:
                confidence = max(confidence, 0.82)
        confidence = round(min(0.95, max(0.30, confidence)), 3)

        negations = sorted(
            {
                getattr(hit, "negation_word")
                for hit in hits
                if getattr(hit, "negation_word", None)
            }
        )
        intensifiers = sorted(
            {
                getattr(hit, "degree_word")
                for hit in hits
                if getattr(hit, "degree_word", None)
            }
        )
        positive_hits = [hit.to_dict() for hit in hits if hit.polarity == "positive"]
        negative_hits = [hit.to_dict() for hit in hits if hit.polarity == "negative"]
        reason = self._reason(
            positive_hits, negative_hits, negations, intensifiers, sarcasm
        )
        return SentimentResult(
            label=label,
            score=round(score, 3),
            confidence=confidence,
            positive_hits=positive_hits,
            negative_hits=negative_hits,
            negations=negations,
            intensifiers=intensifiers,
            is_sarcasm=sarcasm,
            reason=reason,
        )

    @staticmethod
    def _reason(
        positive_hits: list[dict],
        negative_hits: list[dict],
        negations: list[str],
        intensifiers: list[str],
        sarcasm: bool,
    ) -> str:
        parts = []
        if positive_hits:
            parts.append("正向：" + "、".join(hit["word"] for hit in positive_hits[:4]))
        if negative_hits:
            parts.append("负向：" + "、".join(hit["word"] for hit in negative_hits[:4]))
        if negations:
            parts.append("否定：" + "、".join(negations[:3]))
        if intensifiers:
            parts.append("程度：" + "、".join(intensifiers[:3]))
        if sarcasm:
            parts.append("反讽语气")
        if not parts:
            return "未命中情感词，按中性处理"
        return "规则情感｜" + "；".join(parts)[:120]


def _config_path(key: str) -> str:
    try:
        return str(current_app.config.get(key, ""))
    except RuntimeError:
        return ""


@lru_cache(maxsize=4)
def _get_analyzer(positive_path: str, negative_path: str) -> SentimentAnalyzer:
    return SentimentAnalyzer(positive_path, negative_path)


def analyze_sentiment(text: str) -> SentimentResult:
    positive_path = _config_path("POSITIVE_WORDS_PATH")
    negative_path = _config_path("NEGATIVE_WORDS_PATH")
    return _get_analyzer(positive_path, negative_path).analyze(text)


def rule_sentiment(text: str) -> tuple[str, float]:
    """兼容旧调用：返回 (label, confidence)。"""
    result = analyze_sentiment(text)
    return result.label, result.confidence
