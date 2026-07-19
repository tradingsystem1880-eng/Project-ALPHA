"""Local-only system readiness projection for ``alpha info system``."""

from __future__ import annotations

import os
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from alpha_core.config import AlphaSettings
from alpha_data.store import ParquetStore

PINNED_NAUTILUS_VERSION = "1.228.0"


def _existing_disk_probe(path: Path) -> Path:
    probe = path.absolute()
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    return probe


def _snapshot_count(root: Path) -> int:
    if not root.is_dir():
        return 0
    return sum(
        1
        for candidate in root.iterdir()
        if candidate.is_dir() and (candidate / "manifest.json").is_file()
    )


def _nautilus_version() -> str | None:
    try:
        return version("nautilus-trader")
    except PackageNotFoundError:
        return None


def system_status(settings: AlphaSettings | None = None) -> dict[str, Any]:
    """Report local filesystem/package/config readiness without performing network probes."""
    resolved = AlphaSettings() if settings is None else settings
    data_dir = resolved.data_dir
    exists = data_dir.is_dir()
    disk_probe = _existing_disk_probe(data_dir)
    writable_probe = data_dir if exists else disk_probe
    actual_nautilus = _nautilus_version()
    cache = resolved.forecast_hub_cache
    return {
        "data_dir": {
            "path": str(data_dir),
            "exists": exists,
            "readable": exists and os.access(data_dir, os.R_OK | os.X_OK),
            "writable": os.access(writable_probe, os.W_OK | os.X_OK),
            "free_bytes": shutil.disk_usage(disk_probe).free,
        },
        "counts": {
            "symbols": len(ParquetStore(data_dir / "store").list_symbols()),
            "snapshots": _snapshot_count(data_dir / "snapshots"),
        },
        "nautilus": {
            "pinned_version": PINNED_NAUTILUS_VERSION,
            "installed_version": actual_nautilus,
            "matches_pin": actual_nautilus == PINNED_NAUTILUS_VERSION,
        },
        "kronos_cache": {
            "configured": cache is not None,
            "path": str(cache) if cache is not None else None,
            "exists": cache.is_dir() if cache is not None else False,
            "local_only": resolved.forecast_local_only,
        },
        "paper_enabled": resolved.paper_enabled,
    }
