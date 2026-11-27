from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from harness.config import settings
from harness.db.auth import append_chat, get_or_create_session, list_chat, require_user
from harness.orchestrator import handle

router = APIRouter(tags=["ask"])


class AskBody(BaseModel):
    text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/ask")
def ask(body: AskBody) -> dict[str, Any]:
    user_id = body.user_id or settings()["default_user_id"]
    require_user(user_id)
    session = get_or_create_session(user_id, body.session_id)
    session_id = session["session_id"]

    # Lịch sử trước tin hiện tại
    prior = list_chat(session_id, user_id, limit=40)
    append_chat(session_id, user_id, "user", body.text)
    # History đưa vào agent = prior + tin user vừa gửi
    history = prior + [{"role": "user", "content": body.text}]

    result = handle(
        body.text,
        source="api",
        user_id=user_id,
        session_id=session_id,
        history=history,
    )
    assistant_text = result.get("message") or result.get("error") or str(result)
    if not isinstance(assistant_text, str):
        assistant_text = str(assistant_text)

    append_chat(
        session_id,
        user_id,
        "assistant",
        assistant_text,
        flow=result.get("flow"),
        meta={
            "ok": result.get("ok"),
            "hitl": result.get("hitl"),
            "missing_fields": result.get("missing_fields"),
        },
    )

    return {
        **result,
        "user_id": user_id,
        "session_id": session_id,
    }
