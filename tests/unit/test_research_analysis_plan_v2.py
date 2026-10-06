import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.research_analysis_plan import (
    default_analysis_plan,
    default_analysis_plan_v2,
    validate_analysis_plan,
    validate_new_exploration_plan,
)
from alpha_core import DataError


def _family(plan: dict[str, Any], family_id: str) -> dict[str, Any]:
    return next(entry for entry in plan["families"] if entry["family"] == family_id)


def test_v2_family_order_is_nonsemantic_but_new_approvals_are_canonical() -> None:
    from alpha_cli.research_d1 import d1_execution_fingerprint
    from tests.unit.test_research_d1_executor import _contract

    canonical = default_analysis_plan_v2(horizon_bars=4)
    reordered = deepcopy(canonical)
    reordered["families"].reverse()
    original = deepcopy(reordered)
    assert validate_analysis_plan(reordered, max_grid_cells=64) == canonical
    assert reordered == original
    assert [entry["family"] for entry in canonical["families"]] == sorted(
        entry["family"] for entry in canonical["families"]
    )
    contract = {**_contract(), "analysis_plan": canonical}
    fingerprint = d1_execution_fingerprint(contract)
    assert d1_execution_fingerprint({**contract, "analysis_plan": reordered}) == fingerprint
    validate_new_exploration_plan(canonical, max_grid_cells=64)
    with pytest.raises(DataError, match="freeze resolved defaults"):
        validate_new_exploration_plan(reordered, max_grid_cells=64)
    _family(reordered, "event_study")["grid"] = {"horizon_bars": [5]}
    assert d1_execution_fingerprint({**contract, "analysis_plan": reordered}) != fingerprint


def test_v2_resolves_defaults_without_mutating_input() -> None:
    plan = default_analysis_plan_v2(horizon_bars=4)
    _family(plan, "temporal_stability")["grid"] = {}
    original = deepcopy(plan)
    resolved = validate_analysis_plan(plan, max_grid_cells=64)
    assert resolved["schema"] == "ResearchAnalysisPlanV2"
    assert _family(resolved, "temporal_stability")["grid"] == {"n_periods": [2]}
    assert plan == original


@pytest.mark.parametrize(
    "grid",
    [
        {"typo": [4]},
        {"horizon_bars": [1.5]},
        {"horizon_bars": [True]},
        {"horizon_bars": [0]},
        {"horizon_bars": [1, 1]},
    ],
)
def test_v2_rejects_invalid_or_duplicate_axes(grid: object) -> None:
    plan = default_analysis_plan_v2(horizon_bars=4)
    _family(plan, "event_study")["grid"] = grid
    with pytest.raises(DataError):
        validate_analysis_plan(plan, max_grid_cells=64)


def test_legacy_plan_retains_permissive_historical_semantics() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    plan["families"][0]["grid"] = {"historical_unused_axis": [1.5]}
    assert validate_analysis_plan(plan, max_grid_cells=64) == plan


def test_rank_ic_cannot_claim_ignored_parameter_trials() -> None:
    plan = default_analysis_plan_v2(horizon_bars=4)
    _family(plan, "conditional_returns").update(
        family="rank_ic", multiplicity="diagnostic", grid={"horizon_bars": [2, 4]}
    )
    with pytest.raises(DataError, match="unsupported.*horizon_bars"):
        validate_analysis_plan(plan, max_grid_cells=64)


def test_v2_fingerprint_distinct_and_stable_with_implicit_defaults() -> None:
    from alpha_cli.research_d1 import d1_execution_fingerprint
    from tests.unit.test_research_d1_executor import _contract

    legacy = _contract()
    legacy_fingerprint = d1_execution_fingerprint(legacy)
    assert legacy_fingerprint == "5163bb3b68d2f987f69257a753b89e8bc9656c5417d1bf5b0e4f0c3459817b2d"
    current = deepcopy(legacy)
    current["analysis_plan"] = default_analysis_plan_v2(horizon_bars=4)
    resolved_fingerprint = d1_execution_fingerprint(current)
    assert resolved_fingerprint != legacy_fingerprint
    _family(current["analysis_plan"], "temporal_stability")["grid"] = {}
    assert d1_execution_fingerprint(current) == resolved_fingerprint
    _family(current["analysis_plan"], "event_study")["rationale"] = (
        "The same contrast, explained differently."
    )
    current["raw_idea"] = "A differently worded observation."
    assert d1_execution_fingerprint(current) == resolved_fingerprint
    assert d1_execution_fingerprint(legacy) == legacy_fingerprint


def test_resolved_operator_not_prose_selects_experiment() -> None:
    from alpha_cli.research_intake import draft_exploration_contract

    choices = {
        "chart_construction": "tiingo_daily_fallback",
        "event_availability": "second_trough_confirmable",
        "primary_outcome": "next_regular_session_return_50bp",
    }
    first = draft_exploration_contract(
        "Double bottom patterns bounce", resolutions=choices, operator_id="double_bottom.v1"
    )
    second = draft_exploration_contract(
        "Support is revisited", resolutions=choices, operator_id="double_bottom.v1"
    )
    assert first["approval_ready"] is True
    assert second["approval_ready"] is True
    for key in ("event_definition", "analysis_plan", "primary_claim", "resolved_material_choices"):
        assert first[key] == second[key]
    assert second["raw_idea"] == "Support is revisited"
    assert second["analysis_plan"]["schema"] == "ResearchAnalysisPlanV2"


def test_operator_cannot_conflict_with_material_event_choice() -> None:
    from alpha_cli.research_intake import draft_exploration_contract

    with pytest.raises(DataError, match="operator.*conflict"):
        draft_exploration_contract(
            "Any wording",
            resolutions={"event_availability": "bybit_funding_event_point_in_time"},
            operator_id="double_bottom.v1",
        )


def test_new_approval_requires_resolved_v2_but_historical_validation_does_not() -> None:
    legacy = default_analysis_plan(horizon_bars=4)
    with pytest.raises(DataError, match="requires ResearchAnalysisPlanV2"):
        validate_new_exploration_plan(legacy, max_grid_cells=64)
    assert validate_analysis_plan(legacy, max_grid_cells=64) == legacy
    current = default_analysis_plan_v2(horizon_bars=4)
    validate_new_exploration_plan(current, max_grid_cells=64)
    _family(current, "temporal_stability")["grid"] = {}
    with pytest.raises(DataError, match="freeze resolved defaults"):
        validate_new_exploration_plan(current, max_grid_cells=64)


def test_pre_cutover_v1_approval_can_execute_admit_and_recover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli.research_analysis_plan as plans
    from alpha_cli.control_store import ControlStore
    from tests.unit.test_research_control_store import (
        PROJECT_ID,
        START,
        _approved_deep_case,
        _d1_evidence_ref,
        _project,
        _published_d1_run,
    )

    store = ControlStore(tmp_path)
    _project(store)
    # Build a pre-cutover approved fixture with the original factory/policy, then
    # restore current policy before exercising execution, admission and recovery.
    with monkeypatch.context() as historical:
        historical.setattr(plans, "default_analysis_plan_v2", plans.default_analysis_plan)
        historical.setattr(plans, "validate_new_exploration_plan", lambda *args, **kwargs: None)
        contract_id, payload = _approved_deep_case(store)
    manifest = _published_d1_run(store, contract_id, payload)
    attempt = store.record_research_attempt(
        PROJECT_ID,
        contract_id,
        kind="d1-deep-research",
        status="completed",
        config_fingerprint=str(manifest["execution_fingerprint"]),
        budget_used={"variants": 6},
        details={
            "evidence_zone": "D1",
            "finding": "Historical V1 remains verifiable.",
            "gate_packet_evidence_ref": _d1_evidence_ref(store, manifest),
        },
        run_id=str(manifest["run_id"]),
        at=START + timedelta(minutes=10),
    )
    recovered = ControlStore(tmp_path).verified_research_attempt(
        PROJECT_ID, str(attempt["attempt_id"])
    )
    assert recovered["manifest"] == manifest


def test_v2_executes_same_measurements_for_same_resolved_parameters(tmp_path: Path) -> None:
    from tests.unit.test_research_d1_executor import _contract, _run, _weekly_lows

    legacy = _contract()
    current = deepcopy(legacy)
    current["analysis_plan"] = default_analysis_plan_v2(horizon_bars=4)
    old = _run(tmp_path, _weekly_lows("recovery"), legacy)
    new = _run(tmp_path, _weekly_lows("recovery"), current)
    reordered = deepcopy(current)
    reordered["analysis_plan"]["families"].reverse()
    reversed_run = _run(tmp_path, _weekly_lows("recovery"), reordered)
    assert reversed_run["execution_fingerprint"] == new["execution_fingerprint"]
    assert old["run_id"] != new["run_id"]
    results = [
        json.loads((tmp_path / "runs" / manifest["run_id"] / "d1_analyses.json").read_text())
        for manifest in (old, new, reversed_run)
    ]
    assert results[0] == results[1] == results[2]


@pytest.mark.parametrize("mutation", ["role_swap", "primary_grid", "false_holm"])
def test_v2_rejects_roles_and_primary_cells_the_runner_cannot_honor(mutation: str) -> None:
    plan = default_analysis_plan_v2(horizon_bars=4)
    if mutation == "role_swap":
        _family(plan, "event_study")["multiplicity"] = "secondary_holm"
        _family(plan, "conditional_returns")["multiplicity"] = "primary"
    elif mutation == "primary_grid":
        _family(plan, "event_study")["grid"]["horizon_bars"] = [1, 4]
    else:
        _family(plan, "temporal_stability")["multiplicity"] = "secondary_holm"
    legacy = {**deepcopy(plan), "schema": "ResearchAnalysisPlanV1"}
    for entry in legacy["families"]:
        if entry["multiplicity"] in {"robustness", "diagnostic"}:
            entry["multiplicity"] = "secondary_holm"
    assert validate_analysis_plan(legacy, max_grid_cells=64) == legacy
    with pytest.raises(DataError, match="role|one prespecified"):
        validate_analysis_plan(plan, max_grid_cells=64)


def test_v2_catalog_roles_match_executable_descriptors() -> None:
    from alpha_cli.research_analysis_plan import ANALYSIS_FAMILIES, analysis_family_catalog

    catalog = {entry["id"]: entry for entry in analysis_family_catalog()}
    assert catalog["event_study"]["multiplicity"] == ["primary"]
    assert catalog["event_study"]["primary_grid_cells"] == 1
    for name, descriptor in ANALYSIS_FAMILIES.items():
        assert catalog[name]["multiplicity"] == [descriptor.finding_role]
        assert catalog[name]["finding_role"] == descriptor.finding_role


def test_explicit_material_choices_resolve_operator_without_prose_keyword() -> None:
    from alpha_cli.research_intake import draft_exploration_contract

    result = draft_exploration_contract(
        "A generic owner research event may predict returns",
        resolutions={
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
    )
    assert result["approval_ready"] is True
    assert result["event_definition"]["name"] == "double_bottom"


def test_unresolved_explicit_operator_stays_draft_only() -> None:
    from alpha_cli.research_intake import draft_exploration_contract

    result = draft_exploration_contract("Revisit support", operator_id="double_bottom.v1")
    assert result["approval_ready"] is False
    assert result["blocking_questions"]
    with pytest.raises(DataError, match="unknown research operator"):
        draft_exploration_contract("Revisit support", operator_id="arbitrary.v1")
