"""Router CU: scripted playbook (Edufun) hoặc vision."""
from __future__ import annotations

from typing import Any

from harness.computer_use.playbook import match_playbook, resolve_strategy
from harness.computer_use.standup import fill_and_submit
from harness.computer_use.vision import fill_and_submit_vision


def run_fill(
    page,
    fields: dict[str, str],
    *,
    url: str | None = None,
    user_id: str = "u1",
) -> dict[str, Any]:
    target = url or page.url
    strategy = resolve_strategy(target)
    if strategy == "scripted":
        pb = match_playbook(target) or match_playbook(page.url)
        result = fill_and_submit(page, fields, playbook=pb)
        result.setdefault("strategy", "scripted")
        return result

    result = fill_and_submit_vision(
        page,
        fields,
        user_id=user_id,
        start_url=target,
    )
    result.setdefault("strategy", "vision")
    return result
