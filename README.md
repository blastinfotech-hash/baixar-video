# baixar

Internal YouTube downloader for a team, running behind EasyPanel with HTTPS.

## What it includes

- Web UI + API (FastAPI)
- Background jobs (RQ + Redis)
- Cleanup job (deletes files/metadata after 24h)
- `yt-dlp` + `ffmpeg` for download/merge/conversion

## Quick local run

Requirements: Docker.

```bash
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

Open:
- http://localhost:8090

## EasyPanel

Create one app called `baixar` using Docker Compose from this folder.
Point `baixar.blastinfo.cloud` to the `baixar_web` service port `8090`.

Notes:
- This compose ships with its own Redis service (no external dependency).
- If you prefer using an existing Redis (e.g. `blast_redis:6379`), override `REDIS_URL` and ensure the app can resolve that hostname in the same Docker network.
