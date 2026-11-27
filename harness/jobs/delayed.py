"""Hàng đợi job trễ trên Redis (sorted set) — thay cron ad-hoc."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from harness.db.redis_client import get_redis

ZKEY = "jobs:delayed"
DEFAULT_TZ = "Asia/Ho_Chi_Minh"


def schedule_job(job_type: str, payload: dict[str, Any], run_at_unix: float) -> str:
    job_id = f"{job_type}:{payload.get('user_id','?')}:{int(run_at_unix)}:{int(time.time()*1000)}"
    body = json.dumps({"id": job_id, "job_type": job_type, "payload": payload}, ensure_ascii=False)
    get_redis().zadd(ZKEY, {body: run_at_unix})
    return job_id


def pop_due(now: float | None = None, limit: int = 20) -> list[dict[str, Any]]:
    now = now if now is not None else time.time()
    r = get_redis()
    raw_items = r.zrangebyscore(ZKEY, min="-inf", max=now, start=0, num=limit)
    out: list[dict[str, Any]] = []
    for raw in raw_items:
        removed = r.zrem(ZKEY, raw)
        if not removed:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def parse_schedule_at(value: str | None, timezone_name: str = DEFAULT_TZ) -> float | None:
    """Trả unix timestamp nếu schedule_at hợp lệ; None = chạy ngay."""
    if not value or not str(value).strip():
        return None
    raw = str(value).strip()
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(raw, fmt).time()
            dt = datetime.combine(now.date(), t, tzinfo=tz)
            if dt <= now:
                dt = dt + timedelta(days=1)
            return dt.timestamp()
        except ValueError:
            pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.timestamp()
    except ValueError:
        return None


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.strip().split(":")
    return int(parts[0]), int(parts[1])


def next_run_unix(
    state: dict[str, Any],
    *,
    timezone_name: str = DEFAULT_TZ,
    after_unix: Optional[float] = None,
) -> Optional[float]:
    """
    Tính lần chạy kế tiếp từ slot lịch email.
    - weekly: weekday 0=Mon..6=Sun + schedule_time
    - once: schedule_date + schedule_time, hoặc weekday+time sắp tới (không lặp lại sau khi chạy)
    """
    time_s = (state.get("schedule_time") or "").strip()
    if not time_s:
        return None
    try:
        hour, minute = _parse_hhmm(time_s)
    except (ValueError, IndexError):
        return None

    tz = ZoneInfo(timezone_name)
    now = datetime.fromtimestamp(after_unix, tz) if after_unix else datetime.now(tz)
    repeat = (state.get("schedule_repeat") or "once").strip()
    weekday = state.get("schedule_weekday")
    date_s = (state.get("schedule_date") or "").strip() or None

    if repeat == "weekly":
        if weekday is None:
            return None
        try:
            target_wd = int(weekday)
        except (TypeError, ValueError):
            return None
        # Python weekday: Mon=0 .. Sun=6 — khớp ISO trong plan
        days_ahead = (target_wd - now.weekday()) % 7
        candidate = datetime.combine(now.date(), datetime.min.time(), tzinfo=tz).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        ) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate = candidate + timedelta(days=7)
        return candidate.timestamp()

    # once
    if date_s:
        try:
            d = datetime.strptime(date_s[:10], "%Y-%m-%d").date()
        except ValueError:
            try:
                d = datetime.strptime(date_s.replace("/", "-")[:10], "%Y-%m-%d").date()
            except ValueError:
                return None
        candidate = datetime.combine(d, datetime.min.time(), tzinfo=tz).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= now:
            return None  # đã qua — không schedule
        return candidate.timestamp()

    if weekday is not None:
        try:
            target_wd = int(weekday)
        except (TypeError, ValueError):
            return None
        days_ahead = (target_wd - now.weekday()) % 7
        candidate = datetime.combine(now.date(), datetime.min.time(), tzinfo=tz).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        ) + timedelta(days=days_ahead)
        if candidate <= now:
            candidate = candidate + timedelta(days=7)
        return candidate.timestamp()

    # chỉ có giờ → lần tới trong ngày hoặc ngày mai
    candidate = datetime.combine(now.date(), datetime.min.time(), tzinfo=tz).replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )
    if candidate <= now:
        candidate = candidate + timedelta(days=1)
    return candidate.timestamp()
