"""Deterministic natural-language intake for ``ResearchContractV1`` drafts.

The conversational layer may improve the prose, but it cannot remove these statistical,
authority, resource, or evidence-boundary defaults.  Material ambiguities are represented as one
bounded question batch instead of being silently guessed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, Final

from alpha_cli.research_analysis_plan import default_analysis_plan
from alpha_cli.research_runtime import registered_d0_material_choices
from alpha_core import DataError
from alpha_research import registered_crypto_crowding_plan

type ResearchContractDraft = dict[str, Any]

_MAX_RAW_IDEA: Final = 8_192
_RESOLUTION_KEYS: Final = frozenset({"chart_construction", "event_availability", "primary_outcome"})
_CHART_CHOICES: Final = frozenset(
    {
        "spy_extended_fixed_4h",
        "es_fixed_4h",
        "spy_rth_60m_four_hour_window",
        "synthetic_only",
        "tiingo_daily_fallback",
        "bybit_btcusdt_linear_hourly",
    }
)
_EVENT_CHOICES: Final = frozenset(
    {
        "second_trough_confirmable",
        "neckline_breakout_confirmed",
        "bybit_funding_event_point_in_time",
    }
)
_OUTCOME_CHOICES: Final = frozenset(
    {
        "four_trading_hour_return_25bp",
        "next_regular_session_return_50bp",
        "next_funding_mark_minus_index_5bp",
    }
)
_ANSWER_BUNDLES: Final = (
    {
        "bundle_id": "synthetic_spy_60m_four_hour_v1",
        "label": "SPY 60-minute synthetic detector validation",
        "answers": {
            "chart_construction": "spy_rth_60m_four_hour_window",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "four_trading_hour_return_25bp",
        },
        "requires_dataset": False,
    },
    {
        "bundle_id": "tiingo_spy_daily_next_session_v1",
        "label": "Qualified Tiingo daily SPY exploration",
        "answers": {
            "chart_construction": "tiingo_daily_fallback",
            "event_availability": "second_trough_confirmable",
            "primary_outcome": "next_regular_session_return_50bp",
        },
        "requires_dataset": True,
    },
    {
        "bundle_id": "bybit_btcusdt_crowding_reversal_v1",
        "label": "Bybit BTCUSDT crowding reversal research",
        "answers": {
            "chart_construction": "bybit_btcusdt_linear_hourly",
            "event_availability": "bybit_funding_event_point_in_time",
            "primary_outcome": "next_funding_mark_minus_index_5bp",
        },
        "requires_dataset": True,
    },
)


def registered_answer_bundles() -> list[dict[str, object]]:
    """Return independent JSON-safe copies of every executable answer bundle."""

    return deepcopy(list(_ANSWER_BUNDLES))


def registered_answer_bundle(bundle_id: str) -> dict[str, object]:
    """Resolve one closed answer bundle or fail without guessing across answer axes."""

    for bundle in _ANSWER_BUNDLES:
        if bundle["bundle_id"] == bundle_id:
            return deepcopy(bundle)
    raise DataError(f"unknown research answer bundle {bundle_id!r}")


def _raw_idea(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\x00" in value
        or len(value) > _MAX_RAW_IDEA
    ):
        raise DataError(f"research raw idea must contain 1..{_MAX_RAW_IDEA} safe characters")
    return value


def _clean_resolutions(values: Mapping[str, str] | None) -> dict[str, str]:
    if values is None:
        return {}
    unknown = sorted(set(values) - _RESOLUTION_KEYS)
    if unknown:
        raise DataError(f"unknown research intake resolution {unknown[0]!r}")
    clean: dict[str, str] = {}
    allowed = {
        "chart_construction": _CHART_CHOICES,
        "event_availability": _EVENT_CHOICES,
        "primary_outcome": _OUTCOME_CHOICES,
    }
    for key, value in values.items():
        if not isinstance(value, str) or value not in allowed[key]:
            raise DataError(f"unsupported {key} research intake resolution {value!r}")
        clean[key] = value
    return clean


def _choice(identifier: str, label: str, consequence: str) -> dict[str, str]:
    return {"id": identifier, "label": label, "consequence": consequence}


def _recommended_bundle_id(raw: str) -> str | None:
    lowered = raw.casefold()
    if (
        "bybit" in lowered
        and ("btcusdt" in lowered or "btc/usdt" in lowered)
        and "funding" in lowered
        and ("open interest" in lowered or re.search(r"\boi\b", lowered) is not None)
        and ("crowding" in lowered or "reversal" in lowered)
    ):
        return "bybit_btcusdt_crowding_reversal_v1"
    names_sp500 = any(token in lowered for token in ("s&p", "sp500", "s and p 500"))
    names_four_hour = re.search(r"\b(?:4h|4[- ]?hour)\b", lowered) is not None
    return "synthetic_spy_60m_four_hour_v1" if names_sp500 and names_four_hour else None


def _material_choice(
    identifier: str,
    label: str,
    consequence: str,
    *,
    availability: str,
    blocked_reason: str | None = None,
) -> dict[str, object]:
    return {
        "id": identifier,
        "label": label,
        "consequence": consequence,
        "availability": availability,
        "blocked_reason": blocked_reason,
    }


def _questions(raw: str, resolutions: Mapping[str, str]) -> list[dict[str, object]]:
    lowered = raw.casefold()
    sp500 = any(token in lowered for token in ("s&p", "sp500", "s and p 500"))
    four_hour = re.search(r"\b(?:4h|4[- ]?hour)\b", lowered) is not None
    result: list[dict[str, object]] = []
    recommended = _recommended_bundle_id(raw)
    crypto_crowding = recommended == "bybit_btcusdt_crowding_reversal_v1"
    if "chart_construction" not in resolutions:
        if crypto_crowding:
            choices = [
                _choice(
                    "bybit_btcusdt_linear_hourly",
                    "Bybit linear BTCUSDT hourly contract",
                    "Keeps Bybit venue lineage, linear-contract units, and USDT quote identity; "
                    "USD and USDC are not substitutes.",
                )
            ]
        elif sp500 and four_hour:
            choices = [
                _choice(
                    "spy_extended_fixed_4h",
                    "SPY fixed four-hour extended-hours bars",
                    "Uses equal 240-minute observations, including explicitly fingerprinted "
                    "extended sessions.",
                ),
                _choice(
                    "es_fixed_4h",
                    "ES fixed four-hour bars",
                    "Requires a separately governed futures roll and overnight-session contract.",
                ),
                _choice(
                    "spy_rth_60m_four_hour_window",
                    "SPY 60-minute RTH proxy",
                    "Uses equal 60-minute bars and a four-trading-hour pattern window; it is not "
                    "labelled a literal four-hour chart.",
                ),
            ]
            choices.append(
                _choice(
                    "tiingo_daily_fallback",
                    "Registered Tiingo-daily fallback bars",
                    "Uses canonical session-daily Tiingo bars (the Gate-4 fallback lane); the "
                    "claim is reframed on a daily horizon and D0 remains synthetic-only.",
                )
            )
        else:
            choices = [
                _choice(
                    "synthetic_only",
                    "Synthetic validation only",
                    "Exercises detector and statistics without making a real-market claim.",
                ),
                _choice(
                    "tiingo_daily_fallback",
                    "Registered Tiingo-daily fallback bars",
                    "Uses canonical session-daily Tiingo bars (the Gate-4 fallback lane); the "
                    "claim is reframed on a daily horizon and D0 remains synthetic-only.",
                ),
            ]
        result.append(
            {
                "id": "chart_construction",
                "prompt": "Which exact instrument and equal-duration chart defines the claim?",
                "blocking_reason": "It changes the primary instrument and event population.",
                "choices": [
                    _material_choice(
                        str(choice["id"]),
                        str(choice["label"]),
                        str(choice["consequence"]),
                        availability=(
                            "available"
                            if choice["id"]
                            in {
                                "spy_rth_60m_four_hour_window",
                                "tiingo_daily_fallback",
                                "bybit_btcusdt_linear_hourly",
                            }
                            else "unavailable"
                        ),
                        blocked_reason=(
                            None
                            if choice["id"]
                            in {
                                "spy_rth_60m_four_hour_window",
                                "tiingo_daily_fallback",
                                "bybit_btcusdt_linear_hourly",
                            }
                            else "No registered end-to-end research operator uses this choice."
                        ),
                    )
                    for choice in choices
                ],
                "recommended_answer_bundle_id": recommended,
            }
        )
    if "event_availability" not in resolutions:
        event_choices = (
            [
                _material_choice(
                    "bybit_funding_event_point_in_time",
                    "Provider funding event, point-in-time",
                    "Uses only completed funding, OI, premium, and diagnostic observations known "
                    "at the provider-declared funding timestamp.",
                    availability="available",
                )
            ]
            if crypto_crowding
            else [
                _material_choice(
                    "second_trough_confirmable",
                    "Second trough confirmable",
                    "Fires only after any required right-pivot observations are available.",
                    availability="available",
                ),
                _material_choice(
                    "neckline_breakout_confirmed",
                    "Neckline breakout confirmed",
                    "Treats breakout confirmation as a different, later event variant.",
                    availability="unavailable",
                    blocked_reason=("No registered end-to-end research operator uses this choice."),
                ),
            ]
        )
        result.append(
            {
                "id": "event_availability",
                "prompt": "When is the event knowable without future information?",
                "blocking_reason": "It changes event timing and prevents a look-ahead detector.",
                "choices": event_choices,
                "recommended_answer_bundle_id": recommended,
            }
        )
    if "primary_outcome" not in resolutions:
        outcome_choices = (
            [
                _material_choice(
                    "next_funding_mark_minus_index_5bp",
                    "Next funding mark-minus-index, -5 bp",
                    "Measures mark return minus index return from the first complete hourly bar "
                    "through the next declared funding timestamp; at least 5 bp underperformance "
                    "is the practical hurdle.",
                    availability="available",
                )
            ]
            if crypto_crowding
            else [
                _material_choice(
                    "four_trading_hour_return_25bp",
                    "Four trading hours, 25 bp",
                    "Tests a positive 240-trading-minute return that clears 0.25%.",
                    availability="available",
                ),
                _material_choice(
                    "next_regular_session_return_50bp",
                    "Next session, 50 bp",
                    "Tests the next regular-session return against a 0.50% hurdle.",
                    availability="available",
                ),
            ]
        )
        result.append(
            {
                "id": "primary_outcome",
                "prompt": "What single horizon and minimum useful move defines a bounce?",
                "blocking_reason": "It fixes the primary endpoint and economic hurdle.",
                "choices": outcome_choices,
                "recommended_answer_bundle_id": recommended,
            }
        )
    return result[:3]


def _chart_fingerprint(choice: str | None) -> dict[str, object]:
    common: dict[str, object] = {
        "provider": "GATE4_QUALIFIED_RESEARCH_PROVIDER_REQUIRED",
        "timezone": "America/New_York",
        "timestamp_semantics": "bar_close_available",
        "adjustment_basis": "point_in_time",
    }
    variants: dict[str, dict[str, object]] = {
        "spy_extended_fixed_4h": {
            "instrument": "SPY",
            "venue": "US_EQUITIES",
            "session": "extended_hours",
            "bar_duration_minutes": 240,
            "anchor": "04:00 America/New_York",
            "label": "literal fixed four-hour SPY extended-hours bars",
        },
        "es_fixed_4h": {
            "instrument": "ES",
            "venue": "CME",
            "session": "owner_frozen_futures_session",
            "bar_duration_minutes": 240,
            "anchor": "owner_frozen",
            "roll_policy": "OWNER_APPROVAL_REQUIRED",
            "label": "literal fixed four-hour ES bars",
        },
        "spy_rth_60m_four_hour_window": {
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
        },
        "synthetic_only": {
            "instrument": "SYNTHETIC",
            "venue": "NOT_APPLICABLE",
            "session": "SYNTHETIC",
            "bar_duration_minutes": 60,
            "anchor": "SYNTHETIC_EPOCH",
            "label": "synthetic validation bars",
        },
        "tiingo_daily_fallback": {
            "provider": "tiingo",
            "instrument": "SPY",
            "venue": "US_EQUITIES",
            "session": "regular_session_daily",
            "bar_duration_minutes": 1_440,
            "anchor": "US_EQUITIES_SESSION_CLOSE",
            "label": "registered Tiingo session-daily Gate-4 fallback bars",
        },
        "bybit_btcusdt_linear_hourly": {
            "provider": "bybit",
            "instrument": "BTCUSDT",
            "venue": "bybit",
            "timezone": "UTC",
            "session": "continuous_crypto",
            "bar_duration_minutes": 60,
            "anchor": "provider_interval_start",
            "adjustment_basis": "provider_native_unadjusted",
            "timestamp_semantics": "interval_start_utc",
            "market_type": "linear",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "label": "Bybit linear BTCUSDT provider-native hourly observations",
        },
    }
    selected = variants.get(choice or "", {"status": "UNRESOLVED"})
    return {**common, **selected}


def _gate1_reason(supported: bool, chart: str | None) -> str:
    if supported and chart == "bybit_btcusdt_linear_hourly":
        return (
            "The registered Bybit BTCUSDT crowding D0 operator is available; empirical D1 "
            "requires one exact compatible qualified CryptoSnapshotV1."
        )
    if supported and chart == "tiingo_daily_fallback":
        return (
            "The registered synthetic session-daily double-bottom D0 operator is available; "
            "the empirical Gate-4 lane additionally requires a registered Tiingo-daily "
            "research dataset bound at draft time."
        )
    if supported:
        return "The canonical synthetic SPY-like 60-minute double-bottom D0 operator is available."
    return (
        "Gate 1 implements only the canonical synthetic SPY-like 60-minute "
        "(240-minute/+25 bp) and registered Tiingo session-daily (next-session/+50 bp) "
        "double-bottom, second-trough-confirmable D0 operators."
    )


def _primary_claim(choice: str | None) -> dict[str, object]:
    variants: dict[str, dict[str, object]] = {
        "four_trading_hour_return_25bp": {
            "estimand": "event_minus_matched_control_arithmetic_return",
            "endpoint": "forward_arithmetic_return",
            "horizon_trading_minutes": 240,
            "direction": "positive",
            "minimum_effect_return": 0.0025,
        },
        "next_regular_session_return_50bp": {
            "estimand": "event_minus_matched_control_arithmetic_return",
            "endpoint": "next_regular_session_arithmetic_return",
            "horizon": "next_regular_session",
            "direction": "positive",
            "minimum_effect_return": 0.005,
        },
        "next_funding_mark_minus_index_5bp": {
            "estimand": "event_mark_return_minus_index_return",
            "endpoint": "next_provider_declared_funding_timestamp",
            "horizon": "next_provider_declared_funding_timestamp",
            "direction": "negative",
            "minimum_effect_return": -0.0005,
        },
    }
    return variants.get(choice or "", {"status": "UNRESOLVED"})


def draft_exploration_contract(
    raw_idea: str,
    *,
    resolutions: Mapping[str, str] | None = None,
) -> ResearchContractDraft:
    """Turn one raw observation into a finite exploration-contract preview.

    The result is deterministic and JSON-safe.  It records research defaults, not empirical
    evidence, and cannot authorize D2, D3, restricted data, paper, promotion, or execution.
    """

    exact_idea = _raw_idea(raw_idea)
    resolved = _clean_resolutions(resolutions)
    questions = _questions(exact_idea, resolved)
    availability = resolved.get("event_availability")
    chart = resolved.get("chart_construction")
    outcome = resolved.get("primary_outcome")
    crypto_crowding = _recommended_bundle_id(exact_idea) == "bybit_btcusdt_crowding_reversal_v1"
    event_name = (
        "bybit_btcusdt_crowding_reversal"
        if crypto_crowding
        else ("double_bottom" if "double bottom" in exact_idea.casefold() else "owner_idea_event")
    )
    double_bottom_supported = (
        event_name == "double_bottom"
        and availability == "second_trough_confirmable"
        and outcome is not None
        and chart is not None
        and (chart, outcome) in registered_d0_material_choices()
    )
    crypto_supported = (
        crypto_crowding
        and chart == "bybit_btcusdt_linear_hourly"
        and availability == "bybit_funding_event_point_in_time"
        and outcome == "next_funding_mark_minus_index_5bp"
    )
    gate1_supported = double_bottom_supported or crypto_supported
    registered_chart_choices = {
        chart_choice for chart_choice, _outcome in registered_d0_material_choices()
    } | {"bybit_btcusdt_linear_hourly"}
    registered_event_choices = {
        "second_trough_confirmable",
        "bybit_funding_event_point_in_time",
    }
    capability_gaps = [
        {
            "id": identifier,
            "availability": "unavailable",
            "blocked_reason": "No registered end-to-end research operator uses this choice.",
        }
        for identifier in sorted(
            (_CHART_CHOICES - registered_chart_choices)
            | (_EVENT_CHOICES - registered_event_choices)
        )
    ]
    return {
        "schema": "ResearchContractV1",
        "schema_version": 1,
        "scope": "exploration",
        "parent_contract_id": None,
        "raw_idea": exact_idea,
        "approval_ready": not questions and gate1_supported,
        "blocking_questions": questions,
        "valid_answer_bundles": registered_answer_bundles(),
        "recommended_answer_bundle_id": _recommended_bundle_id(exact_idea),
        "answer_capability_gaps": capability_gaps,
        "gate1_availability": {
            "state": "AVAILABLE" if gate1_supported else "UNAVAILABLE",
            "reason": _gate1_reason(gate1_supported, chart),
        },
        "resolved_material_choices": dict(sorted(resolved.items())),
        "thesis": (
            {
                "mechanism": "Provisional: unusually positive funding with rising open interest "
                "and premium may identify crowded long positioning that later mean-reverts.",
                "prediction": "The point-in-time crowding event precedes mark-price "
                "underperformance relative to the index through the next funding timestamp.",
                "alternatives": [
                    "UTC funding-slot effect",
                    "recent trend or volatility regime",
                    "long-short positioning imbalance",
                    "mark or index construction artifact",
                    "provider correction or availability lag",
                ],
                "interpretation": "point-in-time predictive association; not a causal effect",
            }
            if crypto_crowding
            else {
                "mechanism": "Provisional: revisited local support may concentrate demand or "
                "reduce near-term selling pressure, producing conditional short-horizon mean "
                "reversion.",
                "prediction": "The point-in-time-valid event has a more positive forward return "
                "than pre-event matched controls after declared costs.",
                "alternatives": [
                    "day-of-week or calendar effect",
                    "prevailing trend and drawdown state",
                    "volatility, VIX, or volatility-term-structure regime",
                    "gap, volume, breadth, rates, or scheduled macro-event state",
                    "session or chart-construction artifact",
                    "correlated-market movement rather than pattern-specific information",
                ],
                "interpretation": "point-in-time-valid predictive association; not a causal effect",
            }
        ),
        "chart_fingerprint": _chart_fingerprint(resolved.get("chart_construction")),
        "event_definition": (
            {
                "name": event_name,
                "availability": availability or "UNRESOLVED",
                "funding_percentile": 0.95,
                "funding_history_observations": 365,
                "requires_positive_24h_open_interest_change": True,
                "requires_positive_premium": True,
                "overlapping_outcomes": "purge",
            }
            if crypto_crowding
            else {
                "name": event_name,
                "availability": availability or "UNRESOLVED",
                "records_both_trough_times": True,
                "fires_only_when_confirmable": True,
                "right_pivot_moves_event_forward": True,
                "neckline_is_separate_variant": True,
                "overlapping_outcomes": "purge",
            }
        ),
        "primary_claim": _primary_claim(outcome),
        "analysis_plan": (
            registered_crypto_crowding_plan().to_dict()
            if crypto_crowding and outcome is not None
            else (
                default_analysis_plan(
                    horizon_bars=4 if outcome == "four_trading_hour_return_25bp" else 1
                )
                if outcome is not None
                else {"status": "UNRESOLVED"}
            )
        ),
        "required_falsifiers": [
            "pseudo-pattern control",
            "shuffled-event control",
            "randomized-price null",
            "single-trough control",
            "weekday-only planted-confounder control",
        ],
        "confounders": [
            "calendar and day of week",
            "trend, volatility, drawdown, gap, and volume state",
            "VIX and volatility term structure",
            "breadth, rates, macro events, and market regime",
            "session and chart construction",
            "related-index behavior",
        ],
        "evidence_topology": {
            "allocations": {"D1": 0.6, "D2": 0.2, "D3": 0.2},
            "D0": {"purpose": "synthetic validation", "real_market_evidence": False},
            "D1": {
                "purpose": "discovery",
                "date_order": "earliest_eligible_dates",
                "watermark": "EXPLORATORY",
                "ledger_every_view": True,
            },
            "D2": {
                "purpose": "sealed research confirmation",
                "state": "SEALED",
                "one_shot": True,
                "owner_confirmation_approval_required": True,
            },
            "D3": {
                "purpose": "final strategy holdout",
                "state": "SEALED",
                "minimum_fraction": 0.2,
                "research_access": "PROHIBITED",
            },
        },
        "statistical_policy": {
            "primary_claim_count": 1,
            "familywise_alpha": 0.05,
            "prospective_power": 0.9,
            "power_gate": "simulation_based_before_D2",
            "dependence_unit": "effective_non_overlapping_event",
            "secondary_outcomes": "descriptive_unless_frozen_Holm_family",
            "selection_rule": "discard leaky, unstable, and underpowered definitions; cluster "
            "near-identical memberships; choose the simplest survivor with the strongest "
            "worst-case adjacent-parameter behavior",
            "causal_language": False,
        },
        "source_policy": {
            "candidate_services": ["OpenAlex", "Semantic Scholar", "Crossref", "Unpaywall"],
            "google_scholar": "manual_browser_verification_only",
            "full_text_retention": "open_access_or_user_provided_only",
            "external_text_trust": "UNTRUSTED_SOURCE",
            "document_instructions_have_authority": False,
        },
        "data_policy": {
            "real_intraday": "BLOCKED_UNTIL_LICENSED_RESEARCH_DATA_GATE",
            "research_dataset_ref_only": True,
            "canonical_daily_or_execution_reuse": False,
            "written_retention_and_model_use_rights_required": True,
        },
        "resource_budget": {
            "triage": {
                "wall_minutes": 20,
                "source_candidates": 20,
                "accessible_full_texts": 5,
                "parameter_sweep_cells": 0,
            },
            "pilot": {"primary_formulations": 1, "sensitivity_contrasts": 8},
            "deep_research": {
                "screened_sources": 40,
                "accessible_full_texts": 12,
                "grid_cells": 64,
                "heavy_compute_minutes": 120,
                "analytical_rounds": 2,
            },
            "safe_retries_per_job": 2,
            "expansion_requires_owner_approval": True,
        },
        "continuation_triggers": [
            "material unresolved confounding",
            "unstable but potentially resolvable parameter neighborhood",
            "contradictory transportability evidence",
            "insufficient precision realistically improvable with remaining D1 data",
        ],
        "stop_rules": [
            "insufficient effective events for prospective power",
            "required falsifier or negative control rejects the thesis",
            "no registered continuation trigger fires",
            "approved budget exhausted",
            "approved contract must change",
            "job fails after two safe retries",
        ],
        "report_plan": {
            "layers": ["90_second_conclusion", "guided_evidence", "technical_appendix"],
            "headline_charts": [
                "data_and_event_validity",
                "primary_association_and_matched_control",
                "parameter_neighborhood_stability",
                "confounder_and_regime_decomposition",
                "sealed_confirmation_or_transportability",
                "null_power_and_multiplicity",
            ],
            "additional_charts": "question_grouped_EXPLORATORY_appendix",
        },
        "language_policy": {
            "required_term": "point-in-time-valid predictive event study",
            "prohibited_claims": [
                "causal effect of an endogenous chart pattern",
                "guaranteed profit",
                "independent replication from correlated ETFs",
            ],
        },
        "authority": {
            "mutable_authority": "SQLite_control_plane",
            "analytical_authority": "immutable_run_artifacts",
            "owner_only": [
                "exploration_approval",
                "confirmation_approval",
                "D2_access",
                "D3_access",
                "budget_expansion",
                "restricted_data",
                "research_disposition",
                "paper_promotion_or_execution",
            ],
            "arbitrary_generated_python": "PROHIBITED",
        },
    }
