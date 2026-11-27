"""Công cụ của bài toán — digitalboo · daily standup từ ghi chú."""
import json
import os

from tracing import tool, TOOLS  # noqa: F401

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")


def _load_json(name: str):
    path = os.path.join(DATA, name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@tool
def get_standup_policy() -> dict:
    """Đọc quy tắc daily standup (cửa sổ giờ, field form).
    Input: không. Output: dict policy (window, fields, rules). Không tác động ra ngoài."""
    return _load_json("standup_policy.json")


@tool
def get_user_notes(user_id: str) -> dict:
    """Lấy ghi chú standup đã lưu của user giả.
    Input: user_id (str). Output: {"user_id", "notes", "updated_at", "found"}. Không tác động ra ngoài."""
    db = _load_json("notes.json")
    row = db.get(user_id)
    if not row:
        return {"user_id": user_id, "notes": "", "updated_at": None, "found": False}
    notes = (row.get("notes") or "").strip()
    return {
        "user_id": user_id,
        "notes": notes,
        "updated_at": row.get("updated_at"),
        "found": bool(notes),
    }
