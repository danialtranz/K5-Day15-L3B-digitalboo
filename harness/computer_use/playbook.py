"""Match URL → playbook YAML (scripted) hoặc vision."""
from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlparse

from harness.config import load_yaml


def sites_config() -> dict[str, Any]:
    return load_yaml("sites.yaml") or {}


def vision_config() -> dict[str, Any]:
    return sites_config().get("vision") or {}


def login_url_patterns() -> list[str]:
    cfg = vision_config()
    patterns = list(cfg.get("login_url_patterns") or [])
    # legacy standup root (nếu còn)
    legacy = (sites_config().get("standup") or {}).get("login_url_patterns") or []
    for p in legacy:
        if p not in patterns:
            patterns.append(p)
    return patterns


def looks_like_login(url: str) -> bool:
    low = (url or "").lower()
    if any(p.lower() in low for p in login_url_patterns()):
        return True
    # OAuth / IdP phổ biến (kể cả khi chưa có trong YAML)
    return any(
        x in low
        for x in (
            "/oauth/authorize",
            "oauth2",
            "accounts.google.com",
            "github.com/login",
            "login.microsoftonline.com",
            "auth0.com",
        )
    )


def _path_matches(url_path: str, prefix: str) -> bool:
    ap = (prefix or "/").rstrip("/") or "/"
    up = url_path or "/"
    if ap == "/":
        return True
    return up == ap or up.startswith(ap + "/")


def match_playbook(url: str) -> Optional[dict[str, Any]]:
    """Trả playbook dict (kèm _id) nếu URL khớp match.host + path_prefix."""
    if not url:
        return None
    u = urlparse(url)
    host = (u.netloc or "").lower()
    if not host:
        return None
    playbooks = sites_config().get("playbooks") or {}
    if not isinstance(playbooks, dict):
        return None
    for pid, pb in playbooks.items():
        if not isinstance(pb, dict):
            continue
        m = pb.get("match") or {}
        hosts = [h.lower() for h in (m.get("hosts") or []) if h]
        if host not in hosts:
            continue
        prefix = m.get("path_prefix") or "/"
        if not _path_matches(u.path or "/", prefix):
            # trang login cùng host vẫn gắn playbook (để biết strategy sau login)
            if looks_like_login(url):
                out = dict(pb)
                out["_id"] = pid
                return out
            continue
        out = dict(pb)
        out["_id"] = pid
        return out
    return None


def resolve_strategy(url: str) -> str:
    pb = match_playbook(url)
    if pb:
        return str(pb.get("strategy") or "scripted")
    return "vision"


def default_playbook_for_scripted() -> dict[str, Any]:
    """Playbook đầu tiên strategy=scripted, hoặc legacy standup root."""
    playbooks = sites_config().get("playbooks") or {}
    for pid, pb in playbooks.items():
        if isinstance(pb, dict) and (pb.get("strategy") or "scripted") == "scripted":
            out = dict(pb)
            out["_id"] = pid
            return out
    legacy = sites_config().get("standup")
    if isinstance(legacy, dict) and legacy:
        out = dict(legacy)
        out["_id"] = "standup_legacy"
        return out
    return {}


def is_safe_https_url(url: str) -> bool:
    u = urlparse(url or "")
    if u.scheme.lower() != "https":
        return False
    if not u.netloc:
        return False
    # chặn credential trong URL
    if u.username or u.password:
        return False
    return True
