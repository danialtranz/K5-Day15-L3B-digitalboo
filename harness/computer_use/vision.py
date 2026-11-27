"""Vision computer-use: screenshot → multimodal LLM → click/type (standup only)."""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from harness.computer_use.playbook import looks_like_login, vision_config
from harness.config import ensure_dirs, settings

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "codebase") not in sys.path:
    sys.path.insert(0, str(ROOT / "codebase"))

VISION_SYSTEM = """Bạn là computer-use agent điền form daily standup trên trình duyệt.
Chỉ trả về ĐÚNG một JSON object, không markdown.
Schema action (một trong các op):
{"op":"click","x":number,"y":number}
{"op":"fill_at","x":number,"y":number,"text":string}
{"op":"type","text":string}
{"op":"press","key":string}
{"op":"scroll","dy":number}
{"op":"need_login"}
{"op":"done","ok":boolean,"reason":string}

Quy tắc:
- Tọa độ x,y theo viewport ảnh (gốc góc trên-trái), đơn vị pixel.
- Nhiệm vụ: điền yesterday / today / blockers (nếu có) rồi bấm nộp/submit.
- Không bịa nội dung — chỉ dùng text được cung cấp trong user message.
- Không điền mật khẩu / OTP. Nếu thấy trang login → need_login.
- Khi đã nộp thành công (thấy thông báo success / form đã submit) → done ok=true.
- Nếu không thể → done ok=false kèm reason ngắn.
"""


def _extract_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        return {}
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.S)
    if fence:
        raw = fence.group(1)
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            raw = raw[start : end + 1]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _exec_action(page, action: dict[str, Any], viewport: dict[str, int]) -> str | None:
    """Thực thi 1 action. Trả error string hoặc None."""
    op = str(action.get("op") or "").strip().lower()
    w = max(1, int(viewport.get("width") or 1280))
    h = max(1, int(viewport.get("height") or 800))

    if op == "click":
        x = _clamp(float(action.get("x") or 0), 0, w - 1)
        y = _clamp(float(action.get("y") or 0), 0, h - 1)
        page.mouse.click(x, y)
        page.wait_for_timeout(400)
        return None

    if op == "fill_at":
        x = _clamp(float(action.get("x") or 0), 0, w - 1)
        y = _clamp(float(action.get("y") or 0), 0, h - 1)
        text = str(action.get("text") or "")
        page.mouse.click(x, y)
        page.wait_for_timeout(200)
        # chọn hết rồi gõ
        page.keyboard.press("Control+A")
        page.keyboard.type(text, delay=5)
        page.wait_for_timeout(300)
        return None

    if op == "type":
        text = str(action.get("text") or "")
        page.keyboard.type(text, delay=5)
        page.wait_for_timeout(200)
        return None

    if op == "press":
        key = str(action.get("key") or "Enter")
        page.keyboard.press(key)
        page.wait_for_timeout(300)
        return None

    if op == "scroll":
        dy = int(action.get("dy") or 400)
        page.mouse.wheel(0, dy)
        page.wait_for_timeout(300)
        return None

    if op in ("need_login", "done"):
        return None

    return f"op không hỗ trợ: {op}"


def fill_and_submit_vision(
    page,
    fields: dict[str, str],
    *,
    user_id: str = "u1",
    start_url: str | None = None,
) -> dict[str, Any]:
    from ai import call_model_vision  # type: ignore

    ensure_dirs()
    s = settings()
    vcfg = vision_config()
    try:
        max_steps = max(1, int(vcfg.get("max_steps") or 12))
    except (TypeError, ValueError):
        max_steps = 12

    target = start_url or page.url
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    artifacts: list[str] = []
    tokens_in = 0
    tokens_out = 0
    actions_log: list[dict[str, Any]] = []

    yesterday = (fields.get("yesterday") or "").strip()
    today = (fields.get("today") or "").strip()
    blockers = (fields.get("blockers") or "").strip()

    for step in range(1, max_steps + 1):
        if looks_like_login(page.url):
            return {
                "submitted": False,
                "need_login": True,
                "error": "need_login",
                "url": page.url,
                "message": (
                    "Trang đang yêu cầu đăng nhập. "
                    "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong."
                ),
                "strategy": "vision",
                "steps": step,
                "actions": actions_log,
                "artifact_path": artifacts[-1] if artifacts else None,
                "artifacts": artifacts,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }

        viewport = page.viewport_size or {"width": 1280, "height": 800}
        png = page.screenshot(type="png", full_page=False)
        shot_path = Path(s["artifacts_dir"]) / f"vision-{stamp}-step{step}.png"
        try:
            shot_path.write_bytes(png)
            artifacts.append(str(shot_path))
        except Exception:
            pass

        user_prompt = (
            f"Bước {step}/{max_steps}. URL hiện tại: {page.url}\n"
            f"Viewport: {viewport.get('width')}x{viewport.get('height')}\n"
            f"yesterday: {yesterday}\n"
            f"today: {today}\n"
            f"blockers: {blockers or '(trống — bỏ qua nếu optional)'}\n"
            "Nhìn ảnh viewport và chọn ĐÚNG một action JSON tiếp theo."
        )
        try:
            reply = call_model_vision(VISION_SYSTEM, user_prompt, png)
        except Exception as e:
            return {
                "submitted": False,
                "error": f"Vision LLM lỗi: {e}",
                "strategy": "vision",
                "steps": step,
                "actions": actions_log,
                "artifact_path": artifacts[-1] if artifacts else None,
                "artifacts": artifacts,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }

        tokens_in += int(reply.get("tokens_in") or 0)
        tokens_out += int(reply.get("tokens_out") or 0)
        action = _extract_json(reply.get("text") or "")
        if not action:
            actions_log.append({"step": step, "raw": (reply.get("text") or "")[:300], "error": "bad_json"})
            continue

        op = str(action.get("op") or "").strip().lower()
        actions_log.append({"step": step, "action": action})

        if op == "need_login":
            return {
                "submitted": False,
                "need_login": True,
                "error": "need_login",
                "url": page.url,
                "message": (
                    "Trang đang yêu cầu đăng nhập. "
                    "Hãy đăng nhập trên cửa sổ trình duyệt rồi nhắn mình khi xong."
                ),
                "strategy": "vision",
                "steps": step,
                "actions": actions_log,
                "artifact_path": artifacts[-1] if artifacts else None,
                "artifacts": artifacts,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
            }

        if op == "done":
            ok = bool(action.get("ok"))
            reason = str(action.get("reason") or "")
            final = artifacts[-1] if artifacts else None
            return {
                "submitted": ok,
                "error": None if ok else (reason or "Vision báo thất bại"),
                "url": page.url,
                "strategy": "vision",
                "steps": step,
                "actions": actions_log,
                "artifact_path": final,
                "artifacts": artifacts,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "reason": reason,
            }

        err = _exec_action(page, action, viewport)
        if err:
            actions_log[-1]["error"] = err

    final = artifacts[-1] if artifacts else None
    return {
        "submitted": False,
        "error": f"Hết {max_steps} bước vision mà chưa done.",
        "url": page.url,
        "strategy": "vision",
        "steps": max_steps,
        "actions": actions_log,
        "artifact_path": final,
        "artifacts": artifacts,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
    }
