"""Checkpointer: lưu state đang chờ user bổ sung (Postgres)."""
from __future__ import annotations

import json
from typing import Any, Optional

from harness.db.session import get_connection


def _row_to_checkpoint(row: Any) -> dict[str, Any]:
    out = dict(row)
    if isinstance(out.get("state"), str):
        out["state"] = json.loads(out["state"])
    if isinstance(out.get("missing_fields"), str):
        out["missing_fields"] = json.loads(out["missing_fields"])
    for k in ("created_at", "updated_at"):
        if out.get(k):
            out[k] = str(out[k])
    return out


def get_pending(session_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, session_id, user_id, intent, state, missing_fields, status, created_at, updated_at
            FROM hitl_checkpoints
            WHERE session_id = %s AND status = 'interrupted'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (session_id,),
        ).fetchone()
    return _row_to_checkpoint(row) if row else None


def get_pending_email_grant(
    user_id: str,
    session_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Checkpoint email_watch đang chờ grant — ưu tiên đúng session."""
    with get_connection() as conn:
        if session_id:
            row = conn.execute(
                """
                SELECT id, session_id, user_id, intent, state, missing_fields, status, created_at, updated_at
                FROM hitl_checkpoints
                WHERE user_id = %s AND session_id = %s AND status = 'interrupted'
                  AND intent = 'email_watch'
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (user_id, session_id),
            ).fetchone()
            if row:
                return _row_to_checkpoint(row)
        row = conn.execute(
            """
            SELECT id, session_id, user_id, intent, state, missing_fields, status, created_at, updated_at
            FROM hitl_checkpoints
            WHERE user_id = %s AND status = 'interrupted' AND intent = 'email_watch'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return _row_to_checkpoint(row) if row else None


def interrupt(
    session_id: str,
    user_id: str,
    intent: str,
    state: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    """Tạo / ghi đè checkpoint interrupted cho session (1 pending / session)."""
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE hitl_checkpoints
            SET status = 'cancelled', updated_at = NOW()
            WHERE session_id = %s AND status = 'interrupted'
            """,
            (session_id,),
        )
        row = conn.execute(
            """
            INSERT INTO hitl_checkpoints (session_id, user_id, intent, state, missing_fields, status)
            VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, 'interrupted')
            RETURNING id, session_id, user_id, intent, state, missing_fields, status, created_at, updated_at
            """,
            (
                session_id,
                user_id,
                intent,
                json.dumps(state, ensure_ascii=False),
                json.dumps(missing_fields, ensure_ascii=False),
            ),
        ).fetchone()
        conn.commit()
    out = dict(row)
    if isinstance(out.get("state"), str):
        out["state"] = json.loads(out["state"])
    if isinstance(out.get("missing_fields"), str):
        out["missing_fields"] = json.loads(out["missing_fields"])
    for k in ("created_at", "updated_at"):
        if out.get(k):
            out[k] = str(out[k])
    return out


def update_pending(
    checkpoint_id: int,
    state: dict[str, Any],
    missing_fields: list[str],
) -> dict[str, Any]:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE hitl_checkpoints
            SET state = %s::jsonb, missing_fields = %s::jsonb, updated_at = NOW()
            WHERE id = %s AND status = 'interrupted'
            RETURNING id, session_id, user_id, intent, state, missing_fields, status
            """,
            (
                json.dumps(state, ensure_ascii=False),
                json.dumps(missing_fields, ensure_ascii=False),
                checkpoint_id,
            ),
        ).fetchone()
        conn.commit()
    if not row:
        return {}
    out = dict(row)
    if isinstance(out.get("state"), str):
        out["state"] = json.loads(out["state"])
    if isinstance(out.get("missing_fields"), str):
        out["missing_fields"] = json.loads(out["missing_fields"])
    return out


def complete(checkpoint_id: int, state: Optional[dict[str, Any]] = None) -> None:
    with get_connection() as conn:
        if state is not None:
            conn.execute(
                """
                UPDATE hitl_checkpoints
                SET status = 'completed', state = %s::jsonb, missing_fields = '[]'::jsonb, updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(state, ensure_ascii=False), checkpoint_id),
            )
        else:
            conn.execute(
                """
                UPDATE hitl_checkpoints
                SET status = 'completed', missing_fields = '[]'::jsonb, updated_at = NOW()
                WHERE id = %s
                """,
                (checkpoint_id,),
            )
        conn.commit()
