"""Hợp đồng EmailProvider — Gmail + Outlook (Microsoft Graph)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: Optional[str]
    expires_at: Optional[datetime]
    scopes: Optional[str]
    email_address: Optional[str] = None


@dataclass
class EmailMessage:
    id: str
    thread_id: Optional[str]
    subject: str
    from_addr: str
    date: Optional[str]
    snippet: str
    body: str


class EmailProvider(Protocol):
    name: str

    def connect_url(self, state: str, redirect_uri: str) -> str: ...

    def exchange_code(self, code: str, redirect_uri: str) -> TokenBundle: ...

    def refresh(self, refresh_token: str) -> TokenBundle: ...

    def list_messages(self, access_token: str, limit: int = 20) -> list[EmailMessage]: ...
