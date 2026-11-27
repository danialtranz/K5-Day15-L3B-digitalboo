"""FastAPI entry: uvicorn harness.api.main:app --host 127.0.0.1 --port 8000"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from harness.api.routes_ask import router as ask_router
from harness.api.routes_auth import router as auth_router
from harness.api.routes_email import router as email_router
from harness.api.routes_jobs import router as jobs_router
from harness.api.routes_standup import router as standup_router
from harness.config import ensure_dirs, settings
from harness.db.session import init_db
from harness.jobs.scheduler import start_background_scheduler, stop_background_scheduler


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_dirs()
    init_db()
    start_background_scheduler()
    try:
        yield
    finally:
        stop_background_scheduler()


app = FastAPI(
    title="digitalboo harness",
    description="Gmail OAuth + standup computer-use (tách CP2)",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:4173",
        "http://localhost:4173",
        "null",  # Electron file://
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(ask_router)
app.include_router(email_router)
app.include_router(standup_router)
app.include_router(jobs_router)


@app.get("/health")
def health():
    s = settings()
    return {
        "ok": True,
        "gmail_configured": bool(s["google_client_id"] and s["google_client_secret"]),
        "standup_allowlist": s["standup_allowlist_url"],
        "scheduler": "embedded",
    }
