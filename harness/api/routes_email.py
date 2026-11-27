"""Gmail + Outlook OAuth + watch + notifications."""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from harness.channels.email.google_gmail import GmailProvider
from harness.channels.email.oauth import (
    build_google_oauth_start,
    build_outlook_oauth_start,
    google_redirect_uri,
    outlook_redirect_uri,
)
from harness.channels.email.outlook_msgraph import OutlookProvider
from harness.channels.email.token_store import delete_account, get_account, upsert_account
from harness.channels.notify import list_notifications, mark_all_read, mark_read
from harness.config import settings
from harness.db.auth import append_chat
from harness.db.redis_client import pop_oauth_state
from harness.flows.email_watch import run_email_watch
from harness.orchestrator import resume_email_after_oauth

router = APIRouter(prefix="/email", tags=["email"])


def _oauth_done_html(
    *,
    title: str,
    user_id: str,
    email: str | None,
    resume: dict[str, Any],
    event_type: str,
) -> HTMLResponse:
    resume_js = json.dumps(resume, ensure_ascii=False, default=str)
    msg = resume.get("message") or f"{title}."
    important = resume.get("important")
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body style="font-family:sans-serif;padding:2rem;max-width:40rem">
  <h1>{title}</h1>
  <p>user_id=<b>{user_id}</b></p>
  <p>email=<b>{email or "unknown"}</b></p>
  <p>{msg}</p>
  <p>{"Tin quan trọng: " + str(important) if important is not None else ""}</p>
  <p><small>Có thể đóng cửa sổ này.</small></p>
  <script>
    (function () {{
      var payload = {resume_js};
      payload.type = "{event_type}";
      try {{
        if (window.opener && !window.opener.closed) {{
          window.opener.postMessage(payload, "*");
        }}
      }} catch (e) {{}}
      setTimeout(function () {{ window.close(); }}, 1200);
    }})();
  </script>
</body></html>
"""
    return HTMLResponse(html)


def _finish_oauth(
    *,
    provider: str,
    user_id: str,
    session_id: Optional[str],
    checkpoint_id: Optional[int],
    email: Optional[str],
    label: str,
    event_type: str,
    watch_hint: str,
) -> HTMLResponse:
    resume: dict = {
        "ok": True,
        "flow": "email_oauth",
        "message": f"Đã kết nối {label} ({email or 'ok'}).",
        "granted": True,
        "provider": provider,
    }
    try:
        resume = resume_email_after_oauth(
            user_id=user_id,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
        )
        resume["granted"] = True
        resume["provider"] = provider
    except Exception as e:
        resume = {
            "ok": False,
            "flow": "email_oauth",
            "granted": True,
            "provider": provider,
            "error": "watch_after_oauth_failed",
            "message": (
                f"Đã kết nối {label} ({email or 'ok'}) nhưng chưa đọc được hộp thư: {e}. "
                f"{watch_hint}"
            ),
        }

    if session_id:
        try:
            append_chat(
                session_id,
                user_id,
                "assistant",
                resume.get("message") or f"Đã connect {label} và quét mail.",
                flow=resume.get("flow") or "email_watch",
                meta={
                    "ok": resume.get("ok"),
                    "granted": resume.get("granted"),
                    "provider": provider,
                    "resumed_from_oauth": True,
                    "important": resume.get("important"),
                },
            )
        except Exception:
            pass

    title = f"{label} đã kết nối" if resume.get("granted") else label
    return _oauth_done_html(
        title=title,
        user_id=user_id,
        email=email,
        resume=resume,
        event_type=event_type,
    )


@router.get("/oauth/google/start")
def oauth_google_start(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
    format: Optional[str] = Query(None, description="json = trả oauth_url cho popup"),
):
    s = settings()
    user_id = user_id or s["default_user_id"]
    try:
        start = build_google_oauth_start(
            user_id,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if (format or "").lower() == "json":
        return JSONResponse(
            {
                "ok": True,
                "popup": True,
                "provider": "google",
                "oauth_url": start["oauth_url"],
                "user_id": user_id,
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        )
    return RedirectResponse(start["oauth_url"])


@router.get("/oauth/google/callback")
def oauth_google_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    if error:
        raise HTTPException(400, f"OAuth error: {error}")
    if not code or not state:
        raise HTTPException(400, "Thiếu code/state")
    raw = pop_oauth_state(state)
    if not raw:
        raise HTTPException(400, "State không hợp lệ hoặc hết hạn")
    payload = json.loads(raw)
    user_id = payload.get("user_id") or settings()["default_user_id"]
    session_id = payload.get("session_id")
    checkpoint_id = payload.get("checkpoint_id")

    provider = GmailProvider()
    bundle = provider.exchange_code(code, google_redirect_uri())
    email = provider.fetch_profile_email(bundle.access_token)
    bundle.email_address = email
    upsert_account(user_id, "google", bundle)

    return _finish_oauth(
        provider="google",
        user_id=user_id,
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        email=email,
        label="Gmail",
        event_type="gmail_oauth_done",
        watch_hint=(
            "Hãy bật Gmail API trên Google Cloud "
            "(APIs & Services → Library → Gmail API → Enable), "
            "rồi nhắn lại trong chat để quét mail."
        ),
    )


@router.get("/oauth/outlook/start")
def oauth_outlook_start(
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    checkpoint_id: Optional[int] = None,
    format: Optional[str] = Query(None, description="json = trả oauth_url cho popup"),
):
    s = settings()
    user_id = user_id or s["default_user_id"]
    try:
        start = build_outlook_oauth_start(
            user_id,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e

    if (format or "").lower() == "json":
        return JSONResponse(
            {
                "ok": True,
                "popup": True,
                "provider": "outlook",
                "oauth_url": start["oauth_url"],
                "user_id": user_id,
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        )
    return RedirectResponse(start["oauth_url"])


@router.get("/oauth/outlook/callback")
def oauth_outlook_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    if error:
        raise HTTPException(400, f"OAuth error: {error}")
    if not code or not state:
        raise HTTPException(400, "Thiếu code/state")
    raw = pop_oauth_state(state)
    if not raw:
        raise HTTPException(400, "State không hợp lệ hoặc hết hạn")
    payload = json.loads(raw)
    user_id = payload.get("user_id") or settings()["default_user_id"]
    session_id = payload.get("session_id")
    checkpoint_id = payload.get("checkpoint_id")

    provider = OutlookProvider()
    bundle = provider.exchange_code(code, outlook_redirect_uri())
    email = provider.fetch_profile_email(bundle.access_token)
    bundle.email_address = email
    upsert_account(user_id, "outlook", bundle)

    return _finish_oauth(
        provider="outlook",
        user_id=user_id,
        session_id=session_id,
        checkpoint_id=checkpoint_id,
        email=email,
        label="Outlook",
        event_type="outlook_oauth_done",
        watch_hint=(
            "Kiểm tra Azure App đã thêm redirect URI và quyền "
            "Mail.Read / User.Read / offline_access, rồi nhắn lại trong chat."
        ),
    )


@router.get("/status")
def email_status(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    google = get_account(user_id, "google")
    outlook = get_account(user_id, "outlook")

    def _brief(row: Optional[dict]) -> dict:
        if not row:
            return {"connected": False}
        return {
            "connected": True,
            "email_address": row.get("email_address"),
            "expires_at": str(row.get("expires_at")) if row.get("expires_at") else None,
            "scopes": row.get("scopes"),
        }

    primary = "google" if google else ("outlook" if outlook else None)
    primary_row = google or outlook
    return {
        "connected": bool(google or outlook),
        "user_id": user_id,
        "provider": primary,
        "email_address": (primary_row or {}).get("email_address") if primary_row else None,
        "providers": {
            "google": _brief(google),
            "outlook": _brief(outlook),
        },
    }


@router.delete("/oauth/google")
def oauth_google_disconnect(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    delete_account(user_id, "google")
    return {"ok": True, "message": "Đã disconnect Gmail", "provider": "google"}


@router.delete("/oauth/outlook")
def oauth_outlook_disconnect(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    delete_account(user_id, "outlook")
    return {"ok": True, "message": "Đã disconnect Outlook", "provider": "outlook"}


@router.post("/watch")
def watch_now(
    user_id: Optional[str] = None,
    provider: Optional[str] = Query(None, description="google | outlook"),
):
    state = {}
    if provider:
        state["email_provider"] = provider
    return run_email_watch(user_id or settings()["default_user_id"], state=state)


@router.get("/notifications")
def notifications(
    user_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    since_id: Optional[int] = Query(None, description="Chỉ lấy id > since_id (desktop poll)"),
):
    """Desktop app poll: ?unread_only=true hoặc ?since_id=N."""
    user_id = user_id or settings()["default_user_id"]
    rows = list_notifications(
        user_id,
        limit=limit,
        unread_only=unread_only,
        since_id=since_id,
    )
    for r in rows:
        if r.get("created_at"):
            r["created_at"] = str(r["created_at"])
        if r.get("read_at"):
            r["read_at"] = str(r["read_at"])
    return {"items": rows, "user_id": user_id}


@router.post("/notifications/{notification_id}/read")
def notification_read(notification_id: int, user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    row = mark_read(notification_id, user_id)
    if not row:
        raise HTTPException(404, "Notification không tồn tại")
    if row.get("created_at"):
        row["created_at"] = str(row["created_at"])
    if row.get("read_at"):
        row["read_at"] = str(row["read_at"])
    return {"ok": True, "item": row}


@router.post("/notifications/read-all")
def notifications_read_all(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    n = mark_all_read(user_id)
    return {"ok": True, "marked": n, "user_id": user_id}
