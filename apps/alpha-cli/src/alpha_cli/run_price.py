"""Price bars for a run that saved no snapshot, read through ``alpha data run-price``.

The check hashes stored bars with the engine's own fingerprint, so it runs in the CLI process and
this module only calls it. It returns the bars only when the CLI says they match the run's record.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
from pathlib import Path

_ALPHA_BIN = "alpha"
_TIMEOUT_S = 30.0
_ENV_NAMES = frozenset(
    {
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "PATH",
        "PYTHONPATH",
        "TMPDIR",
        "TZ",
        "VIRTUAL_ENV",
        "ALPHA_BULK_DATA_DIR",
        "ALPHA_BULK_VOLUME_UUID",
    }
)
_FIELDS = ("t", "o", "h", "l", "c", "v")
AVAILABLE = "available"
UNAVAILABLE = "price_unavailable"


def verified_bars(run_id: str, *, data_dir: Path) -> tuple[str, list[dict[str, float]]]:
    """``(status, rows)``; rows only when the status is ``available``. A refusal never raises."""
    env = {name: value for name, value in os.environ.items() if name in _ENV_NAMES}
    env["ALPHA_DATA_DIR"] = str(data_dir)
    try:
        proc = subprocess.run(
            [_ALPHA_BIN, "data", "run-price", run_id, "--json"],
            capture_output=True,
            text=True,
            env=env,
            check=False,
            timeout=_TIMEOUT_S,
        )
        payload = json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return UNAVAILABLE, []
    if not isinstance(payload, dict) or not isinstance(payload.get("status"), str):
        return UNAVAILABLE, []
    status: str = payload["status"]
    raw = payload.get("bars")
    if status != AVAILABLE or not isinstance(raw, list):
        return (status if status != AVAILABLE else UNAVAILABLE), []
    rows: list[dict[str, float]] = []
    for item in raw:
        if not isinstance(item, dict):
            return UNAVAILABLE, []
        row = {key: item.get(key) for key in _FIELDS}
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
            for value in row.values()
        ):
            return UNAVAILABLE, []
        rows.append({key: float(value) for key, value in row.items() if value is not None})
    return AVAILABLE, rows
