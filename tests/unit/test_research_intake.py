"""Natural-language intake builds a bounded, owner-reviewable research contract."""

from __future__ import annotations

import json

import pytest

from alpha_cli.research_intake import draft_exploration_contract
from alpha_core import DataError

RAW_IDEA = "i notice the S&P500 bounces when it has double bottoms on the 4h time frame"


def test_four_hour_double_bottom_intake_preserves_words_and_blocks_on_three_material_choices() -> (
    None
):
    draft = draft_exploration_contract(RAW_IDEA)

    assert draft["schema"] == "ResearchContractV1"
    assert draft["scope"] == "exploration"
    assert draft["raw_idea"] == RAW_IDEA
    assert draft["approval_ready"] is False
    questions = draft["blocking_questions"]
    assert [question["id"] for question in questions] == [
        "chart_construction",
        "event_availability",
        "primary_outcome",
    ]
    assert len(questions) == 3
    assert [choice["id"] for choice in questions[0]["choices"]] == [
        "spy_extended_fixed_4h",
        "es_fixed_4h",
        "spy_rth_60m_four_hour_window",
        "tiingo_daily_fallback",
    ]
    assert draft["evidence_topology"]["allocations"] == {"D1": 0.6, "D2": 0.2, "D3": 0.2}
    assert draft["evidence_topology"]["D2"]["state"] == "SEALED"
    assert draft["evidence_topology"]["D3"]["minimum_fraction"] == 0.2
    assert draft["resource_budget"]["triage"]["parameter_sweep_cells"] == 0
    assert draft["resource_budget"]["deep_research"]["grid_cells"] == 64
    assert len(draft["report_plan"]["headline_charts"]) == 6
    assert "causal" in " ".join(draft["language_policy"]["prohibited_claims"])


def test_material_resolutions_make_the_contract_approval_ready_and_deterministic() -> None:
    resolutions = {
        "chart_construction": "spy_rth_60m_four_hour_window",
        "event_availability": "second_trough_confirmable",
        "primary_outcome": "four_trading_hour_return_25bp",
    }
    first = draft_exploration_contract(RAW_IDEA, resolutions=resolutions)
    second = draft_exploration_contract(RAW_IDEA, resolutions=dict(reversed(resolutions.items())))

    assert first == second
    assert first["blocking_questions"] == []
    assert first["approval_ready"] is True
    assert first["gate1_availability"]["state"] == "AVAILABLE"
    assert first["chart_fingerprint"] == {
        "provider": "alpha_synthetic_fixture",
        "instrument": "SYNTHETIC_SPY",
        "venue": "SYNTHETIC",
        "timezone": "UTC",
        "session": "synthetic_equal_duration",
        "bar_duration_minutes": 60,
        "pattern_window_trading_minutes": 240,
        "anchor": "SYNTHETIC_EPOCH",
        "adjustment_basis": "synthetic_not_applicable",
        "timestamp_semantics": "bar_end_available",
        "label": "synthetic SPY-like 60-minute D0 fixture with a four-hour pattern window",
    }
    assert first["event_definition"]["availability"] == "second_trough_confirmable"
    assert first["primary_claim"]["horizon_trading_minutes"] == 240
    assert first["primary_claim"]["minimum_effect_return"] == 0.0025
    material = json.dumps(
        {
            "chart": first["chart_fingerprint"],
            "event": first["event_definition"],
            "claim": first["primary_claim"],
        },
        sort_keys=True,
    ).upper()
    assert "REQUIRED" not in material
    assert "UNRESOLVED" not in material
    assert json.dumps(first, sort_keys=True, allow_nan=False) == json.dumps(
        second, sort_keys=True, allow_nan=False
    )


@pytest.mark.parametrize(
    ("raw_idea", "resolutions"),
    [
        (
            RAW_IDEA,
            {
                "chart_construction": chart,
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "four_trading_hour_return_25bp",
            },
        )
        for chart in ("spy_extended_fixed_4h", "es_fixed_4h", "synthetic_only")
    ]
    + [
        (
            RAW_IDEA,
            {
                "chart_construction": "spy_rth_60m_four_hour_window",
                "event_availability": "neckline_breakout_confirmed",
                "primary_outcome": "four_trading_hour_return_25bp",
            },
        ),
        (
            RAW_IDEA,
            {
                "chart_construction": "spy_rth_60m_four_hour_window",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "next_regular_session_return_50bp",
            },
        ),
        (
            RAW_IDEA,
            {
                "chart_construction": "tiingo_daily_fallback",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "four_trading_hour_return_25bp",
            },
        ),
        (
            RAW_IDEA,
            {
                "chart_construction": "tiingo_daily_fallback",
                "event_availability": "neckline_breakout_confirmed",
                "primary_outcome": "next_regular_session_return_50bp",
            },
        ),
        (
            "A generic owner research event may predict returns",
            {
                "chart_construction": "spy_rth_60m_four_hour_window",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "four_trading_hour_return_25bp",
            },
        ),
    ],
)
def test_resolved_but_unimplemented_variants_are_explicitly_unavailable_drafts(
    raw_idea: str, resolutions: dict[str, str]
) -> None:
    draft = draft_exploration_contract(raw_idea, resolutions=resolutions)

    assert draft["blocking_questions"] == []
    assert draft["approval_ready"] is False
    assert draft["gate1_availability"]["state"] == "UNAVAILABLE"
    assert "Gate 1 implements only" in draft["gate1_availability"]["reason"]


def test_daily_gate4_material_combo_is_an_available_approval_ready_draft() -> None:
    """R6a (ADR-0026): the Gate-4 Tiingo-daily lane is a second supported Gate-1 combo."""
    resolutions = {
        "chart_construction": "tiingo_daily_fallback",
        "event_availability": "second_trough_confirmable",
        "primary_outcome": "next_regular_session_return_50bp",
    }
    draft = draft_exploration_contract(RAW_IDEA, resolutions=resolutions)

    assert draft["blocking_questions"] == []
    assert draft["approval_ready"] is True
    assert draft["gate1_availability"]["state"] == "AVAILABLE"
    reason = draft["gate1_availability"]["reason"]
    assert "session-daily" in reason
    assert "registered" in reason.casefold()
    assert draft["chart_fingerprint"] == {
        "provider": "tiingo",
        "instrument": "SPY",
        "venue": "US_EQUITIES",
        "timezone": "America/New_York",
        "session": "regular_session_daily",
        "bar_duration_minutes": 1_440,
        "anchor": "US_EQUITIES_SESSION_CLOSE",
        "adjustment_basis": "point_in_time",
        "timestamp_semantics": "bar_close_available",
        "label": "registered Tiingo session-daily Gate-4 fallback bars",
    }
    assert draft["primary_claim"]["horizon"] == "next_regular_session"
    assert draft["primary_claim"]["minimum_effect_return"] == 0.005
    assert draft["analysis_plan"]["families"]
    material = json.dumps(
        {
            "chart": draft["chart_fingerprint"],
            "event": draft["event_definition"],
            "claim": draft["primary_claim"],
        },
        sort_keys=True,
    ).upper()
    assert "REQUIRED" not in material
    assert "UNRESOLVED" not in material


def test_unknown_or_conflicting_material_resolution_fails_closed() -> None:
    with pytest.raises(DataError, match="unknown research intake resolution"):
        draft_exploration_contract(RAW_IDEA, resolutions={"library": "pandas"})
    with pytest.raises(DataError, match="unsupported chart_construction"):
        draft_exploration_contract(
            RAW_IDEA,
            resolutions={
                "chart_construction": "mixed_240_and_150_minute_spy_bars",
                "event_availability": "second_trough_confirmable",
                "primary_outcome": "four_trading_hour_return_25bp",
            },
        )
    for removed_choice in ("daily_adjusted_bars", "owner_specified_fixed_duration"):
        with pytest.raises(DataError, match="unsupported chart_construction"):
            draft_exploration_contract(
                RAW_IDEA,
                resolutions={"chart_construction": removed_choice},
            )
    with pytest.raises(DataError, match="unsupported primary_outcome"):
        draft_exploration_contract(
            RAW_IDEA,
            resolutions={"primary_outcome": "owner_specified_economic_hurdle"},
        )


@pytest.mark.parametrize("raw", ["", "   ", "bad\x00idea"])
def test_invalid_raw_idea_is_rejected(raw: str) -> None:
    with pytest.raises(DataError, match="raw idea"):
        draft_exploration_contract(raw)
