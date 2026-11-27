"""Ghi notification vào Postgres + file outbox (MVP báo user / desktop poll)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from harness.config import ensure_dirs, settings
from harness.db.session import get_connection


def push(
    user_id: str,
    kind: str,
    title: str,
    body: str,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_dirs()
    meta = meta or {}
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO notifications (user_id, kind, title, body, meta)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (user_id, kind, title, body, json.dumps(meta)),
        ).fetchone()
        conn.commit()

    outbox = Path(settings()["outbox_dir"])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = outbox / f"{stamp}-{kind}-{row['id']}.md"
    path.write_text(
        f"# {title}\n\nuser: {user_id}\nkind: {kind}\n\n{body}\n",
        encoding="utf-8",
    )
    print(f"[notify] {title} → {path}")
    return {"id": row["id"], "path": str(path), "created_at": str(row["created_at"])}


def list_notifications(
    user_id: str,
    limit: int = 50,
    *,
    unread_only: bool = False,
    since_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    clauses = ["user_id = %s"]
    params: list[Any] = [user_id]
    if unread_only:
        clauses.append("read_at IS NULL")
    if since_id is not None:
        clauses.append("id > %s")
        params.append(since_id)
    where = " AND ".join(clauses)
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, kind, title, body, meta, created_at, read_at
            FROM notifications
            WHERE {where}
            ORDER BY id ASC
            LIMIT %s
            """,
            tuple(params),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_read(notification_id: int, user_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE notifications
            SET read_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id, kind, title, body, meta, created_at, read_at
            """,
            (notification_id, user_id),
        ).fetchone()
        conn.commit()
    return dict(row) if row else None


def mark_all_read(user_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE notifications
            SET read_at = NOW()
            WHERE user_id = %s AND read_at IS NULL
            """,
            (user_id,),
        )
        conn.commit()
        return row.rowcount or 0
