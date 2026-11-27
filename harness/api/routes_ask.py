from __future__ import annotations

import json
import time
from typing import Any, Iterator, Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from harness.config import settings
from harness.db.auth import append_chat, get_or_create_session, list_chat, require_user
from harness.orchestrator import handle

router = APIRouter(tags=["ask"])


class AskBody(BaseModel):
    text: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None


def _run_ask(body: AskBody) -> dict[str, Any]:
    user_id = body.user_id or settings()["default_user_id"]
    require_user(user_id)
    session = get_or_create_session(user_id, body.session_id)
    session_id = session["session_id"]

    prior = list_chat(session_id, user_id, limit=40)
    append_chat(session_id, user_id, "user", body.text)
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
        "message": assistant_text,
        "user_id": user_id,
        "session_id": session_id,
    }


@router.post("/ask")
def ask(body: AskBody) -> dict[str, Any]:
    return _run_ask(body)


def _sse(event: str, data: Any) -> str:
    payload = json.dumps(data, ensure_ascii=False, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


def _chunk_text(text: str, size: int = 10) -> Iterator[str]:
    if not text:
        return
    i = 0
    n = len(text)
    while i < n:
        j = min(i + size, n)
        # cố gắng cắt ở khoảng trắng gần cuối chunk (đỡ gãy từ)
        if j < n:
            space = text.rfind(" ", i, j + 8)
            if space > i:
                j = space + 1
        yield text[i:j]
        i = j


def _ask_sse_gen(body: AskBody) -> Iterator[str]:
    yield _sse("status", {"phase": "working", "message": "Đang xử lý…"})
    try:
        result = _run_ask(body)
    except Exception as e:
        yield _sse("error", {"message": str(e)})
        return

    text = result.get("message") or ""
    # Meta sớm (HITL/actions) trước khi stream chữ — UI biết khóa input nếu cần
    yield _sse(
        "meta",
        {
            "ok": result.get("ok"),
            "session_id": result.get("session_id"),
            "user_id": result.get("user_id"),
            "flow": result.get("flow"),
            "hitl": result.get("hitl"),
            "missing_fields": result.get("missing_fields"),
            "actions": result.get("actions"),
            "ui": result.get("ui"),
        },
    )

    for piece in _chunk_text(text, size=12):
        yield _sse("delta", {"text": piece})
        time.sleep(0.018)

    yield _sse("done", result)


@router.post("/ask/stream")
def ask_stream(body: AskBody) -> StreamingResponse:
    """SSE: status → meta → delta* → done (hoặc error)."""
    return StreamingResponse(
        _ask_sse_gen(body),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
