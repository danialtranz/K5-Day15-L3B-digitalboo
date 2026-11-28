"""Đọc cấu hình từ .env + YAML harness/config."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = Path(__file__).resolve().parent / "config"

load_dotenv(ROOT / ".env")


def _env(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key)
    if val is None or val == "":
        return default
    return val


@lru_cache
def settings() -> dict[str, Any]:
    return {
        "database_url": _env(
            "DATABASE_URL",
            "postgresql://digitalboo:digitalboo@127.0.0.1:15432/digitalboo",
        ),
        "redis_url": _env("REDIS_URL", "redis://:digitalboo@127.0.0.1:16379/0"),
        "app_host": _env("APP_HOST", "127.0.0.1"),
        "app_port": int(_env("APP_PORT", "8000") or "8000"),
        "oauth_redirect_base": _env("OAUTH_REDIRECT_BASE", "http://127.0.0.1:8000"),
        "default_user_id": _env("DEFAULT_USER_ID", "u1"),
        "google_client_id": _env("GOOGLE_CLIENT_ID", ""),
        "google_client_secret": _env("GOOGLE_CLIENT_SECRET", ""),
        "standup_allowlist_url": _env("STANDUP_ALLOWLIST_URL", ""),
        "playwright_user_data_dir": ROOT
        / (_env("PLAYWRIGHT_USER_DATA_DIR", "harness/state/browser") or "harness/state/browser"),
        "playwright_headless": (_env("PLAYWRIGHT_HEADLESS", "0") or "0") == "1",
        "login_wait_timeout_sec": int(_env("LOGIN_WAIT_TIMEOUT_SEC", "300") or "300"),
        "email_watch_interval_sec": int(_env("EMAIL_WATCH_INTERVAL_SEC", "0") or "0"),
        "standup_timezone": _env("STANDUP_TIMEZONE", "Asia/Ho_Chi_Minh"),
        "mem0_api_key": _env("MEM0_API_KEY", ""),
        "mem0_enabled": (_env("MEM0_ENABLED", "1") or "1") == "1",
        # oss = local Memory() + OpenAI key (demo ổn)
        # platform = MemoryClient + MEM0_API_KEY (cần BYOK sau free trial)
        "mem0_mode": (_env("MEM0_MODE", "oss") or "oss").strip().lower(),
        "root": ROOT,
        "state_dir": ROOT / "harness" / "state",
        "outbox_dir": ROOT / "outbox",
        "artifacts_dir": ROOT / "harness" / "state" / "artifacts",
    }


def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def ensure_dirs() -> None:
    s = settings()
    for key in ("state_dir", "outbox_dir", "artifacts_dir", "playwright_user_data_dir"):
        Path(s[key]).mkdir(parents=True, exist_ok=True)
