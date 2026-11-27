"""Hàng đợi job trễ trên Redis (sorted set) — thay cron ad-hoc."""
from __future__ import annotations

import json
import time
from typing import Any

from harness.db.redis_client import get_redis

ZKEY = "jobs:delayed"


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


def parse_schedule_at(value: str | None, timezone_name: str = "Asia/Ho_Chi_Minh") -> float | None:
    """Trả unix timestamp nếu schedule_at hợp lệ; None = chạy ngay."""
    if not value or not str(value).strip():
        return None
    from datetime import datetime
    from zoneinfo import ZoneInfo

    raw = str(value).strip()
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    # HH:MM hoặc HH:MM:SS hôm nay (nếu đã qua → ngày mai)
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            t = datetime.strptime(raw, fmt).time()
            dt = datetime.combine(now.date(), t, tzinfo=tz)
            if dt <= now:
                from datetime import timedelta

                dt = dt + timedelta(days=1)
            return dt.timestamp()
        except ValueError:
            pass
    # ISO-ish
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return dt.timestamp()
    except ValueError:
        return None
