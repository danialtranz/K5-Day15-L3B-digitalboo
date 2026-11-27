"""Ghi notification vào Postgres + file outbox + toast desktop Windows."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from harness.config import ensure_dirs, settings
from harness.db.session import get_connection


def _escape_ps_single(s: str) -> str:
    return (s or "").replace("'", "''")


def _desktop_toast(title: str, body: str) -> bool:
    """Hiện toast/balloon ngay trên desktop Windows. Trả True nếu gửi được."""
    if sys.platform != "win32":
        return False
    title = (title or "digitalboo")[:120]
    body = (body or "")[:400]
    # Balloon tip qua NotifyIcon — không cần thư viện ngoài, chạy nền.
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.BalloonTipTitle = '{_escape_ps_single(title)}'
$n.BalloonTipText = '{_escape_ps_single(body)}'
$n.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$n.ShowBalloonTip(8000)
Start-Sleep -Milliseconds 8500
$n.Dispose()
"""
    try:
        subprocess.Popen(
            [
                "powershell",
                "-NoProfile",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return True
    except Exception as e:
        print(f"[notify] desktop toast failed: {e}")
        return False


def push(
    user_id: str,
    kind: str,
    title: str,
    body: str,
    meta: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    ensure_dirs()
    meta = meta or {}
    with get_connection() as conn:
        row = conn.execute(
            """
            INSERT INTO notifications (user_id, kind, title, body, meta)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            RETURNING id, created_at
            """,
            (user_id, kind, title, body, json.dumps(meta)),
        ).fetchone()
        conn.commit()

    outbox = Path(settings()["outbox_dir"])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = outbox / f"{stamp}-{kind}-{row['id']}.md"
    path.write_text(
        f"# {title}\n\nuser: {user_id}\nkind: {kind}\n\n{body}\n",
        encoding="utf-8",
    )
    desktop = _desktop_toast(title, body)
    print(f"[notify] {title} → {path}" + (" + desktop" if desktop else ""))
    return {
        "id": row["id"],
        "path": str(path),
        "created_at": str(row["created_at"]),
        "desktop": desktop,
    }


def list_notifications(
    user_id: str,
    limit: int = 50,
    *,
    unread_only: bool = False,
    since_id: Optional[int] = None,
) -> list[dict[str, Any]]:
    clauses = ["user_id = %s"]
    params: list[Any] = [user_id]
    if unread_only:
        clauses.append("read_at IS NULL")
    if since_id is not None:
        clauses.append("id > %s")
        params.append(since_id)
    where = " AND ".join(clauses)
    params.append(limit)
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, kind, title, body, meta, created_at, read_at
            FROM notifications
            WHERE {where}
            ORDER BY id ASC
            LIMIT %s
            """,
            tuple(params),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_read(notification_id: int, user_id: str) -> Optional[dict[str, Any]]:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE notifications
            SET read_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id, kind, title, body, meta, created_at, read_at
            """,
            (notification_id, user_id),
        ).fetchone()
        conn.commit()
    return dict(row) if row else None


def mark_all_read(user_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            """
            UPDATE notifications
            SET read_at = NOW()
            WHERE user_id = %s AND read_at IS NULL
            """,
            (user_id,),
        )
        conn.commit()
        return row.rowcount or 0
