"""Bounded read-only V1 evidence over the existing immutable run store.

No engine, re-execution, source admission, approval, or exposure ledger lives here.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.run_store import find_run_dir, read_manifest, research_gate_watermark
from alpha_core import DataError

_MAX_BYTES = 32 * 1024 * 1024
_PARENT = "research_daily_rule_native_v1"
_PROJECTION = "research_daily_rule_projection_v1"


def _json(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        raise DataError("daily report artifact is unavailable or exceeds its bound")
    try:
        with path.open("rb") as handle:
            payload = handle.read(_MAX_BYTES + 1)
        if len(payload) > _MAX_BYTES:
            raise DataError("daily report artifact exceeds its byte bound")
        value = json.loads(payload)
        json.dumps(value, allow_nan=False)
    except (ValueError, OSError) as error:
        raise DataError("daily report artifact is invalid") from error
    if not isinstance(value, dict):
        raise DataError("daily report artifact requires an object")
    return value


def _run(data_dir: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    path = find_run_dir(data_dir, run_id)
    if path is None:
        raise DataError("daily report run is unavailable")
    manifest = read_manifest(path)
    if manifest.get("command") == _PARENT and not isinstance(manifest.get("project_id"), str):
        raise DataError("daily report project identity is missing")
    fingerprints = manifest.get("research_fingerprints")
    if manifest.get("command") == _PARENT and (
        not isinstance(fingerprints, dict) or not isinstance(fingerprints.get("code"), str)
    ):
        raise DataError("daily report source fingerprint is missing")
    if manifest.get("schema_version") != 3:
        raise DataError("daily report requires versioned immutable artifacts")
    # Bound total declared bytes before the verifier reads payloads/Parquet metadata.
    files = [file for file in path.iterdir() if file.is_file()]
    if (
        any(file.is_symlink() for file in files)
        or sum(file.stat().st_size for file in files) > _MAX_BYTES
    ):
        raise DataError("daily report run exceeds its artifact bound")
    verify_manifest_artifacts(path, manifest)
    return path, manifest


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise DataError(f"daily report {label} must be finite")
    return float(value)


def daily_rule_evidence(
    run_id: str,
    *,
    data_dir: Path,
    role: str = "baseline",
    limit: int = 100,
    offset: int = 0,
) -> dict[str, Any]:
    """Inspect exact parent/control selectors and page recorded accounting observations."""
    if role not in {"baseline", "control"}:
        raise DataError("daily report role must be baseline or control")
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise DataError("daily report limit must be between 1 and 1000")
    if type(offset) is not int or not 0 <= offset <= 100_000:
        raise DataError("daily report offset must be between 0 and 100000")
    selected_path = find_run_dir(data_dir, run_id)
    if selected_path is None:
        raise DataError("daily report run is unavailable")
    selected = read_manifest(selected_path)
    empty = {
        "schema": "DailyRuleEvidenceV1",
        "run_id": run_id,
        "available": False,
        "outcome": None,
        "watermark": None,
        "claim_scope": None,
        "data_origin": None,
        "provenance": {},
        "roles": {},
        "accounting": {
            "role": role,
            "rows": [],
            "total": 0,
            "has_more": False,
            "next_offset": None,
        },
        "selectors": {},
        "artifact_sha256": {},
    }
    if selected.get("command") not in {_PARENT, _PROJECTION}:
        return empty
    selected_path, selected = _run(data_dir, run_id)
    parent_id = run_id
    if selected["command"] == _PROJECTION:
        binding = selected.get("daily_rule")
        if not isinstance(binding, dict) or not isinstance(binding.get("parent_run_id"), str):
            raise DataError("daily projection parent binding is missing")
        parent_id = binding["parent_run_id"]
    path, manifest = _run(data_dir, parent_id)
    if manifest.get("command") != _PARENT:
        raise DataError("daily report parent command differs")
    selectors = _json(path / "projections.json")
    if (
        selectors.get("schema") != "DailyRuleProjectionSelectorsV1"
        or selectors.get("parent_run_id") != parent_id
    ):
        raise DataError("daily report selectors differ from the parent")
    study = _json(path / "study.json")
    query = _json(path / "query.json")
    economics = _json(path / "economics.json")
    from pydantic import ValidationError

    from alpha_cli._native_daily_rule_artifacts import validate_daily_economics
    from alpha_cli._native_daily_rule_projection import validate_daily_projections
    from alpha_cli._native_daily_rule_study import DailyRuleStudyV1

    try:
        frozen = DailyRuleStudyV1.model_validate(study)
    except ValidationError as error:
        raise DataError("daily report frozen study is invalid") from error
    canonical_query = json.dumps(query, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if canonical_query != frozen.query_document:
        raise DataError("daily report query differs from the frozen study")
    receipt = _json(path / "native_receipt.json")
    if validate_daily_economics(frozen, receipt.get("economics")) != economics:
        raise DataError("daily report economics differs from the native receipt")
    validate_daily_projections(
        data_dir,
        selectors,
        receipt,
        frozen,
        project_id=str(manifest["project_id"]),
        parent_run_id=parent_id,
        source_fingerprint=str(manifest["research_fingerprints"]["code"]),
    )
    accounting = economics.get("accounting")
    if not isinstance(accounting, dict):
        raise DataError("daily report requires recorded canonical accounting")
    summaries: dict[str, Any] = {}
    role_selectors = selectors.get("roles")
    if not isinstance(role_selectors, dict) or set(role_selectors) != {"baseline", "control"}:
        raise DataError("daily report requires both frozen role selectors")
    selected_found = selected["command"] == _PARENT
    for key in ("baseline", "control"):
        selector = role_selectors[key]
        if not isinstance(selector, dict) or not isinstance(selector.get("run_id"), str):
            raise DataError("daily report role selector is invalid")
        role_path, role_manifest = _run(data_dir, selector["run_id"])
        role_binding = role_manifest.get("daily_rule")
        if (
            hashlib.sha256((role_path / "manifest.json").read_bytes()).hexdigest()
            != selector.get("manifest_sha256")
            or role_manifest.get("command") != _PROJECTION
            or not isinstance(role_binding, dict)
            or role_binding.get("parent_run_id") != parent_id
            or role_binding.get("role") != key
            or role_manifest.get("snapshot_id") != selectors.get("chart_snapshot_id")
            or role_manifest.get("snapshot_hash") != selectors.get("chart_snapshot_hash")
        ):
            raise DataError("daily report role identity changed")
        if selector["run_id"] == run_id:
            selected_found = True
        raw = economics.get(key)
        observations = accounting.get(key)
        if not isinstance(raw, dict) or not isinstance(observations, list) or not observations:
            raise DataError("daily report is missing a role result or recorded accounting")
        if _json(role_path / "raw_result.json") != raw:
            raise DataError("daily report role result differs from the parent's native execution")
        last = observations[-1]
        if not isinstance(last, dict):
            raise DataError("daily report accounting observation is invalid")
        curve = raw.get("equity_curve")
        if (
            not isinstance(curve, list)
            or not curve
            or any(not isinstance(row, list) or len(row) != 2 for row in (curve[0], curve[-1]))
        ):
            raise DataError("daily report role equity is missing")
        starting = _number(curve[0][1], "starting equity")
        final = _number(curve[-1][1], "final equity")
        fees = _number(last.get("fees_total"), "actual total commission")
        trades = raw.get("trades")
        if not isinstance(trades, list):
            raise DataError("daily report role trades are missing")
        summaries[key] = {
            "run_id": selector["run_id"],
            "starting_equity": starting,
            "final_equity": final,
            "orders": raw.get("orders"),
            "fills": raw.get("fills"),
            "rejected": raw.get("rejected"),
            "n_trades": len(trades),
            "fees_total": fees,
            "net_pnl": final - starting,
            "gross_pnl": final - starting + fees,
        }
    if not selected_found:
        raise DataError("daily projection is not one of the parent's frozen selectors")
    observations = accounting[role]
    more = offset + limit < len(observations)
    return {
        **empty,
        "available": True,
        "outcome": economics.get("outcome"),
        "parent_run_id": parent_id,
        "watermark": research_gate_watermark(manifest) or manifest.get("watermark"),
        "claim_scope": study.get("claim_scope"),
        "data_origin": study.get("data_origin"),
        "roles": summaries,
        "selectors": selectors,
        "provenance": {
            "study_sha256": hashlib.sha256((path / "study.json").read_bytes()).hexdigest(),
            "query_sha256": study.get("query_sha256"),
            "crypto_snapshot_id": study.get("snapshot_sha256"),
            "chart_snapshot_id": selectors.get("chart_snapshot_id"),
            "chart_snapshot_hash": selectors.get("chart_snapshot_hash"),
            "economics": study.get("economics"),
            "source_receipts": query.get("source_receipts"),
            "source_sample": query.get("rows", [])[:3],
            "resources": study.get("resources"),
            "point_in_time_claim": False,
            "scientific_acceptance": "not_admitted",
            "gross_pnl_definition": (
                "net PnL plus observed commission; modeled spread/slippage remain in fills"
            ),
        },
        "accounting": {
            "role": role,
            "rows": observations[offset : offset + limit],
            "total": len(observations),
            "has_more": more,
            "next_offset": offset + limit if more else None,
        },
        "artifact_sha256": {name: value["sha256"] for name, value in manifest["artifacts"].items()},
    }
