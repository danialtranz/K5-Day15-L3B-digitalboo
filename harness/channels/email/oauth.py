"""Helper tạo URL OAuth Gmail / Outlook (popup / redirect)."""
from __future__ import annotations

import json
import secrets
from typing import Any, Optional

from harness.channels.email.google_gmail import GmailProvider
from harness.channels.email.outlook_msgraph import OutlookProvider
from harness.config import settings
from harness.db.redis_client import set_oauth_state


def google_redirect_uri() -> str:
    return f"{settings()['oauth_redirect_base'].rstrip('/')}/email/oauth/google/callback"


def outlook_redirect_uri() -> str:
    return f"{settings()['oauth_redirect_base'].rstrip('/')}/email/oauth/outlook/callback"


# backward-compat alias
def redirect_uri() -> str:
    return google_redirect_uri()


def _store_state(
    user_id: str,
    *,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
    provider: str,
) -> str:
    state = secrets.token_urlsafe(24)
    set_oauth_state(
        state,
        json.dumps(
            {
                "user_id": user_id,
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
                "provider": provider,
            }
        ),
    )
    return state


def build_google_oauth_start(
    user_id: str,
    *,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
) -> dict[str, Any]:
    s = settings()
    if not s["google_client_id"] or not s["google_client_secret"]:
        raise ValueError("Thiếu GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET trong .env")
    state = _store_state(
        user_id,
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        provider="google",
    )
    oauth_url = GmailProvider().connect_url(state, google_redirect_uri())
    return {
        "oauth_url": oauth_url,
        "state": state,
        "user_id": user_id,
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "provider": "google",
        "popup": True,
    }


def build_outlook_oauth_start(
    user_id: str,
    *,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
) -> dict[str, Any]:
    s = settings()
    if not s["microsoft_client_id"] or not s["microsoft_client_secret"]:
        raise ValueError(
            "Thiếu MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET trong .env "
            "(Azure App Registration)"
        )
    state = _store_state(
        user_id,
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        provider="outlook",
    )
    oauth_url = OutlookProvider().connect_url(state, outlook_redirect_uri())
    return {
        "oauth_url": oauth_url,
        "state": state,
        "user_id": user_id,
        "session_id": session_id,
        "checkpoint_id": checkpoint_id,
        "provider": "outlook",
        "popup": True,
    }
