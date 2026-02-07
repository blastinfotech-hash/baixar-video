from __future__ import annotations

import os
import re
from typing import Any

from redis import Redis
from rq import get_current_job

from app.cookies import ensure_cookiefile


def _safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9._ -]+", "", s)
    s = re.sub(r"\s+", " ", s)
    return s[:140] if s else "download"


def run_download(
    *,
    url: str,
    format_id: str,
    container: str,
    mode: str,
    download_dir: str,
    redis_url: str,
    job_ttl_hours: int,
) -> dict[str, Any]:
    import yt_dlp

    job = get_current_job()
    job_id = job.id if job else ""
    if not job_id:
        raise RuntimeError("missing rq job id")

    r = Redis.from_url(redis_url, decode_responses=True)

    def set_state(patch: dict[str, Any]) -> None:
        # Write job state to Redis with TTL.
        import json, time

        k = f"job:{job_id}"
        raw = r.get(k)
        data: dict[str, Any] = {}
        if raw:
            try:
                data = json.loads(raw)
            except Exception:
                data = {}
        data.update(patch)
        data.setdefault("job_id", job_id)
        data.setdefault("created_at", int(time.time()))
        data["updated_at"] = int(time.time())
        r.set(k, json.dumps(data))
        r.expire(k, job_ttl_hours * 3600)

    os.makedirs(download_dir, exist_ok=True)
    set_state({"status": "started", "progress": 1, "message": "starting"})

    # Pre-fetch metadata so we can understand if selected format has audio.
    ydl_meta_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "ignoreconfig": True,
    }

    cookiefile = ensure_cookiefile()
    if cookiefile:
        ydl_meta_opts["cookiefile"] = cookiefile
    def extract_meta(opts: dict[str, Any]) -> dict[str, Any]:
        with yt_dlp.YoutubeDL(opts) as ydl:
            return ydl.extract_info(url, download=False)

    try:
        info = extract_meta(ydl_meta_opts)
    except Exception as e:
        if "Requested format is not available" in str(e):
            retry_meta = dict(ydl_meta_opts)
            retry_meta["format"] = "best"
            info = extract_meta(retry_meta)
        else:
            raise

    title = (info.get("title") or "").strip()
    safe_title = _safe_filename(title)

    selected = None
    for f in (info.get("formats") or []):
        if str(f.get("format_id") or "") == str(format_id):
            selected = f
            break
    if not selected:
        raise RuntimeError("format_id not found")

    vcodec = selected.get("vcodec") or "none"
    acodec = selected.get("acodec") or "none"

    # Output template
    outtmpl = os.path.join(download_dir, f"{job_id}-{safe_title}.%(ext)s")

    def hook(d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            pct = 0
            p = (d.get("_percent_str") or "").strip().replace("%", "")
            try:
                pct = int(float(p))
            except Exception:
                pct = 0
            msg_parts = []
            if d.get("_speed_str"):
                msg_parts.append(str(d.get("_speed_str")).strip())
            if d.get("_eta_str"):
                eta = str(d.get("_eta_str")).strip()
                msg_parts.append(f"eta {eta}")
            msg = " - ".join(msg_parts)
            set_state({"status": "downloading", "progress": max(2, min(98, pct)), "message": msg})
        elif status == "finished":
            set_state({"status": "processing", "progress": 99, "message": "processing"})

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreconfig": True,
        "outtmpl": outtmpl,
        "progress_hooks": [hook],
    }

    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    if mode == "audio_mp3":
        # Allow choosing a specific audio format id, but keep it safe.
        ydl_opts["format"] = format_id
        ydl_opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "0"}
        ]
    else:
        ydl_opts["merge_output_format"] = container
        if vcodec != "none" and acodec != "none":
            # already has audio+video
            ydl_opts["format"] = format_id
        elif vcodec != "none" and acodec == "none":
            # video only, merge bestaudio
            ydl_opts["format"] = f"{format_id}+bestaudio/best"
        else:
            # shouldn't happen in auto mode (we do not show audio-only formats there)
            ydl_opts["format"] = "best"

    def attempt_download(opts: dict[str, Any]) -> None:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)

    try:
        attempt_download(ydl_opts)
    except Exception as e:
        msg = str(e)

        # Common edge case: formats may differ between listing and download.
        # Retry with a height-based selector.
        if "Requested format is not available" in msg and mode != "audio_mp3":
            h = selected.get("height")
            try:
                h_int = int(h) if h else 0
            except Exception:
                h_int = 0

            retry_opts = dict(ydl_opts)
            if h_int:
                retry_opts["format"] = f"bestvideo[height<={h_int}]+bestaudio/best"
            else:
                retry_opts["format"] = "bestvideo+bestaudio/best"

            set_state({"status": "downloading", "progress": 2, "message": "retrying with fallback format"})
            try:
                attempt_download(retry_opts)
            except Exception as e2:
                set_state({"status": "failed", "progress": 0, "error": str(e2), "message": "failed"})
                raise
        else:
            set_state({"status": "failed", "progress": 0, "error": msg, "message": "failed"})
            raise

    produced = None
    for name in os.listdir(download_dir):
        if name.startswith(f"{job_id}-"):
            produced = os.path.join(download_dir, name)
            break
    if not produced:
        set_state({"status": "failed", "progress": 0, "error": "file not generated", "message": "failed"})
        raise RuntimeError("file not generated")

    set_state(
        {
            "status": "finished",
            "progress": 100,
            "message": "ok",
            "title": title,
            "file_path": produced,
            "file_name": os.path.basename(produced),
        }
    )

    return {"ok": True, "file_path": produced}
