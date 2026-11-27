"""Gmail OAuth + Gmail API readonly."""
from __future__ import annotations

import base64
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from harness.channels.email.base import EmailMessage, TokenBundle
from harness.config import settings

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
SCOPE = (
    "https://www.googleapis.com/auth/gmail.readonly "
    "https://www.googleapis.com/auth/gmail.send "
    "https://www.googleapis.com/auth/userinfo.email"
)


class GmailProvider:
    name = "google"

    def connect_url(self, state: str, redirect_uri: str) -> str:
        s = settings()
        params = {
            "client_id": s["google_client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
            "include_granted_scopes": "true",
        }
        return f"{GOOGLE_AUTH}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        s = settings()
        data = {
            "code": code,
            "client_id": s["google_client_id"],
            "client_secret": s["google_client_secret"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(GOOGLE_TOKEN, data=data)
            r.raise_for_status()
            payload = r.json()
        return self._to_bundle(payload)

    def refresh(self, refresh_token: str) -> TokenBundle:
        s = settings()
        data = {
            "client_id": s["google_client_id"],
            "client_secret": s["google_client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(GOOGLE_TOKEN, data=data)
            r.raise_for_status()
            payload = r.json()
        bundle = self._to_bundle(payload)
        if not bundle.refresh_token:
            bundle.refresh_token = refresh_token
        return bundle

    def fetch_profile_email(self, access_token: str) -> Optional[str]:
        with httpx.Client(timeout=30) as client:
            r = client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code != 200:
                return None
            return r.json().get("email")

    def list_messages(
        self,
        access_token: str,
        limit: int = 20,
        query: str | None = None,
    ) -> list[EmailMessage]:
        """query: Gmail search string. Mặc định unread trong 7 ngày."""
        q = (query or "").strip() or "is:unread newer_than:7d"
        headers = {"Authorization": f"Bearer {access_token}"}
        out: list[EmailMessage] = []
        with httpx.Client(timeout=60) as client:
            r = client.get(
                f"{GMAIL_API}/users/me/messages",
                headers=headers,
                params={"maxResults": limit, "q": q},
            )
            r.raise_for_status()
            ids = [m["id"] for m in (r.json().get("messages") or [])]
            for mid in ids:
                mr = client.get(
                    f"{GMAIL_API}/users/me/messages/{mid}",
                    headers=headers,
                    params={"format": "full"},
                )
                mr.raise_for_status()
                out.append(self._parse_message(mr.json()))
        return out

    def send_message(
        self,
        access_token: str,
        *,
        to: str,
        subject: str,
        body_text: str,
        body_html: str | None = None,
        from_addr: str | None = None,
    ) -> dict[str, Any]:
        """Gửi mail qua Gmail API (users.messages.send). Cần scope gmail.send."""
        from email.header import Header
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        to = (to or "").strip()
        if not to:
            raise ValueError("missing_to")
        from_line = (from_addr or "").strip() or to

        if body_html:
            msg: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
            msg.attach(MIMEText(body_text or "", "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))
        else:
            msg = MIMEText(body_text or "", "plain", "utf-8")

        msg["To"] = to
        msg["From"] = from_line
        # RFC 2047 — tránh subject tiếng Việt bị mojibake (Ä iá» n…)
        msg["Subject"] = Header(subject or "(no subject)", "utf-8")

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii").rstrip("=")
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=30) as client:
            r = client.post(
                f"{GMAIL_API}/users/me/messages/send",
                headers=headers,
                json={"raw": raw},
            )
            r.raise_for_status()
            return r.json()

    def _to_bundle(self, payload: dict[str, Any]) -> TokenBundle:
        expires_in = int(payload.get("expires_in") or 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return TokenBundle(
            access_token=payload["access_token"],
            refresh_token=payload.get("refresh_token"),
            expires_at=expires_at,
            scopes=payload.get("scope"),
        )

    def _parse_message(self, raw: dict[str, Any]) -> EmailMessage:
        headers = {h["name"].lower(): h["value"] for h in (raw.get("payload") or {}).get("headers") or []}
        body = self._extract_body(raw.get("payload") or {})
        return EmailMessage(
            id=raw.get("id") or "",
            thread_id=raw.get("threadId"),
            subject=headers.get("subject") or "(no subject)",
            from_addr=headers.get("from") or "",
            date=headers.get("date"),
            snippet=raw.get("snippet") or "",
            body=body or (raw.get("snippet") or ""),
        )

    def _extract_body(self, payload: dict[str, Any]) -> str:
        mime = payload.get("mimeType") or ""
        body = payload.get("body") or {}
        data = body.get("data")
        if data and mime.startswith("text/"):
            return _b64url_decode(data)
        for part in payload.get("parts") or []:
            text = self._extract_body(part)
            if text:
                return text
        return ""


def _b64url_decode(data: str) -> str:
    pad = "=" * (-len(data) % 4)
    raw = base64.urlsafe_b64decode(data + pad)
    return raw.decode("utf-8", errors="replace")


def parse_email_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


_HTML_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    return _HTML_TAG.sub(" ", text)
