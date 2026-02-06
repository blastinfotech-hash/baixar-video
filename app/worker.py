from __future__ import annotations

from redis import Redis
from rq import Connection, Queue, Worker

from app.settings import settings


def main() -> None:
    redis = Redis.from_url(settings.redis_url)
    with Connection(redis):
        worker = Worker([Queue("downloads")])
        worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
