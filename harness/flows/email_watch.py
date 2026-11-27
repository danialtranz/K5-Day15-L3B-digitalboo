"""Flow A: quét Gmail → lọc quan trọng → LLM tổng hợp câu trả lời từ tool result."""
from __future__ import annotations

from typing import Any, Optional

from harness.channels import notify as notify_mod
from harness.channels.email.google_gmail import GmailProvider, strip_html
from harness.channels.email.token_store import get_valid_access_token
from harness.config import load_yaml, settings
from harness.hitl.slots import build_gmail_query, compose_email_watch_reply
from harness.jobs.store import mark_mail_seen


def _is_important(subject: str, body: str, from_addr: str, rules: dict) -> tuple[bool, str]:
    # Bỏ qua mail báo cáo cron do chính digitalboo gửi (tránh tự báo "quan trọng")
    subj = (subject or "").strip()
    if subj.lower().startswith("[digitalboo]"):
        return False, ""
    text = f"{subject}\n{body}\n{from_addr}".lower()
    for kw in rules.get("important_keywords") or []:
        if kw.lower() in text:
            return True, f"keyword:{kw}"
    for dom in rules.get("from_domains_boost") or []:
        if dom.lower() in from_addr.lower():
            return True, f"from_domain:{dom}"
    return False, ""


def _short(text: str, n: int = 72) -> str:
    t = " ".join((text or "").split())
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def run_email_watch(
    user_id: str | None = None,
    *,
    query: Optional[str] = None,
    state: Optional[dict[str, Any]] = None,
    source: str = "manual",
    user_text: str = "",
    history_text: str = "",
) -> dict[str, Any]:
    user_id = user_id or settings()["default_user_id"]
    state = state or {}
    token = get_valid_access_token(user_id, "google")
    if not token:
        msg = "Chưa connect Gmail OAuth. Mở GET /email/oauth/google/start"
        notify_mod.push(user_id, "email_need_connect", "Cần connect Gmail", msg)
        return {"ok": False, "error": "not_connected", "message": msg}

    rules = load_yaml("email_rules.yaml")
    limit = int(rules.get("max_messages_per_watch") or 20)
    max_body = int(rules.get("max_body_chars") or 2000)
    q = (query or "").strip() or build_gmail_query(state)
    topic = (state.get("topic") or "").strip() or None
    provider = GmailProvider()
    try:
        messages = provider.list_messages(token, limit=limit, query=q)
    except Exception as e:
        err = str(e)
        hint = ""
        if "403" in err or "Forbidden" in err:
            hint = (
                " Thường do chưa Enable Gmail API trên Google Cloud "
                "(APIs & Services → Library → Gmail API), hoặc OAuth consent thiếu scope."
            )
        raw = {"ok": False, "error": "gmail_api", "message": f"Không đọc được Gmail: {err}.{hint}", "query": q}
        composed = compose_email_watch_reply(
            tool_result=raw,
            user_text=user_text,
            history_text=history_text,
            topic=topic,
        )
        msg = composed.get("text") or raw["message"]
        notify_mod.push(user_id, "email_watch_error", "Lỗi đọc Gmail", msg)
        return {
            **raw,
            "message": msg,
            "topic": topic,
            "_tokens_in": composed.get("_tokens_in"),
            "_tokens_out": composed.get("_tokens_out"),
        }

    important = 0
    already_seen = 0
    items: list[dict[str, Any]] = []
    digest: list[dict[str, Any]] = []

    for m in messages:
        first_time = mark_mail_seen(user_id, m.id, "google")
        if not first_time:
            already_seen += 1
        body = strip_html(m.body)[:max_body]
        ok, reason = _is_important(m.subject, body, m.from_addr, rules)
        snippet = (m.snippet or body[:300] or "").strip()
        row = {
            "message_id": m.id,
            "subject": m.subject,
            "from": m.from_addr,
            "date": m.date,
            "snippet": _short(snippet, 160),
            "important": ok,
            "reason": reason or None,
            "already_seen": not first_time,
        }
        digest.append(row)

        if not ok:
            continue
        important += 1
        items.append(row)
        # Chỉ toast riêng lần đầu thấy mail quan trọng
        if first_time:
            notify_mod.push(
                user_id,
                "email_important",
                f"Mail quan trọng: {m.subject}",
                f"Từ: {m.from_addr}\nLý do: {reason}\n\n{snippet[:500]}",
                {**row, "source": source, "query": q},
            )

    tool_result = {
        "ok": True,
        "query": q,
        "important": important,
        "scanned": len(messages),
        "already_seen": already_seen,
        "digest": digest,
        "topic": topic,
    }
    composed = compose_email_watch_reply(
        tool_result=tool_result,
        user_text=user_text,
        history_text=history_text,
        topic=topic,
    )
    message = composed.get("text") or ""

    summary_meta = {
        "query": q,
        "topic": topic,
        "important": important,
        "scanned": len(messages),
        "already_seen": already_seen,
        "items": items,
        "digest": digest,
        "source": source,
    }
    notify_mod.push(
        user_id,
        "email_watch_summary",
        f"Kiểm tra email: {len(messages)} thư · {important} quan trọng",
        message,
        summary_meta,
    )

    return {
        "ok": True,
        "scanned": len(messages),
        "important": important,
        "already_seen": already_seen,
        "query": q,
        "topic": topic,
        "items": items,
        "digest": digest,
        "source": source,
        "message": message,
        "_tokens_in": composed.get("_tokens_in"),
        "_tokens_out": composed.get("_tokens_out"),
    }
