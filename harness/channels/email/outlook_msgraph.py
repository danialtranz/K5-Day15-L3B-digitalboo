"""Outlook / Microsoft Graph OAuth + Mail.Read (readonly + optional send)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from harness.channels.email.base import EmailMessage, TokenBundle
from harness.config import settings

MS_AUTH = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
GRAPH = "https://graph.microsoft.com/v1.0"
# offline_access → refresh_token; Mail.Read / Mail.Send / User.Read
SCOPE = "offline_access User.Read Mail.Read Mail.Send"


class OutlookProvider:
    name = "outlook"

    def connect_url(self, state: str, redirect_uri: str) -> str:
        s = settings()
        params = {
            "client_id": s["microsoft_client_id"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "response_mode": "query",
            "scope": SCOPE,
            "state": state,
            "prompt": "select_account",
        }
        return f"{MS_AUTH}?{urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle:
        s = settings()
        data = {
            "code": code,
            "client_id": s["microsoft_client_id"],
            "client_secret": s["microsoft_client_secret"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "scope": SCOPE,
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(MS_TOKEN, data=data)
            r.raise_for_status()
            payload = r.json()
        return self._to_bundle(payload)

    def refresh(self, refresh_token: str) -> TokenBundle:
        s = settings()
        data = {
            "client_id": s["microsoft_client_id"],
            "client_secret": s["microsoft_client_secret"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
            "scope": SCOPE,
        }
        with httpx.Client(timeout=30) as client:
            r = client.post(MS_TOKEN, data=data)
            r.raise_for_status()
            payload = r.json()
        bundle = self._to_bundle(payload)
        if not bundle.refresh_token:
            bundle.refresh_token = refresh_token
        return bundle

    def fetch_profile_email(self, access_token: str) -> Optional[str]:
        with httpx.Client(timeout=30) as client:
            r = client.get(
                f"{GRAPH}/me",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"$select": "mail,userPrincipalName,displayName"},
            )
            if r.status_code != 200:
                return None
            data = r.json()
            return (data.get("mail") or data.get("userPrincipalName") or None)

    def list_messages(
        self,
        access_token: str,
        limit: int = 20,
        *,
        search: str | None = None,
        unread_only: bool = True,
        newer_than_days: int = 7,
        after_date: str | None = None,
        before_date: str | None = None,
    ) -> list[EmailMessage]:
        """Đọc inbox qua Graph. search → $search; không thì $filter unread/ngày."""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Prefer": 'outlook.body-content-type="text"',
        }
        params: dict[str, Any] = {
            "$top": max(1, min(int(limit or 20), 50)),
            "$select": "id,conversationId,subject,from,receivedDateTime,bodyPreview,body,isRead",
        }
        q_search = (search or "").strip()
        if q_search:
            # $search không kết hợp tốt với $filter/$orderby
            params["$search"] = f'"{q_search}"'
            headers["ConsistencyLevel"] = "eventual"
        else:
            filters: list[str] = []
            if unread_only:
                filters.append("isRead eq false")
            since = _since_iso(after_date=after_date, newer_than_days=newer_than_days)
            if since:
                filters.append(f"receivedDateTime ge {since}")
            until = _date_end_iso(before_date)
            if until:
                filters.append(f"receivedDateTime lt {until}")
            if filters:
                params["$filter"] = " and ".join(filters)
            params["$orderby"] = "receivedDateTime desc"

        with httpx.Client(timeout=60) as client:
            r = client.get(f"{GRAPH}/me/messages", headers=headers, params=params)
            r.raise_for_status()
            rows = r.json().get("value") or []
        return [self._parse_message(m) for m in rows]

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
        """Gửi mail qua Graph sendMail. Cần Mail.Send."""
        to = (to or "").strip()
        if not to:
            raise ValueError("missing_to")
        content_type = "HTML" if body_html else "Text"
        content = body_html if body_html else (body_text or "")
        payload: dict[str, Any] = {
            "message": {
                "subject": subject or "(no subject)",
                "body": {"contentType": content_type, "content": content},
                "toRecipients": [{"emailAddress": {"address": to}}],
            },
            "saveToSentItems": True,
        }
        if from_addr:
            payload["message"]["from"] = {"emailAddress": {"address": from_addr}}
        headers = {"Authorization": f"Bearer {access_token}"}
        with httpx.Client(timeout=30) as client:
            r = client.post(f"{GRAPH}/me/sendMail", headers=headers, json=payload)
            r.raise_for_status()
            # sendMail trả 202 + empty body
            return {"status_code": r.status_code, "to": to}

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
        from_obj = ((raw.get("from") or {}).get("emailAddress") or {})
        from_addr = from_obj.get("address") or ""
        name = from_obj.get("name") or ""
        if name and from_addr:
            from_line = f"{name} <{from_addr}>"
        else:
            from_line = from_addr or name
        body_obj = raw.get("body") or {}
        body = (body_obj.get("content") or raw.get("bodyPreview") or "").strip()
        return EmailMessage(
            id=raw.get("id") or "",
            thread_id=raw.get("conversationId"),
            subject=raw.get("subject") or "(no subject)",
            from_addr=from_line,
            date=raw.get("receivedDateTime"),
            snippet=(raw.get("bodyPreview") or "")[:300],
            body=body,
        )


def _since_iso(*, after_date: str | None, newer_than_days: int) -> str | None:
    if after_date:
        try:
            d = datetime.strptime(after_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return d.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            pass
    days = max(1, int(newer_than_days or 7))
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return since.strftime("%Y-%m-%dT%H:%M:%SZ")


def _date_end_iso(before_date: str | None) -> str | None:
    if not before_date:
        return None
    try:
        d = datetime.strptime(before_date[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # before_date là exclusive end-of-day kế tiếp cho gọn
        d = d + timedelta(days=1)
        return d.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
