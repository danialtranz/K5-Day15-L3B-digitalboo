"""Long-term memory qua Mem0 — Platform API hoặc OSS local.

Modes (MEM0_MODE):
  - oss (mặc định): `Memory()` local, dùng API_KEY/OpenAI — demo ổn, không phụ thuộc quota Platform
  - platform: `MemoryClient` + MEM0_API_KEY — cần BYOK trên dashboard sau 30 ngày free

Tắt: MEM0_ENABLED=0. Lỗi API không crash harness.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from harness.config import settings

log = logging.getLogger(__name__)


def _openai_key() -> str:
    return (
        (os.getenv("OPENAI_API_KEY") or "").strip()
        or (os.getenv("API_KEY") or "").strip()
        or ""
    )


@lru_cache
def _backend() -> tuple[str, Any] | tuple[None, None]:
    cfg = settings()
    if not cfg.get("mem0_enabled"):
        return None, None

    mode = (cfg.get("mem0_mode") or "oss").strip().lower()
    if mode not in {"oss", "platform"}:
        mode = "oss"

    if mode == "platform":
        key = (cfg.get("mem0_api_key") or "").strip()
        if not key:
            log.warning("MEM0_MODE=platform nhưng thiếu MEM0_API_KEY — tắt Mem0")
            return None, None
        try:
            from mem0 import MemoryClient

            return "platform", MemoryClient(api_key=key)
        except Exception as e:
            log.warning("Mem0 Platform init failed: %s", e)
            return None, None

    # OSS local
    oai = _openai_key()
    if not oai:
        log.warning("MEM0_MODE=oss cần API_KEY hoặc OPENAI_API_KEY — tắt Mem0")
        return None, None
    # Mem0 OSS đọc OPENAI_API_KEY
    os.environ.setdefault("OPENAI_API_KEY", oai)
    try:
        from mem0 import Memory

        state_dir = Path(cfg["state_dir"]) / "mem0"
        state_dir.mkdir(parents=True, exist_ok=True)
        qdrant_path = str(state_dir / "qdrant")
        history_db = str(state_dir / "history.db")
        model = (os.getenv("MODEL_NAME") or "gpt-4o-mini").strip()
        # Model standup/agent có thể không hỗ trợ extract — dùng mini nếu tên lạ
        if model.startswith("gpt-6") or "luna" in model.lower():
            llm_model = "gpt-4o-mini"
        else:
            llm_model = model

        config = {
            "llm": {
                "provider": "openai",
                "config": {"model": llm_model, "api_key": oai},
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "api_key": oai,
                },
            },
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "collection_name": "digitalboo_memories",
                    "path": qdrant_path,
                    "embedding_model_dims": 1536,
                },
            },
            "history_db_path": history_db,
        }
        return "oss", Memory.from_config(config)
    except Exception as e:
        log.warning("Mem0 OSS init failed: %s", e)
        return None, None


def enabled() -> bool:
    mode, client = _backend()
    return client is not None


def mode_name() -> str | None:
    mode, client = _backend()
    return mode if client is not None else None


def search_memories(
    query: str,
    *,
    user_id: str,
    limit: int = 8,
) -> list[str]:
    """Truy hồi fact dài hạn liên quan query."""
    mode, client = _backend()
    if client is None or not (query or "").strip():
        return []
    q = (query or "").strip()
    try:
        if mode == "platform":
            try:
                raw = client.search(q, filters={"user_id": user_id}, limit=limit)
            except TypeError:
                raw = client.search(q, user_id=user_id, limit=limit)
        else:
            try:
                raw = client.search(q, filters={"user_id": user_id}, limit=limit)
            except TypeError:
                raw = client.search(q, user_id=user_id, limit=limit)
    except Exception as e:
        log.warning("Mem0 search failed: %s", e)
        return []
    return _extract_memory_texts(raw, limit=limit)


def add_exchange(
    *,
    user_id: str,
    user_text: str,
    assistant_text: str,
    session_id: Optional[str] = None,
) -> bool:
    """Lưu cặp user/assistant để Mem0 trích fact."""
    mode, client = _backend()
    if client is None:
        return False
    user_text = (user_text or "").strip()
    assistant_text = (assistant_text or "").strip()
    if not user_text:
        return False
    messages = [{"role": "user", "content": user_text}]
    if assistant_text:
        messages.append({"role": "assistant", "content": assistant_text})
    meta: dict[str, Any] = {}
    if session_id:
        meta["session_id"] = session_id
    try:
        kwargs: dict[str, Any] = {"user_id": user_id}
        if meta:
            kwargs["metadata"] = meta
        client.add(messages, **kwargs)
        return True
    except Exception as e:
        log.warning("Mem0 add failed (%s): %s", mode, e)
        return False


def _extract_memory_texts(raw: Any, *, limit: int = 8) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        items = list(raw.get("results") or raw.get("memories") or [])
    elif isinstance(raw, list):
        items = raw
    else:
        return []

    out: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("memory")
                or item.get("text")
                or item.get("content")
                or ""
            ).strip()
        else:
            continue
        if text and text not in out:
            out.append(text)
        if len(out) >= limit:
            break
    return out
