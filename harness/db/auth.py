"""Users / sessions / chat_history — auth tối giản: user_id phải tồn tại."""
from __future__ import annotations

import json
import secrets
from typing import Any, Optional

from fastapi import HTTPException

from harness.db.session import get_connection

SEED_USERS = (
    {"user_id": "u1", "display_name": "Demo User"},
)

# Session seed cố định — dùng cho curl demo
SEED_SESSION_ID = "sess_u1_demo"
SEED_SESSION_USER_ID = "u1"


def seed_users() -> None:
    with get_connection() as conn:
        for u in SEED_USERS:
            conn.execute(
                """
                INSERT INTO users (user_id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (u["user_id"], u["display_name"]),
            )
        conn.execute(
            """
            INSERT INTO sessions (session_id, user_id)
            VALUES (%s, %s)
            ON CONFLICT (session_id) DO NOTHING
            """,
            (SEED_SESSION_ID, SEED_SESSION_USER_ID),
        )
        conn.commit()


def get_user(user_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, display_name, created_at FROM users WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def require_user(user_id: str) -> dict[str, Any]:
    user = get_user(user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail=f"user_id '{user_id}' không tồn tại. Seed mặc định: u1 (POST /auth/login).",
        )
    return user


def create_session(user_id: str) -> dict[str, Any]:
    require_user(user_id)
    session_id = secrets.token_urlsafe(24)
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO sessions (session_id, user_id)
            VALUES (%s, %s)
            RETURNING session_id, user_id, created_at, last_seen_at
            """,
            (session_id, user_id),
        ).fetchone()
        conn.commit()
    out = dict(row)
    for k in ("created_at", "last_seen_at"):
        if out.get(k):
            out[k] = str(out[k])
    return out


def touch_session(session_id: str, user_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE sessions
            SET last_seen_at = NOW()
            WHERE session_id = %s AND user_id = %s AND ended_at IS NULL
            RETURNING session_id, user_id, created_at, last_seen_at
            """,
            (session_id, user_id),
        ).fetchone()
        conn.commit()
    if not row:
        raise HTTPException(401, "session không hợp lệ hoặc đã kết thúc")
    out = dict(row)
    for k in ("created_at", "last_seen_at"):
        if out.get(k):
            out[k] = str(out[k])
    return out


def get_or_create_session(user_id: str, session_id: Optional[str] = None) -> dict[str, Any]:
    require_user(user_id)
    if session_id:
        return touch_session(session_id, user_id)
    return create_session(user_id)


def append_chat(
    session_id: str,
    user_id: str,
    role: str,
    content: str,
    flow: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO chat_history (session_id, user_id, role, content, flow, meta)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, session_id, user_id, role, content, flow, created_at
            """,
            (session_id, user_id, role, content, flow, json.dumps(meta or {})),
        ).fetchone()
        conn.execute(
            "UPDATE sessions SET last_seen_at = NOW() WHERE session_id = %s",
            (session_id,),
        )
        conn.commit()
    out = dict(row)
    if out.get("created_at"):
        out["created_at"] = str(out["created_at"])
    return out


def list_chat(session_id: str, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, session_id, user_id, role, content, flow, meta, created_at
            FROM chat_history
            WHERE session_id = %s AND user_id = %s
            ORDER BY id ASC
            LIMIT %s
            """,
            (session_id, user_id, limit),
        ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        if item.get("created_at"):
            item["created_at"] = str(item["created_at"])
        out.append(item)
    return out
