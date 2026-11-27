"""Auth tối giản: user_id có trong bảng users là được."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from harness.config import settings
from harness.db.auth import create_session, get_user, list_chat, require_user

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(BaseModel):
    user_id: str


@router.post("/login")
def login(body: LoginBody):
    user = require_user(body.user_id)
    session = create_session(body.user_id)
    return {
        "ok": True,
        "user": {
            "user_id": user["user_id"],
            "display_name": user.get("display_name"),
        },
        "session_id": session["session_id"],
        "session": session,
    }


@router.get("/me")
def me(user_id: Optional[str] = None):
    uid = user_id or settings()["default_user_id"]
    user = require_user(uid)
    return {"ok": True, "user": {"user_id": user["user_id"], "display_name": user.get("display_name")}}


@router.get("/users/{user_id}")
def user_exists(user_id: str):
    user = get_user(user_id)
    if not user:
        return {"exists": False, "user_id": user_id}
    return {"exists": True, "user_id": user["user_id"], "display_name": user.get("display_name")}


@router.get("/chat/history")
def chat_history(
    session_id: str = Query(...),
    user_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    uid = user_id or settings()["default_user_id"]
    require_user(uid)
    return {"items": list_chat(session_id, uid, limit=limit)}
