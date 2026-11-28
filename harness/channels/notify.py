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


def _escape_xml(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _desktop_toast(title: str, body: str) -> bool:
    """Toast Action Center Windows 10/11 (ra ngoài app). Balloon tip cũ Win11 thường không hiện."""
    if sys.platform != "win32":
        return False
    title = _escape_xml((title or "digitalboo")[:120])
    body = _escape_xml((body or "")[:400])
    app_id = "digitalboo.demo"
    xml = (
        '<?xml version="1.0" encoding="utf-8"?>'
        "<toast activationType=\"foreground\">"
        "<visual><binding template=\"ToastGeneric\">"
        f"<text>{title}</text><text>{body}</text>"
        "</binding></visual></toast>"
    )
    ensure_dirs()
    outbox = Path(settings()["outbox_dir"])
    tmp = outbox / f"_toast-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.xml"
    try:
        tmp.write_text(xml, encoding="utf-8")
        tmp_ps = _escape_ps_single(str(tmp.resolve()))
        ps = f"""
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType = WindowsRuntime] | Out-Null
$xml = Get-Content -LiteralPath '{tmp_ps}' -Raw -Encoding UTF8
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$toast = [Windows.UI.Notifications.ToastNotification]::new($doc)
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{app_id}')
$notifier.Show($toast)
Start-Sleep -Milliseconds 400
Remove-Item -LiteralPath '{tmp_ps}' -Force -ErrorAction SilentlyContinue
"""
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
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
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
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
    # Poll với since_id: cũ → mới. Lần đầu (không since_id): mới nhất trước (để app seed cursor, không spam toast lịch sử).
    order = "ASC" if since_id is not None else "DESC"
    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, kind, title, body, meta, created_at, read_at
            FROM notifications
            WHERE {where}
            ORDER BY id {order}
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
