"""Trích / gộp slot bằng LLM (không rule keyword)."""
from __future__ import annotations

import json
import re
from typing import Any

STANDUP_REQUIRED = ("yesterday", "today", "url")
STANDUP_OPTIONAL = ("schedule_at",)

EXTRACT_SYSTEM = """Bạn trích thông tin từ tin nhắn user cho agent.
Chỉ trả về ĐÚNG một JSON object, không markdown.
Với intent standup_fill, schema:
{
  "yesterday": string|null,
  "today": string|null,
  "url": string|null,
  "schedule_at": string|null
}
Với intent email_watch, schema:
{
  "notify_interval_sec": number|null,
  "newer_than_days": number|null,
  "after_date": string|null,
  "before_date": string|null,
  "include_read": boolean|null,
  "run_now": boolean|null,
  "schedule_enabled": boolean|null,
  "schedule_time": string|null,
  "schedule_weekday": number|null,
  "schedule_date": string|null,
  "schedule_repeat": "once"|"weekly"|null
}
Giải thích email:
- newer_than_days / after_date / before_date / include_read: khung quét mail (null newer_than → hệ thống mặc định 7 ngày).
- run_now: true nếu user muốn kiểm tra email ngay trong lượt này.
- schedule_enabled: true nếu user muốn hẹn giờ đọc email / nhắc sau này.
- schedule_time: "HH:MM" (24h), vd "07:00".
- schedule_weekday: 0=Thứ Hai … 6=Chủ Nhật (ISO). Thứ Năm = 3.
- schedule_date: "YYYY-MM-DD" khi one-shot có ngày cụ thể.
- schedule_repeat: "weekly" nếu user nói mỗi/hàng tuần/lặp lại; "once" nếu chỉ một lần vào ngày/giờ cụ thể; null nếu không đặt lịch.
Không bịa ngày giờ. Field không có thì null."""

MERGE_SYSTEM = """Bạn đang ở bước HITL: user bổ sung thông tin còn thiếu.
State hiện tại (JSON) và missing_fields được cung cấp.
Hãy gộp tin nhắn mới vào state, trả về ĐÚNG một JSON object cùng schema state (standup hoặc email).
Field cũ giữ nguyên nếu tin nhắn mới không cập nhật. Không bịa.
Không cho phép bỏ qua kết nối email — không tạo field skip_grant.
Với lịch email: điền schedule_time / schedule_weekday / schedule_date / schedule_repeat khi user cung cấp."""

HITL_MESSAGE_SYSTEM = """Bạn là trợ lý digitalboo, nói chuyện tự nhiên với người dùng bằng tiếng Việt.
Nhiệm vụ: viết ĐÚNG một tin nhắn ngắn (1–3 câu) giải thích cần gì tiếp theo, thân thiện, rõ ràng.
TUYỆT ĐỐI KHÔNG dùng jargon kỹ thuật: không nói HITL, checkpoint, missing_fields, grant, OAuth, API, actions, Redis, cron.
Nếu thiếu kết nối Gmail: mời người dùng bấm nút kết nối Gmail trên giao diện (nút sẽ hiện sẵn) — KHÔNG nói có thể bỏ qua.
Nếu thiếu lịch (giờ / thứ trong tuần / ngày): hỏi tự nhiên phần còn thiếu để hẹn đọc email.
Nếu thiếu thông tin standup (hôm qua / hôm nay / URL): hỏi tự nhiên những phần còn thiếu.
Không liệt kê bullet máy móc trừ khi thật cần. Không thêm lời dẫn kiểu "Thiếu thông tin — …".
Chỉ trả về nội dung tin nhắn, không JSON, không markdown fence."""

SCHEDULE_CONFIRM_SYSTEM = """Bạn là trợ lý digitalboo. Viết ĐÚNG một tin nhắn ngắn tiếng Việt xác nhận đã hẹn lịch đọc email quan trọng.
Không jargon (không nói Redis, cron, job_id, unix). Nêu rõ thời điểm và có lặp hàng tuần hay chỉ một lần.
Nếu đồng thời đã quét ngay, nhắc ngắn kết quả quét. Chỉ trả về nội dung tin nhắn."""


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def llm_json(system: str, user: str) -> dict[str, Any]:
    from ai import call_model  # type: ignore

    reply = call_model(system, user)
    parsed = _extract_json(reply.get("text") or "")
    parsed["_model"] = reply.get("model")
    parsed["_tokens_in"] = reply.get("tokens_in")
    parsed["_tokens_out"] = reply.get("tokens_out")
    return parsed


def llm_text(system: str, user: str) -> dict[str, Any]:
    from ai import call_model  # type: ignore

    reply = call_model(system, user)
    return {
        "text": (reply.get("text") or "").strip(),
        "_model": reply.get("model"),
        "_tokens_in": reply.get("tokens_in"),
        "_tokens_out": reply.get("tokens_out"),
    }


def extract_standup_slots(text: str, history_text: str = "") -> dict[str, Any]:
    from harness.memory import with_history

    data = llm_json(
        EXTRACT_SYSTEM,
        with_history(history_text, text, extra="intent=standup_fill — trích slot từ lịch sử + tin hiện tại."),
    )
    return {
        "yesterday": _str_or_none(data.get("yesterday")),
        "today": _str_or_none(data.get("today")),
        "url": _str_or_none(data.get("url")),
        "schedule_at": _str_or_none(data.get("schedule_at")),
        "_model": data.get("_model"),
        "_tokens_in": data.get("_tokens_in"),
        "_tokens_out": data.get("_tokens_out"),
    }


def _parse_int(val: Any, *, min_v: int | None = None, max_v: int | None = None) -> int | None:
    if val is None or val == "":
        return None
    try:
        n = int(val)
    except (TypeError, ValueError):
        return None
    if min_v is not None and n < min_v:
        return None
    if max_v is not None and n > max_v:
        return None
    return n


def extract_email_slots(text: str, history_text: str = "") -> dict[str, Any]:
    from harness.memory import with_history

    data = llm_json(
        EXTRACT_SYSTEM,
        with_history(history_text, text, extra="intent=email_watch — trích slot từ lịch sử + tin hiện tại."),
    )
    interval = _parse_int(data.get("notify_interval_sec"), min_v=1)
    days = _parse_int(data.get("newer_than_days"), min_v=1)
    weekday = _parse_int(data.get("schedule_weekday"), min_v=0, max_v=6)
    include_read = data.get("include_read")
    if include_read is not None:
        include_read = bool(include_read)
    run_now = data.get("run_now")
    if run_now is not None:
        run_now = bool(run_now)
    schedule_enabled = data.get("schedule_enabled")
    if schedule_enabled is not None:
        schedule_enabled = bool(schedule_enabled)
    repeat = _str_or_none(data.get("schedule_repeat"))
    if repeat and repeat not in ("once", "weekly"):
        repeat = None
    # Suy luận: có time/weekday/date → bật schedule
    schedule_time = _normalize_time(_str_or_none(data.get("schedule_time")))
    schedule_date = _str_or_none(data.get("schedule_date"))
    if schedule_enabled is None and (schedule_time or weekday is not None or schedule_date or repeat):
        schedule_enabled = True
    if schedule_enabled and repeat is None and (schedule_date or schedule_time):
        # mặc định once nếu có dấu hiệu lịch nhưng chưa nói lặp — LLM nên set; fallback once
        if weekday is not None and not schedule_date:
            repeat = "weekly"
        else:
            repeat = "once"

    return {
        "notify_interval_sec": interval,
        "newer_than_days": days,
        "after_date": _str_or_none(data.get("after_date")),
        "before_date": _str_or_none(data.get("before_date")),
        "include_read": include_read,
        "run_now": run_now,
        "schedule_enabled": schedule_enabled,
        "schedule_time": schedule_time,
        "schedule_weekday": weekday,
        "schedule_date": schedule_date,
        "schedule_repeat": repeat,
        "_model": data.get("_model"),
        "_tokens_in": data.get("_tokens_in"),
        "_tokens_out": data.get("_tokens_out"),
    }


def build_gmail_query(state: dict[str, Any] | None = None) -> str:
    """Gmail q: mặc định unread + 7 ngày; tôn trọng slot user nếu có."""
    state = state or {}
    parts: list[str] = []
    if not state.get("include_read"):
        parts.append("is:unread")

    after = _str_or_none(state.get("after_date"))
    before = _str_or_none(state.get("before_date"))
    if after or before:
        if after:
            parts.append(f"after:{after.replace('-', '/')}")
        if before:
            parts.append(f"before:{before.replace('-', '/')}")
    else:
        days = state.get("newer_than_days")
        try:
            days = int(days) if days is not None else 7
        except (TypeError, ValueError):
            days = 7
        if days < 1:
            days = 1
        parts.append(f"newer_than:{days}d")

    return " ".join(parts)


def merge_slots(
    intent: str,
    state: dict[str, Any],
    user_text: str,
    missing: list[str],
    history_text: str = "",
) -> dict[str, Any]:
    clean_state = {k: v for k, v in state.items() if not str(k).startswith("_")}
    data = llm_json(
        MERGE_SYSTEM,
        json.dumps(
            {
                "intent": intent,
                "state": clean_state,
                "missing_fields": missing,
                "user_message": user_text,
                "chat_history": history_text,
            },
            ensure_ascii=False,
        ),
    )
    merged = dict(clean_state)
    for k, v in data.items():
        if str(k).startswith("_"):
            continue
        if v is None or v == "":
            continue
        merged[k] = v
    merged.pop("skip_grant", None)
    if "schedule_time" in merged:
        merged["schedule_time"] = _normalize_time(_str_or_none(merged.get("schedule_time")))
    if "schedule_weekday" in merged:
        merged["schedule_weekday"] = _parse_int(merged.get("schedule_weekday"), min_v=0, max_v=6)
    if "schedule_repeat" in merged:
        r = _str_or_none(merged.get("schedule_repeat"))
        merged["schedule_repeat"] = r if r in ("once", "weekly") else merged.get("schedule_repeat")
    merged["_model"] = data.get("_model")
    merged["_tokens_in"] = data.get("_tokens_in")
    merged["_tokens_out"] = data.get("_tokens_out")
    return merged


def standup_missing(state: dict[str, Any]) -> list[str]:
    missing = []
    for key in STANDUP_REQUIRED:
        val = state.get(key)
        if not val or not str(val).strip():
            missing.append(key)
    return missing


def email_missing(state: dict[str, Any], has_grant: bool) -> list[str]:
    """Grant bắt buộc; nếu có lịch thì thiếu time/weekday|date."""
    missing: list[str] = []
    if not has_grant:
        missing.append("email_grant")
    missing.extend(email_schedule_missing(state))
    return missing


def email_schedule_missing(state: dict[str, Any]) -> list[str]:
    """Thiếu slot lịch khi user muốn hẹn giờ đọc email."""
    if not state.get("schedule_enabled"):
        return []
    missing: list[str] = []
    if not _normalize_time(_str_or_none(state.get("schedule_time"))):
        missing.append("schedule_time")
    repeat = _str_or_none(state.get("schedule_repeat")) or "once"
    if repeat == "weekly":
        if _parse_int(state.get("schedule_weekday"), min_v=0, max_v=6) is None:
            missing.append("schedule_weekday")
    else:
        # once: cần date hoặc (weekday+time hôm nay/tới) — bắt buộc schedule_date nếu không có weekday
        if not _str_or_none(state.get("schedule_date")):
            if _parse_int(state.get("schedule_weekday"), min_v=0, max_v=6) is None:
                missing.append("schedule_date")
    return missing


def wants_schedule(state: dict[str, Any]) -> bool:
    return bool(state.get("schedule_enabled"))


def wants_run_now(state: dict[str, Any]) -> bool:
    """Chạy ngay: mặc định true nếu không đặt lịch; nếu có lịch thì chỉ khi run_now=true."""
    if wants_schedule(state):
        return bool(state.get("run_now"))
    # không lịch → chạy ngay (hành vi cũ)
    if state.get("run_now") is False:
        return False
    return True


def _normalize_time(value: str | None) -> str | None:
    if not value:
        return None
    raw = value.strip()
    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            from datetime import datetime

            t = datetime.strptime(raw, fmt)
            return t.strftime("%H:%M")
        except ValueError:
            continue
    return None


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def compose_hitl_message(
    *,
    intent: str,
    missing: list[str],
    user_text: str = "",
    history_text: str = "",
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM tự viết message hiển thị cho user — không template cứng."""
    payload = {
        "intent": intent,
        "still_needed": missing,
        "known_state": {k: v for k, v in (state or {}).items() if not str(k).startswith("_")},
        "user_message": user_text,
        "chat_history": history_text,
    }
    reply = llm_text(HITL_MESSAGE_SYSTEM, json.dumps(payload, ensure_ascii=False))
    text = reply.get("text") or ""
    if not text:
        if "email_grant" in missing:
            text = "Để mình đọc hộp thư giúp bạn, hãy kết nối Gmail bằng nút trên màn hình nhé."
        elif any(x.startswith("schedule_") for x in missing):
            text = "Bạn cho mình biết rõ giờ (và thứ/ngày) muốn mình kiểm tra email giúp bạn nhé."
        else:
            text = "Mình cần thêm một vài thông tin trước khi làm tiếp — bạn bổ sung giúp mình nhé."
    return reply


def compose_schedule_confirm(
    *,
    state: dict[str, Any],
    run_at_unix: float,
    watch_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    when = datetime.fromtimestamp(run_at_unix, tz).strftime("%Y-%m-%d %H:%M %Z")
    payload = {
        "schedule_repeat": state.get("schedule_repeat"),
        "schedule_time": state.get("schedule_time"),
        "schedule_weekday": state.get("schedule_weekday"),
        "schedule_date": state.get("schedule_date"),
        "run_at_local": when,
        "ran_now": bool(watch_result),
        "watch_summary": (watch_result or {}).get("message"),
        "important": (watch_result or {}).get("important"),
    }
    reply = llm_text(SCHEDULE_CONFIRM_SYSTEM, json.dumps(payload, ensure_ascii=False))
    if not reply.get("text"):
        repeat = state.get("schedule_repeat") or "once"
        reply["text"] = (
            f"Mình đã hẹn kiểm tra email lúc {when}"
            + (" mỗi tuần." if repeat == "weekly" else ".")
        )
    return reply
