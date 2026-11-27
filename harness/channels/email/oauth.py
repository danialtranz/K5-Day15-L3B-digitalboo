"""Helper tạo URL Google OAuth (popup / redirect)."""
from __future__ import annotations

import json
import secrets
from typing import Any, Optional

from harness.channels.email.google_gmail import GmailProvider
from harness.config import settings
from harness.db.redis_client import set_oauth_state


def redirect_uri() -> str:
    return f"{settings()['oauth_redirect_base'].rstrip('/')}/email/oauth/google/callback"


def build_google_oauth_start(
    user_id: str,
    *,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
) -> dict[str, Any]:
    s = settings()
    if not s["google_client_id"] or not s["google_client_secret"]:
        raise ValueError("Thiếu GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET trong .env")
    state = secrets.token_urlsafe(24)
    set_oauth_state(
        state,
        json.dumps(
            {
                "user_id": user_id,
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        ),
    )
    oauth_url = GmailProvider().connect_url(state, redirect_uri())
    return {
        "oauth_url": oauth_url,
        "state": state,
        "user_id": user_id,
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "popup": True,
    }
