"""Lightweight public verification seam for immutable v3 run artifacts.

This module intentionally depends only on ``alpha_core`` plus Parquet I/O.  Thin surfaces may use
it to reject tampered artifacts without importing the CLI composer, engine, or validation graph.
"""

from __future__ import annotations

import hashlib
import json
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
    rule_sets = {
        "research_rule_pilot_v1": {"baseline.json", "control.json", "d0_acceptance.json"},
        "research_rule_native_v1": {
            "baseline.json",
            "control.json",
            "rule_positions.json",
            "native_receipt.json",
        },
    }
    rule_sets["research_rule_costed_native_v1"] = {
        "baseline.json",
        "control.json",
        "rule_positions.json",
        "native_receipt.json",
        "economics.json",
        "projections.json",
    }
    rule_sets["research_rule_projection_v1"] = {
        "raw_result.json",
        "equity_curve.parquet",
        "trades.parquet",
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "execution_trace.parquet",
        "indicator_series.parquet",
        "chart_annotations.parquet",
        "calendar_returns.parquet",
        "benchmark_comparison.parquet",
        "exposure_turnover.parquet",
        "return_distribution.parquet",
        "rolling_metrics.parquet",
        "trade_statistics.parquet",
    }
    rule_sets["research_daily_rule_pilot_v1"] = {
        "baseline.json",
        "control.json",
        "d0_acceptance.json",
    }
    rule_sets["research_daily_rule_native_v1"] = {
        "baseline.json",
        "control.json",
        "rule_positions.json",
        "study.json",
        "query.json",
        "native_receipt.json",
        "economics.json",
        "projections.json",
    }
    rule_sets["research_daily_rule_projection_v1"] = rule_sets["research_rule_projection_v1"] | {
        "lineage.json"
    }
    command = manifest.get("command")
    if isinstance(command, str) and command.startswith("research_daily_rule_"):
        origin = manifest.get("data_origin")
        captured = origin == "captured_provider_history"
        watermark = (
            "EXPLORATORY / RECONSTRUCTED DISCOVERY; NOT PROMOTED"
            if captured
            else "ARTIFICIAL FIXTURE / NO MARKET EVIDENCE"
        )
        gate = manifest.get("research_gate")
        context = manifest.get("run_context")
        daily = manifest.get("daily_rule")
        if (
            command
            not in {
                "research_daily_rule_pilot_v1",
                "research_daily_rule_native_v1",
                "research_daily_rule_projection_v1",
            }
            or origin not in {"artificial_fixture", "captured_provider_history"}
            or (command == "research_daily_rule_pilot_v1" and captured)
            or manifest.get("synthetic") is not (not captured)
            or manifest.get("real_market_evidence") is not captured
            or manifest.get("eligible_for_holdout_or_execution") is not False
            or manifest.get("places_orders") is not False
            or manifest.get("scientific_acceptance") != "not_admitted"
            or not isinstance(gate, dict)
            or gate
            != {
                "watermark": watermark,
                "state": "exploratory",
                "claim_scope": "exploratory_reconstructed_discovery_history",
            }
            or not isinstance(context, dict)
            or context.get("kind") != "governed_project"
            or not isinstance(context.get("project_id"), str)
            or context.get("research_gate_state") != "not_completed"
            or (
                command != "research_daily_rule_projection_v1"
                and context.get("project_id") != manifest.get("project_id")
            )
            or not isinstance(daily, dict)
            or daily.get("data_origin") != origin
            or any(
                key in manifest
                for key in (
                    "passed",
                    "verdict",
                    "promotion_id",
                    "candidate_id",
                    "paper_ready",
                    "live_ready",
                )
            )
            or ("watermark" in manifest and manifest["watermark"] != watermark)
        ):
            raise DataError("daily manifest cannot change exploratory authority or origin")
        origin_path = rdir / ("lineage.json" if command.endswith("projection_v1") else "study.json")
        if command != "research_daily_rule_pilot_v1":
            try:
                with origin_path.open("rb") as handle:
                    origin_bytes = handle.read(8 * 1024 * 1024 + 1)
                if len(origin_bytes) > 8 * 1024 * 1024:
                    raise DataError("daily origin artifact exceeds its byte bound")
                origin_document = json.loads(origin_bytes)
            except (OSError, ValueError) as error:
                raise DataError("daily origin artifact is invalid") from error
            if (
                not isinstance(origin_document, dict)
                or origin_document.get("data_origin") != origin
            ):
                raise DataError("daily manifest origin differs from its frozen artifact")
    if isinstance(command, str) and command in rule_sets:
        if (
            set(declared) != rule_sets[command]
            or manifest.get("scientific_acceptance") != "not_admitted"
        ):
            raise DataError("fixed rule artifact set or acceptance changed")
        if any((rdir / name).is_symlink() for name in declared):
            raise DataError("fixed rule artifacts must be regular files")
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
