from __future__ import annotations

import os
import shlex
import subprocess
from typing import Any

from app.cookies import ensure_cookiefile


def run_ydlp_debug(url: str) -> dict[str, Any]:
    """Run yt-dlp via subprocess and return stdout/stderr.

    This is meant for internal debugging only.
    """

    cookiefile = ensure_cookiefile()

    base_cmd = ["yt-dlp", "--ignore-config", "--no-playlist", "--no-warnings", "--verbose"]
    if cookiefile:
        base_cmd += ["--cookies", cookiefile]

    # 1) list formats
    cmd_F = base_cmd + ["-F", url]
    p1 = subprocess.run(cmd_F, capture_output=True, text=True)

    # 2) dump json (metadata)
    cmd_J = base_cmd + ["-J", url]
    p2 = subprocess.run(cmd_J, capture_output=True, text=True)

    def pack(cmd: list[str], p: subprocess.CompletedProcess[str]) -> dict[str, Any]:
        return {
            "cmd": " ".join(shlex.quote(x) for x in cmd),
            "returncode": p.returncode,
            "stdout": (p.stdout or "")[-20000:],
            "stderr": (p.stderr or "")[-20000:],
        }

    return {
        "cookiefile": cookiefile,
        "formats": pack(cmd_F, p1),
        "json": pack(cmd_J, p2),
    }
