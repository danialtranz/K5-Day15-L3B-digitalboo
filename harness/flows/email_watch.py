"""Flow A: quét Gmail hoặc Outlook → lọc quan trọng → LLM tổng hợp từ tool result."""
from __future__ import annotations

from typing import Any, Optional

from harness.channels import notify as notify_mod
from harness.channels.email.google_gmail import GmailProvider, strip_html
from harness.channels.email.outlook_msgraph import OutlookProvider
from harness.channels.email.resolve import resolve_email_provider
from harness.channels.email.token_store import get_valid_access_token
from harness.config import load_yaml, settings
from harness.hitl.slots import build_gmail_query, build_outlook_query, compose_email_watch_reply
from harness.jobs.store import mark_mail_seen


def _is_important(subject: str, body: str, from_addr: str, rules: dict) -> tuple[bool, str]:
    # Bỏ qua mail báo cáo cron do chính digitalboo gửi (tránh vòng lặp tự thông báo)
    subj = (subject or "").strip().lower()
    if subj.startswith("[digitalboo]") or subj.startswith("digitalboo"):
        return False, ""
    if "thông báo tự động từ digitalboo" in (body or "").lower():
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


def _provider_label(provider: str) -> str:
    return "Outlook" if provider == "outlook" else "Gmail"


def _fetch_messages(
    provider: str,
    token: str,
    state: dict[str, Any],
    *,
    query: Optional[str] = None,
    limit: int = 20,
) -> tuple[list[Any], str]:
    """Trả (messages, query_label)."""
    if provider == "outlook":
        oq = build_outlook_query(state)
        q = (query or "").strip() or (oq.get("search") or "") or "(outlook filter)"
        messages = OutlookProvider().list_messages(
            token,
            limit=limit,
            search=oq.get("search"),
            unread_only=bool(oq.get("unread_only", True)),
            newer_than_days=int(oq.get("newer_than_days") or 7),
            after_date=oq.get("after_date"),
            before_date=oq.get("before_date"),
        )
        return messages, q

    q = (query or "").strip() or build_gmail_query(state)
    messages = GmailProvider().list_messages(token, limit=limit, query=q)
    return messages, q


def _rows_from_messages(
    messages: list[Any],
    *,
    user_id: str,
    provider: str,
    rules: dict[str, Any],
    max_body: int,
    label: str,
    source: str,
    query: str,
    notify_new_important: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, int]:
    """Trả (digest, important_items, important_count, already_seen_count)."""
    important = 0
    already_seen = 0
    items: list[dict[str, Any]] = []
    digest: list[dict[str, Any]] = []

    for m in messages:
        first_time = mark_mail_seen(user_id, m.id, provider)
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
            "provider": provider,
        }
        digest.append(row)
        if not ok:
            continue
        important += 1
        items.append(row)
        if notify_new_important and first_time:
            notify_mod.push(
                user_id,
                "email_important",
                f"Mail quan trọng: {m.subject}",
                f"[{label}] Từ: {m.from_addr}\nLý do: {reason}\n\n{snippet[:500]}",
                {**row, "source": source, "query": query},
            )
    return digest, items, important, already_seen


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
    provider = resolve_email_provider(user_id, state)
    if not provider:
        pref = (state.get("email_provider") or "").strip().lower()
        if pref in ("outlook", "microsoft", "hotmail", "live"):
            msg = "Chưa connect Outlook OAuth. Mở GET /email/oauth/outlook/start"
            label = "Outlook"
        elif pref in ("google", "gmail"):
            msg = "Chưa connect Gmail OAuth. Mở GET /email/oauth/google/start"
            label = "Gmail"
        else:
            msg = "Chưa connect email. Kết nối Gmail hoặc Outlook trên giao diện."
            label = "Email"
        notify_mod.push(user_id, "email_need_connect", f"Cần connect {label}", msg)
        return {"ok": False, "error": "not_connected", "message": msg, "provider": pref or None}

    token = get_valid_access_token(user_id, provider)
    if not token:
        label = _provider_label(provider)
        msg = f"Token {label} hết hạn / thiếu refresh. Hãy reconnect."
        notify_mod.push(user_id, "email_need_connect", f"Cần reconnect {label}", msg)
        return {"ok": False, "error": "not_connected", "message": msg, "provider": provider}

    rules = load_yaml("email_rules.yaml")
    limit = int(rules.get("max_messages_per_watch") or 20)
    max_body = int(rules.get("max_body_chars") or 2000)
    topic = (state.get("topic") or "").strip() or None
    has_topic_search = bool(topic or (state.get("search_query") or "").strip())
    label = _provider_label(provider)

    try:
        messages, q = _fetch_messages(
            provider, token, state, query=query, limit=limit
        )
    except Exception as e:
        err = str(e)
        hint = ""
        if provider == "outlook":
            if "401" in err or "Unauthorized" in err:
                hint = " Thử reconnect Outlook (token/scope)."
            elif "403" in err or "Forbidden" in err:
                hint = (
                    " Kiểm tra Azure app đã cấp Mail.Read và admin consent nếu cần."
                )
            api_err = "outlook_api"
        else:
            if "403" in err or "Forbidden" in err:
                hint = (
                    " Thường do chưa Enable Gmail API trên Google Cloud "
                    "(APIs & Services → Library → Gmail API), hoặc OAuth consent thiếu scope."
                )
            api_err = "gmail_api"
        raw = {
            "ok": False,
            "error": api_err,
            "message": f"Không đọc được {label}: {err}.{hint}",
            "query": (query or "").strip() or "",
            "provider": provider,
        }
        composed = compose_email_watch_reply(
            tool_result=raw,
            user_text=user_text,
            history_text=history_text,
            topic=topic,
        )
        msg = composed.get("text") or raw["message"]
        notify_mod.push(user_id, "email_watch_error", f"Lỗi đọc {label}", msg)
        return {
            **raw,
            "message": msg,
            "topic": topic,
            "_tokens_in": composed.get("_tokens_in"),
            "_tokens_out": composed.get("_tokens_out"),
        }

    digest, items, important, already_seen = _rows_from_messages(
        messages,
        user_id=user_id,
        provider=provider,
        rules=rules,
        max_body=max_body,
        label=label,
        source=source,
        query=q,
        notify_new_important=True,
    )

    # Hỏi chủ đề cụ thể (IELTS…) mà query hẹp trả 0/ít thư → quét thêm hộp thư cùng khung ngày
    # (bỏ search_query) để LLM vẫn kể được vài thư thật đang có.
    recent_digest: list[dict[str, Any]] = []
    recent_query = ""
    if has_topic_search:
        broad_state = {
            **state,
            "search_query": None,
            "include_read": True,
        }
        try:
            recent_msgs, recent_query = _fetch_messages(
                provider, token, broad_state, query=None, limit=limit
            )
            recent_digest, recent_items, recent_imp, _ = _rows_from_messages(
                recent_msgs,
                user_id=user_id,
                provider=provider,
                rules=rules,
                max_body=max_body,
                label=label,
                source=source,
                query=recent_query,
                # Chỉ toast important từ lần quét chủ đề; tránh spam khi quét ngữ cảnh
                notify_new_important=False,
            )
            # Gộp important từ recent nếu topic-match trống
            if not items and recent_items:
                items = recent_items
                important = recent_imp
        except Exception as e:
            print(f"[email_watch] recent inbox fallback failed: {e}")

    tool_result = {
        "ok": True,
        "provider": provider,
        "query": q,
        "recent_query": recent_query or None,
        "important": important,
        "scanned": len(messages),
        "recent_scanned": len(recent_digest) if recent_digest else None,
        "already_seen": already_seen,
        "digest": digest,
        "recent_digest": recent_digest,
        "topic": topic,
        "topic_match_count": len(digest),
    }
    composed = compose_email_watch_reply(
        tool_result=tool_result,
        user_text=user_text,
        history_text=history_text,
        topic=topic,
    )
    message = composed.get("text") or ""

    summary_meta = {
        "provider": provider,
        "query": q,
        "topic": topic,
        "important": important,
        "scanned": len(messages),
        "already_seen": already_seen,
        "items": items,
        "digest": digest,
        "recent_digest": recent_digest,
        "source": source,
    }
    # Toast tóm tắt chỉ khi user chủ động hỏi. Background/lịch: không spam summary
    user_initiated = source in ("ask_now", "ask", "chat", "manual")
    if user_initiated:
        shown = len(messages) if messages else len(recent_digest)
        notify_mod.push(
            user_id,
            "email_watch_summary",
            f"Kiểm tra {label}: {shown} thư · {important} quan trọng",
            message,
            summary_meta,
        )

    return {
        "ok": True,
        "provider": provider,
        "scanned": len(messages),
        "important": important,
        "already_seen": already_seen,
        "query": q,
        "topic": topic,
        "items": items,
        "digest": digest,
        "recent_digest": recent_digest,
        "source": source,
        "message": message,
        "_tokens_in": composed.get("_tokens_in"),
        "_tokens_out": composed.get("_tokens_out"),
    }
