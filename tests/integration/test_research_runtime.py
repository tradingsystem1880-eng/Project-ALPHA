"""Gate-1 synthetic pilot publishes immutable, contract-bound research artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import alpha_cli.research_runtime as research_runtime
from alpha_cli import _artifacts
from alpha_cli.artifact_contract import verify_manifest_artifacts
from alpha_cli.research_intake import draft_exploration_contract
from alpha_cli.research_runtime import (
    _canonical,
    d0_execution_fingerprint,
    registered_d0_operator,
    run_synthetic_pilot,
    validate_d0_acceptance_bytes,
    validate_d0_pilot_contract,
)
from alpha_core import DataError
from alpha_research import ResearchChartFingerprintV1


def _contract() -> dict[str, object]:
    contract = draft_exploration_contract(
        "S&P500 bounces after double bottoms on the 4h time frame",
        resolutions={
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
    )
    event_definition = contract["event_definition"]
    primary_claim = contract["primary_claim"]
    protocol: dict[str, object] = {
        "event_definition": dict(event_definition),
        "chart_fingerprint": ResearchChartFingerprintV1(
            instrument="SYNTHETIC_SPY",
            provider="alpha_synthetic_fixture",
            venue="SYNTHETIC",
            timezone="UTC",
            session="synthetic_equal_duration",
            bar_construction=(
                "fixed_60_trading_minute_bars_with_240_trading_minute_pattern_window"
            ),
            bar_duration_seconds=3_600,
            anchor="SYNTHETIC_EPOCH",
            adjustment_basis="synthetic_not_applicable",
            timestamp_semantics="bar_end_available",
        ).to_dict(),
        "primary_claims": [primary_claim],
    }
    contract["protocol"] = protocol
    protocol["d0_operator"] = registered_d0_operator(contract)
    return contract


def _daily_contract() -> dict[str, object]:
    contract = draft_exploration_contract(
        "S&P500 bounces after double bottoms on the daily chart",
        resolutions={
            "chart_construction": "tiingo_daily_fallback",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "next_regular_session_return_50bp",
        },
    )
    event_definition = contract["event_definition"]
    primary_claim = contract["primary_claim"]
    protocol: dict[str, object] = {
        "event_definition": dict(event_definition),
        "chart_fingerprint": ResearchChartFingerprintV1(
            instrument="SPY",
            provider="tiingo",
            venue="US_EQUITIES",
            timezone="America/New_York",
            session="regular_session_daily",
            bar_construction="fixed_session_daily_bars",
            bar_duration_seconds=86_400,
            anchor="US_EQUITIES_SESSION_CLOSE",
            adjustment_basis="point_in_time",
            timestamp_semantics="bar_close_available",
        ).to_dict(),
        "primary_claims": [primary_claim],
    }
    contract["protocol"] = protocol
    protocol["d0_operator"] = registered_d0_operator(contract)
    return contract


def test_registered_d0_operator_is_deterministic_exact_and_defensive() -> None:
    contract = _contract()
    first = registered_d0_operator(contract)
    second = registered_d0_operator(contract)

    assert first == second
    assert first is not second
    assert first["schema"] == "AlphaRegisteredResearchOperatorV1"
    operator = first["operator"]
    assert isinstance(operator, dict)
    assert operator["name"] == "double_bottom"
    assert operator["version"] == 1
    assert operator["implementation"] == "alpha_research.patterns.detect_double_bottom_events"
    assert operator["spec"] == {
        "pivot_left": 1,
        "pivot_right": 2,
        "min_separation": 3,
        "max_separation": 6,
        "trough_tolerance": 0.03,
        "min_rebound": 0.05,
    }
    event = first["event"]
    assert isinstance(event, dict)
    assert event["availability"] == "second_trough_confirmable"
    chart = first["chart"]
    assert isinstance(chart, dict)
    assert chart["construction_choice"] == "spy_rth_60m_four_hour_window"
    primary_outcome = first["primary_outcome"]
    assert isinstance(primary_outcome, dict)
    assert primary_outcome["horizon"] == 240
    assert primary_outcome["minimum_effect_return"] == 0.0025
    assert first["topology"] == {
        "schema_version": 2,
        "allocation": "chronological_60_20_20_by_dependency_group",
        "cross_boundary_outcomes": "REJECT",
    }
    fixture = first["fixture"]
    assert isinstance(fixture, dict)
    assert fixture["fixture_id"] == "spy_60m_double_bottom_v1"
    assert fixture["fixture_version"] == 1
    assert fixture["bar_duration_minutes"] == 60
    assert fixture["real_market_evidence"] is False
    assert isinstance(fixture["definition_fingerprint"], str)
    assert len(fixture["definition_fingerprint"]) == 64
    assert isinstance(first["fingerprint"], str)
    assert len(first["fingerprint"]) == 64
    operator["name"] = "mutated"
    current_operator = registered_d0_operator(contract)["operator"]
    assert isinstance(current_operator, dict)
    assert current_operator["name"] == "double_bottom"


def test_d0_contract_validator_returns_the_exact_registered_binding() -> None:
    contract = _contract()
    assert validate_d0_pilot_contract(contract) == registered_d0_operator(contract)


@pytest.mark.parametrize(
    ("chart_choice", "outcome_choice", "message"),
    [
        (
            "es_fixed_4h",
            "four_trading_hour_return_25bp",
            "registers no D0 operator generation for the 'es_fixed_4h' chart",
        ),
        (
            "synthetic_only",
            "four_trading_hour_return_25bp",
            "registers no D0 operator generation for the 'synthetic_only' chart",
        ),
        (
            "spy_rth_60m_four_hour_window",
            "next_regular_session_return_50bp",
            "registered with the four_trading_hour_return_25bp primary outcome",
        ),
        (
            "tiingo_daily_fallback",
            "four_trading_hour_return_25bp",
            "registered with the next_regular_session_return_50bp primary outcome",
        ),
    ],
)
def test_registered_d0_operator_rejects_materially_different_fixtures(
    chart_choice: str,
    outcome_choice: str,
    message: str,
) -> None:
    contract = draft_exploration_contract(
        "S&P500 bounces after double bottoms on the 4h time frame",
        resolutions={
            "chart_construction": chart_choice,
            "event_availability": "second_trough_confirmable",
            "primary_outcome": outcome_choice,
        },
    )
    contract["protocol"] = {}

    with pytest.raises(DataError, match=message):
        registered_d0_operator(contract)


def test_synthetic_pilot_is_deterministic_exploratory_and_point_in_time(tmp_path: Path) -> None:
    contract_id = "rc_" + "a" * 64
    first = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id=contract_id,
        contract=_contract(),
    )
    second = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id=contract_id,
        contract=dict(reversed(_contract().items())),
    )

    assert first == second
    assert first["research_contract_id"] == contract_id
    assert first["evidence_zone"] == "D0"
    assert first["watermark"] == "EXPLORATORY"
    assert first["places_orders"] is False
    assert first["d0_operator"] == registered_d0_operator(_contract())
    assert first["d0_operator_fingerprint"] == first["d0_operator"]["fingerprint"]
    run_dir = tmp_path / "runs" / str(first["run_id"])
    events = json.loads((run_dir / "events.json").read_text(encoding="utf-8"))
    chart_data = json.loads((run_dir / "chart-data.json").read_text(encoding="utf-8"))
    assert len(events) == 1
    assert events[0]["confirmation_index"] > events[0]["second_trough_index"]
    assert events[0]["confirmed_at"] >= events[0]["second_trough_at"]
    assert chart_data["watermark"] == "EXPLORATORY"
    assert chart_data["run_id"] == first["run_id"]
    assert chart_data["protocol_sha256"] == first["contract_hash"]
    assert chart_data["plain_language_answer"]
    assert chart_data["uncertainty"]
    assert chart_data["caveat"]
    rendered = (run_dir / "detector-validity.png").read_bytes()
    assert rendered.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"EXPLORATORY" in rendered
    assert first["artifacts"]["detector-validity.png"]["media_type"] == ("application/octet-stream")
    verify_manifest_artifacts(run_dir, first)


def test_synthetic_pilot_records_null_controls_and_no_real_data_claim(tmp_path: Path) -> None:
    manifest = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "b" * 64,
        contract=_contract(),
    )

    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    acceptance_raw = (run_dir / "d0_acceptance.json").read_bytes()
    acceptance = json.loads(acceptance_raw.decode("utf-8"))
    assert acceptance_raw == _canonical(acceptance).encode("utf-8")
    assert acceptance["schema"] == "ResearchD0AcceptanceV1"
    assert acceptance["schema_version"] == 1
    assert acceptance["run_id"] == manifest["run_id"]
    assert acceptance["research_contract_id"] == manifest["research_contract_id"]
    assert acceptance["contract_hash"] == manifest["contract_hash"]
    assert acceptance["dataset_hash"] == manifest["dataset_hash"]
    assert acceptance["execution_fingerprint"] == manifest["execution_fingerprint"]
    assert b'"passed"' not in acceptance_raw
    assert b'"all_passed"' not in acceptance_raw
    measurements = acceptance["measurements"]
    assert len(measurements["planted_events"]) == 1
    assert measurements["monotonic_event_count"] == 0
    assert measurements["single_trough_event_count"] == 0
    assert measurements["topology"]["forward_outcome_observations"] == 4
    assert measurements["topology"]["rejected_boundaries"] == ["D1_D2", "D2_D3"]
    assert measurements["power"]["estimated_power"] >= 0.89


def test_d0_acceptance_byte_validator_matches_file_validator(tmp_path: Path) -> None:
    manifest = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "c" * 64,
        contract=_contract(),
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    raw = (run_dir / "d0_acceptance.json").read_bytes()
    validated = validate_d0_acceptance_bytes(
        raw,
        manifest,
        project_id=str(manifest["project_id"]),
        contract_id=str(manifest["research_contract_id"]),
        contract_hash=str(manifest["contract_hash"]),
        dataset_hash=str(manifest["dataset_hash"]),
        execution_fingerprint=str(manifest["execution_fingerprint"]),
        d0_operator_fingerprint=str(manifest["d0_operator_fingerprint"]),
    )
    assert validated["run_id"] == manifest["run_id"]
    with pytest.raises(DataError, match="canonical JSON"):
        validate_d0_acceptance_bytes(
            raw + b"\n",
            manifest,
            project_id=str(manifest["project_id"]),
            contract_id=str(manifest["research_contract_id"]),
            contract_hash=str(manifest["contract_hash"]),
            dataset_hash=str(manifest["dataset_hash"]),
            execution_fingerprint=str(manifest["execution_fingerprint"]),
            d0_operator_fingerprint=str(manifest["d0_operator_fingerprint"]),
        )
    assert manifest["real_market_evidence"] is False
    assert manifest["eligible_for_holdout_or_execution"] is False


def test_synthetic_pilot_recovers_identical_artifacts_left_before_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = _artifacts.write_manifest
    failed = False

    def interrupt_before_manifest(path: Path, manifest: dict[str, object]) -> None:
        nonlocal failed
        if not failed:
            failed = True
            raise DataError("simulated loss after artifact publication")
        original(path, manifest)

    monkeypatch.setattr(_artifacts, "write_manifest", interrupt_before_manifest)
    with pytest.raises(DataError, match="simulated loss"):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "c" * 64,
            contract=_contract(),
        )
    run_dirs = list((tmp_path / "runs").iterdir())
    assert len(run_dirs) == 1
    assert not (run_dirs[0] / "manifest.json").exists()

    recovered = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "c" * 64,
        contract=_contract(),
    )
    verify_manifest_artifacts(run_dirs[0], recovered)


def test_synthetic_pilot_rejects_invalid_authority_inputs(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="finite JSON"):
        _canonical({"effect": float("nan")})
    with pytest.raises(DataError, match="canonical project_id"):
        run_synthetic_pilot(
            tmp_path,
            project_id="caller-label",
            contract_id="rc_" + "d" * 64,
            contract=_contract(),
        )
    with pytest.raises(DataError, match="content-addressed contract_id"):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="caller-label",
            contract=_contract(),
        )
    with pytest.raises(DataError, match="ResearchContractV1"):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "d" * 64,
            contract={"schema": "ResearchContractV2"},
        )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda contract: contract["event_definition"].__setitem__("name", "owner_idea_event"),
            "only supports the canonical double_bottom event",
        ),
        (
            lambda contract: contract["event_definition"].__setitem__(
                "availability", "neckline_breakout_confirmed"
            ),
            "only supports second_trough_confirmable availability",
        ),
        (
            lambda contract: contract["resolved_material_choices"].__setitem__(
                "event_availability", "neckline_breakout_confirmed"
            ),
            "material event availability disagrees",
        ),
        (
            lambda contract: contract["protocol"]["d0_operator"].__setitem__(
                "fingerprint", "0" * 64
            ),
            "registered D0 operator binding does not match",
        ),
        (
            lambda contract: contract["protocol"]["d0_operator"]["operator"]["spec"].__setitem__(
                "pivot_right", 0
            ),
            "registered D0 operator binding does not match",
        ),
        (
            lambda contract: contract["resolved_material_choices"].__setitem__(
                "chart_construction", "synthetic_only"
            ),
            "registers no D0 operator generation for the 'synthetic_only' chart",
        ),
        (
            lambda contract: contract["chart_fingerprint"].__setitem__("bar_duration_minutes", 240),
            "chart fingerprint does not match",
        ),
        (
            lambda contract: (
                contract["primary_claim"].__setitem__("horizon_trading_minutes", 60),
                contract["protocol"]["primary_claims"][0].__setitem__(
                    "horizon_trading_minutes", 60
                ),
            ),
            "primary claim does not match",
        ),
        (
            lambda contract: (
                contract["primary_claim"].__setitem__("minimum_effect_return", 0.01),
                contract["protocol"]["primary_claims"][0].__setitem__(
                    "minimum_effect_return", 0.01
                ),
            ),
            "primary claim does not match",
        ),
        (
            lambda contract: contract["protocol"]["d0_operator"]["topology"].__setitem__(
                "schema_version", 1
            ),
            "registered D0 operator binding does not match",
        ),
        (
            # A well-formed foreign generation is still refused before compute, but as an
            # explicit generation mismatch rather than an error implying tampering.
            lambda contract: contract["protocol"]["d0_operator"]["fixture"].__setitem__(
                "fixture_version", 2
            ),
            "generation mismatch, not tampering",
        ),
    ],
)
def test_synthetic_pilot_rejects_unsupported_or_drifted_event_contracts(
    tmp_path: Path,
    mutate: object,
    message: str,
) -> None:
    contract = _contract()
    assert callable(mutate)
    mutate(contract)

    with pytest.raises(DataError, match=message):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "1" * 64,
            contract=contract,
        )
    assert not (tmp_path / "runs").exists()


def test_synthetic_pilot_requires_approved_consistent_protocol_binding(tmp_path: Path) -> None:
    for field, replacement, message in (
        ("approval_ready", False, "approval_ready=true"),
        ("blocking_questions", [{"id": "event_availability"}], "no blocking questions"),
        ("scope", "confirmation", "exploration contract"),
    ):
        contract = _contract()
        contract[field] = replacement
        with pytest.raises(DataError, match=message):
            run_synthetic_pilot(
                tmp_path,
                project_id="11111111-1111-4111-8111-111111111111",
                contract_id="rc_" + "2" * 64,
                contract=contract,
            )

    contract = _contract()
    protocol = contract["protocol"]
    assert isinstance(protocol, dict)
    protocol["event_definition"] = {"name": "double_bottom"}
    with pytest.raises(DataError, match="protocol event definition disagrees"):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "3" * 64,
            contract=contract,
        )
    assert not (tmp_path / "runs").exists()


def test_synthetic_pilot_fails_when_fixture_or_hash_contract_drifts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(research_runtime, "detect_double_bottom_events", lambda _bars, _spec: ())
    with pytest.raises(DataError, match="did not calibrate"):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "e" * 64,
            contract=_contract(),
        )
    monkeypatch.undo()
    contract = _contract()
    contract["hashes"] = ["not", "an", "object"]
    with pytest.raises(DataError, match="hashes must be an object"):
        run_synthetic_pilot(
            tmp_path,
            project_id="11111111-1111-4111-8111-111111111111",
            contract_id="rc_" + "f" * 64,
            contract=contract,
        )


def test_future_generation_contract_binding_gets_a_generation_error() -> None:
    """A well-formed different registered generation must not be reported as tampering."""
    contract = _contract()
    protocol = contract["protocol"]
    assert isinstance(protocol, dict)
    binding = protocol["d0_operator"]
    assert isinstance(binding, dict)
    fixture = binding["fixture"]
    assert isinstance(fixture, dict)
    fixture["fixture_version"] = 2
    with pytest.raises(DataError, match="generation mismatch, not tampering"):
        validate_d0_pilot_contract(contract)


def test_future_generation_acceptance_artifact_gets_a_generation_error(tmp_path: Path) -> None:
    """Reading a run from another registered generation fails with the generation error."""
    manifest = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "a" * 64,
        contract=_contract(),
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    path = run_dir / "d0_acceptance.json"
    acceptance = json.loads(path.read_text(encoding="utf-8"))
    acceptance["fixture_version"] = 2
    path.write_text(_canonical(acceptance), encoding="utf-8")

    with pytest.raises(DataError, match="generation mismatch, not tampering"):
        research_runtime.validate_d0_acceptance_artifact(
            run_dir,
            manifest,
            project_id=str(manifest["project_id"]),
            contract_id=str(manifest["research_contract_id"]),
            contract_hash=str(manifest["contract_hash"]),
            dataset_hash=str(manifest["dataset_hash"]),
            execution_fingerprint=str(manifest["execution_fingerprint"]),
            d0_operator_fingerprint=str(manifest["d0_operator_fingerprint"]),
        )


def test_registered_d0_fingerprints_are_pinned() -> None:
    """Golden pin: any registered-constant drift must be a conscious generation bump."""
    operator = registered_d0_operator(_contract())
    assert operator["fingerprint"] == (
        "03911da2217e694b4406dbbc42a641a791889af656299feef6cb4783e77f0c42"
    )
    assert d0_execution_fingerprint(_contract()) == (
        "aec9becaf16abf768a22f2a8a9a1a680524227e07026915b73368db213c1f487"
    )
    daily_operator = registered_d0_operator(_daily_contract())
    assert daily_operator["fingerprint"] == (
        "deac44ea9d639e1cc82a63e65c158c4b557449d6c7e88b4ce2e1bbe44212c2e6"
    )
    assert d0_execution_fingerprint(_daily_contract()) == (
        "03c38397a68a0924fcbc5cfb1e433c95d30184dbaf93142a1f7dca8d44f23279"
    )


def test_registered_daily_generation_operator_binds_the_gate4_material_combo() -> None:
    """R6a (ADR-0026): the tiingo_daily_fallback combo has its own registered generation."""
    contract = _daily_contract()
    operator = registered_d0_operator(contract)
    assert validate_d0_pilot_contract(contract) == operator
    fixture = operator["fixture"]
    assert isinstance(fixture, dict)
    assert fixture["fixture_id"] == "spy_session_daily_double_bottom_v1"
    assert fixture["fixture_version"] == 1
    assert fixture["bar_duration_minutes"] == 1_440
    assert fixture["real_market_evidence"] is False
    chart = operator["chart"]
    assert isinstance(chart, dict)
    assert chart["construction_choice"] == "tiingo_daily_fallback"
    primary_outcome = operator["primary_outcome"]
    assert isinstance(primary_outcome, dict)
    assert primary_outcome["choice"] == "next_regular_session_return_50bp"
    assert primary_outcome["horizon"] == "next_regular_session"
    assert primary_outcome["minimum_effect_return"] == 0.005
    sixty = registered_d0_operator(_contract())
    daily_inner = operator["operator"]
    sixty_inner = sixty["operator"]
    assert isinstance(daily_inner, dict) and isinstance(sixty_inner, dict)
    assert daily_inner["spec"] == sixty_inner["spec"]  # one shared detector across generations
    assert operator["fingerprint"] != sixty["fingerprint"]
    daily_fixture = fixture
    sixty_fixture = sixty["fixture"]
    assert isinstance(sixty_fixture, dict)
    assert daily_fixture["definition_fingerprint"] != sixty_fixture["definition_fingerprint"]


def test_daily_synthetic_pilot_calibrates_and_reverifies_under_its_generation(
    tmp_path: Path,
) -> None:
    manifest = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "9" * 64,
        contract=_daily_contract(),
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    acceptance = json.loads((run_dir / "d0_acceptance.json").read_text(encoding="utf-8"))
    assert acceptance["fixture_id"] == "spy_session_daily_double_bottom_v1"
    assert acceptance["fixture_version"] == 1
    measurements = acceptance["measurements"]
    assert len(measurements["planted_events"]) == 1
    assert measurements["monotonic_event_count"] == 0
    assert measurements["single_trough_event_count"] == 0
    assert measurements["topology"]["forward_outcome_observations"] == 1
    assert measurements["topology"]["rejected_boundaries"] == ["D1_D2", "D2_D3"]
    power = measurements["power"]
    assert power["alternative_effect"] == 0.010
    assert power["minimum_effect"] == 0.005
    assert power["standard_deviation"] == 0.012
    assert power["required_observations"] == 50
    assert power["estimated_power"] >= 0.89
    assert power["seed"] == 7  # protocol-frozen, shared by every generation
    assert manifest["real_market_evidence"] is False
    assert manifest["watermark"] == "EXPLORATORY"
    research_runtime.validate_d0_acceptance_artifact(
        run_dir,
        manifest,
        project_id=str(manifest["project_id"]),
        contract_id=str(manifest["research_contract_id"]),
        contract_hash=str(manifest["contract_hash"]),
        dataset_hash=str(manifest["dataset_hash"]),
        execution_fingerprint=str(manifest["execution_fingerprint"]),
        d0_operator_fingerprint=str(manifest["d0_operator_fingerprint"]),
    )


def test_acceptance_from_the_other_registered_generation_is_an_authority_mismatch(
    tmp_path: Path,
) -> None:
    """A registered-but-different generation contradicting its own manifest fails closed."""
    manifest = run_synthetic_pilot(
        tmp_path,
        project_id="11111111-1111-4111-8111-111111111111",
        contract_id="rc_" + "8" * 64,
        contract=_daily_contract(),
    )
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    path = run_dir / "d0_acceptance.json"
    acceptance = json.loads(path.read_text(encoding="utf-8"))
    acceptance["fixture_id"] = "spy_60m_double_bottom_v1"
    path.write_text(_canonical(acceptance), encoding="utf-8")

    with pytest.raises(DataError, match="authority mismatch"):
        research_runtime.validate_d0_acceptance_artifact(
            run_dir,
            manifest,
            project_id=str(manifest["project_id"]),
            contract_id=str(manifest["research_contract_id"]),
            contract_hash=str(manifest["contract_hash"]),
            dataset_hash=str(manifest["dataset_hash"]),
            execution_fingerprint=str(manifest["execution_fingerprint"]),
            d0_operator_fingerprint=str(manifest["d0_operator_fingerprint"]),
        )
