#!/usr/bin/env python3
"""Claude Code status line for Project ALPHA: branch and dirty-file count.

Reads the status JSON Claude Code pipes on stdin and resolves the session's repo root from it.
Never raises: a broken harness must degrade to a plain display, not a hidden error.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    cwd = Path(
        (payload.get("workspace") or {}).get("current_dir") or payload.get("cwd") or Path.cwd()
    )

    top = _git(cwd, "rev-parse", "--show-toplevel")
    if not top:
        print("alpha · no repo")
        return 0
    root = Path(top)

    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    status = _git(root, "status", "--porcelain")
    dirty = len([line for line in status.splitlines() if line.strip()])
    print(f"{branch} · ±{dirty}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
