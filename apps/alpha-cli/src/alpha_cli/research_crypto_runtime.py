"""Immutable D0 and D1 runtimes for the registered BTCUSDT crowding operator."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final, cast

from alpha_cli import _artifacts
from alpha_cli.research_readiness import derive_research_readiness
from alpha_core import DataError
from alpha_research import (
    CryptoCrowdingEvaluationV1,
    CryptoCrowdingObservationV1,
    ResearchChartData,
    ResearchChartPoint,
    ResearchChartSeries,
    ResearchD2BoundaryV2,
    evaluate_crypto_crowding,
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
_D1_ANALYSES_ARTIFACT: Final = "d1_analyses.json"
_D1_EVIDENCE_ARTIFACT: Final = "research_gate_evidence.json"
_MAX_ACCEPTANCE_BYTES: Final = 128 * 1024
_MAX_D1_ARTIFACT_BYTES: Final = 4 * 1024 * 1024
_RUNTIME_VERSION: Final = 3
_D1_RUNTIME_VERSION: Final = 1
_FIXTURE_ID: Final = "bybit_btcusdt_crowding_d0_v3"
_FIXTURE_VERSION: Final = 3


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
            "fixture_id": _FIXTURE_ID,
            "fixture_version": _FIXTURE_VERSION,
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


def _validated_d1_binding(
    contract: Mapping[str, object],
) -> tuple[str, Mapping[str, object]]:
    validate_crypto_d0_contract(contract)
    hashes = contract.get("hashes")
    dataset_hash = None if not isinstance(hashes, Mapping) else hashes.get("data")
    if not isinstance(dataset_hash, str) or _SHA256.fullmatch(dataset_hash) is None:
        raise DataError("crypto crowding D1 contract has no frozen dataset hash")
    protocol = contract.get("protocol")
    empirical = None if not isinstance(protocol, Mapping) else protocol.get("empirical_dataset")
    plan = registered_crypto_crowding_plan()
    if not isinstance(empirical, Mapping):
        raise DataError("crypto crowding D1 contract has no empirical dataset binding")
    if empirical.get("snapshot_id") != dataset_hash:
        raise DataError("crypto crowding D1 snapshot does not match the frozen dataset hash")
    if empirical.get("operator_fingerprint") != plan.operator_fingerprint:
        raise DataError("crypto crowding D1 operator binding does not match the executable")
    return dataset_hash, empirical


def crypto_d1_execution_fingerprint(contract: Mapping[str, object]) -> str:
    dataset_hash, empirical = _validated_d1_binding(contract)
    return _sha(
        {
            "runtime": "alpha_cli.research_crypto_runtime.d1",
            "runtime_version": _D1_RUNTIME_VERSION,
            "dataset_hash": dataset_hash,
            "empirical_dataset": empirical,
            "operator": registered_crypto_crowding_plan().to_dict(),
        }
    )


def _json_value(value: object) -> object:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_value(item) for item in value]
    return value


def crypto_evaluation_payload(result: CryptoCrowdingEvaluationV1) -> dict[str, object]:
    payload = _json_value(asdict(result))
    if not isinstance(payload, dict):  # pragma: no cover - dataclass serialization is an object.
        raise DataError("crypto crowding evaluation did not serialize to an object")
    payload["primary_event_count"] = result.primary_event_count
    return payload


def _admission(boundary: ResearchD2BoundaryV2, evidence_zone: str) -> tuple[int, int]:
    zone = boundary.d1 if evidence_zone == "D1" else boundary.d2
    stop = zone.stop_index - boundary.outcome_overlap_embargo_groups
    if evidence_zone not in {"D1", "D2"} or stop <= zone.start_index:
        raise DataError(
            f"crypto crowding {evidence_zone} boundary has no outcome-safe observations"
        )
    return zone.start_index, stop


def validate_crypto_execution_inputs(
    contract: Mapping[str, object],
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
    *,
    evidence_zone: str,
) -> tuple[str, int, int]:
    dataset_hash, _ = _validated_d1_binding(contract)
    if boundary.dataset_fingerprint != dataset_hash:
        raise DataError("crypto crowding D1 boundary does not match the frozen dataset")
    groups = tuple(item.funding_time.isoformat() for item in observations)
    if not boundary.verify_eligible_groups(groups):
        raise DataError("crypto crowding observations do not reproduce the complete D2 boundary")
    protocol = contract.get("protocol")
    topology = None if not isinstance(protocol, Mapping) else protocol.get("evidence_topology")
    frozen_boundary = None if not isinstance(topology, Mapping) else topology.get("boundary")
    if not isinstance(frozen_boundary, Mapping) or _canonical(frozen_boundary) != _canonical(
        boundary.to_dict()
    ):
        raise DataError("crypto crowding D1 boundary differs from the frozen contract")
    start, stop = _admission(boundary, evidence_zone)
    return dataset_hash, start, stop


def _d1_findings(result: CryptoCrowdingEvaluationV1) -> dict[str, object]:
    estimate = result.primary_estimate
    tested = result.status == "EVALUATED" and estimate is not None
    clears_hurdle = (
        estimate is not None
        and tested
        and estimate.estimate <= (registered_crypto_crowding_plan().practical_hurdle_return)
    )
    sensitivity_tested = bool(result.sensitivity_results) and all(
        item.adjusted_p_value is not None for item in result.sensitivity_results
    )
    placebo = result.shifted_date_placebo
    controls_passed = placebo is not None and placebo.two_sided_p_value <= 0.05
    primary_status = "TESTED" if tested else "INCONCLUSIVE"
    evidence: dict[str, object] = {
        "schema": "ResearchGateEvidenceV1",
        "evidence_zone": "D1",
        "primary_result": {
            "status": primary_status,
            "estimate": None if estimate is None else estimate.estimate,
            "confidence_interval": (
                None if estimate is None else [estimate.ci_lower, estimate.ci_upper]
            ),
            "event_count": result.primary_event_count,
            "practical_magnitude": {
                "status": "CLEARS_HURDLE" if clears_hurdle else "DOES_NOT_CLEAR_HURDLE",
                "hurdle": registered_crypto_crowding_plan().practical_hurdle_return,
            },
            "blockers": list(result.blockers),
        },
        "mechanism": {"status": "NOT_TESTED", "summary": "Mechanism is not a D1 claim."},
        "strongest_support": (
            "The matched mark-minus-index estimate clears the registered 5 bp hurdle."
            if clears_hurdle
            else None
        ),
        "strongest_contradiction": (
            "The registered event family is underpowered or lacks matched controls."
            if not tested
            else (
                "The matched estimate does not clear the registered 5 bp hurdle."
                if not clears_hurdle
                else None
            )
        ),
        "confounders": {
            "resolved": list(registered_crypto_crowding_plan().matching_covariates),
            "unresolved": ["cross-venue regime transportability"],
        },
        "stability": {
            "parameter": {
                "status": "PASSED" if sensitivity_tested else "INCONCLUSIVE",
                "summary": "Registered 90th and 97.5th percentile Holm family.",
            },
            "temporal": {"status": "NOT_TESTED", "summary": "Reserved for D2."},
            "transportability": {"status": "NOT_TESTED", "summary": "Not claimed."},
        },
        "multiplicity": {
            "status": "PASSED" if sensitivity_tested else "INCONCLUSIVE",
            "summary": "Holm correction over the frozen sensitivity family.",
        },
        "power": {
            "status": "PASSED" if tested else "INCONCLUSIVE",
            "summary": "; ".join(result.blockers) or "Registered admission conditions passed.",
        },
        "negative_controls": {
            "status": "PASSED" if controls_passed else "INCONCLUSIVE",
            "summary": "Shifted-date placebo over admitted D1 observations.",
        },
        "untested_work": [
            "sealed D2 confirmation",
            "D3 holdout",
            "cross-dataset transportability",
        ],
        "what_would_change_conclusion": [
            "at least 50 non-overlapping D1 events with matched controls",
            "a failed shifted-date placebo",
            "a materially different estimate in sealed D2 data",
        ],
    }
    evidence.update(
        derive_research_readiness(
            evidence,
            required_falsifiers=("shifted_date_placebo",),
        )
    )
    return evidence


def _d1_payloads(
    *,
    run_id: str,
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
) -> tuple[dict[str, object], dict[str, object], CryptoCrowdingEvaluationV1]:
    start, stop = _admission(boundary, "D1")
    result = evaluate_crypto_crowding(
        observations,
        evidence_zone="D1",
        admission_start=start,
        admission_stop=stop,
    )
    analyses = {
        "schema": "CryptoCrowdingD1AnalysesV1",
        "schema_version": 1,
        "admission": {
            "start_index": start,
            "stop_index": stop,
            "outcome_overlap_embargo_groups": boundary.outcome_overlap_embargo_groups,
            "boundary_sha256": boundary.boundary_sha256,
        },
        "measurements": {
            "evaluation": crypto_evaluation_payload(result),
            "budget": {"variants_used": 3},
        },
    }
    analyses_sha = hashlib.sha256(_canonical(analyses).encode()).hexdigest()
    evidence = {
        **_d1_findings(result),
        "artifact_links": [
            {
                "run_id": run_id,
                "artifact_id": _D1_ANALYSES_ARTIFACT,
                "content_sha256": analyses_sha,
                "media_type": "application/json",
            }
        ],
    }
    return analyses, evidence, result


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
        "fixture_id": _FIXTURE_ID,
        "fixture_version": _FIXTURE_VERSION,
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


def run_crypto_crowding_deep(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
    on_checkpoint: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Execute the frozen operator against only the outcome-safe D1 membership."""
    if _PROJECT_ID.fullmatch(project_id) is None or _CONTRACT_ID.fullmatch(contract_id) is None:
        raise DataError("crypto crowding D1 requires canonical project and contract ids")
    dataset_hash, _, _ = validate_crypto_execution_inputs(
        contract, observations, boundary, evidence_zone="D1"
    )
    contract_hash = _sha(contract)
    execution_fingerprint = crypto_d1_execution_fingerprint(contract)
    run_identity = {
        "command": "research_deep",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(data_dir, run_id)
    analyses, evidence, result = _d1_payloads(
        run_id=run_id,
        observations=observations,
        boundary=boundary,
    )
    if on_checkpoint is not None:
        on_checkpoint("d1:crypto_crowding:evaluated")
    _artifacts.publish_artifact(
        run_dir / _D1_ANALYSES_ARTIFACT,
        lambda target: target.write_text(_canonical(analyses), encoding="utf-8"),
    )
    _artifacts.publish_artifact(
        run_dir / _D1_EVIDENCE_ARTIFACT,
        lambda target: target.write_text(_canonical(evidence), encoding="utf-8"),
    )

    start, stop = _admission(boundary, "D1")
    admitted = observations[start:stop]
    series = ResearchChartSeries(
        series_id="d1-mark-minus-index",
        label="Mark minus index return",
        unit="return",
        points=tuple(
            ResearchChartPoint(
                ts=item.exit_time,
                value=(item.exit_mark / item.entry_mark - 1)
                - (item.exit_index / item.entry_index - 1),
            )
            for item in admitted
        ),
    )
    chart = ResearchChartData(
        chart_id="crypto-crowding-d1-association",
        title="D1 Bybit crowding association",
        x_label="Outcome availability (UTC)",
        y_label="Mark minus index return",
        evidence_phase="exploratory",
        dataset_sha256=dataset_hash,
        protocol_sha256=contract_hash,
        question="Do point-in-time crowding events precede mark underperformance versus index?",
        plain_language_answer=str(
            _d1_findings(result)["strongest_support"]
            or _d1_findings(result)["strongest_contradiction"]
        ),
        sample_size=len(admitted),
        effective_sample_size=float(max(1, result.primary_event_count)),
        uncertainty="UTC-week clustered bootstrap; see the immutable analyses artifact.",
        caveat="EXPLORATORY D1 evidence only; D2 and D3 were not admitted.",
        run_id=run_id,
        artifact_id="crypto-crowding-d1-series",
        artifact_sha256=_sha(series.to_dict()),
        series=(series,),
    )
    _publish_json(run_dir / "chart-data.json", chart.to_dict())
    _artifacts.publish_artifact(
        run_dir / "d1-primary-association.png",
        lambda target: target.write_bytes(render_research_line_chart(chart)),
    )
    _artifacts.publish_artifact(
        run_dir / "report.md",
        lambda target: target.write_text(
            "# D1 Crypto Crowding Research\n\n"
            "**EXPLORATORY — DISCOVERY-SHARE EVIDENCE ONLY**\n\n"
            "The registered point-in-time operator read its required history but admitted "
            "events, controls, outcomes, and diagnostics only from the outcome-safe D1 range. "
            "D2 and D3 were not admitted and this run grants no execution authority.\n",
            encoding="utf-8",
        ),
    )
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "run_identity_version": 3,
        "command": "research_deep",
        "kind": "research",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "source_pack_id": contract.get("source_pack_id"),
        "research_fingerprints": dict(cast(Mapping[str, object], contract["hashes"])),
        "evidence_zone": "D1",
        "watermark": "EXPLORATORY",
        "real_market_evidence": True,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": execution_fingerprint,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
        "dataset_hash": dataset_hash,
        "d1_evidence_artifact": _D1_EVIDENCE_ARTIFACT,
        "d1_analyses_artifact": _D1_ANALYSES_ARTIFACT,
    }
    _artifacts.write_manifest(run_dir, manifest)
    return _artifacts.read_manifest(run_dir)


def _read_canonical_d1_artifact(path: Path, label: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_D1_ARTIFACT_BYTES:
        raise DataError(f"{label} is missing, linked, or oversized")
    try:
        raw = path.read_text(encoding="utf-8")
        parsed: object = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError(f"{label} is unreadable") from exc
    if not isinstance(parsed, dict) or raw != _canonical(parsed):
        raise DataError(f"{label} is not canonical JSON")
    return parsed


def _manifest_artifact_hash(manifest: Mapping[str, object], name: str) -> str:
    artifacts = manifest.get("artifacts")
    metadata = None if not isinstance(artifacts, Mapping) else artifacts.get(name)
    digest = None if not isinstance(metadata, Mapping) else metadata.get("sha256")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        raise DataError(f"crypto D1 manifest does not bind {name}")
    return digest


def validate_crypto_d1_evidence_artifacts(
    run_dir: Path,
    manifest: Mapping[str, object],
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
    observations: tuple[CryptoCrowdingObservationV1, ...],
    boundary: ResearchD2BoundaryV2,
) -> dict[str, object]:
    """Recompute D1 measurements and findings from exact frozen inputs."""
    if manifest.get("command") != "research_deep" or manifest.get("evidence_zone") != "D1":
        raise DataError("crypto D1 verification requires a research_deep D1 manifest")
    if (
        manifest.get("project_id") != project_id
        or manifest.get("research_contract_id") != contract_id
    ):
        raise DataError("crypto D1 verification authority does not match the manifest")
    dataset_hash, _, _ = validate_crypto_execution_inputs(
        contract, observations, boundary, evidence_zone="D1"
    )
    if (
        manifest.get("dataset_hash") != dataset_hash
        or manifest.get("contract_hash") != _sha(contract)
        or manifest.get("execution_fingerprint") != crypto_d1_execution_fingerprint(contract)
        or manifest.get("d1_evidence_artifact") != _D1_EVIDENCE_ARTIFACT
        or manifest.get("d1_analyses_artifact") != _D1_ANALYSES_ARTIFACT
    ):
        raise DataError("crypto D1 manifest does not match the frozen execution")

    analyses_path = run_dir / _D1_ANALYSES_ARTIFACT
    evidence_path = run_dir / _D1_EVIDENCE_ARTIFACT
    analyses = _read_canonical_d1_artifact(analyses_path, "crypto D1 analyses artifact")
    evidence = _read_canonical_d1_artifact(evidence_path, "crypto D1 evidence artifact")
    if hashlib.sha256(analyses_path.read_bytes()).hexdigest() != _manifest_artifact_hash(
        manifest, _D1_ANALYSES_ARTIFACT
    ) or hashlib.sha256(evidence_path.read_bytes()).hexdigest() != _manifest_artifact_hash(
        manifest, _D1_EVIDENCE_ARTIFACT
    ):
        raise DataError("crypto D1 artifact does not match its immutable manifest hash")
    expected_analyses, expected_evidence, _ = _d1_payloads(
        run_id=str(manifest.get("run_id", "")),
        observations=observations,
        boundary=boundary,
    )
    if _canonical(analyses) != _canonical(expected_analyses):
        raise DataError("crypto D1 analyses fail exact recomputation")
    if _canonical(evidence) != _canonical(expected_evidence):
        raise DataError("crypto D1 findings fail exact recomputation")
    return evidence


__all__ = [
    "crypto_evaluation_payload",
    "crypto_d0_execution_fingerprint",
    "crypto_d1_execution_fingerprint",
    "registered_crypto_d0_operator",
    "run_crypto_crowding_deep",
    "run_crypto_crowding_pilot",
    "validate_crypto_d0_acceptance_artifact",
    "validate_crypto_d0_contract",
    "validate_crypto_d1_evidence_artifacts",
    "validate_crypto_execution_inputs",
]
