from __future__ import annotations

import time

from redis import Redis
from redis.exceptions import ConnectionError
from rq import Queue, Worker
from rq.connections import Connection

from app.settings import settings


def main() -> None:
    # Wait for Redis to be reachable; EasyPanel networks can come up slightly later.
    while True:
        try:
            redis = Redis.from_url(settings.redis_url)
            redis.ping()
            break
        except ConnectionError:
            time.sleep(2)
        except Exception:
            time.sleep(2)

    with Connection(redis):
        worker = Worker([Queue("downloads")])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
