"""Trích / gộp slot bằng LLM (không rule keyword)."""
from __future__ import annotations

import json
import re
from typing import Any

STANDUP_REQUIRED = ("yesterday", "today", "url")
STANDUP_OPTIONAL = ("schedule_at", "schedule_enabled", "schedule_time", "schedule_repeat")

EXTRACT_SYSTEM = """Bạn trích thông tin từ tin nhắn user cho agent.
Chỉ trả về ĐÚNG một JSON object, không markdown.
Với intent standup_fill, schema:
{
  "yesterday": string|null,
  "today": string|null,
  "url": string|null,
  "schedule_at": string|null,
  "run_now": boolean|null,
  "schedule_enabled": boolean|null,
  "schedule_time": string|null,
  "schedule_weekday": number|null,
  "schedule_date": string|null,
  "schedule_repeat": "once"|"daily"|"weekly"|null
}
Giải thích standup:
- url: link trang nộp standup (https…).
- yesterday / today: nội dung điền form; null nếu user chỉ hẹn lịch chưa đưa nội dung.
- schedule_enabled: true nếu user muốn hẹn giờ / định kỳ điền standup (vd «mỗi 8h tối», «từ giờ cứ…»).
- schedule_time: "HH:MM" 24h — «8h tối» → "20:00", «8 giờ sáng» → "08:00".
- schedule_repeat: "daily" nếu mỗi ngày / hàng ngày / cứ mỗi … tối; "weekly" nếu mỗi tuần + thứ; "once" nếu chỉ một lần.
- schedule_weekday: 0=Thứ Hai … 6=Chủ Nhật khi weekly.
- schedule_date: "YYYY-MM-DD" khi one-shot có ngày.
- schedule_at: legacy "HH:MM" one-shot (ưu tiên dùng schedule_* ở trên).
- run_now: true chỉ khi user muốn điền ngay bây giờ; nếu chỉ hẹn lịch thì false hoặc null.
Với intent email_watch, schema:
{
  "email_provider": "google"|"outlook"|null,
  "notify_interval_sec": number|null,
  "newer_than_days": number|null,
  "after_date": string|null,
  "before_date": string|null,
  "include_read": boolean|null,
  "search_query": string|null,
  "topic": string|null,
  "run_now": boolean|null,
  "schedule_enabled": boolean|null,
  "schedule_time": string|null,
  "schedule_weekday": number|null,
  "schedule_date": string|null,
  "schedule_repeat": "once"|"weekly"|null
}
Giải thích email:
- email_provider: "outlook" nếu user nói Outlook/Hotmail/Microsoft/Office 365; "google" nếu Gmail/Google; null nếu không chỉ định (hệ thống dùng tài khoản đã kết nối).
- newer_than_days / after_date / before_date / include_read: khung quét mail (null newer_than → hệ thống mặc định 7 ngày).
- search_query: chuỗi tìm khi user hỏi chủ đề cụ thể (vd «đăng ký nhập học», «hóa đơn»). Viết keyword/OR tiếng Việt+Anh, không bọc ngoặc thừa; null nếu chỉ «đọc mail quan trọng / kiểm tra hộp thư».
- topic: mô tả ngắn chủ đề user hỏi (tiếng Việt), null nếu quét chung.
- include_read: true nếu user hỏi về một chủ đề cụ thể (có thể đã đọc); false/null nếu chỉ quét unread.
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
Với lịch (email/standup): điền schedule_time / schedule_weekday / schedule_date / schedule_repeat khi user cung cấp.
«8h tối» → schedule_time "20:00"; «mỗi ngày» → schedule_repeat "daily"."""

HITL_MESSAGE_SYSTEM = """Bạn là trợ lý digitalboo, nói chuyện tự nhiên với người dùng bằng tiếng Việt.
Nhiệm vụ: viết ĐÚNG một tin nhắn ngắn (1–3 câu) giải thích cần gì tiếp theo, thân thiện, rõ ràng.
Được dùng Markdown nhẹ (in đậm, list) khi giúp đọc rõ hơn — không bọc cả tin trong code fence.
TUYỆT ĐỐI KHÔNG dùng jargon kỹ thuật: không nói HITL, checkpoint, missing_fields, grant, OAuth, API, actions, Redis, cron.
Nếu thiếu kết nối email: mời người dùng bấm nút kết nối Gmail hoặc Outlook trên giao diện (nút sẽ hiện sẵn) — KHÔNG nói có thể bỏ qua.
Nếu thiếu lịch (giờ / thứ trong tuần / ngày): hỏi tự nhiên phần còn thiếu để hẹn giờ.
Nếu thiếu thông tin standup (hôm qua / hôm nay / URL): hỏi tự nhiên những phần còn thiếu.
Nếu still_needed có browser_login: bảo người dùng đăng nhập trên cửa sổ trình duyệt vừa mở (GitHub/Google/portal), xong thì nhắn lại (vd «đã đăng nhập») để mình tiếp tục điền form. Không yêu cầu gửi mật khẩu trong chat.
Nhắc nhẹ mỗi ô hôm qua/hôm nay nên ≥40 ký tự (theo form portal) khi sắp điền ngay; nếu known_state có _min_chars thì nêu đúng ngưỡng đó.
Nếu known_state._expired_timeout: báo đã hết thời gian chờ nội dung standup, bỏ qua lần này, lịch ngày sau vẫn giữ.
Không liệt kê bullet máy móc trừ khi thật cần. Không thêm lời dẫn kiểu "Thiếu thông tin — …".
Chỉ trả về nội dung tin nhắn, không JSON, không markdown fence."""

SCHEDULE_CONFIRM_SYSTEM = """Bạn là trợ lý digitalboo. Viết ĐÚNG một tin nhắn ngắn tiếng Việt xác nhận đã hẹn lịch.
Không jargon (không nói Redis, cron, job_id, unix). Nêu rõ việc gì (đọc email / điền standup), URL nếu có, thời điểm, và lặp daily/weekly hay chỉ một lần.
Nhắc nhẹ: đến giờ hệ thống mới chạy; kết quả (thành công/thất bại) sẽ báo qua thông báo desktop.
Nếu đồng thời đã chạy ngay, nhắc ngắn kết quả. Chỉ trả về nội dung tin nhắn."""

EMAIL_WATCH_REPLY_SYSTEM = """Bạn là trợ lý digitalboo. Nhiệm vụ: viết tin nhắn trả lời user SAU KHI đã chạy tool đọc email (Gmail hoặc Outlook).
Chỉ dựa trên tool_result. Không bịa mail, người gửi, hay nội dung không có trong dữ liệu.
Hai danh sách trong tool_result:
- digest / topic_matches: thư khớp chủ đề tìm kiếm (có thể rỗng).
- recent_digest: thư gần đây trong cùng khung thời gian (ngữ cảnh hộp thư) — dùng khi topic không khớp.
Trả lời đúng câu hỏi user:
- Nếu hỏi về chủ đề cụ thể (topic/search, vd IELTS / kết quả thi):
  1) Mở đầu nói rõ CÓ hoặc KHÔNG thấy mail khớp chủ đề đó (dựa vào digest / topic_match_count).
  2) Nếu CÓ: nêu 1–3 thư khớp (người gửi + tiêu đề + ý ngắn).
  3) Nếu KHÔNG / digest rỗng: BẮT BUỘC lấy 1–3 thư từ recent_digest (ưu tiên important=true, rồi thư không phải quảng cáo). Câu kiểu: «Không thấy email kết quả IELTS trong … ngày gần đây; trong hộp thư mình thấy …». Nếu recent_digest cũng rỗng mới nói hộp thư trống trong khung đó.
- Nếu user cũng hỏi mail quan trọng: nêu thư important=true từ digest hoặc recent_digest.
- Có thể nhắc nhẹ nguồn (Gmail / Outlook) nếu tool_result.provider có.
Giọng tiếng Việt tự nhiên, 2–8 câu hoặc list ngắn. Markdown nhẹ (in đậm, list) OK.
Không jargon (không nói heuristic, keyword rule, query, already_seen, digest, Graph API, recent_digest).
Không nói «chưa có email nào được trả về» nếu recent_digest còn thư. Không dump 20 mail promo.
Chỉ trả về nội dung tin nhắn, không JSON, không markdown fence."""

STANDUP_REPLY_SYSTEM = """Bạn là trợ lý digitalboo. Viết ĐÚNG một tin nhắn tiếng Việt SAU KHI hệ thống đã thử điền / nộp daily standup trên web.
Chỉ dựa trên tool_result + fields đã dùng. Không bịa đã nộp nếu ok=false / submitted=false.
Giải thích theo error nếu có:
- already_done: hệ thống ghi nhận đã nộp hôm nay (không khẳng định đã mở trình duyệt vừa rồi).
- need_login / browser_login: mời user đăng nhập trên cửa sổ trình duyệt rồi nhắn lại.
- no_notes / no_grant / fields_too_short / outside_window / locked / submit_failed / browser_error: nói rõ cần gì tiếp theo, thân thiện.
- ok + submitted: xác nhận đã điền và nộp, có thể nhắc ngắn nội dung hôm qua/hôm nay nếu có trong fields.
Không jargon (Redis, job_id, Playwright, force, allow_resubmit). Markdown nhẹ OK.
Chỉ trả về nội dung tin nhắn, không JSON, không markdown fence."""


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
    schedule_time = _normalize_time(_str_or_none(data.get("schedule_time")))
    # Legacy schedule_at "HH:MM" → schedule_time
    legacy_at = _str_or_none(data.get("schedule_at"))
    if not schedule_time and legacy_at:
        schedule_time = _normalize_time(legacy_at) or schedule_time

    schedule_enabled = data.get("schedule_enabled")
    if schedule_enabled is not None:
        schedule_enabled = bool(schedule_enabled)
    repeat = _str_or_none(data.get("schedule_repeat"))
    if repeat and repeat not in ("once", "daily", "weekly"):
        repeat = None
    weekday = _parse_int(data.get("schedule_weekday"), min_v=0, max_v=6)
    schedule_date = _str_or_none(data.get("schedule_date"))
    run_now = data.get("run_now")
    if run_now is not None:
        run_now = bool(run_now)

    # Suy luận: có giờ/lặp → bật lịch
    if schedule_enabled is None and (schedule_time or weekday is not None or schedule_date or repeat or legacy_at):
        schedule_enabled = True
    if schedule_enabled and repeat is None:
        # «mỗi ngày / từ giờ cứ …» → daily; có weekday → weekly; còn lại once
        if weekday is not None and not schedule_date:
            repeat = "weekly"
        elif schedule_date:
            repeat = "once"
        elif schedule_time or legacy_at:
            repeat = "daily"
    # Chỉ hẹn lịch → mặc định không chạy ngay
    if schedule_enabled and run_now is None:
        run_now = False

    return {
        "yesterday": _str_or_none(data.get("yesterday")),
        "today": _str_or_none(data.get("today")),
        "url": _str_or_none(data.get("url")),
        "schedule_at": legacy_at,
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
    search_query = _str_or_none(data.get("search_query"))
    topic = _str_or_none(data.get("topic"))
    # Hỏi chủ đề cụ thể → mặc định quét cả mail đã đọc
    if search_query or topic:
        if include_read is None:
            include_read = True
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

    provider = _str_or_none(data.get("email_provider"))
    if provider:
        provider = provider.strip().lower()
        if provider in ("gmail", "google"):
            provider = "google"
        elif provider in ("outlook", "microsoft", "hotmail", "live", "office365", "o365"):
            provider = "outlook"
        else:
            provider = None

    return {
        "email_provider": provider,
        "notify_interval_sec": interval,
        "newer_than_days": days,
        "after_date": _str_or_none(data.get("after_date")),
        "before_date": _str_or_none(data.get("before_date")),
        "include_read": include_read,
        "search_query": search_query,
        "topic": topic,
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

    search = _str_or_none(state.get("search_query"))
    if search:
        # Bỏ operator nguy hiểm; giữ OR/dấu ngoặc đơn giản cho Gmail q
        parts.append(f"({search})")

    return " ".join(parts)


def build_outlook_query(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tham số list Outlook/Graph từ slot (không phải Gmail q)."""
    state = state or {}
    days = state.get("newer_than_days")
    try:
        days = int(days) if days is not None else 7
    except (TypeError, ValueError):
        days = 7
    if days < 1:
        days = 1
    search = _str_or_none(state.get("search_query"))
    return {
        "search": search,
        "unread_only": not bool(state.get("include_read")),
        "newer_than_days": days,
        "after_date": _str_or_none(state.get("after_date")),
        "before_date": _str_or_none(state.get("before_date")),
    }


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
        allowed = ("once", "daily", "weekly") if intent == "standup_fill" else ("once", "weekly")
        merged["schedule_repeat"] = r if r in allowed else merged.get("schedule_repeat")
    if "schedule_enabled" in merged and merged.get("schedule_enabled") is not None:
        merged["schedule_enabled"] = bool(merged.get("schedule_enabled"))
    if "run_now" in merged and merged.get("run_now") is not None:
        merged["run_now"] = bool(merged.get("run_now"))
    if "email_provider" in merged:
        ep = _str_or_none(merged.get("email_provider"))
        if ep:
            ep = ep.strip().lower()
            if ep in ("gmail", "google"):
                ep = "google"
            elif ep in ("outlook", "microsoft", "hotmail", "live", "office365", "o365"):
                ep = "outlook"
            else:
                ep = None
        merged["email_provider"] = ep
    merged["_model"] = data.get("_model")
    merged["_tokens_in"] = data.get("_tokens_in")
    merged["_tokens_out"] = data.get("_tokens_out")
    return merged


def standup_schedule_missing(state: dict[str, Any]) -> list[str]:
    """Thiếu slot lịch khi user muốn hẹn giờ điền standup."""
    if not state.get("schedule_enabled"):
        return []
    missing: list[str] = []
    if not _normalize_time(_str_or_none(state.get("schedule_time"))):
        # fallback legacy
        if not _normalize_time(_str_or_none(state.get("schedule_at"))):
            missing.append("schedule_time")
    repeat = _str_or_none(state.get("schedule_repeat")) or "daily"
    if repeat == "weekly":
        if _parse_int(state.get("schedule_weekday"), min_v=0, max_v=6) is None:
            missing.append("schedule_weekday")
    elif repeat == "once":
        if not _str_or_none(state.get("schedule_date")):
            if _parse_int(state.get("schedule_weekday"), min_v=0, max_v=6) is None:
                # once + chỉ có giờ vẫn OK (next_run_unix xử lý ngày mai)
                pass
    return missing


def standup_missing(state: dict[str, Any], *, min_chars: int | None = None) -> list[str]:
    missing: list[str] = []
    schedule_only = bool(state.get("schedule_enabled")) and not bool(state.get("run_now"))

    if schedule_only:
        # Chỉ hẹn lịch: cần URL + giờ lịch; nội dung điền lấy notes lúc chạy
        if not (state.get("url") or "").strip():
            missing.append("url")
        missing.extend(standup_schedule_missing(state))
    else:
        for key in STANDUP_REQUIRED:
            val = state.get(key)
            if not val or not str(val).strip():
                missing.append(key)
        # Portal scripted yêu cầu độ dài tối thiểu khi chạy ngay
        if min_chars and min_chars > 0:
            for key in ("yesterday", "today"):
                if key in missing:
                    continue
                val = (state.get(key) or "").strip()
                if val and len(val) < min_chars:
                    missing.append(key)
        missing.extend(standup_schedule_missing(state))

    # Cờ chờ user đăng nhập trên browser (giữ qua HITL)
    if state.get("_need_browser_login") or state.get("browser_login_pending"):
        if "browser_login" not in missing:
            missing.append("browser_login")
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
    """LLM tự viết message hiển thị cho user — không template if/else."""
    payload = {
        "intent": intent,
        "still_needed": missing,
        "known_state": {k: v for k, v in (state or {}).items() if not str(k).startswith("_")},
        "user_message": user_text,
        "chat_history": history_text,
    }
    return llm_text(HITL_MESSAGE_SYSTEM, json.dumps(payload, ensure_ascii=False))


def _slim_digest(rows: Any, limit: int = 25) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in (rows or [])[:limit]:
        if not isinstance(r, dict):
            continue
        out.append(
            {
                "from": r.get("from"),
                "subject": r.get("subject"),
                "snippet": r.get("snippet"),
                "date": r.get("date"),
                "important": bool(r.get("important")),
                "reason": r.get("reason"),
            }
        )
    return out


def compose_email_watch_reply(
    *,
    tool_result: dict[str, Any],
    user_text: str = "",
    history_text: str = "",
    topic: str | None = None,
) -> dict[str, Any]:
    """LLM tổng hợp câu trả lời từ kết quả tool email — không template if/else."""
    slim = _slim_digest(tool_result.get("digest"))
    recent = _slim_digest(tool_result.get("recent_digest"))
    payload = {
        "user_message": user_text,
        "chat_history": history_text,
        "topic": topic or tool_result.get("topic"),
        "tool_result": {
            "ok": tool_result.get("ok"),
            "provider": tool_result.get("provider"),
            "query": tool_result.get("query"),
            "scanned": tool_result.get("scanned"),
            "topic_match_count": tool_result.get("topic_match_count", len(slim)),
            "important": tool_result.get("important"),
            "already_seen": tool_result.get("already_seen"),
            "error": (
                (tool_result.get("error") or tool_result.get("message"))
                if not tool_result.get("ok")
                else None
            ),
            "digest": slim,
            "recent_digest": recent,
            "recent_scanned": tool_result.get("recent_scanned"),
        },
    }
    return llm_text(EMAIL_WATCH_REPLY_SYSTEM, json.dumps(payload, ensure_ascii=False))


def compose_standup_reply(
    *,
    tool_result: dict[str, Any],
    user_text: str = "",
    history_text: str = "",
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """LLM tổng hợp câu trả lời sau khi thử điền standup — không template if/else."""
    detail = tool_result.get("detail") if isinstance(tool_result.get("detail"), dict) else None
    payload = {
        "user_message": user_text,
        "chat_history": history_text,
        "fields": {
            "yesterday": (fields or {}).get("yesterday"),
            "today": (fields or {}).get("today"),
            "blockers": (fields or {}).get("blockers"),
        },
        "tool_result": {
            "ok": tool_result.get("ok"),
            "error": tool_result.get("error"),
            "need_login": bool(tool_result.get("need_login") or tool_result.get("need_hitl")),
            "missing_fields": tool_result.get("missing_fields"),
            "submitted": (detail or tool_result).get("submitted") if detail or tool_result else None,
            "strategy": (detail or {}).get("strategy") or tool_result.get("strategy"),
            "url": (detail or {}).get("url") or tool_result.get("url"),
            "message": tool_result.get("message"),
        },
    }
    return llm_text(STANDUP_REPLY_SYSTEM, json.dumps(payload, ensure_ascii=False))


def compose_schedule_confirm(
    *,
    state: dict[str, Any],
    run_at_unix: float,
    watch_result: dict[str, Any] | None = None,
    kind: str = "email",
) -> dict[str, Any]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    tz = ZoneInfo("Asia/Ho_Chi_Minh")
    when = datetime.fromtimestamp(run_at_unix, tz).strftime("%Y-%m-%d %H:%M %Z")
    payload = {
        "kind": kind,
        "url": state.get("url"),
        "schedule_repeat": state.get("schedule_repeat"),
        "schedule_time": state.get("schedule_time") or state.get("schedule_at"),
        "schedule_weekday": state.get("schedule_weekday"),
        "schedule_date": state.get("schedule_date"),
        "run_at_local": when,
        "ran_now": bool(watch_result),
        "watch_summary": (watch_result or {}).get("message"),
        "important": (watch_result or {}).get("important"),
    }
    return llm_text(SCHEDULE_CONFIRM_SYSTEM, json.dumps(payload, ensure_ascii=False))
