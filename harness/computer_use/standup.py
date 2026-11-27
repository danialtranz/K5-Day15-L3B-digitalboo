"""Điền form standup theo playbook YAML (scripted)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from harness.computer_use.playbook import match_playbook
from harness.config import ensure_dirs, settings


def _min_chars(site: dict[str, Any]) -> int:
    try:
        return max(1, int(site.get("min_chars") or 40))
    except (TypeError, ValueError):
        return 40


def _validate_fields(fields: dict[str, str], site: dict[str, Any]) -> str | None:
    need = _min_chars(site)
    for key in ("yesterday", "today"):
        val = (fields.get(key) or "").strip()
        if len(val) < need:
            return (
                f"Ô «{key}» cần tối thiểu {need} ký tự "
                f"(hiện {len(val)}). Hãy viết dài hơn rồi thử lại."
            )
    return None


def _fill_one(page, sel: str, value: str, key: str) -> str | None:
    locator = page.locator(sel).first
    try:
        locator.wait_for(state="visible", timeout=15000)
        locator.click(timeout=5000)
        locator.fill(value or "")
        current = locator.input_value(timeout=3000)
        if (current or "").strip() != (value or "").strip():
            locator.fill("")
            locator.type(value or "", delay=8)
        return None
    except Exception as e:
        return f"Không điền được field {key}: {e}"


def fill_and_submit(
    page,
    fields: dict[str, str],
    playbook: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_dirs()
    s = settings()
    site = playbook or match_playbook(page.url)
    if not site:
        return {
            "submitted": False,
            "error": f"Không có playbook scripted cho URL: {page.url}",
            "strategy": "scripted",
        }

    bad = _validate_fields(fields, site)
    if bad:
        return {"submitted": False, "error": bad, "strategy": "scripted"}

    from harness.computer_use.playbook import looks_like_login

    ready = site.get("form_ready_selector") or "#standup-yesterday"
    try:
        page.locator(ready).first.wait_for(state="visible", timeout=20000)
    except Exception as e:
        url = page.url
        if looks_like_login(url):
            return {
                "submitted": False,
                "need_login": True,
                "error": "need_login",
                "url": url,
                "message": (
                    "Trang đang yêu cầu đăng nhập (không thấy form standup). "
                    "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong."
                ),
                "strategy": "scripted",
            }
        return {
            "submitted": False,
            "need_login": True,
            "error": f"Không thấy form standup trên trang ({url}): {e}",
            "url": url,
            "message": (
                f"Không thấy form standup trên trang ({url}). "
                "Nếu cần đăng nhập, hãy đăng nhập trên trình duyệt rồi nhắn mình khi xong."
            ),
            "strategy": "scripted",
        }

    field_cfg = site.get("fields") or {}
    ordered = ("yesterday", "today", "blockers")
    for key in ordered:
        value = fields.get(key)
        if value is None:
            continue
        if key == "blockers" and not str(value).strip():
            continue
        sel = (field_cfg.get(key) or {}).get("selector")
        if not sel:
            continue
        err = _fill_one(page, sel, str(value), key)
        if err:
            return {"submitted": False, "error": err, "strategy": "scripted"}

    submit_sel = site.get("submit_selector") or "button[type='submit']"
    try:
        btn = page.locator(submit_sel).first
        btn.wait_for(state="visible", timeout=10000)
        for _ in range(10):
            if btn.is_enabled():
                break
            page.wait_for_timeout(300)
        if not btn.is_enabled():
            return {
                "submitted": False,
                "error": "Nút nộp vẫn disabled — kiểm tra độ dài hôm qua/hôm nay (≥40 ký tự).",
                "strategy": "scripted",
            }
        btn.click(timeout=5000)
    except Exception as e:
        return {"submitted": False, "error": f"Không click Submit: {e}", "strategy": "scripted"}

    patterns = site.get("success_patterns") or ["đã nộp", "success"]
    ok = False
    deadline_ms = 12000
    step = 500
    waited = 0
    while waited < deadline_ms:
        body = ""
        try:
            body = (page.locator("body").inner_text(timeout=2000) or "").lower()
        except Exception:
            pass
        if any(p.lower() in body for p in patterns):
            ok = True
            break
        try:
            if page.locator(ready).count() == 0:
                ok = True
                break
        except Exception:
            pass
        page.wait_for_timeout(step)
        waited += step

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifact = Path(s["artifacts_dir"]) / f"standup-{stamp}.png"
    try:
        page.screenshot(path=str(artifact), full_page=True)
    except Exception:
        artifact = Path("")

    if not ok:
        return {
            "submitted": False,
            "error": "Đã bấm nộp nhưng không thấy xác nhận thành công trên trang.",
            "url": page.url,
            "artifact_path": str(artifact) if artifact else None,
            "strategy": "scripted",
            "playbook_id": site.get("_id"),
        }

    return {
        "submitted": True,
        "url": page.url,
        "artifact_path": str(artifact) if artifact else None,
        "strategy": "scripted",
        "playbook_id": site.get("_id"),
    }
