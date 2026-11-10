"""数据概览/情感倾向的时间范围工具。"""
from __future__ import annotations

from datetime import date, datetime, timedelta

RANGE_OPTIONS = (
    ("all", "全部"),
    ("365", "一年内"),
    ("180", "半年内"),
)
RANGE_KEYS = {key for key, _ in RANGE_OPTIONS}


def normalize_range(value: str | None, default: str = "all") -> str:
    value = (value or "").strip()
    return value if value in RANGE_KEYS else default


def range_label(value: str) -> str:
    return dict(RANGE_OPTIONS).get(value, "全部")


def range_start(value: str, now: datetime | None = None) -> datetime | None:
    """返回区间起点；全部返回 None。"""
    if value not in {"365", "180"}:
        return None
    now = now or datetime.now()
    days = 365 if value == "365" else 180
    return (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def month_start(value: datetime | date) -> datetime:
    if isinstance(value, date) and not isinstance(value, datetime):
        value = datetime.combine(value, datetime.min.time())
    return value.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def month_sequence(start: datetime, end: datetime) -> list[str]:
    current = month_start(start)
    last = month_start(end)
    result = []
    while current <= last:
        result.append(current.strftime("%Y-%m"))
        # 下个月
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)
    return result


def last_months(count: int, now: datetime | None = None) -> list[str]:
    now = now or datetime.now()
    current = month_start(now)
    result = []
    for offset in range(count - 1, -1, -1):
        year = current.year
        month = current.month - offset
        while month <= 0:
            month += 12
            year -= 1
        result.append(f"{year:04d}-{month:02d}")
    return result
