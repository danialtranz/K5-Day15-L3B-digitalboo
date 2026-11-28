"""Grant standup + dedupe job trong Postgres."""
from __future__ import annotations

import json
from datetime import date
from typing import Any, Optional

from harness.config import settings
from harness.db.session import get_connection


def upsert_grant(user_id: str, url: str, site_id: str = "daily_standup", allow_submit: bool = True) -> dict[str, Any]:
    from harness.computer_use.browser import url_permitted
    from harness.computer_use.playbook import is_safe_https_url, match_playbook, resolve_strategy

    if not is_safe_https_url(url):
        raise PermissionError("Grant URL phải là https hợp lệ (không file:/javascript:).")
    # Edufun playbook / vision HTTPS / legacy allowlist host
    if not url_permitted(url):
        allow = settings()["standup_allowlist_url"]
        raise PermissionError(f"Grant URL không được phép: {url} (allow={allow})")
    # site_id theo playbook nếu có
    pb = match_playbook(url)
    if pb and pb.get("_id"):
        site_id = str(pb["_id"])
    elif resolve_strategy(url) == "vision":
        site_id = site_id or "vision_standup"
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
    """Ghi job_runs. status=ok dùng upsert vì unique (user_id, job_type, day_key) khi ok."""
    day_key = day_key or date.today().isoformat()
    payload = (user_id, job_type, day_key, status, json.dumps(detail or {}), artifact_path)
    with get_connection() as conn:
        if status == "ok" and day_key is not None:
            # Partial unique index job_runs_dedupe — nộp lại trong ngày thì cập nhật bản ok
            row = conn.execute(
                """
                INSERT INTO job_runs (user_id, job_type, day_key, status, detail, artifact_path)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (user_id, job_type, day_key)
                    WHERE day_key IS NOT NULL AND status = 'ok'
                DO UPDATE SET
                    detail = EXCLUDED.detail,
                    artifact_path = EXCLUDED.artifact_path,
                    created_at = NOW()
                RETURNING id, created_at
                """,
                payload,
            ).fetchone()
        else:
            row = conn.execute(
                """
                INSERT INTO job_runs (user_id, job_type, day_key, status, detail, artifact_path)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                RETURNING id, created_at
                """,
                payload,
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
