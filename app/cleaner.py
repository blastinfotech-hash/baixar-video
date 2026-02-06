from __future__ import annotations

import json
import os
import time

from redis import Redis
from redis.exceptions import ConnectionError

from app.settings import settings


def cleanup_once() -> None:
    now = int(time.time())
    cutoff = now - (settings.job_ttl_hours * 3600)

    os.makedirs(settings.download_dir, exist_ok=True)

    # Delete old files
    for name in os.listdir(settings.download_dir):
        path = os.path.join(settings.download_dir, name)
        try:
            st = os.stat(path)
        except Exception:
            continue
        if int(st.st_mtime) < cutoff:
            try:
                os.remove(path)
            except Exception:
                pass

    # Delete old job states (extra safety; Redis TTL also applies)
    r = Redis.from_url(settings.redis_url, decode_responses=True)
    cursor = 0
    while True:
        cursor, keys = r.scan(cursor=cursor, match="job:*", count=200)
        for k in keys:
            raw = r.get(k)
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            created_at = int(data.get("created_at") or 0)
            if created_at and created_at < cutoff:
                r.delete(k)
        if cursor == 0:
            break


def main() -> None:
    interval = int(os.getenv("CLEAN_INTERVAL_SECONDS", str(settings.clean_interval_seconds)))
    while True:
        try:
            cleanup_once()
        except ConnectionError:
            # Redis/network may not be ready yet; retry later.
            pass
        except Exception:
            # Keep the container alive even if a cleanup iteration fails.
            pass
        time.sleep(interval)


if __name__ == "__main__":
    main()
