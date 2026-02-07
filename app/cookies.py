from __future__ import annotations

import base64
import os
from pathlib import Path


def ensure_cookiefile() -> str:
    """Return a valid cookiefile path if available.

    Supported inputs:
    - YTDLP_COOKIES: filesystem path to a Netscape cookies.txt
    - YTDLP_COOKIES_B64: base64-encoded cookies.txt content (optional)

    If YTDLP_COOKIES is set but the file does not exist, we ignore it
    to avoid breaking the service.
    """

    download_dir = (os.getenv("DOWNLOAD_DIR") or "/data").strip() or "/data"
    cookie_path = (os.getenv("YTDLP_COOKIES") or "").strip()
    cookie_b64 = (os.getenv("YTDLP_COOKIES_B64") or "").strip()

    if cookie_b64:
        if not cookie_path:
            cookie_path = str(Path(download_dir) / "cookies.txt")

        p = Path(cookie_path)
        p.parent.mkdir(parents=True, exist_ok=True)

        raw = cookie_b64
        # tolerate missing padding
        pad = (-len(raw)) % 4
        if pad:
            raw = raw + ("=" * pad)

        data = base64.b64decode(raw.encode("ascii"))
        p.write_bytes(data)

        try:
            os.chmod(str(p), 0o600)
        except Exception:
            pass

        return str(p)

    if cookie_path and Path(cookie_path).exists():
        return cookie_path

    # Convenience fallback: if a cookies.txt exists in the shared volume,
    # use it even if env vars are not set (helps when only one service got env).
    default_path = Path(download_dir) / "cookies.txt"
    if default_path.exists():
        return str(default_path)

    return ""
