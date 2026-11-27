"""API lịch chạy (Redis delayed jobs) — list / xoá / chạy ngay."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from harness.config import settings
from harness.db.auth import require_user
from harness.jobs.delayed import cancel_scheduled_job, list_scheduled_jobs, pop_job_by_id
from harness.jobs.scheduler import execute_delayed_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/scheduled")
def scheduled_jobs(
    user_id: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
):
    uid = user_id or settings()["default_user_id"]
    require_user(uid)
    items = list_scheduled_jobs(
        user_id=uid,
        limit=limit,
        timezone_name=settings().get("standup_timezone") or "Asia/Ho_Chi_Minh",
    )
    # Không trả _raw ra client
    clean = []
    for it in items:
        clean.append({k: v for k, v in it.items() if k != "_raw"})
    return {"items": clean, "user_id": uid}


@router.post("/scheduled/{job_id:path}/run")
def run_scheduled_job_now(job_id: str, user_id: Optional[str] = None):
    """Kích hoạt sớm 1 job đang chờ trong Redis (không đợi tới giờ cron)."""
    uid = user_id or settings()["default_user_id"]
    require_user(uid)
    job = pop_job_by_id(job_id, user_id=uid)
    if not job:
        raise HTTPException(404, "Job không tồn tại hoặc không thuộc user này")
    out = execute_delayed_job(job, source="manual_run_now")
    result = out.get("result") if isinstance(out.get("result"), dict) else {}
    return {
        "ok": bool(out.get("ok")),
        "id": job_id,
        "job_type": out.get("job_type") or job.get("job_type"),
        "message": (
            (result or {}).get("message")
            or out.get("error")
            or ("Đã chạy job." if out.get("ok") else "Job chạy xong nhưng chưa ok.")
        ),
        "result": out.get("result"),
        "error": out.get("error"),
        "awaiting_content": bool(out.get("awaiting_content") or (result or {}).get("awaiting_content")),
        "session_id": out.get("session_id") or (result or {}).get("session_id"),
    }


@router.delete("/scheduled/{job_id:path}")
def delete_scheduled_job(job_id: str, user_id: Optional[str] = None):
    uid = user_id or settings()["default_user_id"]
    require_user(uid)
    ok = cancel_scheduled_job(job_id, user_id=uid)
    if not ok:
        raise HTTPException(404, "Job không tồn tại hoặc không thuộc user này")
    return {"ok": True, "id": job_id}
