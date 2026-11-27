"""Flow A: quét Gmail unread → lọc quan trọng → notify user."""
from __future__ import annotations

from typing import Any

from harness.channels import notify as notify_mod
from harness.channels.email.google_gmail import GmailProvider, strip_html
from harness.channels.email.token_store import get_valid_access_token
from harness.config import load_yaml, settings
from harness.jobs.store import mark_mail_seen


def _is_important(subject: str, body: str, from_addr: str, rules: dict) -> tuple[bool, str]:
    text = f"{subject}\n{body}\n{from_addr}".lower()
    for kw in rules.get("important_keywords") or []:
        if kw.lower() in text:
            return True, f"keyword:{kw}"
    for dom in rules.get("from_domains_boost") or []:
        if dom.lower() in from_addr.lower():
            return True, f"from_domain:{dom}"
    return False, ""


def run_email_watch(user_id: str | None = None) -> dict[str, Any]:
    user_id = user_id or settings()["default_user_id"]
    token = get_valid_access_token(user_id, "google")
    if not token:
        msg = "Chưa connect Gmail OAuth. Mở GET /email/oauth/google/start"
        notify_mod.push(user_id, "email_need_connect", "Cần connect Gmail", msg)
        return {"ok": False, "error": "not_connected", "message": msg}

    rules = load_yaml("email_rules.yaml")
    limit = int(rules.get("max_messages_per_watch") or 20)
    max_body = int(rules.get("max_body_chars") or 2000)
    provider = GmailProvider()
    messages = provider.list_messages(token, limit=limit)

    important = 0
    skipped = 0
    for m in messages:
        if not mark_mail_seen(user_id, m.id, "google"):
            skipped += 1
            continue
        body = strip_html(m.body)[:max_body]
        ok, reason = _is_important(m.subject, body, m.from_addr, rules)
        if not ok:
            continue
        important += 1
        notify_mod.push(
            user_id,
            "email_important",
            f"Mail quan trọng: {m.subject}",
            f"Từ: {m.from_addr}\nLý do: {reason}\n\n{m.snippet or body[:500]}",
            {"message_id": m.id, "reason": reason, "from": m.from_addr},
        )

    return {
        "ok": True,
        "scanned": len(messages),
        "important": important,
        "already_seen": skipped,
        "message": f"Quét {len(messages)} mail, báo {important} tin quan trọng.",
    }
