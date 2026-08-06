"""Gate-1 deterministic D0 research pilot over synthetic fixtures only."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from alpha_cli import _artifacts
from alpha_core import DataError
from alpha_research import (
    DoubleBottomEvent,
    DoubleBottomSpec,
    EqualDurationResearchBars,
    ResearchBar,
    ResearchChartData,
    ResearchChartFingerprintV1,
    ResearchChartPoint,
    ResearchChartSeries,
    ResearchDatasetRef,
    ResearchEvidenceTopology,
    detect_double_bottom_events,
    render_research_line_chart,
    required_observations_known_sigma,
    simulate_prospective_power_known_sigma,
)

_CONTRACT_ID: Final = re.compile(r"rc_[0-9a-f]{64}")
_PROJECT_ID: Final = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"
)
_SPEC: Final = DoubleBottomSpec(
    pivot_left=1,
    pivot_right=2,
    min_separation=3,
    max_separation=6,
    trough_tolerance=0.03,
    min_rebound=0.05,
)
_D0_OPERATOR_SCHEMA: Final = "AlphaRegisteredResearchOperatorV1"
_D0_OPERATOR_NAME: Final = "double_bottom"
_D0_OPERATOR_VERSION: Final = 1
_D0_EVENT_AVAILABILITY: Final = "second_trough_confirmable"
_D0_CHART_CHOICE: Final = "spy_rth_60m_four_hour_window"
_D0_OUTCOME_CHOICE: Final = "four_trading_hour_return_25bp"
_D0_HORIZON_TRADING_MINUTES: Final = 240
_D0_MINIMUM_EFFECT_RETURN: Final = 0.0025
_D0_TOPOLOGY_SCHEMA_VERSION: Final = 2
_D0_FIXTURE_ID: Final = "spy_60m_double_bottom_v1"
_D0_FIXTURE_VERSION: Final = 1
_D0_RUNTIME_VERSION: Final = 3
_D0_ACCEPTANCE_SCHEMA: Final = "ResearchD0AcceptanceV1"
_D0_ACCEPTANCE_ARTIFACT: Final = "d0_acceptance.json"
_D0_ACCEPTANCE_MAX_BYTES: Final = 128 * 1024
_PLANTED_LOWS: Final = (
    105.0,
    103.0,
    100.0,
    95.0,
    99.0,
    101.0,
    100.0,
    95.5,
    99.0,
    101.0,
    *(102.0 + index for index in range(15)),
)
_MONOTONIC_LOWS: Final = tuple(90.0 + index for index in range(25))
_SINGLE_TROUGH_LOWS: Final = (
    105.0,
    101.0,
    95.0,
    100.0,
    *(101.0 + index for index in range(21)),
)

_D0_CONTRACT_CHART: Final = {
    "provider": "alpha_synthetic_fixture",
    "timezone": "UTC",
    "timestamp_semantics": "bar_end_available",
    "adjustment_basis": "synthetic_not_applicable",
    "instrument": "SYNTHETIC_SPY",
    "venue": "SYNTHETIC",
    "session": "synthetic_equal_duration",
    "bar_duration_minutes": 60,
    "pattern_window_trading_minutes": 240,
    "anchor": "SYNTHETIC_EPOCH",
    "label": "synthetic SPY-like 60-minute D0 fixture with a four-hour pattern window",
}
_D0_PRIMARY_CLAIM: Final = {
    "estimand": "event_minus_matched_control_arithmetic_return",
    "endpoint": "forward_arithmetic_return",
    "horizon_trading_minutes": _D0_HORIZON_TRADING_MINUTES,
    "direction": "positive",
    "minimum_effect_return": _D0_MINIMUM_EFFECT_RETURN,
}


def _canonical(value: object) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise DataError("synthetic research pilot input must contain finite JSON values") from exc


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _d0_fixture_definition() -> dict[str, object]:
    return {
        "fixture": _D0_FIXTURE_ID,
        "fixture_version": _D0_FIXTURE_VERSION,
        "planted_lows": list(_PLANTED_LOWS),
        "monotonic_lows": list(_MONOTONIC_LOWS),
        "single_trough_lows": list(_SINGLE_TROUGH_LOWS),
    }


def _d0_protocol_chart() -> dict[str, object]:
    return ResearchChartFingerprintV1(
        instrument="SYNTHETIC_SPY",
        provider="alpha_synthetic_fixture",
        venue="SYNTHETIC",
        timezone="UTC",
        session="synthetic_equal_duration",
        bar_construction="fixed_60_trading_minute_bars_with_240_trading_minute_pattern_window",
        bar_duration_seconds=3_600,
        anchor="SYNTHETIC_EPOCH",
        adjustment_basis="synthetic_not_applicable",
        timestamp_semantics="bar_end_available",
    ).to_dict()


def _contract_mapping(
    parent: Mapping[str, object], field: str, *, label: str
) -> Mapping[str, object]:
    value = parent.get(field)
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise DataError(f"synthetic research pilot requires {label}")
    return value


def registered_d0_operator(contract: Mapping[str, object]) -> dict[str, object]:
    """Build the exact material contract/operator binding executable by the Gate-1 pilot."""

    event = _contract_mapping(
        contract,
        "event_definition",
        label="one material event definition",
    )
    if event.get("name") != _D0_OPERATOR_NAME:
        raise DataError("Gate-1 D0 only supports the canonical double_bottom event")
    if event.get("availability") != _D0_EVENT_AVAILABILITY:
        raise DataError("Gate-1 D0 only supports second_trough_confirmable availability")
    required_event_semantics = {
        "records_both_trough_times": True,
        "fires_only_when_confirmable": True,
        "right_pivot_moves_event_forward": True,
        "neckline_is_separate_variant": True,
        "overlapping_outcomes": "purge",
    }
    for field, expected in required_event_semantics.items():
        if event.get(field) != expected:
            raise DataError(f"Gate-1 D0 event definition requires {field}={expected!r}")

    resolved = _contract_mapping(
        contract,
        "resolved_material_choices",
        label="resolved material choices",
    )
    if resolved.get("event_availability") != event.get("availability"):
        raise DataError("material event availability disagrees with the event definition")
    chart_choice = resolved.get("chart_construction")
    outcome_choice = resolved.get("primary_outcome")
    if chart_choice != _D0_CHART_CHOICE:
        raise DataError(
            "Gate-1 D0 only supports the spy_rth_60m_four_hour_window chart construction"
        )
    if outcome_choice != _D0_OUTCOME_CHOICE:
        raise DataError("Gate-1 D0 only supports the four_trading_hour_return_25bp primary outcome")

    primary_claim = _contract_mapping(
        contract,
        "primary_claim",
        label="one resolved primary claim",
    )
    chart = _contract_mapping(
        contract,
        "chart_fingerprint",
        label="one resolved chart fingerprint",
    )
    if _canonical(chart) != _canonical(_D0_CONTRACT_CHART):
        raise DataError("Gate-1 D0 chart fingerprint does not match its executable fixture")
    if _canonical(primary_claim) != _canonical(_D0_PRIMARY_CLAIM):
        raise DataError("Gate-1 D0 primary claim does not match its executable power fixture")

    protocol = _contract_mapping(contract, "protocol", label="an immutable protocol")
    protocol_chart = _contract_mapping(
        protocol,
        "chart_fingerprint",
        label="a protocol chart fingerprint",
    )
    if _canonical(protocol_chart) != _canonical(_d0_protocol_chart()):
        raise DataError("Gate-1 D0 protocol chart does not match its executable fixture")
    payload: dict[str, object] = {
        "schema": _D0_OPERATOR_SCHEMA,
        "operator": {
            "name": _D0_OPERATOR_NAME,
            "version": _D0_OPERATOR_VERSION,
            "implementation": "alpha_research.patterns.detect_double_bottom_events",
            "spec": asdict(_SPEC),
        },
        "event": {
            "name": event["name"],
            "availability": event["availability"],
            "timestamp_policy": "right_pivot_bar_close_available",
            "definition": dict(event),
        },
        "chart": {
            "construction_choice": chart_choice,
            "contract_fingerprint": dict(chart),
            "protocol_fingerprint": dict(protocol_chart),
        },
        "primary_outcome": {
            "choice": outcome_choice,
            "horizon": _D0_HORIZON_TRADING_MINUTES,
            "minimum_effect_return": _D0_MINIMUM_EFFECT_RETURN,
            "claim": dict(primary_claim),
        },
        "topology": {
            "schema_version": _D0_TOPOLOGY_SCHEMA_VERSION,
            "allocation": "chronological_60_20_20_by_dependency_group",
            "cross_boundary_outcomes": "REJECT",
        },
        "fixture": {
            "fixture_id": _D0_FIXTURE_ID,
            "fixture_version": _D0_FIXTURE_VERSION,
            "definition_fingerprint": _sha(_d0_fixture_definition()),
            "bar_duration_minutes": 60,
            "real_market_evidence": False,
        },
    }
    return {**payload, "fingerprint": _sha(payload)}


def validate_d0_pilot_contract(contract: Mapping[str, object]) -> dict[str, object]:
    """Fail closed unless ``contract`` binds the exact registered Gate-1 event operator."""

    if contract.get("schema") != "ResearchContractV1":
        raise DataError("synthetic research pilot requires ResearchContractV1")
    if contract.get("scope") != "exploration":
        raise DataError("synthetic research pilot requires an exploration contract")
    if contract.get("approval_ready") is not True:
        raise DataError("synthetic research pilot requires approval_ready=true")
    if contract.get("blocking_questions") != []:
        raise DataError("synthetic research pilot requires no blocking questions")

    expected_binding = registered_d0_operator(contract)
    event = _contract_mapping(contract, "event_definition", label="one material event definition")
    primary_claim = _contract_mapping(
        contract,
        "primary_claim",
        label="one resolved primary claim",
    )
    protocol = _contract_mapping(contract, "protocol", label="an immutable protocol")
    protocol_event = _contract_mapping(
        protocol,
        "event_definition",
        label="a protocol event definition",
    )
    if _canonical(protocol_event) != _canonical(event):
        raise DataError("protocol event definition disagrees with the material contract")
    protocol_claims = protocol.get("primary_claims")
    if (
        not isinstance(protocol_claims, list)
        or len(protocol_claims) != 1
        or _canonical(protocol_claims[0]) != _canonical(primary_claim)
    ):
        raise DataError("protocol primary claim disagrees with the material contract")

    binding = _contract_mapping(
        protocol,
        "d0_operator",
        label="a registered D0 operator binding",
    )
    if _canonical(binding) != _canonical(expected_binding):
        raise DataError("registered D0 operator binding does not match the executable operator")
    return expected_binding


def d0_execution_fingerprint(contract: Mapping[str, object]) -> str:
    """Fingerprint the exact registered D0 runtime before a launch is reserved."""

    d0_operator = validate_d0_pilot_contract(contract)
    return _sha(
        {
            "runtime": "alpha_cli.research_runtime.synthetic_pilot",
            "runtime_version": _D0_RUNTIME_VERSION,
            "d0_operator": d0_operator,
        }
    )


def _bars(lows: Sequence[float], dataset_id: str, content_sha256: str) -> EqualDurationResearchBars:
    dataset = ResearchDatasetRef(
        dataset_id=dataset_id,
        provider="alpha_synthetic_fixture",
        provider_symbol="SYNTHETIC_SPY",
        symbol="SPY",
        venue="SYNTHETIC",
        timeframe="60m",
        timezone="UTC",
        session="synthetic_equal_duration",
        content_sha256=content_sha256,
    )
    start = datetime(2020, 1, 1, tzinfo=UTC)
    values = tuple(
        ResearchBar(
            dataset_id=dataset_id,
            start=start + timedelta(hours=index),
            end=start + timedelta(hours=index + 1),
            available_at=start + timedelta(hours=index + 1),
            open=low + 1.0,
            high=low + 6.0,
            low=low,
            close=low + 2.0,
            volume=1_000.0 + index,
        )
        for index, low in enumerate(lows)
    )
    return EqualDurationResearchBars(dataset, values)


def _event_payload(event: DoubleBottomEvent) -> dict[str, object]:
    raw = asdict(event)
    return {
        key: (
            value.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if isinstance(value, datetime)
            else value
        )
        for key, value in raw.items()
    }


def _publish_text(path: Path, content: str) -> None:
    _publish_bytes(path, content.encode("utf-8"))


def _publish_bytes(path: Path, content: bytes) -> None:

    def write(target: Path) -> None:
        target.write_bytes(content)

    _artifacts.publish_artifact(path, write)


def _publish_json(path: Path, payload: object) -> None:
    _publish_text(path, json.dumps(payload, sort_keys=True, indent=2, allow_nan=False))


def _d0_acceptance_payload(
    *,
    run_id: str,
    project_id: str,
    contract_id: str,
    contract_hash: str,
    dataset_hash: str,
    execution_fingerprint: str,
    d0_operator_fingerprint: str,
    measurements: Mapping[str, object],
) -> dict[str, object]:
    return {
        "schema": _D0_ACCEPTANCE_SCHEMA,
        "schema_version": 1,
        "run_id": run_id,
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
        "d0_operator_fingerprint": d0_operator_fingerprint,
        "fixture_id": _D0_FIXTURE_ID,
        "fixture_version": _D0_FIXTURE_VERSION,
        "evidence_zone": "D0",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "measurements": dict(measurements),
    }


def _recomputed_d0_measurements() -> dict[str, object]:
    """Re-execute every deterministic Gate-1 criterion from the registered fixture."""

    planted = _bars(_PLANTED_LOWS, "d0-planted", _sha(_d0_fixture_definition()))
    monotonic = _bars(_MONOTONIC_LOWS, "d0-monotonic", _sha(_MONOTONIC_LOWS))
    single_trough = _bars(
        _SINGLE_TROUGH_LOWS,
        "d0-single-trough",
        _sha(_SINGLE_TROUGH_LOWS),
    )
    planted_events = detect_double_bottom_events(planted, _SPEC)
    monotonic_events = detect_double_bottom_events(monotonic, _SPEC)
    single_trough_events = detect_double_bottom_events(single_trough, _SPEC)
    topology = ResearchEvidenceTopology.for_observations(
        len(planted.bars),
        forward_outcome_observations=_D0_HORIZON_TRADING_MINUTES // 60,
    )
    rejected_boundaries: list[str] = []
    for phase, boundary_index in (
        ("D1_D2", topology.discovery.stop - topology.forward_outcome_observations),
        ("D2_D3", topology.confirmation.stop - topology.forward_outcome_observations),
    ):
        try:
            topology.event_partition_for(boundary_index)
        except DataError:
            rejected_boundaries.append(phase)
        else:  # pragma: no cover - a topology regression must stop publication immediately.
            raise DataError(f"registered D0 topology failed to reject {phase} boundary crossing")
    required = required_observations_known_sigma(
        alternative_effect=0.0075,
        minimum_effect=_D0_MINIMUM_EFFECT_RETURN,
        standard_deviation=0.015,
        alpha=0.05,
        target_power=0.90,
    )
    power = simulate_prospective_power_known_sigma(
        sample_size=required,
        alternative_effect=0.0075,
        minimum_effect=_D0_MINIMUM_EFFECT_RETURN,
        standard_deviation=0.015,
        alpha=0.05,
        simulations=20_000,
        seed=7,
    )
    return {
        "planted_events": [_event_payload(event) for event in planted_events],
        "monotonic_event_count": len(monotonic_events),
        "single_trough_event_count": len(single_trough_events),
        "topology": {
            "contract_hash": topology.contract_hash,
            "forward_outcome_observations": topology.forward_outcome_observations,
            "rejected_boundaries": rejected_boundaries,
        },
        "power": {
            "alternative_effect": 0.0075,
            "minimum_effect": _D0_MINIMUM_EFFECT_RETURN,
            "standard_deviation": 0.015,
            "alpha": 0.05,
            "target_power": 0.90,
            "required_observations": required,
            "simulations": 20_000,
            "seed": 7,
            "estimated_power": power.estimated_power,
        },
    }


def validate_d0_acceptance_artifact(
    run_dir: Path,
    manifest: Mapping[str, object],
    *,
    project_id: str,
    contract_id: str,
    contract_hash: str,
    dataset_hash: str,
    execution_fingerprint: str,
    d0_operator_fingerprint: str,
) -> dict[str, object]:
    """Validate the hashed typed D0 result; manifest outcome prose is never run authority."""

    path = run_dir / _D0_ACCEPTANCE_ARTIFACT
    if path.is_symlink() or not path.is_file():
        raise DataError("completed D0 run is missing its typed acceptance artifact")
    try:
        raw = path.read_bytes()
    except OSError as exc:  # pragma: no cover - the manifest verifier normally catches this first.
        raise DataError("D0 acceptance artifact cannot be read") from exc
    if len(raw) > _D0_ACCEPTANCE_MAX_BYTES:
        raise DataError("D0 acceptance artifact exceeds the bounded JSON size")
    try:
        parsed: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("D0 acceptance artifact is not valid UTF-8 JSON") from exc
    if not isinstance(parsed, dict) or not all(isinstance(key, str) for key in parsed):
        raise DataError("D0 acceptance artifact must contain a JSON object")
    acceptance: dict[str, object] = parsed
    if raw != _canonical(acceptance).encode("utf-8"):
        raise DataError("D0 acceptance artifact must use canonical JSON bytes")
    expected_identity: dict[str, object] = {
        "schema": _D0_ACCEPTANCE_SCHEMA,
        "schema_version": 1,
        "run_id": manifest.get("run_id"),
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
        "d0_operator_fingerprint": d0_operator_fingerprint,
        "fixture_id": _D0_FIXTURE_ID,
        "fixture_version": _D0_FIXTURE_VERSION,
        "evidence_zone": "D0",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
    }
    mismatches = [
        field for field, expected in expected_identity.items() if acceptance.get(field) != expected
    ]
    if mismatches:
        raise DataError(
            "D0 acceptance artifact authority mismatch: " + ", ".join(sorted(mismatches))
        )
    if manifest.get("d0_acceptance_artifact") != _D0_ACCEPTANCE_ARTIFACT:
        raise DataError("completed D0 manifest does not select its typed acceptance artifact")
    measurements = acceptance.get("measurements")
    if not isinstance(measurements, Mapping):
        raise DataError("D0 acceptance artifact has no typed raw measurements")
    expected_measurements = _recomputed_d0_measurements()
    if _canonical(measurements) != _canonical(expected_measurements):
        raise DataError("D0 acceptance measurements fail exact deterministic recomputation")
    power = expected_measurements["power"]
    if not isinstance(power, Mapping) or float(power["estimated_power"]) < 0.89:
        raise DataError("D0 acceptance failed the registered prospective-power tolerance")
    planted_events = expected_measurements["planted_events"]
    if (
        not isinstance(planted_events, list)
        or len(planted_events) != 1
        or expected_measurements["monotonic_event_count"] != 0
        or expected_measurements["single_trough_event_count"] != 0
    ):
        raise DataError("D0 acceptance failed the registered detector/null criteria")
    planted_event = planted_events[0]
    if (
        not isinstance(planted_event, Mapping)
        or not isinstance(planted_event.get("confirmation_index"), int)
        or not isinstance(planted_event.get("second_trough_index"), int)
        or planted_event["confirmation_index"] <= planted_event["second_trough_index"]
        or not isinstance(planted_event.get("confirmed_at"), str)
        or not isinstance(planted_event.get("second_trough_at"), str)
        or planted_event["confirmed_at"] < planted_event["second_trough_at"]
    ):
        raise DataError("D0 acceptance failed point-in-time event availability")
    expected_fields = {*expected_identity, "measurements"}
    if set(acceptance) != expected_fields:
        raise DataError("D0 acceptance artifact contains unregistered fields")
    return acceptance


def run_synthetic_pilot(
    data_dir: Path,
    *,
    project_id: str,
    contract_id: str,
    contract: Mapping[str, object],
) -> dict[str, Any]:
    """Run the accepted synthetic fixture without opening D1, D2, D3, or the network."""

    if _PROJECT_ID.fullmatch(project_id) is None:
        raise DataError("synthetic research pilot requires a canonical project_id")
    if _CONTRACT_ID.fullmatch(contract_id) is None:
        raise DataError("synthetic research pilot requires a content-addressed contract_id")
    d0_operator = validate_d0_pilot_contract(contract)

    dataset_hash = _sha(_d0_fixture_definition())
    planted = _bars(_PLANTED_LOWS, "d0-planted", dataset_hash)
    monotonic = _bars(_MONOTONIC_LOWS, "d0-monotonic", _sha(_MONOTONIC_LOWS))
    single_trough = _bars(
        _SINGLE_TROUGH_LOWS,
        "d0-single-trough",
        _sha(_SINGLE_TROUGH_LOWS),
    )
    events = detect_double_bottom_events(planted, _SPEC)
    monotonic_events = detect_double_bottom_events(monotonic, _SPEC)
    single_trough_events = detect_double_bottom_events(single_trough, _SPEC)
    if len(events) != 1 or monotonic_events or single_trough_events:
        raise DataError("synthetic research acceptance fixture did not calibrate as planted")

    topology = ResearchEvidenceTopology.for_observations(
        len(planted.bars),
        forward_outcome_observations=_D0_HORIZON_TRADING_MINUTES // 60,
    )
    topology_payload = topology.to_dict()
    if topology_payload.get("schema_version") != _D0_TOPOLOGY_SCHEMA_VERSION:
        raise DataError("registered D0 topology version does not match the executable topology")
    rejected_boundaries: list[str] = []
    for phase, boundary_index in (
        ("D1_D2", topology.discovery.stop - topology.forward_outcome_observations),
        ("D2_D3", topology.confirmation.stop - topology.forward_outcome_observations),
    ):
        try:
            topology.event_partition_for(boundary_index)
        except DataError:
            rejected_boundaries.append(phase)
        else:  # pragma: no cover - a topology regression must stop publication immediately.
            raise DataError(f"registered D0 topology failed to reject {phase} boundary crossing")
    required = required_observations_known_sigma(
        alternative_effect=0.0075,
        minimum_effect=_D0_MINIMUM_EFFECT_RETURN,
        standard_deviation=0.015,
        alpha=0.05,
        target_power=0.90,
    )
    power = simulate_prospective_power_known_sigma(
        sample_size=required,
        alternative_effect=0.0075,
        minimum_effect=_D0_MINIMUM_EFFECT_RETURN,
        standard_deviation=0.015,
        alpha=0.05,
        simulations=20_000,
        seed=7,
    )
    event_rows = [_event_payload(event) for event in events]
    contract_hash = _sha(contract)
    contract_hashes = contract.get("hashes", {})
    if not isinstance(contract_hashes, Mapping):
        raise DataError("synthetic research pilot contract hashes must be an object")
    research_fingerprints = dict(contract_hashes)
    execution_fingerprint = d0_execution_fingerprint(contract)
    run_identity = {
        "command": "research_pilot",
        "project_id": project_id,
        "research_contract_id": contract_id,
        "contract_hash": contract_hash,
        "dataset_hash": dataset_hash,
        "execution_fingerprint": execution_fingerprint,
    }
    run_id = _sha(run_identity)[:16]
    run_dir = _artifacts.run_dir(Path(data_dir), run_id)
    chart_points = tuple(ResearchChartPoint(ts=bar.end, value=bar.low) for bar in planted.bars)
    chart_series = ResearchChartSeries(
        series_id="synthetic-low",
        label="Synthetic low",
        unit="synthetic price units",
        points=chart_points,
    )
    chart_series_sha = _sha(chart_series.to_dict())
    chart = ResearchChartData(
        chart_id="detector-validity",
        title="D0 detector timing and null-fixture validity",
        x_label="Synthetic bar end (UTC)",
        y_label="Synthetic low",
        evidence_phase="exploratory",
        dataset_sha256=dataset_hash,
        protocol_sha256=contract_hash,
        question="Does the detector find the planted pattern only after it is knowable?",
        plain_language_answer=(
            "Yes in this synthetic fixture; this validates mechanics, not market predictiveness."
        ),
        sample_size=len(planted.bars),
        effective_sample_size=float(len(events)),
        uncertainty="Not estimated for this detector-acceptance fixture.",
        caveat="A planted synthetic pattern is not real-market evidence or a trading signal.",
        run_id=run_id,
        artifact_id="detector-validity-series",
        artifact_sha256=chart_series_sha,
        series=(chart_series,),
    )
    _publish_json(run_dir / "events.json", event_rows)
    _publish_json(
        run_dir / "topology.json",
        {
            **topology_payload,
            "note": "D0 validates mechanics only; these windows are not opened as market evidence.",
        },
    )
    _publish_json(
        run_dir / "power.json",
        {
            "known_sigma_fixture_only": True,
            "required_observations": required,
            "simulation": asdict(power),
        },
    )
    _publish_json(run_dir / "chart-data.json", {**chart.to_dict(), "events": event_rows})
    _publish_bytes(run_dir / "detector-validity.png", render_research_line_chart(chart))
    _publish_text(
        run_dir / "report.md",
        "# D0 Synthetic Pilot\n\n"
        "**EXPLORATORY — NOT REAL-MARKET EVIDENCE**\n\n"
        "The planted point-in-time double bottom was detected after its right-hand confirmation "
        "window. Monotonic and single-trough fixtures produced no events. D1, D2, and D3 were "
        "not accessed.\n",
    )
    measurements: dict[str, object] = {
        "planted_events": event_rows,
        "monotonic_event_count": len(monotonic_events),
        "single_trough_event_count": len(single_trough_events),
        "topology": {
            "contract_hash": topology.contract_hash,
            "forward_outcome_observations": topology.forward_outcome_observations,
            "rejected_boundaries": rejected_boundaries,
        },
        "power": {
            "alternative_effect": 0.0075,
            "minimum_effect": _D0_MINIMUM_EFFECT_RETURN,
            "standard_deviation": 0.015,
            "alpha": 0.05,
            "target_power": 0.90,
            "required_observations": required,
            "simulations": 20_000,
            "seed": 7,
            "estimated_power": power.estimated_power,
        },
    }
    d0_operator_fingerprint = str(d0_operator["fingerprint"])
    _publish_text(
        run_dir / _D0_ACCEPTANCE_ARTIFACT,
        _canonical(
            _d0_acceptance_payload(
                run_id=run_id,
                project_id=project_id,
                contract_id=contract_id,
                contract_hash=contract_hash,
                dataset_hash=dataset_hash,
                execution_fingerprint=execution_fingerprint,
                d0_operator_fingerprint=d0_operator_fingerprint,
                measurements=measurements,
            )
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
        "research_fingerprints": research_fingerprints,
        "evidence_zone": "D0",
        "watermark": "EXPLORATORY",
        "real_market_evidence": False,
        "eligible_for_holdout_or_execution": False,
        "places_orders": False,
        "snapshot_id": None,
        "snapshot_hash": None,
        "execution_fingerprint": execution_fingerprint,
        "d0_operator": d0_operator,
        "d0_operator_fingerprint": d0_operator_fingerprint,
        "d0_acceptance_artifact": _D0_ACCEPTANCE_ARTIFACT,
        "strategy_fingerprint": None,
        "source_fingerprint": contract_hash,
        "dataset_hash": dataset_hash,
    }
    _artifacts.write_manifest(run_dir, manifest)
    return _artifacts.read_manifest(run_dir)
