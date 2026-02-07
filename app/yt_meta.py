from __future__ import annotations

from typing import Any, cast

from app.cookies import ensure_cookiefile


def _size_mb(filesize: int | float | None) -> str:
    if not filesize:
        return ""
    try:
        return f"{float(filesize)/1024/1024:.1f}MB"
    except Exception:
        return ""


def list_formats(url: str) -> dict[str, Any]:
    import yt_dlp

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        # Avoid unexpected global config (e.g. format overrides)
        "ignoreconfig": True,
    }

    cookiefile = ensure_cookiefile()
    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    def extract(opts: dict[str, Any]) -> dict[str, Any]:
        with yt_dlp.YoutubeDL(cast(Any, opts)) as ydl:
            # yt-dlp returns a typed InfoDict; treat as plain dict.
            info = ydl.extract_info(url, download=False)
            return cast(dict[str, Any], dict(info))

    try:
        info = extract(ydl_opts)
    except Exception as e:
        # Some environments end up with an implicit/leftover format constraint.
        # Retry with a safe default.
        if "Requested format is not available" in str(e):
            retry_opts = dict(ydl_opts)
            retry_opts["format"] = "best"
            info = extract(retry_opts)
        else:
            raise

    fmts = info.get("formats") or []

    # Format IDs on YouTube can be brittle (can change between listing and download).
    # For an internal tool, it's more reliable to let users choose a target resolution
    # and download using a selector: bestvideo[height<=X]+bestaudio/best
    heights: set[int] = set()
    for f in fmts:
        vcodec = f.get("vcodec") or "none"
        if vcodec == "none":
            continue
        h = int(f.get("height") or 0)
        if h:
            heights.add(h)

    video_formats: list[dict[str, Any]] = []
    for h in sorted(heights, reverse=True):
        video_formats.append(
            {
                "format_id": f"h:{h}",
                "label": f"{h}p (best video <= {h}p + best audio)",
                "height": h,
            }
        )

    # Always offer an automatic best option
    video_formats.append({"format_id": "best", "label": "Melhor disponivel (auto)", "height": 0})

    audio_formats: list[dict[str, Any]] = [
        {"format_id": "bestaudio", "label": "Melhor audio (para MP3)", "abr": 0}
    ]

    return {
        "title": info.get("title") or "",
        "duration": info.get("duration") or 0,
        "video_formats": video_formats,
        "audio_formats": audio_formats,
    }
