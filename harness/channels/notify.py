"""Ghi notification vào Postgres + file outbox (MVP báo user)."""
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


def list_notifications(user_id: str, limit: int = 50) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, kind, title, body, meta, created_at, read_at
            FROM notifications
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]
