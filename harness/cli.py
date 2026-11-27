"""CLI: python -m harness <command>"""
from __future__ import annotations

import argparse
import json

from harness.config import ensure_dirs, settings
from harness.db.session import init_db
from harness.flows.email_watch import run_email_watch
from harness.flows.standup_submit import run_standup_submit
from harness.jobs.scheduler import run_scheduler
from harness.jobs.store import upsert_grant
from harness.orchestrator import handle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="harness", description="digitalboo harness CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db", help="Tạo schema Postgres")

    p_grant = sub.add_parser("grant-standup", help="Grant URL standup allowlist")
    p_grant.add_argument("--url", required=True)
    p_grant.add_argument("--user-id", default=None)

    p_email = sub.add_parser("watch-email", help="Quét Gmail một lần")
    p_email.add_argument("--user-id", default=None)
    p_email.add_argument("--once", action="store_true", default=True)

    p_run = sub.add_parser("run-standup", help="Chạy fill+Submit standup")
    p_run.add_argument("--user-id", default=None)
    p_run.add_argument("--now", action="store_true", help="Bỏ qua cửa sổ giờ (force)")

    p_sched = sub.add_parser("scheduler", help="Chạy vòng cron")
    p_sched.add_argument("--once", action="store_true")

    p_ask = sub.add_parser("ask", help="Hỏi orchestrator")
    p_ask.add_argument("text")
    p_ask.add_argument("--user-id", default=None)

    p_serve = sub.add_parser("serve", help="Chạy FastAPI")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    args = parser.parse_args(argv)
    ensure_dirs()

    if args.cmd == "init-db":
        init_db()
        print("OK: schema created + seed user u1")
        return 0

    if args.cmd == "grant-standup":
        init_db()
        uid = args.user_id or settings()["default_user_id"]
        row = upsert_grant(uid, args.url)
        print(json.dumps({"ok": True, "url": row["url"], "user_id": uid}, ensure_ascii=False))
        return 0

    if args.cmd == "watch-email":
        init_db()
        print(json.dumps(run_email_watch(args.user_id), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "run-standup":
        init_db()
        print(
            json.dumps(
                run_standup_submit(args.user_id, force=bool(args.now)),
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    if args.cmd == "scheduler":
        init_db()
        run_scheduler(once=bool(args.once))
        return 0

    if args.cmd == "ask":
        init_db()
        print(json.dumps(handle(args.text, user_id=args.user_id), ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "serve":
        import uvicorn

        init_db()
        host = args.host or settings()["app_host"]
        port = args.port or settings()["app_port"]
        uvicorn.run("harness.api.main:app", host=host, port=port, reload=False)
        return 0

    return 1
