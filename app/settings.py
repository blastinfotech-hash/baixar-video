from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://localhost:6379/0"
    download_dir: str = "/data"
    job_ttl_hours: int = 24
    clean_interval_seconds: int = 3600
    public_base_url: str = ""
    basic_auth_user: str = ""
    basic_auth_pass: str = ""
    port: int = 8090


settings = Settings()
