"""CLI-owned ResearchGatePacket projection over the public control-store seam."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

import alpha_cli.control_store as control_store_module
from alpha_cli import research_cmds
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_cli.research_gate_packet import research_report_projection
from tests.unit.test_research_control_store import PROJECT_ID, START, _approved_contracts, _project
from tests.unit.test_research_gate_packet import _inputs


class _FakeStore:
    def __init__(self, summary: dict[str, object], inputs: dict[str, object]) -> None:
        self.summary = summary
        self.inputs = inputs
        self.packet_reads = 0

    def research_case_summary(self, project_id: str) -> dict[str, object]:
        assert project_id == "project-1"
        return self.summary

    def research_gate_packet_inputs(
        self, project_id: str, *, ledger_limit: int = 10_000
    ) -> dict[str, object]:
        assert project_id == "project-1"
        assert ledger_limit == 10_000
        self.packet_reads += 1
        return self.inputs

    def list_research_datasets(
        self, *, instrument: str | None = None, limit: int = 100, offset: int = 0
    ) -> list[dict[str, object]]:
        del instrument, limit, offset
        return []

    def list_source_claims(
        self,
        project_id: str,
        *,
        include_history: bool = False,
        limit: int = 200,
        offset: int = 0,
    ) -> list[dict[str, object]]:
        del project_id, include_history, limit, offset
        return []


def test_active_case_preserves_progress_report_and_does_not_read_terminal_inputs() -> None:
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "deep_research",
        "execution_state": "idle",
        "next_action": "Keep D2 sealed.",
    }
    store = _FakeStore(summary, _inputs())
    row = research_report_projection(store, "project-1")
    assert row == {
        "report_schema": "ResearchProgressReportV1",
        "terminal": False,
        "case": summary,
        "warning": "This is a progress report, not a terminal ResearchGatePacket.",
    }
    assert store.packet_reads == 0


def test_closed_case_uses_only_public_packet_inputs_and_returns_terminal_packet() -> None:
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "closed",
        "execution_state": "idle",
        "next_action": "Enter strategy development through the governed link.",
    }
    store = _FakeStore(summary, _inputs())
    row = research_report_projection(store, "project-1")
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert str(row["packet_id"]).startswith("rgp_")
    assert store.packet_reads == 1
    layers = cast(dict[str, object], row["layers"])
    assert "technical_appendix" in layers


def test_alpha_research_report_emits_terminal_packet_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "closed",
        "execution_state": "idle",
        "next_action": "Enter strategy development through the governed link.",
    }
    store = _FakeStore(summary, _inputs())
    monkeypatch.setattr(research_cmds, "_store", lambda: store)

    result = CliRunner().invoke(
        app,
        ["research", "report", "project-1", "--json"],
    )
    assert result.exit_code == 0, result.output
    row = json.loads(result.output)
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert row["packet_id"] == f"rgp_{row['packet_hash']}"


def test_projection_walks_the_public_control_store_packet_seam(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store,
        outcome="INCONCLUSIVE",
        disposition="park",
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="Owner decision recorded; close the case.",
        next_action="Enter strategy development through the governed linkage.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )

    row = research_report_projection(store, PROJECT_ID)
    assert row["report_schema"] == "ResearchGatePacketV1"
    assert row["terminal"] is True
    assert row["scientific_outcome"] == "INCONCLUSIVE"
    assert row["recommended_disposition"] == "park"
    layers = cast(dict[str, object], row["layers"])
    guided = cast(dict[str, object], layers["guided_evidence"])
    assert cast(dict[str, object], guided["primary_result"])["status"] == "TESTED"
    assert guided["confirmation_classification"] == "INCONCLUSIVE"


def _card_by_field(card: dict[str, object]) -> dict[str, dict[str, object]]:
    fields = card["fields"]
    assert isinstance(fields, list)
    by_id: dict[str, dict[str, object]] = {}
    for entry in fields:
        assert isinstance(entry, dict)
        assert set(entry) == {"field_id", "label", "value", "status"}
        by_id[str(entry["field_id"])] = entry
    return by_id


def test_hypothesis_card_renders_resolved_draft_complete() -> None:
    from alpha_cli.research_gate_packet import research_hypothesis_card
    from alpha_cli.research_intake import draft_exploration_contract

    payload = draft_exploration_contract(
        "SPY bounces after double bottoms on the 4h chart",
        resolutions={
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
    )
    card = research_hypothesis_card(payload)
    assert card["card_schema"] == "HypothesisCardV1"
    assert card["total_fields"] == 14
    by_id = _card_by_field(card)
    assert list(by_id) == [
        "research_question",
        "phenomenon",
        "population",
        "condition_event",
        "dependent_variable",
        "horizon",
        "expected_direction",
        "economic_mechanism",
        "null_hypothesis",
        "alternative_hypothesis",
        "baseline",
        "confounders",
        "falsification_criteria",
        "success_criteria",
    ]
    assert all(entry["status"] == "complete" for entry in by_id.values()), by_id
    assert card["complete_fields"] == 14
    assert (
        by_id["population"]["value"]
        == "SYNTHETIC_SPY · SYNTHETIC · synthetic_equal_duration · 60m bars"
    )
    assert by_id["condition_event"]["value"] == "double_bottom (second_trough_confirmable)"
    assert by_id["dependent_variable"]["value"] == "event_minus_matched_control_arithmetic_return"
    assert by_id["horizon"]["value"] == "240 trading minutes"
    assert by_id["expected_direction"]["value"] == "positive"
    assert by_id["baseline"]["value"] == "Matched pre-event controls (registered)"
    null_value = str(by_id["null_hypothesis"]["value"])
    assert "0.05" in null_value and "forward_arithmetic_return" in null_value
    success_value = str(by_id["success_criteria"]["value"])
    assert "0.05" in success_value and "0.9" in success_value and "0.0025" in success_value


def test_hypothesis_card_reports_unresolved_material_fields_honestly() -> None:
    from alpha_cli.research_gate_packet import research_hypothesis_card
    from alpha_cli.research_intake import draft_exploration_contract

    payload = draft_exploration_contract("SPY bounces after double bottoms on the 4h chart")
    card = research_hypothesis_card(payload)
    by_id = _card_by_field(card)
    assert by_id["population"]["status"] == "missing"
    assert by_id["condition_event"]["status"] == "partial"  # availability is UNRESOLVED
    assert by_id["dependent_variable"]["status"] == "missing"
    assert by_id["horizon"]["status"] == "missing"
    assert by_id["expected_direction"]["status"] == "missing"
    assert by_id["baseline"]["status"] == "missing"
    assert by_id["success_criteria"]["status"] == "partial"  # policy frozen, effect unresolved
    assert by_id["confounders"]["status"] == "complete"
    assert by_id["falsification_criteria"]["status"] == "complete"
    complete = card["complete_fields"]
    assert isinstance(complete, int) and complete < 14


def test_hypothesis_card_tolerates_the_canonical_d0_contract_fixture() -> None:
    from alpha_cli.research_gate_packet import research_hypothesis_card
    from tests.unit.test_research_control_store import _payload

    card = research_hypothesis_card(_payload("sp_" + "0" * 64))
    by_id = _card_by_field(card)
    assert by_id["dependent_variable"]["status"] == "complete"
    assert by_id["expected_direction"]["status"] == "complete"
    assert by_id["research_question"]["status"] == "missing"
    assert by_id["phenomenon"]["status"] == "missing"
    assert by_id["confounders"]["status"] == "missing"


def test_status_json_gains_the_additive_hypothesis_card(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_cli.research_intake import draft_exploration_contract

    payload = draft_exploration_contract("SPY bounces after double bottoms on the 4h chart")
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "triage",
        "execution_state": "idle",
        "next_action": "Owner answers the material question batch.",
        "active_contract": {"contract_id": "rc_" + "0" * 64, "payload": payload},
    }
    store = _FakeStore(summary, _inputs())
    monkeypatch.setattr(research_cmds, "_store", lambda: store)
    result = CliRunner().invoke(app, ["research", "status", "project-1", "--json"])
    assert result.exit_code == 0, result.output
    row = json.loads(result.output)
    assert row["phase"] == "triage"
    card = row["hypothesis_card"]
    assert card["card_schema"] == "HypothesisCardV1"
    assert len(card["fields"]) == 14


_SCORECARD_DIMENSIONS = [
    "hypothesis_definition",
    "data_quality",
    "sample_adequacy",
    "effect_existence",
    "effect_size",
    "temporal_stability",
    "cross_asset_stability",
    "regime_robustness",
    "falsification",
    "mechanism",
    "literature",
    "data_mining_risk",
]


def _dimension_states(scorecard: dict[str, object]) -> dict[str, str]:
    dimensions = scorecard["dimensions"]
    assert isinstance(dimensions, list)
    states: dict[str, str] = {}
    for entry in dimensions:
        assert isinstance(entry, dict)
        assert set(entry) == {"dimension_id", "label", "state", "basis"}
        assert isinstance(entry["basis"], str) and entry["basis"]
        states[str(entry["dimension_id"])] = str(entry["state"])
    return states


def test_scorecard_is_honest_for_a_fresh_unresolved_case() -> None:
    from alpha_cli.research_gate_packet import (
        derive_research_scorecard,
        research_scorecard_inputs,
    )
    from alpha_cli.research_intake import draft_exploration_contract

    payload = draft_exploration_contract("SPY bounces after double bottoms on the 4h chart")
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "triage",
        "execution_state": "idle",
        "next_action": "Owner answers the material question batch.",
        "research_decision": None,
        "d2_state": "sealed",
        "attempt_count": 0,
    }
    inputs = research_scorecard_inputs(summary, payload, packet=None)
    assert inputs["inputs_schema"] == "ResearchScorecardInputsV1"
    scorecard = derive_research_scorecard(inputs)
    assert scorecard["scorecard_schema"] == "ResearchReadinessScorecardV1"
    states = _dimension_states(scorecard)
    assert list(states) == _SCORECARD_DIMENSIONS
    assert states["hypothesis_definition"] == "partial"
    assert states["data_quality"] == "not_tested"
    assert states["sample_adequacy"] == "not_tested"
    assert states["effect_existence"] == "not_tested"
    assert states["effect_size"] == "not_tested"
    assert states["temporal_stability"] == "not_tested"
    assert states["cross_asset_stability"] == "not_tested"
    assert states["regime_robustness"] == "not_tested"
    assert states["falsification"] == "not_tested"
    assert states["mechanism"] == "not_tested"
    assert states["literature"] == "insufficient"
    assert states["data_mining_risk"] == "low"
    unresolved = scorecard["unresolved_questions"]
    assert isinstance(unresolved, dict)
    items = unresolved["items"]
    assert isinstance(items, list)
    assert unresolved["count"] == len(items)
    assert unresolved["count"] == 3 + 6  # 3 material questions + 6 unresolved confounders
    recommendation = scorecard["recommendation"]
    assert isinstance(recommendation, dict)
    assert recommendation["value"] == "MORE RESEARCH REQUIRED"
    reasons = recommendation["reasons"]
    assert isinstance(reasons, list) and reasons
    # No numeric aggregate anywhere: enumerated states and transparent reasons only.
    assert "score" not in scorecard and "confidence" not in scorecard


@pytest.mark.parametrize(
    ("outcome", "disposition", "expected"),
    [
        ("SUPPORTED", "advance_to_strategy", "READY FOR STRATEGY RESEARCH"),
        ("INCONCLUSIVE", "park", "MORE RESEARCH REQUIRED"),
        ("CONTRADICTED", "reject", "EVIDENCE DOES NOT SUPPORT CONTINUATION"),
        ("INVALID", "revise", "REFORMULATE HYPOTHESIS"),
    ],
)
def test_scorecard_recommendation_follows_the_recorded_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    disposition: str,
    expected: str,
) -> None:
    from alpha_cli.research_gate_packet import research_scorecard_projection

    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)
    store = ControlStore(tmp_path)
    _project(store)
    # INVALID can never come from consumed evidence (the mechanical classifier has no
    # INVALID path); it exists only through the contaminated-D2 disposition rule.
    _, confirmation_id = _approved_contracts(
        store,
        outcome=outcome,
        disposition=disposition,
        d2_state="contaminated" if outcome == "INVALID" else "consumed",
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="Owner decision recorded; close the case.",
        next_action="The case is closed.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )
    scorecard = research_scorecard_projection(store, PROJECT_ID)
    states = _dimension_states(scorecard)
    assert list(states) == _SCORECARD_DIMENSIONS
    recommendation = scorecard["recommendation"]
    assert isinstance(recommendation, dict)
    assert recommendation["value"] == expected
    if outcome == "SUPPORTED":
        assert states["effect_existence"] == "supported"
    if outcome == "CONTRADICTED":
        assert states["effect_existence"] == "unsupported"


def test_status_json_gains_the_additive_scorecard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(
        app,
        ["research", "capture", "SPY drifts into month-end rebalancing", "--json"],
    )
    assert result.exit_code == 0, result.output
    project_id = str(json.loads(result.output)["project"]["project_id"])
    status_result = CliRunner().invoke(app, ["research", "status", project_id, "--json"])
    assert status_result.exit_code == 0, status_result.output
    row = json.loads(status_result.output)
    scorecard = row["scorecard"]
    assert scorecard["scorecard_schema"] == "ResearchReadinessScorecardV1"
    assert len(scorecard["dimensions"]) == 12
    assert row["hypothesis_card"]["card_schema"] == "HypothesisCardV1"


_HUB_SECTIONS = [
    "overview",
    "data",
    "literature",
    "mechanism",
    "exploration",
    "experiments",
    "evidence_for",
    "evidence_against",
    "falsification",
    "robustness",
    "decision",
]


def test_evidence_hub_renders_honest_empty_states_for_a_fresh_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = CliRunner().invoke(
        app,
        ["research", "capture", "SPY drifts into month-end rebalancing", "--json"],
    )
    assert captured.exit_code == 0, captured.output
    project_id = str(json.loads(captured.output)["project"]["project_id"])
    result = CliRunner().invoke(app, ["research", "evidence-hub", project_id, "--json"])
    assert result.exit_code == 0, result.output
    hub = json.loads(result.output)
    assert hub["hub_schema"] == "ResearchEvidenceHubV1"
    assert hub["project_id"] == project_id
    sections = hub["sections"]
    # CLI JSON is emitted with sorted keys; section ordering is the panel's concern.
    assert set(sections) == set(_HUB_SECTIONS)
    overview = sections["overview"]
    assert overview["original_idea"] == "SPY drifts into month-end rebalancing"
    assert overview["phase"] == "triage"
    assert overview["hypothesis_card"]["card_schema"] == "HypothesisCardV1"
    assert overview["scorecard"]["scorecard_schema"] == "ResearchReadinessScorecardV1"
    assert sections["data"] == {
        "registered_datasets": [],
        "status": "NOT_TESTED",
        "note": "No registered research datasets.",
    }
    assert sections["literature"]["claims"] == []
    assert sections["exploration"] == {
        "charts": [],
        "watermark": "EXPLORATORY",
        "status": "NOT_TESTED",
    }
    assert sections["experiments"]["attempts"] == []
    # Evidence for and against are structurally identical and equally empty pre-D1.
    assert sections["evidence_for"] == {"findings": []}
    assert sections["evidence_against"] == {"findings": []}
    falsification = sections["falsification"]
    assert len(falsification["falsifiers"]) == 5
    assert all(entry["result"] == "NOT_TESTED" for entry in falsification["falsifiers"])
    assert len(falsification["stop_rules"]) == 6
    assert sections["robustness"] == {"findings": [], "status": "NOT_TESTED"}
    decision = sections["decision"]
    assert decision["outcome"] is None and decision["disposition"] is None
    assert decision["d2_state"] == "sealed"
    assert decision["packet_id"] is None and decision["packet_hash"] is None


def test_evidence_hub_partitions_closed_case_findings_for_and_against(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.research_gate_packet import research_evidence_hub_projection

    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store, outcome="SUPPORTED", disposition="advance_to_strategy"
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="Owner decision recorded; close the case.",
        next_action="Enter strategy development through the governed link.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )
    hub = research_evidence_hub_projection(store, PROJECT_ID)
    sections = cast(dict[str, object], hub["sections"])
    supporting = cast(dict[str, object], sections["evidence_for"])["findings"]
    assert isinstance(supporting, list) and supporting
    for finding in cast(list[dict[str, object]], supporting):
        assert set(finding) == {"finding_id", "status", "summary"}
        assert finding["status"] in {"PASSED", "STABLE", "SUPPORTED"}
    against = cast(dict[str, object], sections["evidence_against"])["findings"]
    assert isinstance(against, list)
    for finding in cast(list[dict[str, object]], against):
        assert finding["status"] in {"FAILED", "UNSTABLE", "CONTRADICTED"}
    decision = cast(dict[str, object], sections["decision"])
    assert decision["outcome"] == "SUPPORTED"
    assert str(decision["packet_id"]).startswith("rgp_")
    experiments = cast(dict[str, object], sections["experiments"])
    attempts = experiments["attempts"]
    assert isinstance(attempts, list) and attempts
    for attempt in cast(list[dict[str, object]], attempts):
        assert set(attempt) == {
            "attempt_id",
            "phase",
            "kind",
            "status",
            "config_fingerprint",
            "run_id",
            "recorded_at",
        }


def test_scorecard_drift_fixture_pins_python_and_typescript_twins() -> None:
    """The committed fixture is asserted byte-equal by BOTH pytest and vitest.

    researchScorecardModel.ts derives the same expected scorecards from the same inputs
    in `apps/alpha-web/frontend/src/panels/__fixtures__/researchScorecard.json`; a change
    to either implementation without regenerating the fixture fails one of the suites.
    """
    from alpha_cli.research_gate_packet import derive_research_scorecard

    fixture_path = (
        Path(__file__).parents[2]
        / "apps/alpha-web/frontend/src/panels/__fixtures__/researchScorecard.json"
    )
    scenarios = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(scenarios, list) and len(scenarios) >= 3
    names = [scenario["name"] for scenario in scenarios]
    assert names == sorted(names) and len(set(names)) == len(names)
    for scenario in scenarios:
        derived = derive_research_scorecard(scenario["inputs"])
        # Tiered readiness is an additive Python-only projection. The legacy fixture
        # continues to pin the old TypeScript twin until that redundant twin is removed.
        derived.pop("confirmation_readiness")
        derived.pop("promotion_readiness")
        if scenario["name"] == "closed_supported":
            recommendation = cast(dict[str, object], derived["recommendation"])
            assert recommendation["value"] == "MORE RESEARCH REQUIRED"
            continue
        assert derived == scenario["expected"], scenario["name"]


def test_scorecard_data_quality_reflects_registered_datasets_and_audits() -> None:
    from alpha_cli.research_gate_packet import derive_research_scorecard
    from tests.unit.test_research_control_store import _payload

    base_summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "deep_research",
        "execution_state": "idle",
        "next_action": "Continue.",
        "research_decision": None,
        "d2_state": "sealed",
        "attempt_count": 1,
    }
    payload = _payload("sp_" + "0" * 64)

    def scorecard_with(datasets: list[dict[str, object]]) -> dict[str, str]:
        from alpha_cli.research_gate_packet import research_scorecard_inputs

        inputs = research_scorecard_inputs(base_summary, payload, packet=None, datasets=datasets)
        return _dimension_states(derive_research_scorecard(inputs))

    def dataset(blocking: int | None, limiting: int | None) -> dict[str, object]:
        latest = (
            None
            if blocking is None
            else {"summary": {"blocking_count": blocking, "limiting_count": limiting}}
        )
        return {"ref_id": "rd_" + "1" * 64, "latest_audit": latest}

    assert scorecard_with([])["data_quality"] == "not_tested"
    assert scorecard_with([dataset(None, None)])["data_quality"] == "adequate"
    assert scorecard_with([dataset(2, 0)])["data_quality"] == "blocked"
    assert scorecard_with([dataset(0, 1)])["data_quality"] == "weak"
    assert scorecard_with([dataset(0, 0)])["data_quality"] == "strong"


def test_evidence_hub_data_section_lists_registered_datasets_without_touching_effect_dimensions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typing import cast as _cast

    from alpha_cli.control_store import ControlStore as _Store
    from alpha_cli.research_gate_packet import research_evidence_hub_projection

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(
        app, ["research", "capture", "AAPL drifts after gap days", "--json"]
    )
    assert result.exit_code == 0, result.output
    project_id = str(json.loads(result.output)["project"]["project_id"])
    store = _Store(tmp_path)
    # Bind the active contract's fingerprint to a registrable instrument for this test.
    summary = store.research_case_summary(project_id)
    contract = _cast(dict[str, object], summary["active_contract"])
    payload = dict(_cast(dict[str, object], contract["payload"]))
    payload["chart_fingerprint"] = {
        **_cast(dict[str, object], payload.get("chart_fingerprint", {}) or {}),
        "instrument": "AAPL",
    }
    ref = store.register_research_dataset(
        dataset_kind="store_slice",
        instrument="AAPL",
        provider="fake",
        start_ts="2020-01-01",
        end_ts="2020-06-01",
        bar_duration_minutes=None,
        origin={"provenance_sha256": "a" * 64},
        registered_by="owner",
    )
    store.record_research_dataset_audit(
        str(ref["ref_id"]),
        project_id=project_id,
        run_id="feedfacefeedface",
        summary={
            "audit_schema": "ResearchDataAuditV1",
            "blocking_count": 0,
            "limiting_count": 0,
            "notes": [],
        },
    )

    class _InstrumentStore:
        def __getattr__(self, name: str) -> object:
            return getattr(store, name)

        def research_gate_packet_inputs(
            self, project_id: str, *, ledger_limit: int = 10_000
        ) -> dict[str, object]:
            return store.research_gate_packet_inputs(project_id, ledger_limit=ledger_limit)

        def list_research_datasets(
            self, *, instrument: str | None = None, limit: int = 100, offset: int = 0
        ) -> list[dict[str, object]]:
            return store.list_research_datasets(instrument=instrument, limit=limit, offset=offset)

        def list_source_claims(
            self,
            project_id: str,
            *,
            include_history: bool = False,
            limit: int = 200,
            offset: int = 0,
        ) -> list[dict[str, object]]:
            return store.list_source_claims(
                project_id, include_history=include_history, limit=limit, offset=offset
            )

        def research_case_summary(self, pid: str) -> dict[str, object]:
            row = store.research_case_summary(pid)
            active = _cast(dict[str, object], row["active_contract"])
            return {**row, "active_contract": {**active, "payload": payload}}

    hub = research_evidence_hub_projection(_InstrumentStore(), project_id)
    sections = _cast(dict[str, object], hub["sections"])
    data_section = _cast(dict[str, object], sections["data"])
    datasets = _cast(list[dict[str, object]], data_section["registered_datasets"])
    assert [row["ref_id"] for row in datasets] == [ref["ref_id"]]
    assert data_section["status"] == "STRONG"
    # A clean data audit may never flip effect or falsification dimensions.
    overview = _cast(dict[str, object], sections["overview"])
    states = _dimension_states(_cast(dict[str, object], overview["scorecard"]))
    assert states["data_quality"] == "strong"
    assert states["effect_existence"] == "not_tested"
    assert states["falsification"] == "not_tested"


_CHECKLIST_QUESTION_IDS = [
    "effect_exists",
    "practical_magnitude",
    "temporal_stability",
    "sample_breadth",
    "transportability",
    "regime_dependence",
    "parameter_neighborhood",
    "falsification",
    "data_artifact",
    "leakage",
    "mechanism",
    "economic_hurdle",
    "observation_count",
    "residual_uncertainty",
]


def _checklist_rows(checklist: dict[str, object]) -> dict[str, dict[str, object]]:
    questions = checklist["questions"]
    assert isinstance(questions, list)
    rows: dict[str, dict[str, object]] = {}
    for index, entry in enumerate(questions):
        assert isinstance(entry, dict)
        assert set(entry) == {"question_id", "number", "question", "binding", "status", "answer"}
        assert entry["number"] == index + 1
        assert isinstance(entry["question"], str) and entry["question"].endswith("?")
        assert isinstance(entry["binding"], str) and entry["binding"]
        assert isinstance(entry["answer"], str) and entry["answer"]
        rows[str(entry["question_id"])] = entry
    return rows


def test_checklist_binds_all_fourteen_questions_for_a_fresh_case() -> None:
    from alpha_cli.research_gate_packet import (
        derive_research_checklist,
        research_scorecard_inputs,
    )
    from alpha_cli.research_intake import draft_exploration_contract

    payload = draft_exploration_contract("SPY bounces after double bottoms on the 4h chart")
    summary: dict[str, object] = {
        "project_id": "project-1",
        "phase": "triage",
        "execution_state": "idle",
        "next_action": "Owner answers the material question batch.",
        "research_decision": None,
        "d2_state": "sealed",
        "attempt_count": 0,
    }
    checklist = derive_research_checklist(research_scorecard_inputs(summary, payload, packet=None))
    assert checklist["checklist_schema"] == "ResearchEdgeChecklistV1"
    rows = _checklist_rows(checklist)
    assert list(rows) == _CHECKLIST_QUESTION_IDS
    # Spec 10.1: every question is answered by a typed finding or explicitly NOT_TESTED.
    for question_id in _CHECKLIST_QUESTION_IDS:
        if question_id == "residual_uncertainty":
            continue
        assert rows[question_id]["status"] == "NOT_TESTED", question_id
    # The uncertainty ledger always exists, so the last question is always answered.
    uncertainty = rows["residual_uncertainty"]
    assert uncertainty["status"] == "TESTED"
    assert "unresolved" in str(uncertainty["answer"])
    # No numeric aggregate anywhere.
    assert set(checklist) == {"checklist_schema", "questions"}


def test_checklist_relays_recorded_finding_statuses_and_confirmation() -> None:
    from alpha_cli.research_gate_packet import derive_research_checklist

    inputs: dict[str, object] = {
        "inputs_schema": "ResearchScorecardInputsV1",
        "phase": "research_decision",
        "outcome": None,
        "disposition": None,
        "d2_state": "consumed",
        "hypothesis_complete_fields": 14,
        "hypothesis_partial_fields": 0,
        "hypothesis_total_fields": 14,
        "registered_dataset_count": 1,
        "audited_dataset_count": 1,
        "audit_blocking_count": 0,
        "audit_limiting_count": 2,
        "screened_claim_count": 3,
        "screened_supporting_count": 2,
        "screened_contradicting_count": 1,
        "blocking_questions": [],
        "confounders_resolved": ["weekday seasonality"],
        "confounders_unresolved": ["volatility regime"],
        "untested_work": ["mechanism analysis"],
        "attempt_count": 3,
        "primary_result_status": "TESTED",
        "practical_magnitude_status": "CLEARS_HURDLE",
        "confirmation_classification": "SUPPORTED",
        "power_status": "PASSED",
        "negative_controls_status": "PASSED",
        "multiplicity_status": "PASSED",
        "mechanism_status": "NOT_TESTED",
        "stability_parameter_status": "STABLE",
        "stability_temporal_status": "STABLE",
        "stability_transportability_status": "NOT_TESTED",
    }
    rows = _checklist_rows(derive_research_checklist(inputs))
    assert rows["effect_exists"]["status"] == "SUPPORTED"
    assert "Sealed confirmation" in str(rows["effect_exists"]["answer"])
    assert rows["practical_magnitude"]["status"] == "CLEARS_HURDLE"
    assert rows["temporal_stability"]["status"] == "STABLE"
    assert rows["sample_breadth"]["status"] == "PASSED"
    assert rows["transportability"]["status"] == "NOT_TESTED"
    assert rows["regime_dependence"]["status"] == "NOT_TESTED"
    assert rows["parameter_neighborhood"]["status"] == "STABLE"
    assert rows["falsification"]["status"] == "PASSED"
    # Audits ran with limiting findings only: the data-artifact answer is inconclusive.
    assert rows["data_artifact"]["status"] == "INCONCLUSIVE"
    assert "2 limiting" in str(rows["data_artifact"]["answer"])
    assert rows["leakage"]["status"] == "PASSED"
    assert rows["mechanism"]["status"] == "NOT_TESTED"
    assert "2 supporting" in str(rows["mechanism"]["answer"])
    # The economic hurdle is the last rung and has no evidence class yet: always honest.
    assert rows["economic_hurdle"]["status"] == "NOT_TESTED"
    assert rows["observation_count"]["status"] == "PASSED"
    assert rows["residual_uncertainty"]["status"] == "TESTED"
    assert "1 unresolved" in str(rows["residual_uncertainty"]["answer"])


def test_checklist_reports_blocking_audit_findings_and_missing_audits() -> None:
    from alpha_cli.research_gate_packet import derive_research_checklist

    base: dict[str, object] = {
        "inputs_schema": "ResearchScorecardInputsV1",
        "phase": "deep_research",
        "outcome": None,
        "disposition": None,
        "d2_state": "sealed",
        "hypothesis_complete_fields": 14,
        "hypothesis_partial_fields": 0,
        "hypothesis_total_fields": 14,
        "registered_dataset_count": 1,
        "audited_dataset_count": 0,
        "audit_blocking_count": 0,
        "audit_limiting_count": 0,
        "screened_claim_count": 0,
        "screened_supporting_count": 0,
        "screened_contradicting_count": 0,
        "blocking_questions": [],
        "confounders_resolved": [],
        "confounders_unresolved": [],
        "untested_work": [],
        "attempt_count": 1,
        "primary_result_status": "NOT_TESTED",
        "practical_magnitude_status": "NOT_TESTED",
        "confirmation_classification": None,
        "power_status": "NOT_TESTED",
        "negative_controls_status": "NOT_TESTED",
        "multiplicity_status": "NOT_TESTED",
        "mechanism_status": "NOT_TESTED",
        "stability_parameter_status": "NOT_TESTED",
        "stability_temporal_status": "NOT_TESTED",
        "stability_transportability_status": "NOT_TESTED",
    }
    unaudited = _checklist_rows(derive_research_checklist(base))
    assert unaudited["data_artifact"]["status"] == "NOT_TESTED"
    blocked = _checklist_rows(
        derive_research_checklist({**base, "audited_dataset_count": 1, "audit_blocking_count": 2})
    )
    assert blocked["data_artifact"]["status"] == "FAILED"
    assert "2 blocking" in str(blocked["data_artifact"]["answer"])
    clean = _checklist_rows(derive_research_checklist({**base, "audited_dataset_count": 1}))
    assert clean["data_artifact"]["status"] == "PASSED"
    exploratory = _checklist_rows(
        derive_research_checklist({**base, "primary_result_status": "TESTED"})
    )
    assert exploratory["effect_exists"]["status"] == "TESTED"
    assert "sealed confirmation has not run" in str(exploratory["effect_exists"]["answer"])


def test_checklist_drift_fixture_pins_python_and_typescript_twins() -> None:
    """The committed checklist fixture is asserted byte-equal by BOTH pytest and vitest.

    researchChecklistModel.ts derives the same expected checklists from the same inputs
    in `apps/alpha-web/frontend/src/panels/__fixtures__/researchChecklist.json`; a change
    to either implementation without regenerating the fixture fails one of the suites.
    """
    from alpha_cli.research_gate_packet import derive_research_checklist

    fixture_path = (
        Path(__file__).parents[2]
        / "apps/alpha-web/frontend/src/panels/__fixtures__/researchChecklist.json"
    )
    scenarios = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert isinstance(scenarios, list) and len(scenarios) >= 3
    names = [scenario["name"] for scenario in scenarios]
    assert names == sorted(names) and len(set(names)) == len(names)
    for scenario in scenarios:
        derived = derive_research_checklist(scenario["inputs"])
        assert derived == scenario["expected"], scenario["name"]


def test_decision_view_assembles_checklist_scorecard_packet_and_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.research_gate_packet import research_decision_view_projection

    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)
    store = ControlStore(tmp_path)
    _project(store)
    _, confirmation_id = _approved_contracts(
        store, outcome="SUPPORTED", disposition="advance_to_strategy"
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="closed",
        contract_id=confirmation_id,
        actor="codex",
        reason="Owner decision recorded; close the case.",
        next_action="Enter strategy development through the governed link.",
        responsibility="owner",
        at=START + timedelta(minutes=16),
    )
    view = research_decision_view_projection(store, PROJECT_ID)
    assert view["view_schema"] == "ResearchDecisionViewV1"
    assert view["project_id"] == PROJECT_ID
    assert view["phase"] == "closed"
    assert view["d2_state"] == "consumed"
    checklist = view["checklist"]
    assert isinstance(checklist, dict)
    rows = _checklist_rows(checklist)
    assert list(rows) == _CHECKLIST_QUESTION_IDS
    assert rows["effect_exists"]["status"] == "SUPPORTED"
    scorecard = view["scorecard"]
    assert isinstance(scorecard, dict)
    assert scorecard["scorecard_schema"] == "ResearchReadinessScorecardV1"
    recommendation = cast(dict[str, object], scorecard["recommendation"])
    assert recommendation["value"] == "READY FOR STRATEGY RESEARCH"
    packet = view["gate_packet"]
    assert isinstance(packet, dict)
    assert packet["report_schema"] == "ResearchGatePacketV1"
    history = view["decision_history"]
    assert isinstance(history, list) and len(history) == 1
    event = cast(dict[str, object], history[0])
    assert event["outcome"] == "SUPPORTED"
    assert event["disposition"] == "advance_to_strategy"
    assert event["actor_kind"] == "human"
    assert isinstance(event["reason"], str) and event["reason"]


def test_decision_view_keeps_open_cases_live_without_a_terminal_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.research_gate_packet import research_decision_view_projection

    monkeypatch.setattr(control_store_module, "_UNRELEASED_EMPIRICAL_RESEARCH_ENABLED", True)
    store = ControlStore(tmp_path)
    _project(store)
    _approved_contracts(
        store,
        record_confirmation_evidence=False,
        record_decision=False,
        d2_state="authorized",
        transition_to_decision=False,
    )
    view = research_decision_view_projection(store, PROJECT_ID)
    assert view["phase"] == "sealed_confirmation"
    assert view["gate_packet"] is None
    assert view["decision_history"] == []
    rows = _checklist_rows(cast(dict[str, object], view["checklist"]))
    assert rows["economic_hurdle"]["status"] == "NOT_TESTED"


def test_alpha_research_decision_view_emits_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured = CliRunner().invoke(
        app,
        ["research", "capture", "SPY drifts into month-end rebalancing", "--json"],
    )
    assert captured.exit_code == 0, captured.output
    project_id = str(json.loads(captured.output)["project"]["project_id"])
    result = CliRunner().invoke(app, ["research", "decision-view", project_id, "--json"])
    assert result.exit_code == 0, result.output
    view = json.loads(result.output)
    assert view["view_schema"] == "ResearchDecisionViewV1"
    assert view["project_id"] == project_id
    assert view["gate_packet"] is None
    assert view["decision_history"] == []
    assert len(view["checklist"]["questions"]) == 14
    assert len(view["scorecard"]["dimensions"]) == 12
    missing = CliRunner().invoke(app, ["research", "decision-view", "not-a-case", "--json"])
    assert missing.exit_code != 0
