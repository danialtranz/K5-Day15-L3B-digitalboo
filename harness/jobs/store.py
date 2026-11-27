"""Grant standup + dedupe job trong Postgres."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional
from urllib.parse import urlparse

from harness.config import settings
from harness.db.session import get_connection


def upsert_grant(user_id: str, url: str, site_id: str = "daily_standup", allow_submit: bool = True) -> dict[str, Any]:
    allow = settings()["standup_allowlist_url"]
    if allow:
        if urlparse(url).netloc.lower() != urlparse(allow).netloc.lower():
            raise PermissionError(f"Grant URL phải cùng host allowlist ({allow})")
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO standup_grants (user_id, site_id, url, allow_submit, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                site_id = EXCLUDED.site_id,
                url = EXCLUDED.url,
                allow_submit = EXCLUDED.allow_submit,
                updated_at = NOW()
            RETURNING *
            """,
            (user_id, site_id, url, allow_submit),
        ).fetchone()
        conn.commit()
    return dict(row)


def get_grant(user_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM standup_grants WHERE user_id = %s",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def already_done(user_id: str, job_type: str, day_key: Optional[str] = None) -> bool:
    day_key = day_key or date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM job_runs
            WHERE user_id = %s AND job_type = %s AND day_key = %s AND status = 'ok'
            LIMIT 1
            """,
            (user_id, job_type, day_key),
        ).fetchone()
    return row is not None


def record_job(
    user_id: str,
    job_type: str,
    status: str,
    detail: Optional[dict[str, Any]] = None,
    artifact_path: Optional[str] = None,
    day_key: Optional[str] = None,
) -> dict[str, Any]:
    day_key = day_key or date.today().isoformat()
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO job_runs (user_id, job_type, day_key, status, detail, artifact_path)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            RETURNING id, created_at
            """,
            (user_id, job_type, day_key, status, json.dumps(detail or {}), artifact_path),
        ).fetchone()
        conn.commit()
    return dict(row)


def mark_mail_seen(user_id: str, message_id: str, provider: str = "google") -> bool:
    """True nếu lần đầu thấy message (insert ok)."""
    with get_connection() as conn:
        try:
            conn.execute(
                """
                INSERT INTO mail_seen (user_id, provider, message_id)
                VALUES (%s, %s, %s)
                """,
                (user_id, provider, message_id),
            )
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
