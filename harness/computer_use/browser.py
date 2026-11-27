"""Playwright browser: persistent profile + pause để user tự login."""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator, Optional
from urllib.parse import urlparse

from harness.channels import notify as notify_mod  # noqa: F401 — submodule
from harness.config import ensure_dirs, load_yaml, settings


def host_allowed(url: str, allowlist_url: str) -> bool:
    if not allowlist_url:
        return False
    a = urlparse(allowlist_url)
    u = urlparse(url)
    if not a.netloc or not u.netloc:
        return False
    if a.netloc.lower() != u.netloc.lower():
        return False
    # path allowlist: URL hiện tại phải cùng prefix path (nếu allowlist có path)
    ap = (a.path or "/").rstrip("/") or "/"
    up = u.path or "/"
    if ap != "/" and not (up == ap or up.startswith(ap + "/")):
        # vẫn cho phép trang login trên cùng host
        return _looks_like_login(url)
    return True


def _looks_like_login(url: str) -> bool:
    low = url.lower()
    patterns = (load_yaml("sites.yaml").get("standup") or {}).get("login_url_patterns") or []
    return any(p.lower() in low for p in patterns)


@contextmanager
def open_browser(start_url: str, user_id: str = "u1"):
    """Yield Playwright page. Caller phải đóng context qua generator."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("Cần cài playwright: pip install playwright && playwright install chromium") from e

    ensure_dirs()
    s = settings()
    allow = s["standup_allowlist_url"]
    if not host_allowed(start_url, allow):
        raise PermissionError(f"URL không nằm allowlist: {start_url} (allow={allow})")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(s["playwright_user_data_dir"]),
            headless=bool(s["playwright_headless"]),
            viewport={"width": 1280, "height": 800},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")
        wait_until_logged_in(page, allow, user_id=user_id, timeout_sec=s["login_wait_timeout_sec"])
        try:
            yield page
        finally:
            context.close()


def wait_until_logged_in(page, allowlist_url: str, user_id: str, timeout_sec: int = 300) -> None:
    """Nếu đang ở trang login → notify user và poll đến khi thoát login / vào allowlist path."""
    deadline = time.time() + timeout_sec
    notified = False
    while time.time() < deadline:
        url = page.url
        if _looks_like_login(url):
            if not notified:
                notify_mod.push(
                    user_id,
                    "standup_login",
                    "Cần đăng nhập standup",
                    "Hãy đăng nhập trên cửa sổ trình duyệt Playwright, rồi đợi agent tiếp tục.",
                    {"url": url},
                )
                notified = True
            page.wait_for_timeout(2000)
            continue
        if host_allowed(url, allowlist_url):
            return
        # host lạ → abort
        if allowlist_url and urlparse(url).netloc.lower() != urlparse(allowlist_url).netloc.lower():
            raise PermissionError(f"Rời allowlist host: {url}")
        page.wait_for_timeout(1000)
    raise TimeoutError("Hết thời gian chờ user đăng nhập standup")
