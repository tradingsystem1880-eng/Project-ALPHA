"""Immutable, content-hashed data snapshots with a provenance manifest."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from alpha_core import DataError
from alpha_data.store import ParquetStore


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _check_snapshot_id(snapshot_id: str) -> None:
    """Reject ids that could escape the snapshots root when joined into a path."""
    if (
        not snapshot_id
        or ".." in snapshot_id
        or "/" in snapshot_id
        or "\\" in snapshot_id
        or snapshot_id.startswith(".")
    ):
        raise DataError(f"invalid snapshot id for storage: {snapshot_id!r}")


def _copy_snapshot_files(
    store: ParquetStore, staging: Path, symbols: list[str]
) -> dict[str, dict[str, Any]]:
    """Populate a private staging directory and return its per-symbol hashes."""
    (staging / "bars").mkdir()
    (staging / "actions").mkdir()
    sym_manifest: dict[str, dict[str, Any]] = {}
    for sym in symbols:
        bars_src = store._bars_path(sym)  # noqa: SLF001 — snapshot is a peer of the store
        if not bars_src.exists():
            raise DataError(f"cannot snapshot {sym!r}: no bars in store")
        bars_rel = bars_src.relative_to(store.root / "bars")  # preserve slash-symbol subdirs
        bars_dst = staging / "bars" / bars_rel
        bars_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bars_src, bars_dst)
        entry: dict[str, Any] = {
            "bars_sha256": _sha256(bars_dst),
            "bars_file": f"bars/{bars_rel.as_posix()}",
        }
        actions_src = store._actions_path(sym)  # noqa: SLF001
        if actions_src.exists():
            actions_rel = actions_src.relative_to(store.root / "actions")
            actions_dst = staging / "actions" / actions_rel
            actions_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(actions_src, actions_dst)
            entry["actions_sha256"] = _sha256(actions_dst)
            entry["actions_file"] = f"actions/{actions_rel.as_posix()}"
        sym_manifest[sym] = entry
    return sym_manifest


def create_snapshot(
    store: ParquetStore,
    snaps_root: Path,
    snapshot_id: str,
    symbols: list[str],
    *,
    source: str,
    adapter_version: str,
    parser_version: str,
    created_at: datetime,
) -> dict[str, Any]:
    """Freeze bars + actions for `symbols` into snaps_root/snapshot_id/ with a manifest."""
    _check_snapshot_id(snapshot_id)
    dest = snaps_root / snapshot_id
    if dest.exists():
        raise DataError(f"snapshot {snapshot_id!r} already exists at {dest}")
    snaps_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{snapshot_id}.", suffix=".tmp", dir=snaps_root))
    try:
        manifest: dict[str, Any] = {
            "snapshot_id": snapshot_id,
            "created_at": created_at.isoformat(),
            "source": source,
            "adapter_version": adapter_version,
            "parser_version": parser_version,
            "symbols": _copy_snapshot_files(store, staging, symbols),
        }
        (staging / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
        )
        os.rename(staging, dest)
    except OSError:
        if dest.exists():
            raise DataError(f"snapshot {snapshot_id!r} already exists at {dest}") from None
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return manifest


def verify_snapshot(snapshot_dir: Path) -> None:
    """Re-hash every file and compare to the manifest. Raises DataError on any mismatch."""
    manifest_path = snapshot_dir / "manifest.json"
    if not manifest_path.exists():
        raise DataError(f"no manifest in {snapshot_dir}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise DataError(f"corrupt snapshot manifest at {manifest_path}") from exc
    if not isinstance(manifest, dict) or not isinstance(manifest.get("symbols"), dict):
        raise DataError(f"invalid snapshot manifest at {manifest_path}")
    for sym, entry in manifest["symbols"].items():
        bars_file = snapshot_dir / entry["bars_file"]
        if not bars_file.exists() or _sha256(bars_file) != entry["bars_sha256"]:
            raise DataError(f"snapshot integrity failure for {sym} bars ({bars_file})")
        if "actions_sha256" in entry:
            af = snapshot_dir / entry["actions_file"]
            if not af.exists() or _sha256(af) != entry["actions_sha256"]:
                raise DataError(f"snapshot integrity failure for {sym} actions ({af})")
