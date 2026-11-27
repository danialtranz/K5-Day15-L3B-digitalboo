"""Định dạng lịch sử chat cùng session cho prompt LLM."""
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


def with_history(history_text: Optional[str], current_user: str, extra: str = "") -> str:
    parts = [
        "Lịch sử hội thoại cùng session (cũ → mới):",
        history_text or "(chưa có lịch sử)",
        "",
        "Tin nhắn hiện tại của user:",
        current_user,
    ]
    if extra:
        parts.extend(["", extra])
    return "\n".join(parts)
