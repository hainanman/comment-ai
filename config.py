"""应用配置：环境变量、路径、阈值、AI 参数。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
except Exception:  # python-dotenv 未安装时仍允许启动
    pass


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


_DB_URI = os.getenv(
    "DATABASE_URL",
    "sqlite:///comment_ai.db",
)

_ENGINE_OPTIONS = {}
if not _DB_URI.startswith("sqlite"):
    _ENGINE_OPTIONS = {
        "pool_size": 5,
        "max_overflow": 5,
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = _DB_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _ENGINE_OPTIONS

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = 8 * 60 * 60
    MAX_CONTENT_LENGTH = 1024 * 1024

    AI_ENABLED = env_bool("AI_ENABLED", True)
    AI_MODEL = os.getenv("AI_MODEL", "qwen-plus")
    AI_ENDPOINT = os.getenv(
        "AI_ENDPOINT",
        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    )
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
    LLM_TIMEOUT = env_float("LLM_TIMEOUT", 4.0)
    LLM_JSON_MODE = env_bool("LLM_JSON_MODE", True)
    REVIEW_THRESHOLD = env_float("REVIEW_THRESHOLD", 0.50)
    REJECT_THRESHOLD = env_float("REJECT_THRESHOLD", 0.85)
    MAX_COMMENT_LENGTH = env_int("MAX_COMMENT_LENGTH", 500)
    DAILY_LLM_LIMIT = env_int("DAILY_LLM_LIMIT", 300)

    SENSITIVE_WORDS_PATH = DATA_DIR / "sensitive_words.txt"
    POSITIVE_WORDS_PATH = DATA_DIR / "sentiment_positive.txt"
    NEGATIVE_WORDS_PATH = DATA_DIR / "sentiment_negative.txt"
    STOPWORDS_PATH = DATA_DIR / "stopwords.txt"
    USERDICT_PATH = DATA_DIR / "userdict.txt"

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = LOG_DIR / "app.log"
