"""Điền form standup + Submit — chỉ trên page đã allowlist."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from harness.computer_use.browser import host_allowed
from harness.config import ensure_dirs, load_yaml, settings


def fill_and_submit(page, fields: dict[str, str]) -> dict[str, Any]:
    ensure_dirs()
    s = settings()
    allow = s["standup_allowlist_url"]
    if not host_allowed(page.url, allow):
        return {"submitted": False, "error": f"URL không allowlist: {page.url}"}

    site = load_yaml("sites.yaml").get("standup") or {}
    field_cfg = site.get("fields") or {}
    for key, value in fields.items():
        sel = (field_cfg.get(key) or {}).get("selector")
        if not sel:
            continue
        locator = page.locator(sel).first
        try:
            locator.wait_for(state="visible", timeout=5000)
            locator.fill(value or "")
        except Exception as e:
            return {"submitted": False, "error": f"Không điền được field {key}: {e}"}

    submit_sel = site.get("submit_selector") or "button[type='submit']"
    try:
        page.locator(submit_sel).first.click(timeout=5000)
    except Exception as e:
        return {"submitted": False, "error": f"Không click Submit: {e}"}

    page.wait_for_timeout(1500)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact = Path(s["artifacts_dir"]) / f"standup-{stamp}.png"
    try:
        page.screenshot(path=str(artifact), full_page=True)
    except Exception:
        artifact = Path("")

    return {
        "submitted": True,
        "url": page.url,
        "artifact_path": str(artifact) if artifact else None,
    }
