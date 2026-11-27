"""Gmail OAuth + watch + notifications."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from harness.channels.email.google_gmail import GmailProvider
from harness.channels.email.oauth import build_google_oauth_start, redirect_uri
from harness.channels.email.token_store import delete_account, get_account, upsert_account
from harness.channels.notify import list_notifications, mark_all_read, mark_read
from harness.config import settings
from harness.db.auth import append_chat
from harness.db.redis_client import pop_oauth_state
from harness.flows.email_watch import run_email_watch
from harness.orchestrator import resume_email_after_oauth

router = APIRouter(prefix="/email", tags=["email"])


@router.get("/oauth/google/start")
def oauth_start(
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
                "oauth_url": start["oauth_url"],
                "user_id": user_id,
                "session_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        )
    return RedirectResponse(start["oauth_url"])


@router.get("/oauth/google/callback")
def oauth_callback(
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
    bundle = provider.exchange_code(code, redirect_uri())
    email = provider.fetch_profile_email(bundle.access_token)
    bundle.email_address = email
    upsert_account(user_id, "google", bundle)

    # Grant đã OK — quét mail có thể fail (vd Gmail API chưa bật) nhưng không được 500 popup
    resume: dict = {
        "ok": True,
        "flow": "email_oauth",
        "message": f"Đã kết nối Gmail ({email or 'ok'}).",
        "granted": True,
    }
    try:
        resume = resume_email_after_oauth(
            user_id=user_id,
            session_id=session_id,
            checkpoint_id=checkpoint_id,
        )
        resume["granted"] = True
    except Exception as e:
        resume = {
            "ok": False,
            "flow": "email_oauth",
            "granted": True,
            "error": "watch_after_oauth_failed",
            "message": (
                f"Đã kết nối Gmail ({email or 'ok'}) nhưng chưa đọc được hộp thư: {e}. "
                "Hãy bật Gmail API trên Google Cloud (APIs & Services → Library → Gmail API → Enable), "
                "rồi nhắn lại trong chat để quét mail."
            ),
        }

    # Ghi vào chat history nếu có session
    if session_id:
        try:
            append_chat(
                session_id,
                user_id,
                "assistant",
                resume.get("message") or "Đã connect Gmail và quét mail.",
                flow=resume.get("flow") or "email_watch",
                meta={
                    "ok": resume.get("ok"),
                    "granted": resume.get("granted"),
                    "resumed_from_oauth": True,
                    "important": resume.get("important"),
                },
            )
        except Exception:
            pass

    resume_js = json.dumps(resume, ensure_ascii=False, default=str)
    msg = resume.get("message") or "Gmail connected."
    important = resume.get("important")
    title = "Gmail đã kết nối" if resume.get("granted") else "Gmail"
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
      payload.type = "gmail_oauth_done";
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
