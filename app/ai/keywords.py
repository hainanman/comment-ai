"""关键词提取：jieba TF-IDF + TextRank；jieba 不可用时降级为正则词频。"""
from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

from flask import current_app

logger = logging.getLogger(__name__)

try:
    import jieba
    import jieba.analyse

    JIEBA_AVAILABLE = True
except Exception:  # pragma: no cover - 依赖缺失时仍可启动
    jieba = None
    JIEBA_AVAILABLE = False

DEFAULT_STOPWORDS = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一",
    "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
    "没有", "看", "好", "自己", "这", "那", "这个", "那个", "还是", "但是",
    "因为", "所以", "而且", "以及", "非常", "比较", "真的", "感觉", "觉得",
    "可以", "已经", "就是", "什么", "怎么", "这样", "那样", "一下", "有点",
    "东西", "商品", "评论", "使用", "买了", "收到", "快递", "客服",
}

_POS = ("n", "vn", "v", "a", "an", "nr", "ns", "nt")


def _data_path(config_key: str, filename: str) -> Path:
    try:
        return Path(current_app.config[config_key])
    except (RuntimeError, KeyError):
        return Path(__file__).resolve().parents[2] / "data" / filename


def initialize() -> None:
    if not JIEBA_AVAILABLE:
        logger.warning("jieba 未安装，关键词提取将使用正则词频兜底")
        return
    jieba.initialize()
    userdict = _data_path("USERDICT_PATH", "userdict.txt")
    if userdict.exists():
        try:
            jieba.load_userdict(str(userdict))
            logger.info("用户词典加载完成：%s", userdict)
        except Exception as exc:
            logger.warning("用户词典加载失败：%s", exc)


def _load_stopwords() -> set[str]:
    words = set(DEFAULT_STOPWORDS)
    path = _data_path("STOPWORDS_PATH", "stopwords.txt")
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            word = line.strip()
            if word and not word.startswith("#"):
                words.add(word)
    return words


def _valid(word: str, stopwords: set[str]) -> bool:
    word = word.strip()
    if not (2 <= len(word) <= 8):
        return False
    if word in stopwords:
        return False
    if word.isdigit():
        return False
    if not re.search(r"[\u4e00-\u9fa5A-Za-z]", word):
        return False
    return True


def _fallback_keywords(text: str, top_k: int, stopwords: set[str]) -> list[str]:
    if JIEBA_AVAILABLE:
        tokens = jieba.lcut(text)
    else:
        tokens = re.findall(r"[\u4e00-\u9fa5A-Za-z]{2,8}", text)
    counter = Counter(
        token.strip() for token in tokens if _valid(token.strip(), stopwords)
    )
    return [word for word, _ in counter.most_common(top_k)]


def extract_keywords(text: str, top_k: int = 5) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    stopwords = _load_stopwords()

    if JIEBA_AVAILABLE:
        try:
            tfidf = dict(
                jieba.analyse.extract_tags(
                    text, topK=10, withWeight=True, allowPOS=_POS
                )
            )
            textrank = dict(
                jieba.analyse.textrank(
                    text, topK=10, withWeight=True, allowPOS=_POS
                )
            )
        except Exception as exc:
            logger.warning("jieba 关键词提取失败：%s", exc)
            tfidf, textrank = {}, {}

        merged: dict[str, float] = {}
        for source in (tfidf, textrank):
            if not source:
                continue
            max_weight = max(source.values()) or 1.0
            for word, weight in source.items():
                word = word.strip()
                if not _valid(word, stopwords):
                    continue
                merged[word] = merged.get(word, 0.0) + 0.5 * (weight / max_weight)
        ranked = sorted(merged.items(), key=lambda item: item[1], reverse=True)
        words = [word for word, _ in ranked[:top_k]]
        if words:
            return words

    return _fallback_keywords(text, top_k, stopwords)
