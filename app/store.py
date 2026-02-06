from __future__ import annotations

import json
import time
from typing import Any

from redis import Redis

from app.settings import settings


def redis_conn() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=True)


def job_key(job_id: str) -> str:
    return f"job:{job_id}"


def set_state(job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    r = redis_conn()
    k = job_key(job_id)
    raw = r.get(k)
    data: dict[str, Any] = {}
    if raw:
        try:
            data = json.loads(raw)
        except Exception:
            data = {}
    data.update(patch)
    data.setdefault("created_at", int(time.time()))
    data["updated_at"] = int(time.time())
    r.set(k, json.dumps(data))
    r.expire(k, settings.job_ttl_hours * 3600)
    return data


def get_state(job_id: str) -> dict[str, Any] | None:
    r = redis_conn()
    raw = r.get(job_key(job_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None
