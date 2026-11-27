"""Flow B: grant → notes → Playwright fill + Submit (1 URL allowlist)."""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from harness.channels import notify as notify_mod
from harness.computer_use.browser import open_browser
from harness.computer_use.standup import fill_and_submit
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
) -> dict[str, Any]:
    from harness.jobs.store import upsert_grant

    user_id = user_id or settings()["default_user_id"]
    if url:
        try:
            upsert_grant(user_id, url)
        except PermissionError as e:
            return {"ok": False, "error": "url_not_allowlisted", "message": str(e)}

    grant = get_grant(user_id)
    if not grant and not url:
        msg = "Chưa có grant/URL standup."
        notify_mod.push(user_id, "standup_need_grant", "Cần grant standup", msg)
        return {"ok": False, "error": "no_grant", "message": msg}

    if not force and not _in_window():
        msg = "Ngoài cửa sổ standup 00:01–09:00 (dùng force=true / schedule để chạy)."
        return {"ok": False, "error": "outside_window", "message": msg}

    if already_done(user_id, "standup_submit"):
        return {"ok": False, "error": "already_done", "message": "Đã nộp standup hôm nay."}

    lock_key = f"lock:standup:{user_id}"
    if not acquire_lock(lock_key, ttl_sec=600):
        return {"ok": False, "error": "locked", "message": "Job standup đang chạy."}

    try:
        data = fields or _load_fields_from_notes(user_id)
        if not data:
            msg = "Thiếu nội dung standup (hôm qua / hôm nay). Không bịa, không submit."
            notify_mod.push(user_id, "standup_need_notes", "Thiếu notes", msg)
            record_job(user_id, "standup_submit", "skipped", {"reason": "no_notes"})
            return {"ok": False, "error": "no_notes", "message": msg}

        target = url or (grant["url"] if grant else None) or settings()["standup_allowlist_url"]
        with open_browser(target, user_id=user_id) as page:
            result = fill_and_submit(page, data)

        if not result.get("submitted"):
            record_job(user_id, "standup_submit", "error", result)
            notify_mod.push(user_id, "standup_fail", "Standup thất bại", result.get("error") or "unknown")
            return {"ok": False, "error": "submit_failed", "message": result.get("error"), "detail": result}

        record_job(
            user_id,
            "standup_submit",
            "ok",
            result,
            artifact_path=result.get("artifact_path"),
        )
        notify_mod.push(
            user_id,
            "standup_ok",
            "Đã Submit standup",
            f"URL: {result.get('url')}\nArtifact: {result.get('artifact_path')}",
            result,
        )
        return {"ok": True, "flow": "standup_submit", "message": "Đã điền và Submit standup.", "detail": result}
    finally:
        release_lock(lock_key)
