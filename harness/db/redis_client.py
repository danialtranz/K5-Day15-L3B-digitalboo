"""Redis client: OAuth state, job locks, pub/sub nhẹ."""
from __future__ import annotations

from typing import Optional

import redis

from harness.config import settings

_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings()["redis_url"], decode_responses=True)
    return _client


def acquire_lock(key: str, ttl_sec: int = 120) -> bool:
    return bool(get_redis().set(key, "1", nx=True, ex=ttl_sec))


def release_lock(key: str) -> None:
    get_redis().delete(key)


def set_oauth_state(state: str, payload: str, ttl_sec: int = 600) -> None:
    get_redis().setex(f"oauth:state:{state}", ttl_sec, payload)


def pop_oauth_state(state: str) -> Optional[str]:
    r = get_redis()
    key = f"oauth:state:{state}"
    val = r.get(key)
    if val is not None:
        r.delete(key)
    return val
