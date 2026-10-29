"""Lineage-bound comparisons of portable predictions; no economic simulation."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from alpha_cli.ml_contract import (
    MLContractError,
    canonical_json_bytes,
    sha256_file,
    validate_result_bundle,
)

_KEYS = ["fold", "split", "target_ts", "symbol", "origin_ts", "available_at"]
_ARTIFACTS = (
    "request.json",
    "result.json",
    "panel.parquet",
    "predictions.parquet",
    "input_anchor.json",
    "ensemble_diagnostics.parquet",
)


def _artifact_hashes(exchange: Path) -> dict[str, str]:
    hashes = {}
    for name in _ARTIFACTS:
        path = exchange / name
        if path.is_symlink():
            raise MLContractError("comparison artifacts may not be symlinks")
        if path.is_file():
            hashes[name] = sha256_file(path)
    return hashes


def compare_exchanges(exchanges: Sequence[Path]) -> dict[str, Any]:
    """Compare exact frozen inputs and OOS samples, retaining each model's own score units.

    There is no winner selection or profitability claim. Predictive metrics already recorded
    by the worker remain worker diagnostics; costed economics require canonical ALPHA replay.
    """
    if not 2 <= len(exchanges) <= 10:
        raise MLContractError("comparison requires 2 to 10 completed exchanges")
    candidates: list[dict[str, Any]] = []
    common: bytes | None = None
    prediction_keys = None
    worker_kind: str | None = None
    worker_lineage: bytes | None = None
    config_hashes: set[str] = set()
    for exchange in exchanges:
        before = _artifact_hashes(exchange)
        validated = validate_result_bundle(exchange)
        request, result = validated.request.request, validated.result
        for name, payload in (("request.json", request), ("result.json", result)):
            if hashlib.sha256(canonical_json_bytes(payload)).hexdigest() != before.get(name):
                raise MLContractError("comparison source changed during validation")
        frozen = {
            key: value
            for key, value in request.items()
            if key not in {"config_hash", "schema_version", "model"}
        }
        identity = canonical_json_bytes(frozen)
        if common is not None and identity != common:
            raise MLContractError("comparison requires identical frozen inputs except model recipe")
        common = identity
        config_hash = str(request["config_hash"])
        if config_hash in config_hashes:
            raise MLContractError("comparison contains a duplicate model configuration")
        config_hashes.add(config_hash)
        kind = str(result["worker"]["kind"])
        if worker_kind is not None and kind != worker_kind:
            raise MLContractError("comparison cannot mix fake and real worker predictions")
        worker_kind = kind
        diagnostics = result["diagnostics"]
        if request["schema_version"] == 3 and kind == "qlib":
            source_hash = diagnostics.get("adapter_source_hash")
            versions = diagnostics.get("backend_versions")
            if (
                not isinstance(source_hash, str)
                or len(source_hash) != 64
                or any(char not in "0123456789abcdef" for char in source_hash)
                or diagnostics.get("model_backend") != request["model"]["name"]
                or not isinstance(versions, dict)
                or not versions
                or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in versions.items()
                )
                or not isinstance(diagnostics.get("model_parameters"), dict)
            ):
                raise MLContractError("schema3 real comparison requires adapter/backend provenance")
        lineage = canonical_json_bytes(
            {
                "worker": result["worker"],
                "adapter_source_hash": diagnostics.get("adapter_source_hash"),
                "versions": diagnostics.get("versions"),
            }
        )
        if worker_lineage is not None and lineage != worker_lineage:
            raise MLContractError("comparison requires the same worker source/version lineage")
        worker_lineage = lineage
        frame = validated.predictions
        keys = frame.select(_KEYS).sort(_KEYS)
        if prediction_keys is not None and not keys.equals(prediction_keys):
            raise MLContractError("comparison requires identical prediction sample keys")
        prediction_keys = keys
        scores = frame.get_column("score")
        signal_analysis = diagnostics.get("signal_analysis", {})
        if not isinstance(signal_analysis, dict):
            raise MLContractError("worker signal_analysis must be an object")
        candidates.append(
            {
                "config_hash": config_hash,
                "schema_version": request["schema_version"],
                "model": request["model"],
                "request_sha256": before["request.json"],
                "result_sha256": before["result.json"],
                "predictions_sha256": result["predictions"]["sha256"],
                "worker_lock_hash": request["worker_lock_hash"],
                "model_hashes": sorted(frame.get_column("model_hash").unique().to_list()),
                "prediction_rows": frame.height,
                "score": {
                    "min": scores.min(),
                    "max": scores.max(),
                    "mean": scores.mean(),
                    "std": scores.std(ddof=0),
                },
                "worker_reported_ic": signal_analysis.get("ic"),
                "backend_versions": diagnostics.get("backend_versions"),
                "adapter_source_hash": diagnostics.get("adapter_source_hash"),
            }
        )
        if _artifact_hashes(exchange) != before:
            raise MLContractError("comparison source changed during validation")
    report: dict[str, Any] = {
        "schema_version": 1,
        "authority": "predictive_diagnostics_only",
        "worker_kind": worker_kind,
        "worker_lineage": result["worker"],
        "membership_status": validated.request.membership_status,
        "survivorship_warning": request["survivorship_warning"],
        "snapshot_hash": request["snapshot_hash"],
        "panel_sha256": request["panel"]["sha256"],
        "seed": request["seed"],
        "frozen_inputs_hash": hashlib.sha256(common or b"").hexdigest(),
        "candidates": sorted(candidates, key=lambda item: item["config_hash"]),
        "promotion_eligible": False,
        "counterfactual_refit": False,
        "economics": "Run each exchange through canonical ALPHA replay with explicit costs.",
        "caveat": "Score units differ across recipes; no winner or net profitability is inferred.",
    }
    report["comparison_hash"] = hashlib.sha256(canonical_json_bytes(report)).hexdigest()
    return report


def publish_comparison(report: dict[str, Any], output: Path) -> None:
    """Publish a complete JSON artifact atomically; identical retries verify existing bytes."""
    if output.suffix.lower() != ".json":
        raise MLContractError("comparison output must use a .json suffix")
    if output.is_symlink():
        raise MLContractError("comparison output may not be a symlink")
    encoded = canonical_json_bytes(report)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{output.name}.", dir=output.parent) as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
        try:
            os.link(handle.name, output)
        except FileExistsError:
            if output.is_symlink() or output.read_bytes() != encoded:
                raise MLContractError(
                    "comparison output already contains different bytes"
                ) from None
