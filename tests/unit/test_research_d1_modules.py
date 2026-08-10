"""Pure D1 analysis-family modules: deterministic, fail-loud, engine-free."""

from __future__ import annotations

import pytest

from alpha_core import DataError
from alpha_research.conditional_returns import (
    conditional_return_summary,
    difference_in_means,
    forward_returns,
    quantile_breakdown,
)
from alpha_research.ic import rank_ic, rolling_rank_ic
from alpha_research.leadlag import leadlag_profile, leakage_diagnostic
from alpha_research.stability import (
    rolling_effect_size,
    subsample_consistency,
    temporal_split_effects,
)


def test_forward_returns_are_outcome_constructors_with_explicit_tails() -> None:
    closes = [100.0, 110.0, 121.0, 133.1]
    outcomes = forward_returns(closes, horizon=1)
    assert outcomes[0] == pytest.approx(0.1)
    assert outcomes[2] == pytest.approx(0.1)
    assert outcomes[3] is None  # the tail has no future close; never fabricated
    with pytest.raises(DataError, match="horizon"):
        forward_returns(closes, horizon=0)
    with pytest.raises(DataError, match="positive"):
        forward_returns([100.0, -1.0], horizon=1)


def test_conditional_return_summary_reports_per_group_distributions() -> None:
    rows = conditional_return_summary({"event": [0.02, 0.01, 0.03], "control": [0.0, -0.01, 0.01]})
    assert [row["group"] for row in rows] == ["control", "event"]
    event = next(row for row in rows if row["group"] == "event")
    assert event["n"] == 3
    assert float(event["mean"]) == pytest.approx(0.02)
    assert float(event["median"]) == pytest.approx(0.02)
    with pytest.raises(DataError, match="empty"):
        conditional_return_summary({"event": []})


def test_difference_in_means_reports_effect_and_standardized_size() -> None:
    result = difference_in_means([0.02, 0.03, 0.04], [0.0, 0.01, -0.01])
    assert float(result["difference"]) == pytest.approx(0.03)
    assert float(result["difference_in_medians"]) == pytest.approx(0.03)
    assert float(result["standardized_effect"]) > 1.0
    assert result["n_treatment"] == 3 and result["n_control"] == 3
    with pytest.raises(DataError, match="at least two"):
        difference_in_means([0.02], [0.0, 0.01])


def test_quantile_breakdown_is_monotone_for_a_perfect_signal() -> None:
    signal = [float(i) for i in range(20)]
    outcome = [value / 100.0 for value in signal]
    rows = quantile_breakdown(signal, outcome, quantiles=4)
    assert [row["bucket"] for row in rows] == [1, 2, 3, 4]
    means = [float(row["mean_outcome"]) for row in rows]
    assert means == sorted(means)
    assert sum(int(row["n"]) for row in rows) == 20
    with pytest.raises(DataError, match="length"):
        quantile_breakdown(signal, outcome[:-1], quantiles=4)
    with pytest.raises(DataError, match="quantiles"):
        quantile_breakdown(signal, outcome, quantiles=1)


def test_rank_ic_matches_known_monotone_and_antitone_signals() -> None:
    signal = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert rank_ic(signal, [0.1, 0.2, 0.3, 0.4, 0.5]) == pytest.approx(1.0)
    assert rank_ic(signal, [0.5, 0.4, 0.3, 0.2, 0.1]) == pytest.approx(-1.0)
    with pytest.raises(DataError, match="at least three"):
        rank_ic([1.0, 2.0], [0.1, 0.2])
    with pytest.raises(DataError, match="constant"):
        rank_ic([1.0, 1.0, 1.0], [0.1, 0.2, 0.3])


def test_rolling_rank_ic_uses_trailing_windows_only() -> None:
    signal = [float(i) for i in range(12)]
    outcome = [float(i) for i in range(12)]
    series = rolling_rank_ic(signal, outcome, window=5)
    assert len(series) == 12
    assert all(value is None for value in series[:4])
    assert series[-1] == pytest.approx(1.0)


def test_temporal_split_effects_partition_chronologically() -> None:
    event_outcomes = [0.02] * 10 + [-0.01] * 10
    rows = temporal_split_effects(event_outcomes, n_periods=2)
    assert [row["period"] for row in rows] == [1, 2]
    assert float(rows[0]["mean"]) == pytest.approx(0.02)
    assert float(rows[1]["mean"]) == pytest.approx(-0.01)
    assert rows[0]["n"] == rows[1]["n"] == 10
    with pytest.raises(DataError, match="periods"):
        temporal_split_effects(event_outcomes, n_periods=1)


def test_rolling_effect_size_marks_warmup_and_degenerate_windows_none() -> None:
    outcomes = [0.0] * 4 + [0.01, 0.02, 0.01, 0.02, 0.01]
    series = rolling_effect_size(outcomes, window=4)
    assert len(series) == len(outcomes)
    assert all(value is None for value in series[:3])  # warmup
    assert series[3] is None  # zero-variance trailing window: undefined, never fabricated
    assert series[-1] is not None and float(series[-1]) > 0.0
    with pytest.raises(DataError, match="window"):
        rolling_effect_size(outcomes, window=1)


def test_subsample_consistency_reports_sign_agreement_deterministically() -> None:
    outcomes = [0.02, 0.03, 0.01, 0.04, 0.02, 0.05, 0.01, 0.02]
    result = subsample_consistency(outcomes, n_splits=4)
    assert result["n_splits"] == 4
    assert result["positive_fraction"] == pytest.approx(1.0)
    assert subsample_consistency(outcomes, n_splits=4) == result  # deterministic
    mixed = subsample_consistency([0.02, -0.02] * 4, n_splits=2)
    assert 0.0 <= float(mixed["positive_fraction"]) <= 1.0


def test_leadlag_profile_flags_leakage_when_the_signal_predicts_the_past() -> None:
    outcome = [0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0, -1.0, 0.0, 1.0, 0.0, -1.0]
    causal_signal = outcome[1:] + [0.0]  # signal[t] anticipates outcome[t+1]
    profile = leadlag_profile(causal_signal, outcome, max_lag=2)
    assert {row["lag"] for row in profile} == {-2, -1, 0, 1, 2}
    healthy = leakage_diagnostic(profile)
    assert healthy["suspicious"] is False

    leaky_signal = [0.0, *outcome[:-1]]  # signal[t] mirrors outcome[t-1]: constructed leak
    leaky_profile = leadlag_profile(leaky_signal, outcome, max_lag=2)
    diagnosis = leakage_diagnostic(leaky_profile)
    assert diagnosis["suspicious"] is True
    assert "lag" in str(diagnosis["reason"]).casefold()


def test_event_time_forward_effect_prevents_a_false_leakage_flag() -> None:
    profile: list[dict[str, float | int | None]] = [
        {"lag": -1, "n": 20, "correlation": 0.30},
        {"lag": 0, "n": 21, "correlation": 0.55},
        {"lag": 1, "n": 20, "correlation": 0.10},
    ]

    diagnosis = leakage_diagnostic(profile)

    assert diagnosis["suspicious"] is False
