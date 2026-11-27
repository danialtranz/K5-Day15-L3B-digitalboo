"""Flow B: grant → notes → Playwright fill + Submit (scripted playbook hoặc vision CU)."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from harness.channels import notify as notify_mod
from harness.computer_use.worker import get_worker
from harness.config import load_yaml, settings
from harness.db.redis_client import acquire_lock, release_lock
from harness.jobs.store import already_done, get_grant, record_job

# Cho phép import tools CP2
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "codebase") not in sys.path:
    sys.path.insert(0, str(ROOT / "codebase"))


def _in_window(now: Optional[datetime] = None) -> bool:
    sched = load_yaml("schedule.yaml").get("standup") or {}
    tz_name = settings()["standup_timezone"]
    now = now or datetime.now(ZoneInfo(tz_name))
    start = sched.get("window_start") or "00:01"
    end = sched.get("window_end") or "09:00"
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    minutes = now.hour * 60 + now.minute
    return (sh * 60 + sm) <= minutes <= (eh * 60 + em)


def _load_fields_from_notes(user_id: str) -> dict[str, str] | None:
    try:
        from tools import get_user_notes  # type: ignore
    except Exception:
        return None
    row = get_user_notes(user_id)
    notes = (row.get("notes") or "").strip()
    if not notes or len(notes) < 20:
        return None
    # Tách thô theo nhãn; fallback gán cả khối vào today
    yesterday, today, blockers = "", "", ""
    low = notes.lower()
    if "hôm qua" in low or "hom qua" in low:
        # heuristic đơn giản: chia dòng
        parts = notes.split("\n")
        bucket = "today"
        chunks: dict[str, list[str]] = {"yesterday": [], "today": [], "blockers": []}
        for line in parts:
            ll = line.lower()
            if "hôm qua" in ll or "hom qua" in ll or "yesterday" in ll:
                bucket = "yesterday"
            elif "hôm nay" in ll or "hom nay" in ll or "today" in ll:
                bucket = "today"
            elif "vướng" in ll or "vuong" in ll or "blocker" in ll:
                bucket = "blockers"
            chunks[bucket].append(line)
        yesterday = "\n".join(chunks["yesterday"]).strip() or notes
        today = "\n".join(chunks["today"]).strip() or notes
        blockers = "\n".join(chunks["blockers"]).strip()
    else:
        yesterday = notes
        today = notes
    return {"yesterday": yesterday, "today": today, "blockers": blockers or "Không"}


def run_standup_submit(
    user_id: str | None = None,
    force: bool = False,
    fields: Optional[dict[str, str]] = None,
    url: Optional[str] = None,
    *,
    resume_browser: bool = False,
    notify: bool = True,
    await_login: bool = False,
) -> dict[str, Any]:
    """
    await_login=True: dùng cho job lịch — nếu cần đăng nhập thì chờ trên cửa sổ
    (kèm toast), không trả HITL chat (vì không có session user đang chat).
    """
    from harness.jobs.store import upsert_grant

    def _toast(kind: str, title: str, body: str, meta: Optional[dict[str, Any]] = None) -> None:
        if notify:
            notify_mod.push(user_id, kind, title, body, meta)

    user_id = user_id or settings()["default_user_id"]
    if url:
        try:
            upsert_grant(user_id, url)
        except PermissionError as e:
            return {"ok": False, "error": "url_not_allowlisted", "message": str(e)}

    grant = get_grant(user_id)
    if not grant and not url:
        msg = "Chưa có grant/URL standup."
        _toast("standup_need_grant", "Cần grant standup", msg)
        return {"ok": False, "error": "no_grant", "message": msg, "need_hitl": True, "missing_fields": ["url"]}

    if not force and not _in_window():
        msg = "Ngoài cửa sổ standup 00:01–09:00 (dùng force=true / schedule để chạy)."
        return {"ok": False, "error": "outside_window", "message": msg}

    if already_done(user_id, "standup_submit"):
        return {"ok": False, "error": "already_done", "message": "Đã nộp standup hôm nay."}

    lock_key = f"lock:standup:{user_id}"
    if not acquire_lock(lock_key, ttl_sec=600):
        return {"ok": False, "error": "locked", "message": "Job standup đang chạy."}

    worker = get_worker()
    try:
        data = fields or _load_fields_from_notes(user_id)
        if not data:
            msg = "Thiếu nội dung standup (hôm qua / hôm nay). Không bịa, không submit."
            _toast("standup_need_notes", "Thiếu notes", msg)
            record_job(user_id, "standup_submit", "skipped", {"reason": "no_notes"})
            return {
                "ok": False,
                "error": "no_notes",
                "message": msg,
                "need_hitl": True,
                "missing_fields": ["yesterday", "today"],
            }

        target = url or (grant["url"] if grant else None) or settings()["standup_allowlist_url"]

        quiet = not notify
        # Resume sau HITL login: dùng session browser đang giữ (nếu còn)
        if resume_browser:
            st = worker.status(user_id)
            if not st.get("open"):
                prep = worker.prepare(user_id, target, quiet=quiet)
                if prep.get("ok") is False:
                    msg = prep.get("error") or "Không mở được trình duyệt."
                    return {"ok": False, "error": "browser_error", "message": msg}
                if prep.get("need_login"):
                    return {
                        "ok": False,
                        "error": "need_login",
                        "need_login": True,
                        "need_hitl": True,
                        "missing_fields": ["browser_login"],
                        "message": prep.get("message")
                        or "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong.",
                        "url": prep.get("url"),
                    }
            result = worker.fill(user_id, data, wait_login=True, quiet=quiet)
        else:
            prep = worker.prepare(user_id, target, quiet=quiet)
            if prep.get("ok") is False:
                msg = prep.get("error") or "Không mở được trình duyệt."
                record_job(user_id, "standup_submit", "error", {"error": msg})
                _toast("standup_fail", "Standup thất bại", msg)
                return {"ok": False, "error": "browser_error", "message": msg}

            if prep.get("need_login"):
                if await_login:
                    # Job lịch: luôn toast ngay (kể cả notify=False) để user kịp đăng nhập
                    notify_mod.push(
                        user_id,
                        "standup_login",
                        "Standup theo lịch — cần đăng nhập",
                        prep.get("message")
                        or "Hãy đăng nhập trên cửa sổ trình duyệt đang mở.",
                        {"url": prep.get("url"), "target_url": target},
                    )
                    result = worker.fill(user_id, data, wait_login=True, quiet=quiet)
                else:
                    # Chat HITL: giữ browser mở, chờ user nhắn lại
                    return {
                        "ok": False,
                        "error": "need_login",
                        "need_login": True,
                        "need_hitl": True,
                        "missing_fields": ["browser_login"],
                        "message": prep.get("message")
                        or "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong.",
                        "url": prep.get("url"),
                        "target_url": target,
                    }
            else:
                result = worker.fill(user_id, data, wait_login=False, quiet=quiet)

        if result.get("ok") is False and result.get("error") and not result.get("submitted"):
            # worker-level error envelope
            if result.get("need_login") or result.get("error") == "need_login":
                return {
                    "ok": False,
                    "error": "need_login",
                    "need_login": True,
                    "need_hitl": True,
                    "missing_fields": ["browser_login"],
                    "message": result.get("message")
                    or "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong.",
                    "url": result.get("url"),
                }
            return {
                "ok": False,
                "error": result.get("error") or "browser_error",
                "message": result.get("message") or result.get("error"),
                "detail": result,
            }

        if result.get("need_login"):
            return {
                "ok": False,
                "error": "need_login",
                "need_login": True,
                "need_hitl": True,
                "missing_fields": ["browser_login"],
                "message": result.get("message")
                or "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong.",
                "url": result.get("url"),
                "detail": result,
            }

        if not result.get("submitted"):
            record_job(user_id, "standup_submit", "error", result)
            _toast(
                "standup_fail",
                "Standup thất bại",
                result.get("error") or result.get("message") or "unknown",
                result,
            )
            # Thiếu form / field → HITL thay vì chỉ lỗi cứng
            err = (result.get("error") or "").lower()
            if "không thấy form" in err or "không điền được" in err:
                return {
                    "ok": False,
                    "error": "need_login",
                    "need_login": True,
                    "need_hitl": True,
                    "missing_fields": ["browser_login"],
                    "message": (
                        result.get("error")
                        or "Chưa điền được form. Nếu cần đăng nhập, hãy đăng nhập trên trình duyệt rồi nhắn mình."
                    ),
                    "detail": result,
                }
            return {
                "ok": False,
                "error": "submit_failed",
                "message": result.get("error") or result.get("message"),
                "detail": result,
            }

        record_job(
            user_id,
            "standup_submit",
            "ok",
            result,
            artifact_path=result.get("artifact_path"),
        )
        _toast(
            "standup_ok",
            "Đã nộp standup thành công",
            f"Đã điền và nộp standup.\nURL: {result.get('url')}",
            result,
        )
        strategy = result.get("strategy") or "scripted"
        return {
            "ok": True,
            "flow": "standup_submit",
            "message": f"Đã điền và Submit standup ({strategy}).",
            "detail": result,
        }
    finally:
        release_lock(lock_key)
