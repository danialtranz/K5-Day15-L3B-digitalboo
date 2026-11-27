"""Playwright browser: persistent profile + pause để user tự login."""
from __future__ import annotations

import time
from contextlib import contextmanager
from urllib.parse import urlparse

from harness.channels import notify as notify_mod
from harness.computer_use.playbook import (
    is_safe_https_url,
    looks_like_login,
    match_playbook,
    resolve_strategy,
)
from harness.config import ensure_dirs, settings


def host_allowed(url: str, allowlist_url: str) -> bool:
    """Tương thích cũ: cùng host (+ path) với STANDUP_ALLOWLIST_URL, hoặc login cùng host."""
    if not allowlist_url:
        return False
    a = urlparse(allowlist_url)
    u = urlparse(url)
    if not a.netloc or not u.netloc:
        return False
    if a.netloc.lower() != u.netloc.lower():
        return False
    ap = (a.path or "/").rstrip("/") or "/"
    up = u.path or "/"
    if ap != "/" and not (up == ap or up.startswith(ap + "/")):
        return looks_like_login(url)
    return True


def url_permitted(url: str) -> bool:
    """
    Cho phép mở browser khi:
    - khớp playbook (Edufun), hoặc
    - HTTPS an toàn (vision CU cho URL user cung cấp), hoặc
    - cùng host với STANDUP_ALLOWLIST_URL (legacy).
    """
    if not url or not is_safe_https_url(url):
        return False
    if match_playbook(url):
        return True
    if resolve_strategy(url) == "vision":
        return True
    allow = settings().get("standup_allowlist_url") or ""
    return bool(allow) and host_allowed(url, allow)


def same_host(url: str, ref_url: str) -> bool:
    if not ref_url or not url:
        return False
    return urlparse(url).netloc.lower() == urlparse(ref_url).netloc.lower()


def _on_target_path(url: str, target_url: str) -> bool:
    ap = (urlparse(target_url).path or "/").rstrip("/") or "/"
    up = urlparse(url).path or "/"
    if ap == "/":
        return True
    return up == ap or up.startswith(ap + "/")


@contextmanager
def open_browser(start_url: str, user_id: str = "u1"):
    """Yield Playwright page. Caller phải đóng context qua generator."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError("Cần cài playwright: pip install playwright && playwright install chromium") from e

    ensure_dirs()
    s = settings()
    if not url_permitted(start_url):
        raise PermissionError(
            f"URL không được phép (cần https + playbook hoặc vision an toàn): {start_url}"
        )

    strategy = resolve_strategy(start_url)
    notify_mod.push(
        user_id,
        "standup_browser",
        "Đang mở trình duyệt standup",
        f"Agent mở ({strategy}): {start_url}\nNếu cần đăng nhập, hãy đăng nhập trên cửa sổ vừa mở.",
        {"url": start_url, "strategy": strategy},
    )

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(s["playwright_user_data_dir"]),
            headless=bool(s["playwright_headless"]),
            viewport={"width": 1280, "height": 800},
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(start_url, wait_until="domcontentloaded")
        wait_until_logged_in(
            page,
            start_url,
            user_id=user_id,
            timeout_sec=s["login_wait_timeout_sec"],
            target_url=start_url,
            vision_mode=(strategy == "vision"),
        )
        try:
            yield page
        finally:
            context.close()


def wait_until_logged_in(
    page,
    allowlist_url: str,
    user_id: str,
    timeout_sec: int = 300,
    target_url: str | None = None,
    vision_mode: bool = False,
) -> None:
    """Nếu đang ở trang login → notify user và poll đến khi thoát login / vào target."""
    deadline = time.time() + timeout_sec
    notified = False
    navigated_back = False
    target = target_url or allowlist_url
    ref_host = target or allowlist_url

    while time.time() < deadline:
        url = page.url
        if looks_like_login(url):
            if not notified:
                notify_mod.push(
                    user_id,
                    "standup_login",
                    "Cần đăng nhập standup",
                    "Hãy đăng nhập trên cửa sổ trình duyệt Playwright, rồi đợi agent tiếp tục.",
                    {"url": url},
                )
                notified = True
            navigated_back = False
            page.wait_for_timeout(2000)
            continue

        # OAuth (GitHub/Google/…) nhảy host — luôn chờ, không abort sớm
        if not same_host(url, ref_host):
            # Sau OAuth thường về host gốc; nếu đã thoát login thì thử quay target
            if not navigated_back and target:
                try:
                    page.goto(target, wait_until="domcontentloaded")
                    navigated_back = True
                except Exception:
                    page.wait_for_timeout(1000)
            else:
                page.wait_for_timeout(1000)
            continue

        if target and not _on_target_path(url, target):
            if not navigated_back:
                try:
                    page.goto(target, wait_until="domcontentloaded")
                    navigated_back = True
                except Exception:
                    page.wait_for_timeout(1000)
            else:
                page.wait_for_timeout(1000)
            continue

        if notified:
            notify_mod.push(
                user_id,
                "standup_login_ok",
                "Đã đăng nhập standup",
                "Agent tiếp tục điền form standup.",
                {"url": url},
            )
        return

    raise TimeoutError("Hết thời gian chờ user đăng nhập standup")
