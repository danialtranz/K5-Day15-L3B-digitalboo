"""Gmail OAuth + watch + notifications."""
from __future__ import annotations

import json
import secrets
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from harness.channels.email.google_gmail import GmailProvider
from harness.channels.email.token_store import delete_account, get_account, upsert_account
from harness.channels.notify import list_notifications
from harness.config import settings
from harness.db.redis_client import pop_oauth_state, set_oauth_state
from harness.flows.email_watch import run_email_watch

router = APIRouter(prefix="/email", tags=["email"])


def _redirect_uri() -> str:
    return f"{settings()['oauth_redirect_base'].rstrip('/')}/email/oauth/google/callback"


@router.get("/oauth/google/start")
def oauth_start(user_id: Optional[str] = None):
    s = settings()
    if not s["google_client_id"] or not s["google_client_secret"]:
        raise HTTPException(400, "Thiếu GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET trong .env")
    user_id = user_id or s["default_user_id"]
    state = secrets.token_urlsafe(24)
    set_oauth_state(state, json.dumps({"user_id": user_id}))
    url = GmailProvider().connect_url(state, _redirect_uri())
    return RedirectResponse(url)


@router.get("/oauth/google/callback")
def oauth_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    if error:
        raise HTTPException(400, f"OAuth error: {error}")
    if not code or not state:
        raise HTTPException(400, "Thiếu code/state")
    raw = pop_oauth_state(state)
    if not raw:
        raise HTTPException(400, "State không hợp lệ hoặc hết hạn")
    payload = json.loads(raw)
    user_id = payload.get("user_id") or settings()["default_user_id"]
    provider = GmailProvider()
    bundle = provider.exchange_code(code, _redirect_uri())
    email = provider.fetch_profile_email(bundle.access_token)
    bundle.email_address = email
    upsert_account(user_id, "google", bundle)
    html = f"""
    <html><body style="font-family:sans-serif;padding:2rem">
      <h1>Gmail connected</h1>
      <p>user_id=<b>{user_id}</b></p>
      <p>email=<b>{email or 'unknown'}</b></p>
      <p>Có thể đóng tab này. Gọi POST /email/watch để quét mail.</p>
    </body></html>
    """
    return HTMLResponse(html)


@router.get("/status")
def email_status(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    row = get_account(user_id, "google")
    if not row:
        return {"connected": False, "user_id": user_id, "provider": "google"}
    return {
        "connected": True,
        "user_id": user_id,
        "provider": "google",
        "email_address": row.get("email_address"),
        "expires_at": str(row.get("expires_at")),
        "scopes": row.get("scopes"),
    }


@router.delete("/oauth/google")
def oauth_disconnect(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    delete_account(user_id, "google")
    return {"ok": True, "message": "Đã disconnect Gmail"}


@router.post("/watch")
def watch_now(user_id: Optional[str] = None):
    return run_email_watch(user_id or settings()["default_user_id"])


@router.get("/notifications")
def notifications(user_id: Optional[str] = None, limit: int = Query(50, ge=1, le=200)):
    user_id = user_id or settings()["default_user_id"]
    rows = list_notifications(user_id, limit=limit)
    # Không lộ meta nhạy cảm quá mức; giữ nguyên MVP
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])
        if r.get("read_at"):
            r["read_at"] = str(r["read_at"])
    return {"items": rows}
