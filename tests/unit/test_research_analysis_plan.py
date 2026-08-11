"""The preregistered per-hypothesis D1 analysis plan (spec §9.2, ADR-0025)."""

from __future__ import annotations

import pytest

from alpha_cli.research_analysis_plan import (
    FALSIFICATION_ANALYSIS_FAMILIES,
    REGISTERED_ANALYSIS_FAMILIES,
    default_analysis_plan,
    validate_analysis_plan,
)
from alpha_core import DataError


def test_default_plan_is_registered_and_validates() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    validated = validate_analysis_plan(plan, max_grid_cells=64)
    families = [str(entry["family"]) for entry in validated["families"]]
    assert families[0] == "event_study"
    assert set(families) <= REGISTERED_ANALYSIS_FAMILIES
    primaries = [entry for entry in validated["families"] if entry["multiplicity"] == "primary"]
    assert len(primaries) == 1 and primaries[0]["family"] == "event_study"
    falsifiers = {
        str(entry["family"])
        for entry in validated["families"]
        if entry["multiplicity"] == "falsification"
    }
    assert falsifiers == FALSIFICATION_ANALYSIS_FAMILIES
    assert validated == plan  # validation never rewrites the frozen plan


def test_plan_requires_the_registered_schema_and_shape() -> None:
    with pytest.raises(DataError, match="ResearchAnalysisPlanV1"):
        validate_analysis_plan({"schema": "Other", "families": []}, max_grid_cells=64)
    with pytest.raises(DataError, match="at least one"):
        validate_analysis_plan(
            {"schema": "ResearchAnalysisPlanV1", "families": []}, max_grid_cells=64
        )
    with pytest.raises(DataError, match="fields"):
        validate_analysis_plan(
            {
                "schema": "ResearchAnalysisPlanV1",
                "families": [{"family": "event_study"}],
            },
            max_grid_cells=64,
        )


def test_plan_rejects_unregistered_and_duplicate_families() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    entry = dict(plan["families"][0])
    entry["family"] = "kitchen_sink_scan"
    with pytest.raises(DataError, match="unregistered"):
        validate_analysis_plan(
            {**plan, "families": [entry, *plan["families"][1:]]}, max_grid_cells=64
        )
    with pytest.raises(DataError, match="duplicate"):
        validate_analysis_plan(
            {**plan, "families": [plan["families"][0], *plan["families"][:5]]},
            max_grid_cells=64,
        )


def test_plan_rejects_blanket_batteries() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    extras = [
        {
            "family": name,
            "rationale": "padding",
            "grid": {},
            "multiplicity": "secondary_holm",
        }
        for name in sorted(REGISTERED_ANALYSIS_FAMILIES - FALSIFICATION_ANALYSIS_FAMILIES)
        if name not in {str(entry["family"]) for entry in plan["families"]}
    ]
    with pytest.raises(DataError, match="blanket"):
        validate_analysis_plan(
            {**plan, "families": [*plan["families"], *extras]}, max_grid_cells=64
        )


def test_plan_requires_a_rationale_per_family() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    entry = {**plan["families"][1], "rationale": "  "}
    with pytest.raises(DataError, match="rationale"):
        validate_analysis_plan(
            {**plan, "families": [plan["families"][0], entry, *plan["families"][2:]]},
            max_grid_cells=64,
        )


def test_plan_rejects_unbounded_grids() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    base = plan["families"][0]
    bad_grid: object
    for bad_grid in (
        {"horizon_bars": []},  # empty axis
        {"horizon_bars": [float("nan")]},  # non-finite value
        {"horizon_bars": "1,2,3"},  # axis must be a list
        {"a": [1], "b": [1], "c": [1], "d": [1], "e": [1]},  # too many axes
    ):
        with pytest.raises(DataError, match="grid"):
            validate_analysis_plan(
                {**plan, "families": [{**base, "grid": bad_grid}, *plan["families"][1:]]},
                max_grid_cells=64,
            )
    wide = {**base, "grid": {"horizon_bars": list(range(1, 13)), "window": list(range(1, 13))}}
    with pytest.raises(DataError, match="budget"):
        validate_analysis_plan(
            {**plan, "families": [wide, *plan["families"][1:]]}, max_grid_cells=64
        )


def test_plan_enforces_the_multiplicity_structure() -> None:
    plan = default_analysis_plan(horizon_bars=4)
    no_primary = [
        {**entry, "multiplicity": "secondary_holm"} if entry["multiplicity"] == "primary" else entry
        for entry in plan["families"]
    ]
    with pytest.raises(DataError, match="primary"):
        validate_analysis_plan({**plan, "families": no_primary}, max_grid_cells=64)
    misfiled_null = [
        {**entry, "multiplicity": "secondary_holm"}
        if entry["family"] == "shuffled_event_null"
        else entry
        for entry in plan["families"]
    ]
    with pytest.raises(DataError, match="falsification"):
        validate_analysis_plan({**plan, "families": misfiled_null}, max_grid_cells=64)
    misfiled_primary = [
        {**entry, "multiplicity": "falsification"} if entry["multiplicity"] == "primary" else entry
        for entry in plan["families"]
    ]
    with pytest.raises(DataError, match="falsification"):
        validate_analysis_plan({**plan, "families": misfiled_primary}, max_grid_cells=64)


def test_intake_draft_registers_the_default_plan() -> None:
    from alpha_cli.research_intake import draft_exploration_contract

    draft = draft_exploration_contract(
        "A double bottom on the S&P 500 4-hour chart bounces",
        resolutions={
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
    )
    plan = draft["analysis_plan"]
    assert validate_analysis_plan(plan, max_grid_cells=64) == plan
    event_grid = plan["families"][0]["grid"]
    assert event_grid["horizon_bars"] == [4]

    daily = draft_exploration_contract(
        "A double bottom on the S&P 500 4-hour chart bounces",
        resolutions={
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "next_regular_session_return_50bp",
        },
    )
    assert daily["analysis_plan"]["families"][0]["grid"]["horizon_bars"] == [1]
