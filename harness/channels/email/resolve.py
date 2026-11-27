"""Chọn provider email (google | outlook) theo slot + tài khoản đã OAuth."""
from __future__ import annotations

from typing import Any, Optional

from harness.channels.email.token_store import get_account

PROVIDER_ALIASES = {
    "google": "google",
    "gmail": "google",
    "outlook": "outlook",
    "microsoft": "outlook",
    "hotmail": "outlook",
    "live": "outlook",
    "office365": "outlook",
    "o365": "outlook",
}


def normalize_provider(value: Any) -> Optional[str]:
    if value is None:
        return None
    key = str(value).strip().lower()
    if not key:
        return None
    return PROVIDER_ALIASES.get(key)


def has_email_grant(user_id: str, state: dict[str, Any] | None = None) -> bool:
    state = state or {}
    pref = normalize_provider(state.get("email_provider"))
    if pref == "google":
        return bool(get_account(user_id, "google"))
    if pref == "outlook":
        return bool(get_account(user_id, "outlook"))
    return bool(get_account(user_id, "google") or get_account(user_id, "outlook"))


def resolve_email_provider(
    user_id: str,
    state: dict[str, Any] | None = None,
) -> Optional[str]:
    """Trả 'google' | 'outlook' | None (chưa connect đúng provider)."""
    state = state or {}
    pref = normalize_provider(state.get("email_provider"))
    google = get_account(user_id, "google")
    outlook = get_account(user_id, "outlook")
    if pref == "google":
        return "google" if google else None
    if pref == "outlook":
        return "outlook" if outlook else None
    if google:
        return "google"
    if outlook:
        return "outlook"
    return None


def connected_providers(user_id: str) -> list[str]:
    out: list[str] = []
    if get_account(user_id, "google"):
        out.append("google")
    if get_account(user_id, "outlook"):
        out.append("outlook")
    return out
