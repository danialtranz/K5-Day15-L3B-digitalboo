"""Lưu / đọc OAuth token Gmail & Outlook trong Postgres."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from harness.channels.email.base import TokenBundle
from harness.channels.email.google_gmail import GmailProvider
from harness.channels.email.outlook_msgraph import OutlookProvider
from harness.db.session import get_connection


def upsert_account(user_id: str, provider: str, bundle: TokenBundle) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO email_accounts (
                user_id, provider, email_address, access_token, refresh_token,
                expires_at, scopes, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id, provider) DO UPDATE SET
                email_address = COALESCE(EXCLUDED.email_address, email_accounts.email_address),
                access_token = EXCLUDED.access_token,
                refresh_token = COALESCE(EXCLUDED.refresh_token, email_accounts.refresh_token),
                expires_at = EXCLUDED.expires_at,
                scopes = EXCLUDED.scopes,
                updated_at = NOW()
            """,
            (
                user_id,
                provider,
                bundle.email_address,
                bundle.access_token,
                bundle.refresh_token,
                bundle.expires_at,
                bundle.scopes,
            ),
        )
        conn.commit()


def get_account(user_id: str, provider: str = "google") -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM email_accounts WHERE user_id = %s AND provider = %s",
            (user_id, provider),
        ).fetchone()
    return dict(row) if row else None


def delete_account(user_id: str, provider: str = "google") -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM email_accounts WHERE user_id = %s AND provider = %s",
            (user_id, provider),
        )
        conn.commit()


def get_valid_access_token(user_id: str, provider: str = "google") -> Optional[str]:
    row = get_account(user_id, provider)
    if not row:
        return None
    expires = row.get("expires_at")
    now = datetime.now(timezone.utc)
    if expires is not None and getattr(expires, "tzinfo", None) is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires > now + timedelta(seconds=60):
        return row["access_token"]
    refresh = row.get("refresh_token")
    if not refresh:
        return row["access_token"]
    if provider == "google":
        bundle = GmailProvider().refresh(refresh)
    elif provider == "outlook":
        bundle = OutlookProvider().refresh(refresh)
    else:
        return None
    bundle.email_address = row.get("email_address")
    upsert_account(user_id, provider, bundle)
    return bundle.access_token
