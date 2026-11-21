"""Which code built the screen, and which code is running now (the staleness signal).

``npm run build`` writes ``build-info.json`` next to ``index.html``. ``/healthz`` returns it with
the commit of the running Python code, so the screen can tell the owner when the two differ.
"""

from __future__ import annotations

import json
import subprocess
from functools import lru_cache
from pathlib import Path

_UNKNOWN = "unknown"


def read_build_info(app_dir: Path) -> dict[str, str]:
    """Return the commit and time recorded in the built bundle; ``unknown`` if absent or bad."""
    try:
        raw = json.loads((app_dir / "build-info.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"build_commit": _UNKNOWN, "build_time": _UNKNOWN}
    if not isinstance(raw, dict):
        return {"build_commit": _UNKNOWN, "build_time": _UNKNOWN}
    commit = raw.get("commit")
    built_at = raw.get("built_at")
    return {
        "build_commit": commit if isinstance(commit, str) and commit else _UNKNOWN,
        "build_time": built_at if isinstance(built_at, str) and built_at else _UNKNOWN,
    }


@lru_cache(maxsize=1)
def code_commit() -> str:
    """Return the git commit of the running Python code; ``unknown`` outside a git checkout."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return _UNKNOWN
    commit = done.stdout.strip()
    return commit if done.returncode == 0 and commit else _UNKNOWN
