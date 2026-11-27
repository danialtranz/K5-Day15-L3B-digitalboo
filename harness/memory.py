"""Định dạng lịch sử chat cùng session + long-term Mem0 cho prompt LLM."""
from __future__ import annotations

from typing import Any, Optional


def format_chat_history(
    messages: list[dict[str, Any]],
    *,
    limit: int = 40,
    max_chars: int = 8000,
) -> str:
    """Lấy tối đa `limit` tin gần nhất, cắt theo max_chars."""
    if not messages:
        return "(chưa có lịch sử)"
    slice_msgs = messages[-limit:]
    lines: list[str] = []
    for m in slice_msgs:
        role = (m.get("role") or "user").upper()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = "…\n" + text[-max_chars:]
    return text or "(chưa có lịch sử)"


def format_longterm(memories: list[str], *, max_chars: int = 2000) -> str:
    """Định dạng fact Mem0 để nhét vào prompt."""
    clean = [m.strip() for m in memories if (m or "").strip()]
    if not clean:
        return ""
    lines = ["Ghi nhớ dài hạn về user (Mem0 — sống qua nhiều session):"]
    for m in clean:
        lines.append(f"- {m}")
    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[: max_chars - 1] + "…"
    return text


def with_history(
    history_text: Optional[str],
    current_user: str,
    extra: str = "",
    longterm_text: str = "",
) -> str:
    parts: list[str] = []
    if (longterm_text or "").strip():
        parts.extend([longterm_text.strip(), ""])
    parts.extend(
        [
            "Lịch sử hội thoại cùng session (cũ → mới):",
            history_text or "(chưa có lịch sử)",
            "",
            "Tin nhắn hiện tại của user:",
            current_user,
        ]
    )
    if extra:
        parts.extend(["", extra])
    return "\n".join(parts)
