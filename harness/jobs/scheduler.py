"""Vòng cron: xử lý Redis delayed jobs + email/standup định kỳ."""
from __future__ import annotations

import time

from harness.config import load_yaml, settings
from harness.db.redis_client import acquire_lock, release_lock
from harness.flows.email_watch import run_email_watch
from harness.flows.standup_submit import run_standup_submit
from harness.jobs.delayed import pop_due, schedule_job


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
                print(run_email_watch(uid))
                # lặp chu kỳ nếu repeat
                interval = payload.get("notify_interval_sec")
                if payload.get("repeat") and interval:
                    schedule_job(
                        "email_watch",
                        payload,
                        time.time() + int(interval),
                    )
        except Exception as e:
            print("[scheduler] delayed job error:", e)


def run_scheduler(once: bool = False) -> None:
    s = settings()
    sched = load_yaml("schedule.yaml")
    email_every = int((sched.get("email_watch") or {}).get("interval_sec") or s["email_watch_interval_sec"])
    print(f"[scheduler] delayed jobs + optional email every {email_every}s")
    last_email = 0.0
    while True:
        if acquire_lock("lock:sched:delayed", ttl_sec=30):
            try:
                _run_delayed_jobs()
            finally:
                release_lock("lock:sched:delayed")

        now = time.time()
        # quét email nền (không bắt buộc HITL) — có thể tắt bằng interval rất lớn
        if now - last_email >= email_every:
            if acquire_lock("lock:sched:email", ttl_sec=min(email_every, 120)):
                try:
                    print("[scheduler] background email…", run_email_watch())
                except Exception as e:
                    print("[scheduler] email error:", e)
                finally:
                    release_lock("lock:sched:email")
            last_email = now

        if once:
            break
        time.sleep(5)
