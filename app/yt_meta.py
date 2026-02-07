from __future__ import annotations

from typing import Any
from typing import cast

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

    with yt_dlp.YoutubeDL(cast(Any, ydl_opts)) as ydl:
        info = ydl.extract_info(url, download=False)

    fmts = info.get("formats") or []

    video_formats: list[dict[str, Any]] = []
    audio_formats: list[dict[str, Any]] = []

    for f in fmts:
        fmt_id = str(f.get("format_id") or "").strip()
        if not fmt_id:
            continue

        ext = (f.get("ext") or "").strip()
        vcodec = f.get("vcodec") or "none"
        acodec = f.get("acodec") or "none"
        height = int(f.get("height") or 0)
        fps = f.get("fps") or 0
        abr = f.get("abr") or 0
        filesize = f.get("filesize") or f.get("filesize_approx") or 0
        size = _size_mb(filesize)

        if vcodec != "none":
            # prefer formats that include a height
            label = f"{height}p" if height else "video"
            label = f"{label} {fps}fps" if fps else label
            label = f"{label} {ext}" if ext else label
            if acodec != "none":
                label = f"{label} (va)"
            else:
                label = f"{label} (v)"
            if size:
                label = f"{label} {size}"
            label = f"{label} id={fmt_id}"
            video_formats.append({"format_id": fmt_id, "label": label, "height": height})
        elif acodec != "none":
            label = f"{int(abr)}kbps" if abr else "audio"
            label = f"{label} {ext}" if ext else label
            if size:
                label = f"{label} {size}"
            label = f"{label} id={fmt_id}"
            audio_formats.append({"format_id": fmt_id, "label": label, "abr": abr})

    video_formats.sort(key=lambda x: int(x.get("height") or 0), reverse=True)
    audio_formats.sort(key=lambda x: float(x.get("abr") or 0), reverse=True)

    return {
        "title": info.get("title") or "",
        "duration": info.get("duration") or 0,
        "video_formats": video_formats,
        "audio_formats": audio_formats,
    }
