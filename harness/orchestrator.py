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
from harness.channels import notify as notify_mod

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
        "Được dùng Markdown (in đậm, list, code inline) khi giúp đọc rõ — không bọc cả câu trả lời trong fence. "
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


def _standup_min_chars(url: str | None = None) -> int | None:
    """Chỉ enforce min_chars khi có playbook scripted (Edufun). Vision: không chặn sớm."""
    from harness.computer_use.playbook import match_playbook, resolve_strategy

    if not url:
        return None
    if resolve_strategy(url) != "scripted":
        return None
    pb = match_playbook(url) or {}
    try:
        return max(1, int(pb.get("min_chars") or 40))
    except (TypeError, ValueError):
        return 40


def _standup_schedule_payload(
    user_id: str,
    state: dict[str, Any],
    fields: dict[str, str],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Payload Redis delayed job cho standup (có thể lặp daily/weekly)."""
    clean = {k: v for k, v in state.items() if not str(k).startswith("_")}
    repeat = (clean.get("schedule_repeat") or "daily").strip()
    # daily/weekly: không đóng băng nội dung — tới giờ sẽ hỏi HITL
    fields_out = None
    if repeat == "once":
        has_content = bool(
            (fields.get("yesterday") or "").strip() and (fields.get("today") or "").strip()
        )
        fields_out = fields if has_content else None
    return {
        "user_id": user_id,
        "session_id": session_id,
        "fields": fields_out,
        "url": clean.get("url"),
        "force": True,
        "schedule_enabled": True,
        "schedule_repeat": repeat,
        "schedule_time": clean.get("schedule_time") or clean.get("schedule_at"),
        "schedule_weekday": clean.get("schedule_weekday"),
        "schedule_date": clean.get("schedule_date"),
        "notify_desktop": True,
    }


def _execute_standup(
    user_id: str,
    state: dict[str, Any],
    *,
    resume_browser: bool = False,
    session_id: str | None = None,
) -> dict[str, Any]:
    fields = {
        "yesterday": state.get("yesterday") or "",
        "today": state.get("today") or "",
        "blockers": state.get("blockers") or "",
    }
    url = state.get("url")
    clean = {k: v for k, v in state.items() if not str(k).startswith("_")}
    # Checkpoint sau prompt lịch → luôn chạy CU ngay, không schedule lại
    if clean.get("from_scheduled_prompt"):
        clean["schedule_enabled"] = False
        clean["run_now"] = True
    tz = settings()["standup_timezone"]

    # 1) Đặt lịch — không chạy ngay (trừ khi run_now=true)
    if wants_schedule(clean):
        # Chuẩn hóa legacy schedule_at
        if not clean.get("schedule_time") and clean.get("schedule_at"):
            clean["schedule_time"] = clean.get("schedule_at")
        if not clean.get("schedule_repeat"):
            clean["schedule_repeat"] = "daily"

        run_at = next_run_unix(clean, timezone_name=tz)
        if run_at is None:
            # fallback one-shot HH:MM
            run_at = parse_schedule_at(
                clean.get("schedule_time") or clean.get("schedule_at"),
                tz,
            )
        if run_at is None:
            return {
                "ok": False,
                "flow": "standup_fill",
                "scheduled": False,
                "need_hitl": True,
                "missing_fields": ["schedule_time"],
                "message": "Chưa tính được thời điểm chạy. Bạn cho mình giờ (vd 20:00) rõ hơn nhé.",
                "state": clean,
            }

        payload = _standup_schedule_payload(user_id, clean, fields, session_id=session_id)
        job_id = schedule_job("standup_fill", payload, run_at)
        confirm = compose_schedule_confirm(
            state=clean,
            run_at_unix=run_at,
            kind="standup",
        )
        notify_mod.push(
            user_id,
            "standup_scheduled",
            "Đã hẹn lịch standup",
            confirm.get("text")
            or f"Đã hẹn standup lúc {clean.get('schedule_time')} ({clean.get('schedule_repeat') or 'daily'}).",
            {"job_id": job_id, "run_at_unix": run_at, "url": url, "session_id": session_id},
        )

        out: dict[str, Any] = {
            "ok": True,
            "flow": "standup_fill",
            "scheduled": True,
            "job_id": job_id,
            "run_at_unix": run_at,
            "schedule_repeat": payload.get("schedule_repeat"),
            "message": confirm.get("text")
            or (
                f"Đã hẹn điền standup lúc {clean.get('schedule_time')} "
                f"({payload.get('schedule_repeat')}). Đến giờ mình sẽ hỏi nội dung hôm qua/hôm nay rồi mới điền."
            ),
        }

        # Chỉ chạy thêm ngay khi user explicitly run_now
        if wants_run_now(clean):
            need = _standup_min_chars(url if isinstance(url, str) else None)
            short = []
            if need is not None:
                short = [
                    k
                    for k in ("yesterday", "today")
                    if len((fields.get(k) or "").strip()) < need
                ]
            if short:
                out["message"] = (
                    (out.get("message") or "")
                    + " Phần nội dung hôm qua/hôm nay còn ngắn nên chưa chạy ngay — đến giờ lịch sẽ dùng notes nếu có."
                ).strip()
            else:
                now_result = run_standup_submit(
                    user_id=user_id,
                    force=True,
                    fields=fields if (fields.get("yesterday") and fields.get("today")) else None,
                    url=url,
                    resume_browser=resume_browser,
                )
                out["ran_now"] = True
                out["now_result"] = now_result
                if now_result.get("need_hitl") or now_result.get("need_login"):
                    st = dict(clean)
                    st["browser_login_pending"] = True
                    out.update(
                        {
                            "ok": False,
                            "need_hitl": True,
                            "missing_fields": list(now_result.get("missing_fields") or ["browser_login"]),
                            "state": st,
                            "error": now_result.get("error") or "need_login",
                            "message": now_result.get("message") or out.get("message"),
                        }
                    )
        return out

    # 2) Chạy ngay (không có lịch)
    need = _standup_min_chars(url if isinstance(url, str) else None)
    if need is not None:
        short = [
            k
            for k in ("yesterday", "today")
            if len((fields.get(k) or "").strip()) < need
        ]
        if short:
            labels = {"yesterday": "hôm qua", "today": "hôm nay"}
            parts = ", ".join(
                f"{labels[k]} ({len((fields.get(k) or '').strip())}/{need} ký tự)"
                for k in short
            )
            msg = (
                f"Portal yêu cầu mỗi ô ≥{need} ký tự. "
                f"Phần còn ngắn: {parts}. Bạn viết dài thêm giúp mình nhé."
            )
            return {
                "ok": False,
                "flow": "standup_fill",
                "scheduled": False,
                "error": "fields_too_short",
                "need_hitl": True,
                "missing_fields": short,
                "message": msg,
                "state": {**clean, **fields},
            }

    # Legacy one-shot schedule_at without schedule_enabled
    run_at = parse_schedule_at(state.get("schedule_at"), tz)
    if run_at is not None:
        job_id = schedule_job(
            "standup_fill",
            _standup_schedule_payload(
                user_id,
                {
                    **clean,
                    "schedule_enabled": True,
                    "schedule_repeat": "once",
                    "schedule_time": state.get("schedule_at"),
                },
                fields,
                session_id=session_id,
            ),
            run_at,
        )
        return {
            "ok": True,
            "flow": "standup_fill",
            "scheduled": True,
            "job_id": job_id,
            "run_at_unix": run_at,
            "message": (
                f"Đã lên lịch chạy standup lúc {state.get('schedule_at')} "
                f"(đến giờ mới chạy)."
            ),
        }

    result = run_standup_submit(
        user_id=user_id,
        force=True,
        fields=fields,
        url=url,
        resume_browser=resume_browser,
    )
    out = {
        "ok": result.get("ok", False),
        "flow": "standup_fill",
        "scheduled": False,
        "message": result.get("message") or result.get("error") or "",
        "detail": result,
    }
    if result.get("need_hitl") or result.get("need_login"):
        miss = list(result.get("missing_fields") or ["browser_login"])
        st = dict(clean)
        st["browser_login_pending"] = True
        out.update(
            {
                "need_hitl": True,
                "missing_fields": miss,
                "state": st,
                "error": result.get("error") or "need_login",
            }
        )
    return out


def _execute_email(
    user_id: str,
    state: dict[str, Any],
    *,
    user_text: str = "",
    history_text: str = "",
) -> dict[str, Any]:
    from harness.hitl.slots import build_gmail_query

    clean = {k: v for k, v in state.items() if not str(k).startswith("_")}
    q = build_gmail_query(clean)
    watch_result: dict[str, Any] | None = None
    watch_kwargs = {
        "state": clean,
        "query": q,
        "source": "ask_now",
        "user_text": user_text,
        "history_text": history_text,
    }

    # 1) Chạy ngay nếu cần
    if wants_run_now(clean):
        watch_result = run_email_watch(user_id, **watch_kwargs)

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
            watch_result = run_email_watch(user_id, **watch_kwargs)
        return {
            "ok": True,
            "flow": "email_watch",
            "scheduled": True,
            "job_id": job_id,
            "query": q,
            "message": watch_result.get("message") or "",
            "watch": watch_result,
            "items": watch_result.get("items") or [],
            "tokens_in": watch_result.get("_tokens_in"),
            "tokens_out": watch_result.get("_tokens_out"),
        }

    if watch_result is None:
        watch_result = run_email_watch(user_id, **watch_kwargs)
    return {
        "ok": watch_result.get("ok", False),
        "flow": "email_watch",
        "scheduled": False,
        "message": watch_result.get("message") or watch_result.get("error") or "",
        "tokens_in": watch_result.get("_tokens_in"),
        "tokens_out": watch_result.get("_tokens_out"),
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
        # User xác nhận đã đăng nhập trên browser → bỏ cờ chờ login
        only_login = missing == ["browser_login"] or (
            "browser_login" in missing and not any(
                k in missing for k in ("yesterday", "today", "url")
            )
        )
        if "browser_login" in missing and (text or "").strip():
            merged.pop("browser_login_pending", None)
            merged["_need_browser_login"] = False

        # Giữ cờ prompt từ lịch (LLM merge có thể làm mất)
        if state.get("from_scheduled_prompt"):
            merged["from_scheduled_prompt"] = True
            merged["schedule_enabled"] = False
            merged["run_now"] = True
            if not merged.get("url"):
                merged["url"] = state.get("url")

        url = merged.get("url") if isinstance(merged.get("url"), str) else None
        miss = standup_missing(merged, min_chars=_standup_min_chars(url))
        # Khi chỉ còn browser_login và user đã nhắn → coi như sẵn sàng resume browser
        if only_login and (text or "").strip():
            miss = [m for m in miss if m != "browser_login"]

        if miss:
            clean = {k: v for k, v in merged.items() if not str(k).startswith("_")}
            if "browser_login" in miss:
                clean["browser_login_pending"] = True
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
        clean = {k: v for k, v in merged.items() if not str(k).startswith("_")}
        clean.pop("browser_login_pending", None)
        cp.complete(pending["id"], clean)
        # Sau prompt lịch: đảm bảo chạy CU ngay
        if clean.get("from_scheduled_prompt"):
            clean["schedule_enabled"] = False
            clean["run_now"] = True
        out = _execute_standup(
            user_id,
            clean,
            resume_browser=("browser_login" in missing or only_login),
            session_id=session_id,
        )
        if out.get("need_hitl"):
            return _hitl_interrupt(
                session_id,
                user_id,
                "standup_fill",
                out.get("state") or clean,
                list(out.get("missing_fields") or ["browser_login"]),
                meta,
                user_text=text,
                history_text=history_text,
            )
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
        out = _execute_email(user_id, merged, user_text=text, history_text=history_text)
        tin = (meta.get("tokens_in") or 0) + (out.get("tokens_in") or out.get("_tokens_in") or 0)
        tout = (meta.get("tokens_out") or 0) + (out.get("tokens_out") or out.get("_tokens_out") or 0)
        out.update(meta)
        out["tokens_in"] = tin or None
        out["tokens_out"] = tout or None
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
    url = slots.get("url") if isinstance(slots.get("url"), str) else None
    miss = standup_missing(slots, min_chars=_standup_min_chars(url))
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
    out = _execute_standup(user_id, slots, session_id=session_id)
    if out.get("need_hitl"):
        return _hitl_interrupt(
            session_id,
            user_id,
            "standup_fill",
            out.get("state") or slots,
            list(out.get("missing_fields") or ["browser_login"]),
            {**meta, **{k: v for k, v in out.items() if k in ("message",)}},
            user_text=text,
            history_text=history_text,
        )
    return {**out, **meta}


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
    out = _execute_email(user_id, slots, user_text=text, history_text=history_text)
    tin = (meta.get("tokens_in") or 0) + (out.get("tokens_in") or out.get("_tokens_in") or 0)
    tout = (meta.get("tokens_out") or 0) + (out.get("tokens_out") or out.get("_tokens_out") or 0)
    merged = {**out, **meta, "tokens_in": tin or None, "tokens_out": tout or None}
    return merged


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
