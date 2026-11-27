"""Gửi báo cáo kết quả cronjob về Gmail của user (thành công / thất bại)."""
from __future__ import annotations

import html
import re
from typing import Any

from harness.channels.email.google_gmail import GmailProvider
from harness.channels.email.outlook_msgraph import OutlookProvider
from harness.channels.email.token_store import get_account, get_valid_access_token


def _job_label(job_type: str | None) -> str:
    return {
        "email_watch": "Đọc email",
        "standup_fill": "Điền standup",
        "standup_content_timeout": "Hết hạn chờ standup",
    }.get(str(job_type or ""), str(job_type or "Job"))


def _source_label(source: str) -> str:
    return {
        "scheduler": "Lịch tự động",
        "manual_run_now": "Chạy thử ngay",
        "scheduled_email_watch": "Lịch đọc email",
    }.get(source, source or "Hệ thống")


def _strip_md(text: str) -> str:
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", text or "")
    t = re.sub(r"`([^`]+)`", r"\1", t)
    return t.strip()


def _md_to_html_inline(text: str) -> str:
    esc = html.escape(text or "")
    esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
    esc = re.sub(r"`([^`]+)`", r"<code style=\"font-size:13px;background:#f3f4f6;padding:1px 5px;border-radius:4px;\">\1</code>", esc)
    return esc.replace("\n", "<br>")


def build_job_report(
    *,
    job_type: str | None,
    job_id: str | None,
    ok: bool,
    result: Any = None,
    error: str | None = None,
    source: str = "scheduler",
) -> tuple[str, str, str]:
    """Trả (subject, body_text, body_html)."""
    label = _job_label(job_type)
    src = _source_label(source)
    awaiting = isinstance(result, dict) and bool(
        result.get("awaiting_content")
        or result.get("need_hitl")
        or result.get("need_login")
    )

    if awaiting:
        status_key = "awaiting"
        status = "Đang chờ bạn trong chat"
        subject = f"digitalboo · {label}: cần trả lời trong chat"
        badge_bg, badge_fg = "#ecfdf5", "#0f766e"
        headline = "Cần bạn trả lời trong chat"
        lead = (
            "Đã mở một phiên chat mới trên digitalboo. "
            "Mở app/web và trả lời trực tiếp trong chat đó để mình tiếp tục."
        )
    elif ok:
        status_key = "ok"
        status = "Thành công"
        subject = f"digitalboo · {label}: thành công"
        badge_bg, badge_fg = "#ecfdf5", "#047857"
        headline = f"{label} hoàn tất"
        lead = "Cronjob đã chạy xong ổn."
    else:
        status_key = "fail"
        status = "Thất bại"
        subject = f"digitalboo · {label}: thất bại"
        badge_bg, badge_fg = "#fef2f2", "#b91c1c"
        headline = f"{label} chưa hoàn tất"
        lead = "Có lỗi khi chạy cronjob — xem chi tiết bên dưới."

    detail_msg = ""
    extras: list[str] = []
    if error:
        extras.append(f"Lỗi: {error}")

    if isinstance(result, dict):
        detail_msg = str(result.get("message") or result.get("error") or "").strip()
        if job_type == "email_watch":
            topic = result.get("topic")
            scanned = result.get("scanned")
            important = result.get("important")
            if topic:
                extras.append(f"Chủ đề: {topic}")
            if scanned is not None:
                extras.append(f"Đã quét {scanned} thư · {important or 0} tin đáng chú ý")
        if job_type == "standup_fill" and result.get("need_login"):
            extras.append("Cần đăng nhập portal trên cửa sổ trình duyệt digitalboo đang mở.")
        detail = result.get("detail") if isinstance(result.get("detail"), dict) else None
        if detail and detail.get("message"):
            dmsg = str(detail.get("message")).strip()
            if dmsg and dmsg != detail_msg:
                extras.append(dmsg)
    elif result is not None:
        detail_msg = str(result)

    # —— plain text ——
    text_lines = [
        "digitalboo",
        "",
        headline,
        f"Trạng thái: {status}",
        f"Việc: {label}",
        f"Nguồn: {src}",
        "",
        lead,
    ]
    if detail_msg:
        text_lines.extend(["", _strip_md(detail_msg)])
    for ex in extras:
        text_lines.append(_strip_md(ex))
    text_lines.extend(["", "—", "digitalboo · thông báo cronjob"])
    body_text = "\n".join(text_lines).strip() + "\n"

    # —— HTML ——
    detail_html = ""
    if detail_msg:
        detail_html = f"""
        <div style="margin:20px 0 0;padding:14px 16px;background:#f8fafc;border-radius:12px;border:1px solid #e2e8f0;">
          <div style="font-size:12px;font-weight:600;letter-spacing:0.04em;text-transform:uppercase;color:#64748b;margin-bottom:8px;">Chi tiết</div>
          <div style="font-size:15px;line-height:1.55;color:#0f172a;">{_md_to_html_inline(detail_msg)}</div>
        </div>"""
    extras_html = ""
    if extras:
        items = "".join(
            f'<li style="margin:0 0 6px;">{html.escape(_strip_md(x))}</li>' for x in extras
        )
        extras_html = f'<ul style="margin:16px 0 0;padding-left:18px;color:#334155;font-size:14px;line-height:1.5;">{items}</ul>'

    meta_bits = [f"Việc: {html.escape(label)}", f"Nguồn: {html.escape(src)}"]
    if status_key != "awaiting" and job_id:
        meta_bits.append(f"Mã job: {html.escape(str(job_id)[:48])}…")
    meta_html = " · ".join(meta_bits)

    body_html = f"""<!DOCTYPE html>
<html lang="vi">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f1f5f9;padding:28px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;">
        <tr>
          <td style="padding:18px 22px;background:linear-gradient(135deg,#134e4a 0%,#0f766e 55%,#14b8a6 100%);">
            <div style="font-size:13px;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;color:rgba(255,255,255,0.85);">digitalboo</div>
            <div style="margin-top:6px;font-size:20px;font-weight:700;color:#ffffff;line-height:1.3;">{html.escape(headline)}</div>
          </td>
        </tr>
        <tr>
          <td style="padding:22px;">
            <span style="display:inline-block;padding:5px 10px;border-radius:999px;background:{badge_bg};color:{badge_fg};font-size:12px;font-weight:700;">{html.escape(status)}</span>
            <p style="margin:16px 0 0;font-size:15px;line-height:1.6;color:#334155;">{html.escape(lead)}</p>
            {detail_html}
            {extras_html}
            <p style="margin:22px 0 0;font-size:12px;line-height:1.5;color:#94a3b8;">{meta_html}</p>
          </td>
        </tr>
      </table>
      <p style="margin:14px 0 0;font-size:11px;color:#94a3b8;">Thông báo tự động từ digitalboo harness</p>
    </td></tr>
  </table>
</body>
</html>"""
    return subject, body_text, body_html


def send_job_result_email(
    user_id: str,
    *,
    job_type: str | None,
    job_id: str | None = None,
    ok: bool,
    result: Any = None,
    error: str | None = None,
    source: str = "scheduler",
) -> dict[str, Any]:
    """
    Gửi mail báo cáo về hộp thư đã OAuth (ưu tiên Gmail, fallback Outlook).
    Không ném exception ra ngoài — trả {ok, ...} để caller log.
    """
    provider = "google"
    account = get_account(user_id, "google")
    if not account:
        provider = "outlook"
        account = get_account(user_id, "outlook")
    if not account:
        return {"ok": False, "error": "email_not_connected"}
    to = (account.get("email_address") or "").strip()
    if not to:
        return {"ok": False, "error": "missing_email_address"}

    token = get_valid_access_token(user_id, provider)
    if not token:
        return {"ok": False, "error": "no_access_token"}

    subject, body_text, body_html = build_job_report(
        job_type=job_type,
        job_id=job_id,
        ok=ok,
        result=result,
        error=error,
        source=source,
    )
    try:
        if provider == "outlook":
            sent = OutlookProvider().send_message(
                token,
                to=to,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_addr=to,
            )
            message_id = sent.get("id") or sent.get("status_code")
        else:
            sent = GmailProvider().send_message(
                token,
                to=to,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                from_addr=to,
            )
            message_id = sent.get("id")
        return {
            "ok": True,
            "provider": provider,
            "to": to,
            "subject": subject,
            "message_id": message_id,
        }
    except Exception as e:
        err = str(e)
        hint = None
        if "403" in err or "insufficient" in err.lower() or "Insufficient Permission" in err:
            hint = (
                "Cần reconnect Outlook (Mail.Send)."
                if provider == "outlook"
                else "Cần reconnect Gmail để cấp quyền gmail.send."
            )
        print(f"[email-report] send failed for {user_id}: {err}" + (f" ({hint})" if hint else ""))
        return {
            "ok": False,
            "error": err,
            "hint": hint,
            "to": to,
            "subject": subject,
            "provider": provider,
        }
