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


def _describe_job(job_type: str, payload: dict[str, Any]) -> str:
    """Mô tả ngắn tiếng Việt cho UI."""
    payload = payload or {}
    if job_type == "standup_fill":
        url = payload.get("url") or ""
        repeat = payload.get("schedule_repeat") or "once"
        time_s = payload.get("schedule_time") or ""
        parts = ["Điền / nộp standup trên portal"]
        if url:
            parts.append(f"URL: {url}")
        if repeat == "daily":
            parts.append(f"Lặp mỗi ngày{(' lúc ' + time_s) if time_s else ''}")
            parts.append("Đến giờ hỏi nội dung rồi mới điền")
        elif repeat == "weekly":
            parts.append(f"Lặp mỗi tuần{(' lúc ' + time_s) if time_s else ''}")
            parts.append("Đến giờ hỏi nội dung rồi mới điền")
        elif time_s:
            parts.append(f"Một lần · {time_s}")
        return " · ".join(parts)
    if job_type == "standup_content_timeout":
        return "Hết hạn chờ nội dung standup (bỏ lỡ nếu chưa trả lời)"
    if job_type == "email_watch":
        state = dict(payload.get("state") or {})
        for k in ("schedule_repeat", "schedule_time", "schedule_weekday", "schedule_date"):
            if payload.get(k) is not None and state.get(k) is None:
                state[k] = payload.get(k)
        repeat = state.get("schedule_repeat") or ("interval" if payload.get("notify_interval_sec") else "once")
        time_s = state.get("schedule_time") or ""
        parts = ["Đọc email quan trọng (Gmail)"]
        if repeat == "weekly":
            parts.append(f"Lặp mỗi tuần{(' lúc ' + time_s) if time_s else ''}")
        elif payload.get("notify_interval_sec"):
            parts.append(f"Lặp mỗi {payload.get('notify_interval_sec')} giây")
        elif time_s:
            parts.append(f"Một lần · {time_s}")
        return " · ".join(parts)
    return f"Job `{job_type}`"


def list_scheduled_jobs(
    *,
    user_id: Optional[str] = None,
    limit: int = 100,
    timezone_name: str = DEFAULT_TZ,
) -> list[dict[str, Any]]:
    """Liệt kê job chưa chạy (score = run_at_unix), mới → cũ."""
    r = get_redis()
    # withscores: [(member, score), ...]
    raw_items = r.zrange(ZKEY, 0, max(0, limit - 1), withscores=True)
    tz = ZoneInfo(timezone_name)
    out: list[dict[str, Any]] = []
    for raw, score in raw_items:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        payload = data.get("payload") or {}
        if user_id and str(payload.get("user_id") or "") != str(user_id):
            continue
        run_at = float(score)
        dt = datetime.fromtimestamp(run_at, tz)
        job_type = str(data.get("job_type") or "")
        out.append(
            {
                "id": data.get("id"),
                "job_type": job_type,
                "payload": payload,
                "run_at_unix": run_at,
                "run_at_local": dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
                "description": _describe_job(job_type, payload),
                "_raw": raw if isinstance(raw, str) else raw.decode("utf-8", errors="replace"),
            }
        )
    return out


def _find_job_member(
    job_id: str, *, user_id: Optional[str] = None
) -> tuple[Any, dict[str, Any], float] | None:
    """Tìm (raw_member, data, score) theo job id. None nếu không có / sai user."""
    if not job_id:
        return None
    r = get_redis()
    raw_items = r.zrange(ZKEY, 0, -1, withscores=True)
    for raw, score in raw_items:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue
        if str(data.get("id") or "") != str(job_id):
            continue
        payload = data.get("payload") or {}
        if user_id and str(payload.get("user_id") or "") != str(user_id):
            return None
        return raw, data, float(score)
    return None


def cancel_scheduled_job(job_id: str, *, user_id: Optional[str] = None) -> bool:
    """Xoá 1 job khỏi hàng đợi theo id. Trả True nếu đã xoá."""
    found = _find_job_member(job_id, user_id=user_id)
    if not found:
        return False
    raw, _data, _score = found
    return bool(get_redis().zrem(ZKEY, raw))


def pop_job_by_id(job_id: str, *, user_id: Optional[str] = None) -> dict[str, Any] | None:
    """Gỡ job khỏi hàng đợi và trả body (để chạy ngay). None nếu không tìm thấy."""
    found = _find_job_member(job_id, user_id=user_id)
    if not found:
        return None
    raw, data, score = found
    if not get_redis().zrem(ZKEY, raw):
        return None
    data = dict(data)
    data["run_at_unix"] = score
    return data


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
    Tính lần chạy kế tiếp từ slot lịch (email / standup).
    - daily: mỗi ngày đúng schedule_time
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

    if repeat == "daily":
        candidate = datetime.combine(now.date(), datetime.min.time(), tzinfo=tz).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate <= now:
            candidate = candidate + timedelta(days=1)
        return candidate.timestamp()

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
