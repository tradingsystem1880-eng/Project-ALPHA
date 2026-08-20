#!/usr/bin/env python3
"""Claude Code status line for Project ALPHA.

One glance shows: branch · dirty-file count · gate stamp state (tier + valid
for the current tree?) · pending attestation obligations. Reads the status
JSON Claude Code pipes on stdin, resolves the session's repo root from it,
and reuses scripts/gate.py as the single source of truth. Never raises: a
broken harness must degrade to a plain branch display, not a hidden error.
"""

from __future__ import annotations

import json
import re
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

    stamp_part = "gate:none"
    pending: list[str] = []
    try:
        sys.path.insert(0, str(root / "scripts"))
        import gate

        tier, fresh = gate.stamp_state(root)
        if tier != "none":
            stamp_part = f"gate:{tier}✓" if fresh else f"gate:{tier}-stale"

        quant_paths = gate.scoped_changed_paths(root, gate.matches_quant)
        if quant_paths and not gate.quant_attestation_valid(root):
            pending.append("quant-attest")
        if (root / gate.STATE_DIR / gate.OVERRIDE_FILE).exists():
            pending.append("override-armed")
        if (root / gate.STATE_DIR / gate.ACK_FILE).exists():
            pending.append("ack-armed")
        # A12: a session that exhausted its Stop budget left UNVERIFIED edits behind;
        # the flag stays until a gate passes for the current tree.
        session_id = str(payload.get("session_id") or "")
        if session_id and not fresh:
            safe = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)
            state = gate.read_json(root / gate.STATE_DIR / f"session-{safe}.json")
            if state and state.get("stop_budget_exhausted"):
                pending.append("STOP-BUDGET-EXHAUSTED")
        if not gate.owner_token_configured(root):
            pending.append("owner-token-unset")
    except Exception:
        pass

    parts = [branch, f"±{dirty}", stamp_part]
    if pending:
        parts.append("needs:" + ",".join(pending))
    print(" · ".join(parts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
