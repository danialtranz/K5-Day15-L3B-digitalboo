"""Vòng cron: xử lý Redis delayed jobs (+ email nền). Chạy nền khi harness serve."""
from __future__ import annotations

import threading
import time
from typing import Any, Optional

from harness.config import load_yaml, settings
from harness.db.redis_client import acquire_lock, release_lock
from harness.flows.email_watch import run_email_watch
from harness.flows.standup_prompt import (
    expire_standup_content_prompt,
    fields_ready,
    prompt_standup_content,
)
from harness.flows.standup_submit import run_standup_submit
from harness.jobs.delayed import next_run_unix, pop_due, schedule_job

_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def _reschedule_standup(payload: dict) -> None:
    """Lặp daily/weekly: xếp lần chạy kế tiếp; luôn xóa fields để hỏi lại mỗi ngày."""
    repeat = (payload.get("schedule_repeat") or "").strip()
    if repeat not in ("daily", "weekly"):
        return
    state = {
        "schedule_enabled": True,
        "schedule_repeat": repeat,
        "schedule_time": payload.get("schedule_time"),
        "schedule_weekday": payload.get("schedule_weekday"),
        "schedule_date": payload.get("schedule_date"),
    }
    nxt = next_run_unix(state, timezone_name=settings()["standup_timezone"], after_unix=time.time() + 1)
    if nxt:
        next_payload = dict(payload)
        next_payload["fields"] = None
        job_id = schedule_job("standup_fill", next_payload, nxt)
        print(f"[scheduler] rescheduled standup {repeat} → {job_id} @ {nxt}")


def _notify_standup_job(uid: str, result: dict) -> None:
    """Luôn báo desktop sau job lịch — một lần duy nhất (submit chạy silent)."""
    from harness.channels import notify as notify_mod
    from harness.hitl.slots import compose_standup_reply

    fields = {
        k: result[k]
        for k in ("yesterday", "today", "blockers")
        if result.get(k)
    }
    composed = compose_standup_reply(tool_result=result, fields=fields or None)
    msg = (composed.get("text") or "").strip() or str(
        result.get("message") or result.get("error") or ""
    )

    if result.get("ok"):
        notify_mod.push(
            uid,
            "standup_ok",
            "Standup theo lịch — thành công",
            msg,
            result.get("detail") or result,
        )
        return

    kind = "standup_fail"
    title = "Standup theo lịch — thất bại"
    err = result.get("error")
    if result.get("need_login") or err == "need_login":
        kind = "standup_login"
        title = "Standup theo lịch — cần đăng nhập"
    elif err == "no_notes":
        title = "Standup theo lịch — thiếu nội dung"
    elif err == "already_done":
        title = "Standup theo lịch — đã nộp hôm nay"
    notify_mod.push(uid, kind, title, msg, result)


def _handle_standup_due(uid: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Tới hạn: có fields → CU; không → HITL hỏi nội dung."""
    fields = payload.get("fields")
    if fields_ready(fields):
        result = run_standup_submit(
            user_id=uid,
            force=bool(payload.get("force", True)),
            fields=fields,
            url=payload.get("url"),
            notify=False,
            await_login=True,
        )
        print(result)
        try:
            _notify_standup_job(
                uid,
                result if isinstance(result, dict) else {"ok": False, "message": str(result)},
            )
        except Exception as ne:
            print("[scheduler] standup notify error:", ne)
        return result if isinstance(result, dict) else {"ok": False}

    # Thiếu nội dung ngày hôm đó → hỏi user
    prompt = prompt_standup_content(
        uid,
        url=payload.get("url"),
        session_id=payload.get("session_id"),
        schedule_meta={
            "schedule_time": payload.get("schedule_time"),
            "schedule_repeat": payload.get("schedule_repeat"),
        },
    )
    print("[scheduler] standup awaiting content:", prompt)
    return prompt


def _email_job_outcome(
    uid: str,
    *,
    job_type: str | None,
    job_id: str | None,
    ok: bool,
    result: Any = None,
    error: str | None = None,
    source: str = "scheduler",
) -> None:
    """Gửi kết quả cron (ok/fail) về Gmail user — best-effort."""
    try:
        from harness.channels.email.report import send_job_result_email

        mailed = send_job_result_email(
            uid,
            job_type=job_type,
            job_id=job_id,
            ok=ok,
            result=result,
            error=error,
            source=source,
        )
        if mailed.get("ok"):
            print(f"[scheduler] emailed result → {mailed.get('to')} ({mailed.get('subject')})")
        else:
            print(f"[scheduler] email result skipped/failed: {mailed}")
    except Exception as e:
        print("[scheduler] email result error:", e)


def execute_delayed_job(job: dict[str, Any], *, source: str = "scheduler") -> dict[str, Any]:
    """Chạy 1 delayed job (cron due hoặc kích hoạt tay). Trả kết quả tóm tắt."""
    jtype = job.get("job_type")
    payload = job.get("payload") or {}
    uid = payload.get("user_id") or settings()["default_user_id"]
    job_id = job.get("id")
    print(f"[scheduler] run job {job_id} ({jtype}) source={source}")
    try:
        if jtype == "standup_fill":
            try:
                result = _handle_standup_due(uid, payload)
            finally:
                # Xếp lịch lần sau (kể cả đang chờ nội dung) để không mất chu kỳ daily
                try:
                    _reschedule_standup(payload)
                except Exception as re:
                    print("[scheduler] standup reschedule error:", re)
            # awaiting_content = đã hỏi trong chat (HITL), không phải lỗi chạy job
            awaiting = isinstance(result, dict) and bool(
                result.get("awaiting_content")
                or result.get("need_hitl")
                or result.get("need_login")
            )
            ok = bool((result or {}).get("ok", True)) if not awaiting else True
            if isinstance(result, dict) and result.get("need_login") and not result.get("awaiting_content"):
                ok = False
            out = {
                "ok": ok,
                "job_id": job_id,
                "job_type": jtype,
                "result": result,
                "awaiting_content": awaiting,
                "session_id": (result or {}).get("session_id") if isinstance(result, dict) else None,
            }
            _email_job_outcome(
                uid,
                job_type=jtype,
                job_id=job_id,
                ok=ok,
                result=result,
                source=source,
            )
            return out

        if jtype == "standup_content_timeout":
            result = expire_standup_content_prompt(
                uid,
                session_id=str(payload.get("session_id") or ""),
                checkpoint_id=payload.get("checkpoint_id"),
                url=payload.get("url"),
            )
            print(result)
            out = {
                "ok": True,
                "job_id": job_id,
                "job_type": jtype,
                "result": result,
            }
            _email_job_outcome(
                uid,
                job_type=jtype,
                job_id=job_id,
                ok=True,
                result=result,
                source=source,
            )
            return out

        if jtype == "email_watch":
            state = dict(payload.get("state") or {})
            for k in ("schedule_repeat", "schedule_weekday", "schedule_time", "schedule_date"):
                if payload.get(k) is not None and state.get(k) is None:
                    state[k] = payload.get(k)
            result = run_email_watch(
                uid,
                state=state,
                source=source if source != "scheduler" else "scheduled_email_watch",
            )
            print(result)
            if payload.get("repeat") or (state.get("schedule_repeat") == "weekly"):
                if (payload.get("schedule_repeat") or state.get("schedule_repeat")) == "weekly":
                    nxt = next_run_unix(state, after_unix=time.time() + 1)
                    if nxt:
                        schedule_job("email_watch", payload, nxt)
                elif payload.get("notify_interval_sec"):
                    interval = int(payload["notify_interval_sec"])
                    schedule_job("email_watch", payload, time.time() + interval)
            ok = bool((result or {}).get("ok", False))
            out = {
                "ok": ok,
                "job_id": job_id,
                "job_type": jtype,
                "result": result,
            }
            # Không gửi email báo cáo cho chính job đọc email → tránh vòng lặp
            # (report → inbox → “mail quan trọng” → notify lại).
            return out

        out = {
            "ok": False,
            "job_id": job_id,
            "job_type": jtype,
            "error": f"unknown_job_type:{jtype}",
        }
        _email_job_outcome(
            uid,
            job_type=jtype,
            job_id=job_id,
            ok=False,
            error=out["error"],
            source=source,
        )
        return out
    except Exception as e:
        print("[scheduler] delayed job error:", e)
        if jtype == "standup_fill":
            try:
                from harness.channels import notify as notify_mod

                notify_mod.push(
                    uid,
                    "standup_fail",
                    "Standup thất bại",
                    f"Lỗi khi chạy standup theo lịch: {e}",
                    {"error": str(e)},
                )
                _reschedule_standup(payload)
            except Exception as ne:
                print("[scheduler] standup error-notify failed:", ne)
        out = {
            "ok": False,
            "job_id": job_id,
            "job_type": jtype,
            "error": str(e),
        }
        _email_job_outcome(
            uid,
            job_type=jtype,
            job_id=job_id,
            ok=False,
            error=str(e),
            source=source,
        )
        return out


def _run_delayed_jobs() -> None:
    for job in pop_due():
        execute_delayed_job(job, source="scheduler")


def run_scheduler(once: bool = False, stop_event: Optional[threading.Event] = None) -> None:
    """Poll Redis delayed jobs. once=True chạy 1 vòng; có stop_event để dừng background.

    Background email_watch chỉ chạy khi interval_sec > 0 (mặc định 0 = tắt).
    User muốn đọc mail → bảo trong chat hoặc đặt lịch email_watch tường minh.
    """
    s = settings()
    sched = load_yaml("schedule.yaml")
    raw_interval = (sched.get("email_watch") or {}).get("interval_sec")
    if raw_interval is None:
        raw_interval = s["email_watch_interval_sec"]
    try:
        email_every = int(raw_interval)
    except (TypeError, ValueError):
        email_every = 0
    if email_every > 0:
        print(f"[scheduler] delayed jobs + background email every {email_every}s")
    else:
        print("[scheduler] delayed jobs only (background email OFF — chỉ chạy khi user hỏi/lịch)")
    last_email = 0.0
    while True:
        if stop_event is not None and stop_event.is_set():
            print("[scheduler] stopped")
            break

        if acquire_lock("lock:sched:delayed", ttl_sec=30):
            try:
                _run_delayed_jobs()
            finally:
                release_lock("lock:sched:delayed")

        now = time.time()
        # interval_sec <= 0 → không tự đọc email nền
        if email_every > 0 and now - last_email >= email_every:
            if acquire_lock("lock:sched:email", ttl_sec=min(email_every, 120)):
                try:
                    print("[scheduler] background email…", run_email_watch(source="background"))
                except Exception as e:
                    print("[scheduler] email error:", e)
                finally:
                    release_lock("lock:sched:email")
            last_email = now

        if once:
            break
        for _ in range(5):
            if stop_event is not None and stop_event.is_set():
                break
            time.sleep(1)


def start_background_scheduler() -> None:
    """Khởi động thread scheduler (idempotent)."""
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(
        target=run_scheduler,
        kwargs={"once": False, "stop_event": _stop},
        name="harness-redis-scheduler",
        daemon=True,
    )
    _thread.start()
    print("[scheduler] background thread started (with harness serve)")


def stop_background_scheduler() -> None:
    global _thread
    _stop.set()
    t = _thread
    if t is not None and t.is_alive():
        t.join(timeout=8)
    _thread = None
    print("[scheduler] background thread stopped")
