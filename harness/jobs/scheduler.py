"""Vòng cron: xử lý Redis delayed jobs (+ email nền). Chạy nền khi harness serve."""
from __future__ import annotations

import threading
import time
from typing import Optional

from harness.config import load_yaml, settings
from harness.db.redis_client import acquire_lock, release_lock
from harness.flows.email_watch import run_email_watch
from harness.flows.standup_submit import run_standup_submit
from harness.jobs.delayed import next_run_unix, pop_due, schedule_job

_stop = threading.Event()
_thread: Optional[threading.Thread] = None


def _run_delayed_jobs() -> None:
    for job in pop_due():
        jtype = job.get("job_type")
        payload = job.get("payload") or {}
        uid = payload.get("user_id") or settings()["default_user_id"]
        print("[scheduler] due job", job.get("id"), jtype)
        try:
            if jtype == "standup_fill":
                print(
                    run_standup_submit(
                        user_id=uid,
                        force=bool(payload.get("force", True)),
                        fields=payload.get("fields"),
                        url=payload.get("url"),
                    )
                )
            elif jtype == "email_watch":
                state = dict(payload.get("state") or {})
                # Đồng bộ repeat fields vào state nếu payload tách
                for k in ("schedule_repeat", "schedule_weekday", "schedule_time", "schedule_date"):
                    if payload.get(k) is not None and state.get(k) is None:
                        state[k] = payload.get(k)
                print(
                    run_email_watch(
                        uid,
                        state=state,
                        source="scheduled_email_watch",
                    )
                )
                # Reschedule
                if payload.get("repeat") or (state.get("schedule_repeat") == "weekly"):
                    # weekly calendar
                    if (payload.get("schedule_repeat") or state.get("schedule_repeat")) == "weekly":
                        nxt = next_run_unix(state, after_unix=time.time() + 1)
                        if nxt:
                            schedule_job("email_watch", payload, nxt)
                    elif payload.get("notify_interval_sec"):
                        interval = int(payload["notify_interval_sec"])
                        schedule_job("email_watch", payload, time.time() + interval)
        except Exception as e:
            print("[scheduler] delayed job error:", e)


def run_scheduler(once: bool = False, stop_event: Optional[threading.Event] = None) -> None:
    """Poll Redis delayed jobs. once=True chạy 1 vòng; có stop_event để dừng background."""
    s = settings()
    sched = load_yaml("schedule.yaml")
    email_every = int((sched.get("email_watch") or {}).get("interval_sec") or s["email_watch_interval_sec"])
    print(f"[scheduler] delayed jobs + optional email every {email_every}s")
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
        # Background email poll tắt khoảng rất lớn nếu không cần — giữ tương thích cũ
        if email_every < 86400 * 365 and now - last_email >= email_every:
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
