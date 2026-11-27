"""Orchestrator: 3 intent (LLM) + HITL checkpointer — có memory theo session."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

from harness.channels.email.token_store import get_account
from harness.config import settings
from harness.flows.email_watch import run_email_watch
from harness.flows.standup_submit import run_standup_submit
from harness.hitl import checkpoint as cp
from harness.hitl.slots import (
    compose_hitl_message,
    compose_schedule_confirm,
    email_missing,
    extract_email_slots,
    extract_standup_slots,
    merge_slots,
    standup_missing,
    wants_run_now,
    wants_schedule,
)
from harness.jobs.delayed import next_run_unix, parse_schedule_at, schedule_job
from harness.memory import format_chat_history, with_history

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "codebase") not in sys.path:
    sys.path.insert(0, str(ROOT / "codebase"))

INTENT_SYSTEM = """Bạn là bộ phân loại intent.
Dựa vào lịch sử hội thoại cùng session + tin nhắn hiện tại.
Chỉ trả về ĐÚNG một JSON object, không markdown.
Schema:
{
  "intent": "conversation" | "standup_fill" | "email_watch",
  "reason": string
}
- conversation: chào hỏi, trò chuyện thường, không yêu cầu standup/email
- standup_fill: muốn agent tự điền / nộp daily standup trên web (kể cả đang bổ sung thông tin standup)
- email_watch: muốn agent đọc email và báo tin quan trọng
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM intent rỗng")
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("intent không phải object")
    return data


def detect_intent(text: str, user_id: str, history_text: str = "") -> dict[str, Any]:
    from ai import call_model  # type: ignore

    reply = call_model(
        INTENT_SYSTEM,
        with_history(history_text, text, extra=f"user_id={user_id}"),
    )
    parsed = _extract_json(reply.get("text") or "")
    intent = str(parsed.get("intent") or "conversation").strip()
    if intent not in {"conversation", "standup_fill", "email_watch"}:
        intent = "conversation"
    return {
        "intent": intent,
        "reason": parsed.get("reason") or "",
        "model": reply.get("model"),
        "tokens_in": reply.get("tokens_in"),
        "tokens_out": reply.get("tokens_out"),
    }


def _meta_from(obj: dict[str, Any], **extra: Any) -> dict[str, Any]:
    return {
        "intent_model": obj.get("model") or obj.get("_model"),
        "tokens_in": obj.get("tokens_in") or obj.get("_tokens_in"),
        "tokens_out": obj.get("tokens_out") or obj.get("_tokens_out"),
        **extra,
    }


def _conversation(text: str, history_text: str = "") -> dict[str, Any]:
    from ai import call_model  # type: ignore

    system = (
        "Bạn là trợ lý digitalboo thân thiện. "
        "Nhớ ngữ cảnh từ lịch sử hội thoại cùng session. "
        "Trả lời tiếng Việt, ngắn gọn. "
        "Không soạn standup, không đọc email trừ khi user yêu cầu rõ trong tin hiện tại."
    )
    reply = call_model(system, with_history(history_text, text))
    return {
        "ok": True,
        "flow": "conversation",
        "message": reply.get("text") or "Xin chào!",
        "intent_model": reply.get("model"),
        "tokens_in": reply.get("tokens_in"),
        "tokens_out": reply.get("tokens_out"),
    }


def _execute_standup(user_id: str, state: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "yesterday": state.get("yesterday") or "",
        "today": state.get("today") or "",
        "blockers": state.get("blockers") or "Không",
    }
    url = state.get("url")
    run_at = parse_schedule_at(state.get("schedule_at"), settings()["standup_timezone"])
    if run_at is not None:
        job_id = schedule_job(
            "standup_fill",
            {"user_id": user_id, "fields": fields, "url": url, "force": True},
            run_at,
        )
        return {
            "ok": True,
            "flow": "standup_fill",
            "scheduled": True,
            "job_id": job_id,
            "run_at_unix": run_at,
            "message": (
                f"Đã đủ thông tin. Đã lên lịch Redis chạy standup lúc {state.get('schedule_at')} "
                f"(job_id={job_id})."
            ),
        }

    result = run_standup_submit(
        user_id=user_id,
        force=True,
        fields=fields,
        url=url,
    )
    return {
        "ok": result.get("ok", False),
        "flow": "standup_fill",
        "scheduled": False,
        "message": result.get("message") or result.get("error") or "",
        "detail": result,
    }


def _execute_email(user_id: str, state: dict[str, Any]) -> dict[str, Any]:
    from harness.hitl.slots import build_gmail_query

    clean = {k: v for k, v in state.items() if not str(k).startswith("_")}
    q = build_gmail_query(clean)
    watch_result: dict[str, Any] | None = None

    # 1) Chạy ngay nếu cần
    if wants_run_now(clean):
        watch_result = run_email_watch(user_id, state=clean, query=q, source="ask_now")

    # 2) Đặt lịch calendar (once/weekly) nếu có
    if wants_schedule(clean):
        run_at = next_run_unix(clean)
        if run_at is None:
            return {
                "ok": False,
                "flow": "email_watch",
                "scheduled": False,
                "message": "Chưa tính được thời điểm chạy lịch. Bạn cho mình giờ/ngày rõ hơn nhé.",
                "query": q,
                "watch": watch_result,
            }
        repeat = (clean.get("schedule_repeat") or "once").strip()
        payload = {
            "user_id": user_id,
            "state": clean,
            "repeat": repeat == "weekly",
            "schedule_repeat": repeat,
            "schedule_weekday": clean.get("schedule_weekday"),
            "schedule_time": clean.get("schedule_time"),
            "schedule_date": clean.get("schedule_date"),
        }
        job_id = schedule_job("email_watch", payload, run_at)
        confirm = compose_schedule_confirm(state=clean, run_at_unix=run_at, watch_result=watch_result)
        out: dict[str, Any] = {
            "ok": True,
            "flow": "email_watch",
            "scheduled": True,
            "job_id": job_id,
            "run_at_unix": run_at,
            "schedule_repeat": repeat,
            "query": q,
            "message": confirm.get("text") or "",
            "watch": watch_result,
            "items": (watch_result or {}).get("items") or [],
        }
        if confirm.get("_tokens_in"):
            out["tokens_in"] = confirm.get("_tokens_in")
        if confirm.get("_tokens_out"):
            out["tokens_out"] = confirm.get("_tokens_out")
        return out

    # 3) Legacy: notify_interval_sec lặp theo giây (giữ tương thích)
    interval = clean.get("notify_interval_sec")
    if interval:
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            interval = None
    if interval and interval > 0:
        import time

        job_id = schedule_job(
            "email_watch",
            {
                "user_id": user_id,
                "notify_interval_sec": interval,
                "repeat": True,
                "state": clean,
            },
            time.time() + interval,
        )
        if watch_result is None:
            watch_result = run_email_watch(user_id, state=clean, query=q, source="ask_now")
        return {
            "ok": True,
            "flow": "email_watch",
            "scheduled": True,
            "job_id": job_id,
            "query": q,
            "message": watch_result.get("message") or "",
            "watch": watch_result,
            "items": watch_result.get("items") or [],
        }

    if watch_result is None:
        watch_result = run_email_watch(user_id, state=clean, query=q, source="ask_now")
    return {
        "ok": watch_result.get("ok", False),
        "flow": "email_watch",
        "scheduled": False,
        "message": watch_result.get("message") or watch_result.get("error") or "",
        **watch_result,
    }


def _email_connect_actions(
    user_id: str,
    session_id: str,
    checkpoint_id: Optional[int],
) -> list[dict[str, Any]]:
    """Payload để UI hiện nút Connect Gmail (popup)."""
    from harness.channels.email.oauth import build_google_oauth_start

    try:
        start = build_google_oauth_start(
            user_id,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
        )
    except ValueError as e:
        return [
            {
                "type": "oauth_google",
                "label": "Connect Gmail",
                "error": str(e),
            }
        ]
    return [
        {
            "type": "oauth_google",
            "label": "Connect Gmail",
            "oauth_url": start["oauth_url"],
            "popup": True,
            "user_id": user_id,
            "session_id": session_id,
            "checkpoint_id": checkpoint_id,
            "start_api": f"/email/oauth/google/start?format=json&user_id={user_id}&session_id={session_id}",
        }
    ]


def _hitl_interrupt(
    session_id: str,
    user_id: str,
    intent: str,
    state: dict[str, Any],
    missing: list[str],
    meta: dict[str, Any],
    *,
    user_text: str = "",
    history_text: str = "",
) -> dict[str, Any]:
    clean = {k: v for k, v in state.items() if not str(k).startswith("_")}
    saved = cp.interrupt(session_id, user_id, intent, clean, missing)
    msg = compose_hitl_message(
        intent=intent,
        missing=missing,
        user_text=user_text,
        history_text=history_text,
        state=clean,
    )
    out: dict[str, Any] = {
        "ok": False,
        "flow": "hitl",
        "hitl": True,
        "status": "interrupted",
        "intent": intent,
        "missing_fields": missing,
        "state": clean,
        "checkpoint_id": saved.get("id"),
        "message": msg.get("text") or "",
        **meta,
    }
    # gộp token của lần viết message
    if msg.get("_tokens_in"):
        out["tokens_in"] = (out.get("tokens_in") or 0) + (msg.get("_tokens_in") or 0)
    if msg.get("_tokens_out"):
        out["tokens_out"] = (out.get("tokens_out") or 0) + (msg.get("_tokens_out") or 0)
    if "email_grant" in missing:
        out["actions"] = _email_connect_actions(user_id, session_id, saved.get("id"))
        out["ui"] = {
            "show_connect_email": True,
            "provider": "google",
        }
    return out


def resume_email_after_oauth(
    user_id: str,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
) -> dict[str, Any]:
    """Sau OAuth thành công: đóng HITL email_grant và chạy đọc mail."""
    pending = None
    if session_id:
        pending = cp.get_pending(session_id)
    if not pending or pending.get("intent") != "email_watch":
        pending = cp.get_pending_email_grant(user_id, session_id=session_id)
    if not pending:
        out = _execute_email(user_id, {})
        out["resumed_from_oauth"] = False
        return out

    state = dict(pending.get("state") or {})
    cp.complete(pending["id"], state)
    out = _execute_email(user_id, state)
    out["resumed_from_oauth"] = True
    out["checkpoint_id"] = pending["id"]
    out["session_id"] = pending.get("session_id")
    out["hitl"] = False
    out["status"] = "completed"
    return out


def _resume_hitl(
    text: str,
    user_id: str,
    session_id: str,
    pending: dict[str, Any],
    history_text: str = "",
) -> dict[str, Any]:
    intent = pending["intent"]
    state = dict(pending.get("state") or {})
    missing = list(pending.get("missing_fields") or [])

    merged = merge_slots(intent, state, text, missing, history_text=history_text)
    merged.pop("skip_grant", None)
    meta = _meta_from(merged, intent_reason="hitl_resume", resumed=True)

    if intent == "standup_fill":
        miss = standup_missing(merged)
        if miss:
            clean = {k: v for k, v in merged.items() if not str(k).startswith("_")}
            cp.update_pending(pending["id"], clean, miss)
            msg = compose_hitl_message(
                intent=intent,
                missing=miss,
                user_text=text,
                history_text=history_text,
                state=clean,
            )
            return {
                "ok": False,
                "flow": "hitl",
                "hitl": True,
                "status": "interrupted",
                "intent": intent,
                "missing_fields": miss,
                "state": clean,
                "checkpoint_id": pending["id"],
                "message": msg.get("text") or "",
                **meta,
            }
        cp.complete(pending["id"], {k: v for k, v in merged.items() if not str(k).startswith("_")})
        out = _execute_standup(user_id, merged)
        out.update(meta)
        return out

    if intent == "email_watch":
        has_grant = bool(get_account(user_id, "google"))
        miss = email_missing(merged, has_grant=has_grant)
        if miss:
            clean = {k: v for k, v in merged.items() if not str(k).startswith("_")}
            cp.update_pending(pending["id"], clean, miss)
            msg = compose_hitl_message(
                intent=intent,
                missing=miss,
                user_text=text,
                history_text=history_text,
                state=clean,
            )
            out = {
                "ok": False,
                "flow": "hitl",
                "hitl": True,
                "status": "interrupted",
                "intent": intent,
                "missing_fields": miss,
                "state": clean,
                "checkpoint_id": pending["id"],
                "message": msg.get("text") or "",
                **meta,
            }
            if "email_grant" in miss:
                out["actions"] = _email_connect_actions(user_id, session_id, pending["id"])
                out["ui"] = {"show_connect_email": True, "provider": "google"}
            return out
        cp.complete(pending["id"], {k: v for k, v in merged.items() if not str(k).startswith("_")})
        out = _execute_email(user_id, merged)
        out.update(meta)
        return out

    cp.complete(pending["id"])
    return {"ok": False, "flow": "hitl", "message": f"Intent checkpoint lạ: {intent}", **meta}


def _start_standup(
    text: str,
    user_id: str,
    session_id: str,
    meta: dict[str, Any],
    history_text: str = "",
) -> dict[str, Any]:
    slots = extract_standup_slots(text, history_text=history_text)
    meta = {**meta, **_meta_from(slots)}
    miss = standup_missing(slots)
    if miss:
        return _hitl_interrupt(
            session_id,
            user_id,
            "standup_fill",
            slots,
            miss,
            meta,
            user_text=text,
            history_text=history_text,
        )
    return {**_execute_standup(user_id, slots), **meta}


def _start_email(
    text: str,
    user_id: str,
    session_id: str,
    meta: dict[str, Any],
    history_text: str = "",
) -> dict[str, Any]:
    slots = extract_email_slots(text, history_text=history_text)
    meta = {**meta, **_meta_from(slots)}
    has_grant = bool(get_account(user_id, "google"))
    miss = email_missing(slots, has_grant=has_grant)
    if miss:
        return _hitl_interrupt(
            session_id,
            user_id,
            "email_watch",
            slots,
            miss,
            meta,
            user_text=text,
            history_text=history_text,
        )
    return {**_execute_email(user_id, slots), **meta}


def handle(
    text: str,
    source: str = "ask",
    user_id: str | None = None,
    session_id: str | None = None,
    history: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    text = (text or "").strip()
    user_id = user_id or settings()["default_user_id"]
    session_id = session_id or f"anon-{user_id}"
    history_text = format_chat_history(history or [])

    pending = cp.get_pending(session_id)
    if pending:
        result = _resume_hitl(text, user_id, session_id, pending, history_text=history_text)
        result["source"] = source
        result["history_turns"] = len(history or [])
        return result

    try:
        detected = detect_intent(text, user_id, history_text=history_text)
    except Exception as e:
        return {
            "ok": False,
            "flow": "intent_error",
            "source": source,
            "message": f"Không phân loại được intent bằng LLM: {e}",
        }

    intent = detected["intent"]
    meta = _meta_from(detected, intent_reason=detected.get("reason"), intent=intent)
    meta["source"] = source
    meta["history_turns"] = len(history or [])

    if intent == "conversation":
        out = _conversation(text, history_text=history_text)
        out.update({k: v for k, v in meta.items() if k not in out or out.get(k) is None})
        out["source"] = source
        return out

    if intent == "standup_fill":
        out = _start_standup(text, user_id, session_id, meta, history_text=history_text)
        out["source"] = source
        return out

    if intent == "email_watch":
        out = _start_email(text, user_id, session_id, meta, history_text=history_text)
        out["source"] = source
        return out

    out = _conversation(text, history_text=history_text)
    out["source"] = source
    return out
