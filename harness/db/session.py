"""Postgres connection + schema init."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from harness.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    user_id         TEXT PRIMARY KEY,
    display_name    TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id      TEXT PRIMARY KEY,
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chat_history (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id),
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    flow            TEXT,
    meta            JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chat_history_session_idx
    ON chat_history (session_id, id);

CREATE TABLE IF NOT EXISTS hitl_checkpoints (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(session_id),
    user_id         TEXT NOT NULL REFERENCES users(user_id),
    intent          TEXT NOT NULL,
    state           JSONB NOT NULL DEFAULT '{}',
    missing_fields  JSONB NOT NULL DEFAULT '[]',
    status          TEXT NOT NULL DEFAULT 'interrupted',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS hitl_checkpoints_session_pending_idx
    ON hitl_checkpoints (session_id)
    WHERE status = 'interrupted';

CREATE TABLE IF NOT EXISTS email_accounts (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,
    provider        TEXT NOT NULL DEFAULT 'google',
    email_address   TEXT,
    access_token    TEXT NOT NULL,
    refresh_token   TEXT,
    expires_at      TIMESTAMPTZ,
    scopes          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, provider)
);

CREATE TABLE IF NOT EXISTS mail_seen (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,
    provider        TEXT NOT NULL DEFAULT 'google',
    message_id      TEXT NOT NULL,
    seen_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, provider, message_id)
);

CREATE TABLE IF NOT EXISTS notifications (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,
    kind            TEXT NOT NULL,
    title           TEXT NOT NULL,
    body            TEXT NOT NULL,
    meta            JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read_at         TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS standup_grants (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL UNIQUE,
    site_id         TEXT NOT NULL,
    url             TEXT NOT NULL,
    allow_submit    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_runs (
    id              SERIAL PRIMARY KEY,
    user_id         TEXT NOT NULL,
    job_type        TEXT NOT NULL,
    day_key         TEXT,
    status          TEXT NOT NULL,
    detail          JSONB,
    artifact_path   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS job_runs_dedupe
    ON job_runs (user_id, job_type, day_key)
    WHERE day_key IS NOT NULL AND status = 'ok';
"""


def init_db() -> None:
    with get_connection() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()
    from harness.db.auth import seed_users

    seed_users()


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(settings()["database_url"], row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()
