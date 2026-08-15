"""Immutable D0 runtime for the registered BTCUSDT crowding operator."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, cast

from alpha_cli import _artifacts
from alpha_core import DataError
from alpha_research import (
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    execute_crypto_crowding_d0,
    registered_crypto_crowding_plan,
    render_research_line_chart,
)

_PROJECT_ID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_CONTRACT_ID: Final = re.compile(r"rc_[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_ACCEPTANCE_ARTIFACT: Final = "d0_acceptance.json"
_MAX_ACCEPTANCE_BYTES: Final = 128 * 1024
_RUNTIME_VERSION: Final = 1


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError("crypto crowding runtime value is not canonical JSON") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _publish_json(path: Path, payload: object) -> None:
    rendered = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False)
    _artifacts.publish_artifact(
        path,
        lambda target: target.write_text(rendered, encoding="utf-8"),
    )


def registered_crypto_d0_operator() -> dict[str, object]:
    plan = registered_crypto_crowding_plan()
    fixture = execute_crypto_crowding_d0()
    body: dict[str, object] = {
        "schema": "AlphaRegisteredResearchOperatorV1",
        "name": "bybit_btcusdt_crowding_reversal",
        "version": 1,
        "bundle_id": plan.bundle_id,
        "operator_fingerprint": plan.operator_fingerprint,
        "event_availability": "provider_event_point_in_time",
        "fixture": {
            "fixture_id": "bybit_btcusdt_crowding_d0_v1",
            "fixture_version": 1,
            "definition_fingerprint": fixture.fixture_definition_sha256,
        },
    }
    return {**body, "fingerprint": _sha(body)}


def validate_crypto_d0_contract(contract: Mapping[str, object]) -> dict[str, object]:
    if contract.get("answer_bundle_id") != registered_crypto_crowding_plan().bundle_id:
        raise DataError("crypto crowding contract does not select the registered answer bundle")
    protocol = contract.get("protocol")
    binding = None if not isinstance(protocol, Mapping) else protocol.get("d0_operator")
    expected = registered_crypto_d0_operator()
    if not isinstance(binding, Mapping) or _canonical(binding) != _canonical(expected):
        raise DataError("crypto crowding D0 operator binding does not match the executable")
    hashes = contract.get("hashes")
    if not isinstance(hashes, Mapping) or any(
        not isinstance(hashes.get(field), str) or _SHA256.fullmatch(str(hashes.get(field))) is None
        for field in ("code", "dependency_lock", "environment", "evaluator")
    ):
        raise DataError("crypto crowding contract has no frozen implementation fingerprints")
    return expected


def crypto_d0_execution_fingerprint(contract: Mapping[str, object]) -> str:
    operator = validate_crypto_d0_contract(contract)
    return _sha(
        {
            "runtime": "alpha_cli.research_crypto_runtime.d0",
            "runtime_version": _RUNTIME_VERSION,
            "d0_operator": operator,
        }
    )


def _acceptance_payload(
    *,
    run_id: str,
    project_id: str,
    contract_id: str,
    contract_hash: str,
    execution_fingerprint: str,
    operator: Mapping[str, object],
) -> dict[str, object]:
    result = execute_crypto_crowding_d0()
    return {
        "schema": "ResearchD0AcceptanceV1",
        "schema_version": 1,
        "run_id": run_id,
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": result.fixture_definition_sha256,
        "execution_fingerprint": execution_fingerprint,
        "d0_operator_fingerprint": operator["fingerprint"],
        "fixture_id": "bybit_btcusdt_crowding_d0_v1",
        "fixture_version": 1,
        "evidence_zone": "D0",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "measurements": result.to_dict(),
    }


def run_crypto_crowding_pilot(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
) -> dict[str, Any]:
    if _PROJECT_ID.fullmatch(project_id) is None or _CONTRACT_ID.fullmatch(contract_id) is None:
        raise DataError("crypto crowding pilot requires canonical project and contract ids")
    operator = validate_crypto_d0_contract(contract)
    fixture = execute_crypto_crowding_d0()
    if not fixture.passed:
        raise DataError("crypto crowding deterministic D0 acceptance suite failed")
    contract_hash = _sha(contract)
    execution_fingerprint = crypto_d0_execution_fingerprint(contract)
    run_identity = {
        "command": "research_pilot",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": fixture.fixture_definition_sha256,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(data_dir, run_id)
    acceptance = _acceptance_payload(
        run_id=run_id,
        project_id=project_id,
        contract_id=contract_id,
        contract_hash=contract_hash,
        execution_fingerprint=execution_fingerprint,
        operator=operator,
    )
    scenario_names = (
        "planted",
        "null",
        "confounded",
        "future_poisoned",
        "missing",
        "corrected",
        "insufficient_sample",
    )
    start = datetime(2026, 1, 1, tzinfo=UTC)
    scenario_rows = [
        {"scenario": name, "passed": True, "real_market_evidence": False} for name in scenario_names
    ]
    chart = ResearchChartData(
        chart_id="crypto-crowding-d0-validity",
        title="D0 crypto crowding mechanics acceptance",
        x_label="Registered synthetic scenario",
        y_label="Mechanical pass (1=yes)",
        evidence_phase="exploratory",
        dataset_sha256=fixture.fixture_definition_sha256,
        protocol_sha256=contract_hash,
        question="Do all registered synthetic failure-mode fixtures pass exact recomputation?",
        plain_language_answer="Yes; this validates mechanics only, not market predictiveness.",
        sample_size=len(scenario_names),
        effective_sample_size=float(len(scenario_names)),
        uncertainty="Not applicable to deterministic acceptance scenarios.",
        caveat="Synthetic fixture results are not market evidence or a trading signal.",
        run_id=run_id,
        artifact_id="crypto-crowding-d0-scenarios",
        artifact_sha256=_sha(scenario_rows),
        series=(
            ResearchChartSeries(
                series_id="scenario-pass",
                label="Mechanical pass",
                unit="boolean",
                points=tuple(
                    ResearchChartPoint(ts=start + timedelta(days=index), value=1.0)
                    for index in range(len(scenario_names))
                ),
            ),
        ),
    )
    for name, value in (
        ("events.json", scenario_rows),
        (
            "topology.json",
            {
                "evidence_zone": "D0",
                "D1_read": False,
                "D2_read": False,
                "D3_read": False,
            },
        ),
        (
            "power.json",
            {
                "minimum_effective_events": (
                    registered_crypto_crowding_plan().minimum_effective_events
                ),
                "insufficient_sample_rejected": fixture.insufficient_sample_blocker,
                "real_market_power_claim": False,
            },
        ),
        ("chart-data.json", {**chart.to_dict(), "scenarios": scenario_rows}),
    ):
        _publish_json(run_dir / name, value)
    _artifacts.publish_artifact(
        run_dir / "detector-validity.png",
        lambda target: target.write_bytes(render_research_line_chart(chart)),
    )
    _artifacts.publish_artifact(
        run_dir / _ACCEPTANCE_ARTIFACT,
        lambda target: target.write_text(_canonical(acceptance), encoding="utf-8"),
    )
    _artifacts.publish_artifact(
        run_dir / "report.md",
        lambda target: target.write_text(
            "# D0 Crypto Crowding Pilot\n\n"
            "**SYNTHETIC MECHANICS ONLY — NOT MARKET EVIDENCE**\n\n"
            "The planted, null, confounded, future-poisoned, missing, corrected, and "
            "insufficient-sample fixtures passed exact recomputation. No provider bytes, "
            "sealed evidence, holdout, broker, or order surface was accessed.\n",
            encoding="utf-8",
        ),
    )
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_pilot",
        "kind": "research",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": contract.get("source_pack_id"),
        "research_fingerprints": dict(cast(Mapping[str, object], contract["hashes"])),
        "evidence_zone": "D0",
        "watermark": "EXPLORATORY",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": execution_fingerprint,
        "d0_operator": operator,
        "d0_operator_fingerprint": operator["fingerprint"],
        "d0_acceptance_artifact": _ACCEPTANCE_ARTIFACT,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
        "dataset_hash": fixture.fixture_definition_sha256,
    }
    _artifacts.write_manifest(run_dir, manifest)
    return _artifacts.read_manifest(run_dir)


def validate_crypto_d0_acceptance_artifact(
    run_dir: Path,
    manifest: Mapping[str, object],
    *,
    project_id: str,
    contract_id: str,
    contract_hash: str,
    execution_fingerprint: str,
) -> dict[str, object]:
    path = run_dir / _ACCEPTANCE_ARTIFACT
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_ACCEPTANCE_BYTES:
        raise DataError("crypto crowding D0 acceptance artifact is missing or oversized")
    try:
        raw = path.read_text(encoding="utf-8")
        parsed: object = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("crypto crowding D0 acceptance artifact is unreadable") from exc
    if not isinstance(parsed, dict) or raw != _canonical(parsed):
        raise DataError("crypto crowding D0 acceptance artifact is not canonical")
    operator = registered_crypto_d0_operator()
    expected = _acceptance_payload(
        run_id=str(manifest.get("run_id", "")),
        project_id=project_id,
        contract_id=contract_id,
        contract_hash=contract_hash,
        execution_fingerprint=execution_fingerprint,
        operator=operator,
    )
    if _canonical(parsed) != _canonical(expected) or manifest.get("d0_operator") != operator:
        raise DataError("crypto crowding D0 acceptance fails exact recomputation")
    return parsed


__all__ = [
    "crypto_d0_execution_fingerprint",
    "registered_crypto_d0_operator",
    "run_crypto_crowding_pilot",
    "validate_crypto_d0_acceptance_artifact",
    "validate_crypto_d0_contract",
]
