"""Trích / gộp slot bằng LLM (không rule keyword)."""
from __future__ import annotations

import json
import re
from typing import Any

STANDUP_REQUIRED = ("yesterday", "today", "url")
STANDUP_OPTIONAL = ("schedule_at",)
EMAIL_OPTIONAL = ("notify_interval_sec", "require_grant")

EXTRACT_SYSTEM = """Bạn trích thông tin từ tin nhắn user cho agent.
Chỉ trả về ĐÚNG một JSON object, không markdown.
Với intent standup_fill, schema:
{
  "yesterday": string|null,   // hôm qua làm gì
  "today": string|null,       // hôm nay làm gì
  "url": string|null,         // địa chỉ web điền standup
  "schedule_at": string|null  // giờ chạy, vd "08:30" hoặc ISO; null = chạy ngay
}
Với intent email_watch, schema:
{
  "notify_interval_sec": number|null,  // chu kỳ báo tin quan trọng (giây); null = chạy một lần ngay
  "require_grant": boolean|null        // true nếu user muốn bắt buộc đã connect email
}
Chỉ điền field user thực sự cung cấp; field không có thì null. Không bịa."""

MERGE_SYSTEM = """Bạn đang ở bước HITL: user bổ sung thông tin còn thiếu.
State hiện tại (JSON) và missing_fields được cung cấp.
Hãy gộp tin nhắn mới vào state, trả về ĐÚNG một JSON object cùng schema state (standup hoặc email).
Field cũ giữ nguyên nếu tin nhắn mới không cập nhật. Không bịa."""


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


def extract_email_slots(text: str, history_text: str = "") -> dict[str, Any]:
    from harness.memory import with_history

    data = llm_json(
        EXTRACT_SYSTEM,
        with_history(history_text, text, extra="intent=email_watch — trích slot từ lịch sử + tin hiện tại."),
    )
    interval = data.get("notify_interval_sec")
    try:
        interval = int(interval) if interval is not None else None
    except (TypeError, ValueError):
        interval = None
    return {
        "notify_interval_sec": interval,
        "require_grant": data.get("require_grant"),
        "_model": data.get("_model"),
        "_tokens_in": data.get("_tokens_in"),
        "_tokens_out": data.get("_tokens_out"),
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
    """Grant là optional trừ khi require_grant=true hoặc chưa connect và user chưa bỏ qua."""
    missing = []
    # Nếu chưa connect Gmail → luôn hỏi (HITL) trừ khi state đánh dấu skip_grant
    if not has_grant and not state.get("skip_grant"):
        missing.append("email_grant")
    return missing


def _str_or_none(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


FIELD_LABELS = {
    "yesterday": "hôm qua bạn đã làm gì",
    "today": "hôm nay bạn sẽ làm gì",
    "url": "địa chỉ web form standup (URL)",
    "schedule_at": "giờ muốn agent vào điền (optional, bỏ qua = chạy ngay)",
    "email_grant": "connect Gmail OAuth (mở /email/oauth/google/start) hoặc nói 'bỏ qua grant'",
    "notify_interval_sec": "chu kỳ báo tin quan trọng (giây, optional)",
}


def ask_message(missing: list[str], intent: str) -> str:
    lines = ["Thiếu thông tin — HITL checkpoint. Bạn bổ sung giúp:"]
    for m in missing:
        lines.append(f"- {FIELD_LABELS.get(m, m)}")
    if intent == "standup_fill":
        lines.append(
            "(Optional) Có thể kèm giờ chạy, vd 08:30 — sẽ lên lịch Redis; không có thì chạy ngay."
        )
    if intent == "email_watch":
        lines.append(
            "(Optional) Có thể nói chu kỳ báo tin (giây). Bỏ qua grant bằng cách trả lời 'bỏ qua grant'."
        )
    return "\n".join(lines)
