from __future__ import annotations

import os
from typing import Any

from redis import Redis
from rq import Queue

from app.settings import settings
from app.store import get_state, set_state
from app.yt_job import run_download


def rq_conn() -> Redis:
    return Redis.from_url(settings.redis_url)


def q() -> Queue:
    return Queue("downloads", connection=rq_conn())


def enqueue_download(*, url: str, format_id: str, container: str, mode: str) -> str:
    os.makedirs(settings.download_dir, exist_ok=True)

    job = q().enqueue(
        run_download,
        kwargs={
            "url": url,
            "format_id": format_id,
            "container": container,
            "mode": mode,
            "download_dir": settings.download_dir,
            "redis_url": settings.redis_url,
            "job_ttl_hours": settings.job_ttl_hours,
        },
        job_timeout="2h",
        result_ttl=settings.job_ttl_hours * 3600,
        failure_ttl=settings.job_ttl_hours * 3600,
    )

    set_state(
        job.id,
        {
            "job_id": job.id,
            "status": "queued",
            "progress": 0,
            "message": "queued",
            "url": url,
            "format_id": format_id,
            "container": container,
            "mode": mode,
        },
    )
    return job.id


def get_job_state(job_id: str) -> dict[str, Any] | None:
    state = get_state(job_id)
    if not state:
        return None

    if state.get("status") == "finished":
        base = settings.public_base_url.rstrip("/")
        state["download_url"] = f"{base}/download/{job_id}" if base else f"/download/{job_id}"
    return state
