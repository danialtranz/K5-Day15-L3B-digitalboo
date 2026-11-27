"""Grant + chạy standup computer-use."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl

from harness.config import settings
from harness.flows.standup_submit import run_standup_submit
from harness.jobs.store import get_grant, upsert_grant

router = APIRouter(prefix="/standup", tags=["standup"])


class GrantBody(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    allow_submit: bool = True


class RunBody(BaseModel):
    user_id: Optional[str] = None
    force: bool = False


@router.post("/grant")
def grant(body: GrantBody):
    user_id = body.user_id or settings()["default_user_id"]
    try:
        row = upsert_grant(user_id, str(body.url), allow_submit=body.allow_submit)
    except PermissionError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "ok": True,
        "grant": {
            "user_id": row["user_id"],
            "url": row["url"],
            "site_id": row["site_id"],
            "allow_submit": row["allow_submit"],
        },
    }


@router.get("/grant")
def grant_status(user_id: Optional[str] = None):
    user_id = user_id or settings()["default_user_id"]
    row = get_grant(user_id)
    if not row:
        return {"granted": False, "user_id": user_id}
    return {
        "granted": True,
        "user_id": user_id,
        "url": row["url"],
        "site_id": row["site_id"],
        "allow_submit": row["allow_submit"],
    }


@router.post("/run")
def run(body: RunBody | None = None):
    body = body or RunBody()
    user_id = body.user_id or settings()["default_user_id"]
    return run_standup_submit(user_id, force=body.force)
