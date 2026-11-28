"""Khi tới lịch standup mà chưa có yesterday/today → HITL + toast (chưa CU)."""
from __future__ import annotations

import time
from typing import Any, Optional

from harness.channels import notify as notify_mod
from harness.db.auth import append_chat, create_session
from harness.hitl import checkpoint as cp
from harness.hitl.slots import compose_hitl_message
from harness.jobs.delayed import schedule_job

CONTENT_TIMEOUT_SEC = 2 * 60 * 60  # 2 giờ


def fields_ready(fields: Optional[dict[str, Any]]) -> bool:
    if not fields or not isinstance(fields, dict):
        return False
    y = (fields.get("yesterday") or "").strip()
    t = (fields.get("today") or "").strip()
    return bool(y and t)


def prompt_standup_content(
    user_id: str,
    *,
    url: Optional[str] = None,
    session_id: Optional[str] = None,
    schedule_meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Mở phiên chat MỚI + HITL thiếu yesterday/today + toast desktop.
    Hẹn job timeout 2h để bỏ lỡ nếu user không trả lời.
    (session_id cũ trong job chỉ để tham chiếu — không tái sử dụng.)
    """
    _ = session_id  # lịch có thể gắn session cũ; prompt luôn dùng chat mới
    session = create_session(user_id)
    sid = session["session_id"]
    meta = schedule_meta or {}

    state: dict[str, Any] = {
        "url": url,
        "yesterday": None,
        "today": None,
        "blockers": None,
        # Sau khi user trả lời → chạy CU ngay, không xếp lịch lại từ checkpoint này
        "schedule_enabled": False,
        "run_now": True,
        "from_scheduled_prompt": True,
        "schedule_time": meta.get("schedule_time"),
        "schedule_repeat": meta.get("schedule_repeat"),
    }
    missing = ["yesterday", "today"]
    saved = cp.interrupt(sid, user_id, "standup_fill", state, missing)

    msg = compose_hitl_message(
        intent="standup_fill",
        missing=missing,
        user_text="",
        history_text="",
        state=state,
    )
    text = (msg.get("text") or "").strip()

    try:
        # Tin user giả để sidebar hiện tiêu đề rõ (không phải "New chat")
        append_chat(
            sid,
            user_id,
            "user",
            "Đến giờ standup — cần điền nội dung",
            flow="standup_prompt",
            meta={"synthetic": True, "from_schedule": True},
        )
        append_chat(
            sid,
            user_id,
            "assistant",
            text,
            flow="standup_prompt",
            meta={
                "hitl": True,
                "checkpoint_id": saved.get("id"),
                "missing_fields": missing,
                "from_schedule": True,
            },
        )
    except Exception as e:
        print(f"[standup_prompt] append_chat error: {e}")

    notify_mod.push(
        user_id,
        "standup_need_content",
        "Đến giờ standup — mở chat mới",
        (
            "Đã mở một phiên chat mới để bạn điền hôm qua / hôm nay. "
            "Mở digitalboo và trả lời trong chat đó nhé."
        ),
        {
            "session_id": sid,
            "checkpoint_id": saved.get("id"),
            "url": url,
            "open_chat": True,
        },
    )

    timeout_at = time.time() + CONTENT_TIMEOUT_SEC
    timeout_job_id = schedule_job(
        "standup_content_timeout",
        {
            "user_id": user_id,
            "session_id": sid,
            "checkpoint_id": saved.get("id"),
            "url": url,
        },
        timeout_at,
    )

    return {
        "ok": True,
        "flow": "standup_prompt",
        "awaiting_content": True,
        "session_id": sid,
        "checkpoint_id": saved.get("id"),
        "message": text,
        "timeout_job_id": timeout_job_id,
        "timeout_at_unix": timeout_at,
    }


def expire_standup_content_prompt(
    user_id: str,
    *,
    session_id: str,
    checkpoint_id: Optional[int] = None,
    url: Optional[str] = None,
) -> dict[str, Any]:
    """Nếu checkpoint vẫn chờ yesterday/today → đóng và toast bỏ lỡ."""
    pending = cp.get_pending(session_id)
    if not pending:
        return {"ok": True, "skipped": True, "reason": "no_pending"}

    if checkpoint_id is not None and pending.get("id") != checkpoint_id:
        return {"ok": True, "skipped": True, "reason": "checkpoint_mismatch"}

    if pending.get("intent") != "standup_fill":
        return {"ok": True, "skipped": True, "reason": "wrong_intent"}

    missing = list(pending.get("missing_fields") or [])
    if "yesterday" not in missing and "today" not in missing:
        return {"ok": True, "skipped": True, "reason": "content_already_filled"}

    state = dict(pending.get("state") or {})
    state["expired"] = True
    cp.complete(pending["id"], state)

    composed = compose_hitl_message(
        intent="standup_fill",
        missing=["yesterday", "today"],
        user_text="",
        history_text="",
        state={**state, "_expired_timeout": True, "url": url},
    )
    msg = (composed.get("text") or "").strip()
    if msg:
        try:
            append_chat(
                session_id,
                user_id,
                "assistant",
                msg,
                flow="standup_prompt_timeout",
                meta={"checkpoint_id": pending.get("id"), "url": url},
            )
        except Exception as e:
            print(f"[standup_prompt] timeout append_chat error: {e}")

    notify_mod.push(
        user_id,
        "standup_missed",
        "Bỏ lỡ standup hôm nay",
        msg or "Hết hạn chờ nội dung standup.",
        {"session_id": session_id, "checkpoint_id": pending.get("id"), "url": url},
    )
    return {"ok": True, "expired": True, "checkpoint_id": pending.get("id"), "message": msg}
