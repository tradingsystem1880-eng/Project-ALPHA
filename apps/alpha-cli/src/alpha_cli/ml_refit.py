"""Read-only engineering provenance contracts; no fit dispatch or admission."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

from alpha_cli.ml_compare import publish_comparison
from alpha_cli.ml_contract import MLContractError, canonical_json_bytes, validate_request_bundle
from alpha_cli.research_analysis_plan import analysis_family_catalog

_WORKER_SOURCES = (
    "real.py",
    "features.py",
    "contract.py",
    "tabular.py",
    "tabular_contract.py",
    "tabular_adapters.py",
    "fit_provenance.py",
)
_GENERATOR_SOURCES = ("refit_harness.py", "test_fake_worker.py")
_DIMENSION_FIELDS = {
    "panel": frozenset({"panel", "snapshot_hash"}),
    "seed": frozenset({"seed"}),
    "folds": frozenset({"folds", "purge_sessions", "embargo_sessions"}),
    "costs": frozenset({"costs"}),
}

_MAX_PROTOCOL_BYTES = 64 * 1024
_HASH_FIELDS = frozenset(
    {
        "original_request_sha256",
        "changed_request_sha256",
        "worker_source_sha256",
        "worker_lock_sha256",
    }
)
_PROTOCOL_FIELDS = _HASH_FIELDS | {
    "schema_version",
    "authority",
    "model",
    "fixture",
    "expected_relation",
    "changed_dimensions",
}
_DOUBLE_PARAMETERS = {
    "num_models": 2,
    "num_boost_round": 3,
    "early_stopping_rounds": 2,
    "min_data_in_leaf": 5,
    "num_threads": 1,
}
_FIXTURE_LIMITS = {
    "max_pipeline_fits": 2,
    "max_native_fits": 2,
    "max_panel_rows": 16000,
    "max_features": 158,
    "max_folds": 2,
    "max_members": 2,
    "max_rounds": 3,
    "cpu_threads": 1,
    "max_seconds": 300,
    "max_rss_bytes": 1610612736,
    "automatic_retries": 0,
}
_FIXTURE_WORLDS = frozenset(
    {
        "observed",
        "renamed",
        "unavailable_future",
        "appended_future",
        "past_change",
        "common_exposure",
        "cost_stress",
    }
)


def _require_hash(value: object) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise MLContractError("engineering protocol requires lowercase SHA-256 hashes")
    return value


def _signature(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _read_stable_protocol(path: Path) -> bytes:
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise MLContractError("engineering protocol requires a stable regular file")
            if before.st_size > _MAX_PROTOCOL_BYTES:
                raise MLContractError("engineering protocol exceeds its size bound")
            encoded = handle.read(_MAX_PROTOCOL_BYTES + 1)
            after = os.fstat(handle.fileno())
            current = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise MLContractError("engineering protocol requires a stable regular file") from exc
    if (
        len(encoded) > _MAX_PROTOCOL_BYTES
        or _signature(before) != _signature(after)
        or _signature(before) != _signature(current)
        or len(encoded) != before.st_size
    ):
        raise MLContractError("engineering protocol changed during its read")
    return encoded


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MLContractError("engineering protocol contains duplicate JSON fields")
        result[key] = value
    return result


def _reject_constant(value: str) -> NoReturn:
    raise MLContractError(f"engineering protocol contains non-finite JSON constant {value}")


def _validate_model(model: object) -> None:
    if not isinstance(model, dict) or set(model) != {"name", "parameters"}:
        raise MLContractError("engineering protocol requires an exact model recipe")
    parameters = model["parameters"]
    if not isinstance(parameters, dict):
        raise MLContractError("engineering protocol model parameters must be an object")
    if model["name"] == "linear":
        if set(parameters) != {"estimator", "alpha"} or parameters["estimator"] != "ridge":
            raise MLContractError("engineering protocol supports only the frozen ridge recipe")
        alpha = parameters["alpha"]
        if isinstance(alpha, bool) or not isinstance(alpha, int | float) or alpha != 1:
            raise MLContractError("engineering protocol ridge alpha must equal one")
    elif model["name"] == "double_ensemble":
        if set(parameters) != set(_DOUBLE_PARAMETERS) or any(
            type(parameters[key]) is not int or parameters[key] != expected
            for key, expected in _DOUBLE_PARAMETERS.items()
        ):
            raise MLContractError("engineering protocol requires the frozen DoubleEnsemble recipe")
    else:
        raise MLContractError("engineering protocol supports only ridge and DoubleEnsemble")


def _validate_fixture(payload: dict[str, Any]) -> None:
    fixture = payload["fixture"]
    if not isinstance(fixture, dict) or set(fixture) != {
        "generator",
        "version",
        "world",
        "source_sha256",
        "limits",
    }:
        raise MLContractError("engineering protocol requires the exact fixture declaration")
    if (
        fixture["generator"] != "qlib_w11_fixture"
        or type(fixture["version"]) is not int
        or fixture["version"] != 2
    ):
        raise MLContractError("engineering protocol has an unsupported fixture generator/version")
    world = fixture["world"]
    if not isinstance(world, str) or world not in _FIXTURE_WORLDS:
        raise MLContractError("engineering protocol has an unsupported fixture world")
    _require_hash(fixture["source_sha256"])
    expected_limits = {
        **_FIXTURE_LIMITS,
        "max_native_fits": 4 if payload["model"]["name"] == "double_ensemble" else 2,
    }
    limits = fixture["limits"]
    if (
        not isinstance(limits, dict)
        or set(limits) != set(expected_limits)
        or any(
            type(limits[key]) is not int or limits[key] != expected
            for key, expected in expected_limits.items()
        )
    ):
        raise MLContractError("engineering protocol must retain the frozen invocation ceilings")
    if world in {"observed", "renamed"}:
        expected_dimensions: list[str] = []
    elif world == "cost_stress":
        expected_dimensions = ["costs"]
    else:
        expected_dimensions = ["panel"]
    expected_relation = "same_evidence" if not expected_dimensions else "changed_world"
    if (
        payload["expected_relation"] != expected_relation
        or payload["changed_dimensions"] != expected_dimensions
    ):
        raise MLContractError("fixture world does not match its declared relation/dimensions")


def read_engineering_protocol(path: Path, *, expected_sha256: str) -> dict[str, Any]:
    """Verify one frozen reference, without granting execution or acceptance."""
    expected = _require_hash(expected_sha256)
    encoded = _read_stable_protocol(Path(path))
    if hashlib.sha256(encoded).hexdigest() != expected:
        raise MLContractError("engineering protocol hash does not match its frozen reference")
    try:
        payload = json.loads(
            encoded, object_pairs_hook=_unique_pairs, parse_constant=_reject_constant
        )
    except MLContractError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise MLContractError("engineering protocol is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise MLContractError("engineering protocol must be a JSON object")
    try:
        canonical = canonical_json_bytes(payload)
    except RecursionError as exc:
        raise MLContractError("engineering protocol nesting exceeds its supported bound") from exc
    if canonical != encoded:
        raise MLContractError("engineering protocol must use canonical JSON bytes")
    if set(payload) not in (_PROTOCOL_FIELDS, _PROTOCOL_FIELDS | {"cutoff"}):
        raise MLContractError("engineering protocol has missing or unexpected fields")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise MLContractError("engineering protocol schema_version must be integer one")
    if payload["authority"] != "engineering_provenance_only":
        raise MLContractError("engineering protocol cannot confer native or statistical authority")
    for field in _HASH_FIELDS:
        _require_hash(payload[field])
    _validate_model(payload["model"])
    dimensions = payload["changed_dimensions"]
    if (
        not isinstance(dimensions, list)
        or any(not isinstance(item, str) for item in dimensions)
        or len(dimensions) != len(set(dimensions))
        or not set(dimensions) <= {"panel", "seed", "folds", "costs"}
    ):
        raise MLContractError("engineering protocol has invalid changed_dimensions")
    same_request = payload["original_request_sha256"] == payload["changed_request_sha256"]
    relation = payload["expected_relation"]
    if relation == "same_evidence":
        if not same_request or dimensions:
            raise MLContractError("same_evidence requires identical requests and no changes")
    elif relation == "changed_world":
        if same_request or not dimensions:
            raise MLContractError("changed_world requires distinct requests and declared changes")
    else:
        raise MLContractError("engineering protocol has an unsupported expected_relation")
    _validate_fixture(payload)
    if "cutoff" in payload:
        cutoff = payload["cutoff"]
        try:
            parsed = datetime.fromisoformat(cutoff) if isinstance(cutoff, str) else None
        except ValueError as exc:
            raise MLContractError("engineering cutoff must be an explicit UTC timestamp") from exc
        if parsed is None or parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
            raise MLContractError("engineering cutoff must be an explicit UTC timestamp")
    return payload


def _worker_root() -> Path:
    return Path(__file__).resolve().parents[4] / "workers" / "qlib"


def _file_snapshot(path: Path) -> tuple[str, tuple[int, ...]]:
    """Hash a regular file and retain mutation-sensitive metadata for this read."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise MLContractError(f"refit input must be a stable regular file: {path}")
            digest = hashlib.sha256()
            while block := handle.read(1024 * 1024):
                digest.update(block)
            after = os.fstat(handle.fileno())
            current = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise MLContractError(f"refit input unavailable or not a regular file: {path}") from exc
    signature = _signature(before)
    if signature != _signature(after) or signature != _signature(current):
        raise MLContractError(f"refit input changed during its read: {path}")
    return digest.hexdigest(), signature


def _snapshot(paths: dict[str, Path]) -> dict[str, tuple[str, tuple[int, ...]]]:
    return {name: _file_snapshot(path) for name, path in sorted(paths.items())}


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _request_summary(
    request: dict[str, Any], hashes: dict[str, tuple[str, tuple[int, ...]]], role: str
) -> dict[str, Any]:
    return {
        "request_sha256": hashes[f"{role}/request.json"][0],
        "panel_sha256": hashes[f"{role}/panel.parquet"][0],
        "input_anchor_sha256": hashes[f"{role}/input_anchor.json"][0],
        "config_hash": request["config_hash"],
        "snapshot_hash": request["snapshot_hash"],
        "seed": request["seed"],
        "model": request["model"],
        "costs": request["costs"],
        "universe_membership": request["universe_membership"],
        "survivorship_warning": request["survivorship_warning"],
        "panel_rows": request["panel"]["rows"],
        "fold_count": len(request["folds"]),
        "fold_geometry_sha256": _digest(
            {
                "folds": request["folds"],
                "purge_sessions": request["purge_sessions"],
                "embargo_sessions": request["embargo_sessions"],
            }
        ),
    }


def _native_planning_status() -> dict[str, Any]:
    """Describe this assembly's source integration, never native admission or acceptance.

    The public catalog is descriptive. Neither its presence nor fixture fit ceilings
    map this engineering protocol to an approved native family or resource unit.
    """
    return {
        "native_contract_source": "INTEGRATED_CANDIDATE_CONSUMER_ACCEPTANCE_PENDING",
        "governed_execution": "BLOCKED_QLIB_NATIVE_PROTOCOL_UNREGISTERED",
        "fit_reservation": "BLOCKED_QLIB_FIT_UNIT_MAPPING_UNQUALIFIED",
        "fit_accounting": "BLOCKED_QLIB_FIT_ACCOUNTING_UNQUALIFIED",
        "native_ancestry": "BLOCKED_QLIB_ANCESTRY_REUSE_UNQUALIFIED",
        "native_runtime_qualification": "CONSUMER_PROFILE_UNQUALIFIED",
        "native_planning_diagnostics": {
            "registered_analysis_family_ids": [item["id"] for item in analysis_family_catalog()],
            "protocol_mapping": "ENGINEERING_PROTOCOL_HAS_NO_NATIVE_ADMISSION_MAPPING",
            "resource_unit_mapping": "ML_FITS_NOT_MAPPED_TO_LLM_CALLS_OR_TOKENS",
            "fit_count_manifest": "NOT_ACCEPTED_REQUIRES_OWNER_AND_PROTOCOL_APPROVAL",
        },
    }


def plan_refit(
    original: Path,
    changed: Path,
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
) -> dict[str, Any]:
    """Verify frozen engineering inputs; never dispatch or admit a fit."""
    worker = _worker_root()
    paths = {
        "protocol": Path(protocol_path),
        "worker_lock": worker / "uv.lock",
        **{
            f"source/{name}": worker / "src" / "alpha_qlib_worker" / name
            for name in _WORKER_SOURCES
        },
        **{f"generator/{name}": worker / "tests" / name for name in _GENERATOR_SOURCES},
    }
    for role, exchange in (("original", Path(original)), ("changed", Path(changed))):
        paths.update(
            {
                f"{role}/{name}": exchange / name
                for name in ("request.json", "panel.parquet", "input_anchor.json")
            }
        )
    before = _snapshot(paths)
    protocol = read_engineering_protocol(protocol_path, expected_sha256=expected_protocol_sha256)
    source_hashes = {name: before[f"source/{name}"][0] for name in _WORKER_SOURCES}
    generator_hashes = {name: before[f"generator/{name}"][0] for name in _GENERATOR_SOURCES}
    if _digest(source_hashes) != protocol["worker_source_sha256"]:
        raise MLContractError("current worker source differs from the frozen protocol")
    if _digest(generator_hashes) != protocol["fixture"]["source_sha256"]:
        raise MLContractError("current fixture source differs from the frozen protocol")
    if before["worker_lock"][0] != protocol["worker_lock_sha256"]:
        raise MLContractError("current worker lock differs from the frozen protocol")
    requests = {}
    for role, exchange in (("original", Path(original)), ("changed", Path(changed))):
        validated = validate_request_bundle(exchange)
        request = validated.request
        if request["schema_version"] != 3 or request["model"] != protocol["model"]:
            raise MLContractError("refit plan requires the frozen schema3 model recipe")
        if request["worker_lock_hash"] != protocol["worker_lock_sha256"]:
            raise MLContractError("request worker lock differs from the frozen protocol")
        if before[f"{role}/request.json"][0] != protocol[f"{role}_request_sha256"]:
            raise MLContractError("request hash differs from the frozen protocol")
        if validated.panel.height > 16000 or len(request["folds"]) > 2:
            raise MLContractError("refit inputs exceed the frozen invocation ceilings")
        requests[role] = request
    differences = {
        key
        for key in requests["original"]
        if key != "config_hash" and requests["original"][key] != requests["changed"][key]
    }
    covered = set().union(*_DIMENSION_FIELDS.values())
    observed_dimensions = {
        name for name, fields in _DIMENSION_FIELDS.items() if differences.intersection(fields)
    }
    if differences - covered or observed_dimensions != set(protocol["changed_dimensions"]):
        raise MLContractError("actual request changes differ from declared dimensions")
    after = _snapshot(paths)
    if before != after:
        raise MLContractError("refit inputs or sources changed during validation")
    summaries = {
        role: _request_summary(request, before, role) for role, request in requests.items()
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "qlib_refit_engineering_plan",
        "authority": "engineering_provenance_only",
        "plan_status": "INPUT_IDENTITIES_VERIFIED",
        "protocol_sha256": expected_protocol_sha256,
        "worker_source_sha256": _digest(source_hashes),
        "worker_source_files": source_hashes,
        "fixture_source_sha256": _digest(generator_hashes),
        "fixture_source_files": generator_hashes,
        "worker_lock_sha256": before["worker_lock"][0],
        "world": protocol["fixture"]["world"],
        "expected_relation": protocol["expected_relation"],
        "changed_dimensions": protocol["changed_dimensions"],
        "declared_cutoff": protocol.get("cutoff"),
        "per_invocation_ceilings": protocol["fixture"]["limits"],
        "original": summaries["original"],
        "changed": summaries["changed"],
        "distinct_request_count": len({item["request_sha256"] for item in summaries.values()}),
        "distinct_panel_count": len({item["panel_sha256"] for item in summaries.values()}),
        "independent_observation_count": 0,
        "observed_fit_counts": None,
        "trace_status": "NOT_INSPECTED",
        "causality_status": "NOT_EVALUATED",
        "fixture_generation_status": "NOT_EVALUATED",
        **_native_planning_status(),
        "statistical_qualification": "BLOCKED_STATISTICAL_SOURCE_UNAVAILABLE",
        "dependence_qualification": "BLOCKED_DEPENDENCE_CONTRACT_UNAVAILABLE",
        "counterfactual_refit": False,
        "promotion_eligible": False,
    }
    report["plan_sha256"] = _digest(report)
    return report


def publish_refit_plan(report: dict[str, Any], output: Path) -> None:
    """Reuse the existing immutable JSON publisher; create no operational store."""
    publish_comparison(report, output)


def status_refit_plan(
    record: Path,
    original: Path,
    changed: Path,
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
) -> dict[str, Any]:
    """Recompute the plan rather than trusting a cached status or producer flags."""
    record = Path(record)
    before = _file_snapshot(record)
    encoded = _read_stable_protocol(record)
    current = plan_refit(
        original,
        changed,
        protocol_path=protocol_path,
        expected_protocol_sha256=expected_protocol_sha256,
    )
    if _file_snapshot(record) != before:
        raise MLContractError("refit plan record changed during validation")
    if encoded != canonical_json_bytes(current):
        raise MLContractError("refit plan record is stale or differs from current inputs")
    return {
        "schema_version": 1,
        "authority": "engineering_provenance_only",
        "record_status": "CURRENT",
        "plan_sha256": current["plan_sha256"],
        "trace_status": "NOT_INSPECTED",
        "causality_status": "NOT_EVALUATED",
        "fixture_generation_status": "NOT_EVALUATED",
        **{
            key: current[key]
            for key in (
                "native_contract_source",
                "governed_execution",
                "fit_reservation",
                "fit_accounting",
                "native_ancestry",
                "native_runtime_qualification",
                "native_planning_diagnostics",
            )
        },
        "independent_observation_count": 0,
        "counterfactual_refit": False,
        "promotion_eligible": False,
    }


__all__ = ["plan_refit", "publish_refit_plan", "read_engineering_protocol", "status_refit_plan"]
