"""Browser worker 1 thread: giữ cửa sổ Playwright khi cần user đăng nhập (HITL)."""
from __future__ import annotations

import queue
import threading
import time
from typing import Any, Optional

from harness.channels import notify as notify_mod
from harness.computer_use.playbook import (
    looks_like_login,
    match_playbook,
    resolve_strategy,
)
from harness.computer_use.router import run_fill
from harness.config import ensure_dirs, settings


class NeedLoginError(Exception):
    """Trang đang yêu cầu đăng nhập — giữ browser, chờ HITL."""

    def __init__(self, url: str, message: str = ""):
        self.url = url
        super().__init__(message or f"Cần đăng nhập: {url}")


def _form_ready(page, playbook: Optional[dict[str, Any]]) -> bool:
    if not playbook:
        return not looks_like_login(page.url)
    sel = playbook.get("form_ready_selector") or "#standup-yesterday"
    try:
        loc = page.locator(sel).first
        return bool(loc.count() > 0 and loc.is_visible())
    except Exception:
        return False


def _page_needs_login(page, target_url: str) -> bool:
    url = page.url or ""
    if looks_like_login(url):
        return True
    # Redirect OAuth / authorize thường chứa các token này
    low = url.lower()
    if any(
        x in low
        for x in (
            "/oauth/",
            "oauth/authorize",
            "accounts.google.com",
            "github.com/login",
            "login.microsoftonline.com",
        )
    ):
        return True
    pb = match_playbook(target_url) or match_playbook(url)
    if pb and resolve_strategy(target_url) == "scripted":
        # Đã vào đúng host/path nhưng chưa thấy form → thường là chưa auth
        from urllib.parse import urlparse

        th = (urlparse(target_url).netloc or "").lower()
        uh = (urlparse(url).netloc or "").lower()
        if th and uh and th != uh:
            return True
        if not _form_ready(page, pb):
            # Cho trang load JS một nhịp
            try:
                page.wait_for_timeout(800)
            except Exception:
                pass
            if looks_like_login(page.url):
                return True
            if not _form_ready(page, pb):
                # Không chắc 100% là login (có thể form đổi) — chỉ coi là login nếu URL login-ish
                return looks_like_login(page.url)
    return False


class _BrowserWorker:
    def __init__(self) -> None:
        self._q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="standup-browser", daemon=True)
        self._thread.start()
        self._sessions: dict[str, dict[str, Any]] = {}

    def _loop(self) -> None:
        while True:
            job = self._q.get()
            if job is None:
                break
            reply: queue.Queue = job["reply"]
            try:
                result = self._handle(job)
                reply.put({"ok": True, "result": result})
            except Exception as e:
                reply.put({"ok": False, "error": str(e), "exc_type": type(e).__name__})

    def _call(self, action: str, **payload: Any) -> dict[str, Any]:
        reply: queue.Queue = queue.Queue()
        self._q.put({"action": action, "reply": reply, **payload})
        timeout = float(payload.get("_timeout") or 3600)
        try:
            out = reply.get(timeout=timeout)
        except queue.Empty:
            return {"ok": False, "error": "browser_worker_timeout"}
        if not out.get("ok"):
            return {
                "ok": False,
                "error": out.get("error") or "browser_worker_error",
                "exc_type": out.get("exc_type"),
            }
        return out["result"]

    def prepare(self, user_id: str, start_url: str, *, quiet: bool = False) -> dict[str, Any]:
        return self._call(
            "prepare",
            user_id=user_id,
            start_url=start_url,
            quiet=quiet,
            _timeout=120,
        )

    def fill(
        self,
        user_id: str,
        fields: dict[str, str],
        *,
        wait_login: bool = True,
        quiet: bool = False,
    ) -> dict[str, Any]:
        timeout = settings()["login_wait_timeout_sec"] + 180
        return self._call(
            "fill",
            user_id=user_id,
            fields=fields,
            wait_login=wait_login,
            quiet=quiet,
            _timeout=timeout,
        )

    def close(self, user_id: str) -> dict[str, Any]:
        return self._call("close", user_id=user_id, _timeout=30)

    def status(self, user_id: str) -> dict[str, Any]:
        return self._call("status", user_id=user_id, _timeout=15)

    def _handle(self, job: dict[str, Any]) -> dict[str, Any]:
        action = job["action"]
        if action == "prepare":
            return self._prepare(job["user_id"], job["start_url"], quiet=bool(job.get("quiet")))
        if action == "fill":
            return self._fill(
                job["user_id"],
                job["fields"],
                wait_login=bool(job.get("wait_login", True)),
                quiet=bool(job.get("quiet")),
            )
        if action == "close":
            self._close_session(job["user_id"])
            return {"closed": True}
        if action == "status":
            sess = self._sessions.get(job["user_id"])
            if not sess:
                return {"open": False}
            page = sess["page"]
            return {
                "open": True,
                "url": page.url,
                "need_login": _page_needs_login(page, sess["target_url"]),
                "target_url": sess["target_url"],
            }
        raise ValueError(f"unknown action: {action}")

    def _close_session(self, user_id: str) -> None:
        sess = self._sessions.pop(user_id, None)
        if not sess:
            return
        try:
            sess["context"].close()
        except Exception:
            pass
        try:
            sess["pw"].stop()
        except Exception:
            pass

    def _prepare(self, user_id: str, start_url: str, *, quiet: bool = False) -> dict[str, Any]:
        from playwright.sync_api import sync_playwright

        from harness.computer_use.browser import url_permitted

        ensure_dirs()
        s = settings()
        if not url_permitted(start_url):
            raise PermissionError(
                f"URL không được phép (cần https + playbook hoặc vision an toàn): {start_url}"
            )

        self._close_session(user_id)
        strategy = resolve_strategy(start_url)
        if not quiet:
            notify_mod.push(
                user_id,
                "standup_browser",
                "Đang mở trình duyệt standup",
                f"Agent mở ({strategy}): {start_url}\nNếu cần đăng nhập, hãy đăng nhập trên cửa sổ vừa mở.",
                {"url": start_url, "strategy": strategy},
            )

        pw = sync_playwright().start()
        try:
            context = pw.chromium.launch_persistent_context(
                user_data_dir=str(s["playwright_user_data_dir"]),
                headless=bool(s["playwright_headless"]),
                viewport={"width": 1280, "height": 800},
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(start_url, wait_until="domcontentloaded")
            # Cho redirect OAuth kịp chạy
            page.wait_for_timeout(1500)
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            self._sessions[user_id] = {
                "pw": pw,
                "context": context,
                "page": page,
                "target_url": start_url,
                "strategy": strategy,
            }

            if _page_needs_login(page, start_url):
                if not quiet:
                    notify_mod.push(
                        user_id,
                        "standup_login",
                        "Cần đăng nhập standup",
                        "Hãy đăng nhập trên cửa sổ trình duyệt Playwright, rồi nhắn lại khi xong.",
                        {"url": page.url},
                    )
                return {
                    "need_login": True,
                    "url": page.url,
                    "target_url": start_url,
                    "strategy": strategy,
                    "message": (
                        "Portal đang yêu cầu đăng nhập. "
                        "Hãy đăng nhập trên cửa sổ trình duyệt vừa mở, rồi nhắn mình khi xong nhé."
                    ),
                }

            # Nếu scripted mà form chưa sẵn → cũng coi như cần user xử lý login/HITL
            pb = match_playbook(start_url)
            if pb and not _form_ready(page, pb):
                # Đợi thêm một chút form
                deadline = time.time() + 8
                while time.time() < deadline:
                    if looks_like_login(page.url) or _page_needs_login(page, start_url):
                        if not quiet:
                            notify_mod.push(
                                user_id,
                                "standup_login",
                                "Cần đăng nhập standup",
                                "Hãy đăng nhập trên cửa sổ trình duyệt Playwright, rồi nhắn lại khi xong.",
                                {"url": page.url},
                            )
                        return {
                            "need_login": True,
                            "url": page.url,
                            "target_url": start_url,
                            "strategy": strategy,
                            "message": (
                                "Chưa thấy form standup — có vẻ bạn cần đăng nhập. "
                                "Hãy đăng nhập trên cửa sổ trình duyệt, rồi nhắn mình khi xong."
                            ),
                        }
                    if _form_ready(page, pb):
                        break
                    page.wait_for_timeout(500)
                if not _form_ready(page, pb):
                    return {
                        "need_login": True,
                        "url": page.url,
                        "target_url": start_url,
                        "strategy": strategy,
                        "message": (
                            "Chưa thấy form standup trên trang. "
                            "Nếu đang ở màn đăng nhập, hãy đăng nhập xong rồi nhắn mình."
                        ),
                    }

            return {
                "need_login": False,
                "ready": True,
                "url": page.url,
                "target_url": start_url,
                "strategy": strategy,
            }
        except Exception:
            try:
                pw.stop()
            except Exception:
                pass
            self._sessions.pop(user_id, None)
            raise

    def _wait_login(self, user_id: str, sess: dict[str, Any], timeout_sec: int) -> None:
        from harness.computer_use.browser import wait_until_logged_in

        page = sess["page"]
        target = sess["target_url"]
        strategy = sess.get("strategy") or resolve_strategy(target)
        wait_until_logged_in(
            page,
            target,
            user_id=user_id,
            timeout_sec=timeout_sec,
            target_url=target,
            vision_mode=(strategy == "vision"),
        )
        # Sau login: quay target nếu cần + chờ form
        pb = match_playbook(target)
        if pb and not _form_ready(page, pb):
            try:
                page.goto(target, wait_until="domcontentloaded")
            except Exception:
                pass
            deadline = time.time() + min(60, timeout_sec)
            while time.time() < deadline:
                if looks_like_login(page.url):
                    raise NeedLoginError(page.url)
                if _form_ready(page, pb):
                    return
                page.wait_for_timeout(1000)
            if not _form_ready(page, pb):
                raise NeedLoginError(
                    page.url,
                    "Vẫn chưa thấy form standup sau khi đăng nhập.",
                )

    def _fill(
        self,
        user_id: str,
        fields: dict[str, str],
        *,
        wait_login: bool = True,
        quiet: bool = False,
    ) -> dict[str, Any]:
        sess = self._sessions.get(user_id)
        if not sess:
            return {
                "submitted": False,
                "error": "no_browser_session",
                "need_login": True,
                "message": "Chưa có cửa sổ trình duyệt. Mình mở lại và cần bạn đăng nhập nếu được hỏi.",
            }

        page = sess["page"]
        target = sess["target_url"]
        try:
            if wait_login or _page_needs_login(page, target):
                try:
                    self._wait_login(user_id, sess, settings()["login_wait_timeout_sec"])
                except NeedLoginError as e:
                    return {
                        "submitted": False,
                        "need_login": True,
                        "url": e.url,
                        "error": "need_login",
                        "message": str(e),
                    }
                except TimeoutError as e:
                    return {
                        "submitted": False,
                        "need_login": True,
                        "error": "login_timeout",
                        "message": str(e) or "Hết thời gian chờ đăng nhập.",
                        "url": page.url,
                    }

            result = run_fill(page, fields, url=target, user_id=user_id)

            # Form fail vì redirect login giữa chừng
            if not result.get("submitted"):
                err = (result.get("error") or "").lower()
                if _page_needs_login(page, target) or "không thấy form" in err or "need_login" in err:
                    result["need_login"] = True
                    result["error"] = result.get("error") or "need_login"
                    if not result.get("message"):
                        result["message"] = (
                            "Trang đang yêu cầu đăng nhập hoặc chưa có form. "
                            "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong."
                        )
                    return result

            self._close_session(user_id)
            return result
        except Exception as e:
            # Giữ session nếu còn cần login; đóng nếu lỗi khác
            msg = f"Lỗi trình duyệt/computer-use: {e}"
            if _page_needs_login(page, target) or looks_like_login(page.url):
                return {
                    "submitted": False,
                    "need_login": True,
                    "error": "need_login",
                    "message": (
                        "Portal đang yêu cầu đăng nhập. "
                        "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong."
                    ),
                    "url": page.url,
                    "detail": msg,
                }
            self._close_session(user_id)
            return {"submitted": False, "error": "browser_error", "message": msg}


_worker: Optional[_BrowserWorker] = None
_worker_lock = threading.Lock()


def get_worker() -> _BrowserWorker:
    global _worker
    with _worker_lock:
        if _worker is None:
            _worker = _BrowserWorker()
        return _worker
