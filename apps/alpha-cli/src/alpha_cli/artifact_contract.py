"""Lightweight public verification seam for immutable v3 run artifacts.

This module intentionally depends only on ``alpha_core`` plus Parquet I/O.  Thin surfaces may use
it to reject tampered artifacts without importing the CLI composer, engine, or validation graph.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Final

import polars as pl

from alpha_core import DataError

MANIFEST_SCHEMA_VERSION: Final = 3
ARTIFACT_CONTRACT_VERSION: Final = 3
RESEARCH_PILOT_REQUIRED_ARTIFACTS: Final = (
    "events.json",
    "topology.json",
    "power.json",
    "chart-data.json",
    "detector-validity.png",
    "report.md",
    "d0_acceptance.json",
)


def sha256_file(path: Path) -> str:
    """Return the streaming SHA-256 digest for one artifact."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def artifact_metadata(path: Path) -> dict[str, Any]:
    """Return the deterministic manifest metadata for one artifact."""
    schema: list[dict[str, str]] | None = None
    rows: int | None = None
    media_type = "application/octet-stream"
    if path.suffix == ".parquet":
        try:
            parquet_schema = pl.read_parquet_schema(path)
            rows = int(pl.scan_parquet(path).select(pl.len()).collect().item())
        except (OSError, pl.exceptions.PolarsError) as exc:
            raise DataError(f"unreadable parquet artifact {path}") from exc
        schema = [{"name": name, "dtype": str(dtype)} for name, dtype in parquet_schema.items()]
        media_type = "application/vnd.apache.parquet"
    elif path.suffix == ".html":
        media_type = "text/html"
    return {
        "schema": schema,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
        "rows": rows,
        "media_type": media_type,
    }


def artifact_contract(rdir: Path) -> dict[str, dict[str, Any]]:
    """Build the complete deterministic sidecar contract for one run directory."""
    return {
        path.name: artifact_metadata(path)
        for path in sorted(rdir.iterdir(), key=lambda item: item.name)
        if path.is_file() and path.name != "manifest.json" and not path.name.startswith(".")
    }


def validate_identity_fields(manifest: Mapping[str, Any]) -> None:
    """Validate the identity fields required on every new v3 manifest."""
    if manifest.get("run_identity_version") != 3:
        raise DataError("new manifests require run_identity_version=3")
    for field in ("execution_fingerprint", "strategy_fingerprint", "source_fingerprint"):
        value = manifest.get(field)
        if field == "strategy_fingerprint" and value is None:
            continue
        if not isinstance(value, str) or len(value) != 64:
            raise DataError(f"new manifests require a 64-hex {field}")
        try:
            int(value, 16)
        except ValueError:
            raise DataError(f"new manifests require a 64-hex {field}") from None
    snapshot_hash = manifest.get("snapshot_hash")
    snapshot_id = manifest.get("snapshot_id")
    if snapshot_hash is None:
        if isinstance(snapshot_id, str) and snapshot_id:
            raise DataError("new manifests with snapshot_id require a 64-hex snapshot_hash")
        return
    if not isinstance(snapshot_hash, str) or len(snapshot_hash) != 64:
        raise DataError("new manifests require snapshot_hash to be null or a 64-hex digest")
    try:
        int(snapshot_hash, 16)
    except ValueError:
        raise DataError(
            "new manifests require snapshot_hash to be null or a 64-hex digest"
        ) from None


def verify_manifest_artifacts(rdir: Path, manifest: Mapping[str, Any]) -> None:
    """Verify a v3 manifest's identity and complete machine-readable artifact contract."""
    if manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        return
    validate_identity_fields(manifest)
    if manifest.get("artifact_contract_version") != ARTIFACT_CONTRACT_VERSION:
        raise DataError(f"unsupported artifact contract at {rdir}")
    if manifest.get("run_id") != rdir.name:
        raise DataError(f"run manifest identity does not match directory {rdir}")
    declared = manifest.get("artifacts")
    if not isinstance(declared, dict):
        raise DataError(f"invalid artifact contract at {rdir}: expected an object")
    actual_names = {
        path.name
        for path in rdir.iterdir()
        if path.is_file() and path.name != "manifest.json" and not path.name.startswith(".")
    }
    if set(declared) != actual_names:
        raise DataError(
            f"artifact set mismatch at {rdir}: declared {sorted(declared)}, "
            f"actual {sorted(actual_names)}"
        )
    if manifest.get("command") == "research_pilot":
        required = set(RESEARCH_PILOT_REQUIRED_ARTIFACTS)
        if set(declared) != required:
            raise DataError(
                f"research_pilot artifact set mismatch at {rdir}: required {sorted(required)}, "
                f"declared {sorted(declared)}"
            )
        for filename in sorted(required):
            path = rdir / filename
            if path.is_symlink() or not path.is_file():
                raise DataError(
                    f"research_pilot artifact {filename!r} must be a regular non-symlink file"
                )
    for filename in sorted(actual_names):
        expected = declared.get(filename)
        if not isinstance(expected, dict):
            raise DataError(f"artifact {filename} metadata mismatch at {rdir}")
        path = rdir / filename
        if expected.get("size_bytes") != path.stat().st_size:
            raise DataError(f"artifact {filename} size mismatch at {rdir}")
        if expected.get("sha256") != sha256_file(path):
            raise DataError(f"artifact {filename} hash mismatch at {rdir}")
        metadata = artifact_metadata(path)
        if expected != metadata:
            for field in ("rows", "schema", "media_type"):
                if expected.get(field) != metadata[field]:
                    raise DataError(f"artifact {filename} {field} mismatch at {rdir}")
            raise DataError(f"artifact {filename} metadata mismatch at {rdir}")


__all__ = [
    "ARTIFACT_CONTRACT_VERSION",
    "MANIFEST_SCHEMA_VERSION",
    "RESEARCH_PILOT_REQUIRED_ARTIFACTS",
    "artifact_contract",
    "artifact_metadata",
    "sha256_file",
    "validate_identity_fields",
    "verify_manifest_artifacts",
]
