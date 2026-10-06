"""Hand-computed cases for ``alpha_research.panel`` (Phase C C1)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from alpha_core import DataError
from alpha_research.panel import (
    bucket_turnover,
    cost_adjusted_spread,
    cross_sectional_ic,
    fama_macbeth,
    forward_outcomes,
    ic_decay,
    ic_half_life,
    orthogonalize,
    quantile_returns,
)
from tests.fixtures.panel_fixtures import (
    CONTROL,
    EXPECTED_IC_MEAN,
    EXPECTED_IC_STD,
    EXPECTED_IC_VALUES,
    FACTOR_1,
    FACTOR_2,
    FM_OUTCOME,
    NOISE,
    ORTH_SIGNAL,
    OUTCOME_3X6,
    SIGNAL_3X6,
    geometric_close_panel,
)

REL = 1e-9


def test_cross_sectional_ic_on_hand_panel() -> None:
    series = cross_sectional_ic(SIGNAL_3X6, OUTCOME_3X6, min_names=5)
    assert series.values == pytest.approx(list(EXPECTED_IC_VALUES), rel=REL)
    assert series.n_dates == 3
    assert series.hit_rate == pytest.approx(2 / 3, rel=REL)
    assert series.mean == pytest.approx(EXPECTED_IC_MEAN, rel=REL)
    assert series.std == pytest.approx(EXPECTED_IC_STD, rel=REL)
    assert series.icir == pytest.approx(EXPECTED_IC_MEAN / EXPECTED_IC_STD, rel=REL)
    assert series.t_stat == pytest.approx(
        EXPECTED_IC_MEAN / EXPECTED_IC_STD * math.sqrt(3), rel=REL
    )


def test_ic_std_is_sample_std() -> None:
    series = cross_sectional_ic(SIGNAL_3X6, OUTCOME_3X6, min_names=5)
    assert series.std == pytest.approx(1.1085322, abs=1e-6)
    assert series.std != pytest.approx(0.9051, abs=1e-3)


def test_ic_returns_none_per_date_below_min_names() -> None:
    outcome = OUTCOME_3X6.copy()
    outcome[2, :2] = np.nan  # four finite pairs remain on date 2
    series = cross_sectional_ic(SIGNAL_3X6, outcome, min_names=5)
    assert series.values[2] is None
    assert series.n_dates == 2
    assert series.mean == pytest.approx(0.0, abs=1e-12)
    outcome[2, 1] = 0.01  # exactly five finite pairs scores
    scored = cross_sectional_ic(SIGNAL_3X6, outcome, min_names=5)
    assert scored.values[2] is not None and scored.n_dates == 3


def test_ic_nan_name_is_excluded_not_zero_filled() -> None:
    outcome = OUTCOME_3X6.copy()
    outcome[0, 0] = np.nan
    series = cross_sectional_ic(SIGNAL_3X6, outcome, min_names=5)
    assert series.values[0] == pytest.approx(1.0, rel=REL)


def test_ic_constant_cross_section_is_none() -> None:
    outcome = OUTCOME_3X6.copy()
    outcome[1, :] = 0.02
    series = cross_sectional_ic(SIGNAL_3X6, outcome, min_names=5)
    assert series.values[1] is None
    assert series.n_dates == 2


def test_ic_all_dates_identical_gives_none_icir_and_t() -> None:
    series = cross_sectional_ic(SIGNAL_3X6, SIGNAL_3X6, min_names=5)
    assert series.values == [1.0, 1.0, 1.0]
    assert series.std == 0.0
    assert series.icir is None and series.t_stat is None


def test_ic_rejects_inf_shape_mismatch_and_fewer_than_three_dates() -> None:
    bad = OUTCOME_3X6.copy()
    bad[0, 0] = np.inf
    with pytest.raises(DataError, match="finite"):
        cross_sectional_ic(SIGNAL_3X6, bad)
    with pytest.raises(DataError, match="shape"):
        cross_sectional_ic(SIGNAL_3X6, OUTCOME_3X6[:, :5])
    with pytest.raises(DataError, match="three dates"):
        cross_sectional_ic(SIGNAL_3X6[:2], OUTCOME_3X6[:2])
    with pytest.raises(DataError, match="two-dimensional"):
        cross_sectional_ic(SIGNAL_3X6[0], OUTCOME_3X6[0])
    with pytest.raises(DataError, match="min_names"):
        cross_sectional_ic(SIGNAL_3X6, OUTCOME_3X6, min_names=2)


def test_ic_all_dates_degenerate_is_none_summary() -> None:
    constant = np.full_like(OUTCOME_3X6, 0.02)
    series = cross_sectional_ic(SIGNAL_3X6, constant, min_names=5)
    assert series.values == [None, None, None]
    assert series.n_dates == 0
    assert series.mean is None and series.std is None and series.hit_rate is None


def test_quantile_returns_on_hand_panel() -> None:
    three = quantile_returns(SIGNAL_3X6, OUTCOME_3X6, quantiles=3, min_names=5)
    assert three.mean_by_quantile == pytest.approx([0.0283333333, 0.035, 0.0416666667], rel=1e-8)
    assert three.spread == pytest.approx(0.0133333333, rel=1e-8)
    assert three.monotonicity == pytest.approx(1.0, rel=REL)
    assert three.n_dates == 3
    two = quantile_returns(SIGNAL_3X6, OUTCOME_3X6, quantiles=2, min_names=5)
    assert two.mean_by_quantile == pytest.approx([0.0311111111, 0.0388888889], rel=1e-8)
    assert two.spread == pytest.approx(0.0077777778, rel=1e-8)


def test_quantile_ties_use_stable_rank_order() -> None:
    signal = np.array([[1.0, 1.0, 1.0, 2.0, 2.0, 2.0]] * 3)
    report = quantile_returns(signal, OUTCOME_3X6, quantiles=2, min_names=5)
    # bottom bucket = A,B,C on every date (stable order among ties)
    expected_bottom = float(np.mean([OUTCOME_3X6[t, :3].mean() for t in range(3)]))
    assert report.mean_by_quantile[0] == pytest.approx(expected_bottom, rel=REL)


def test_quantile_rejects_bad_quantiles() -> None:
    for bad in (1, 6, True):  # quantiles must not exceed min_names (=5): no empty buckets
        with pytest.raises(DataError, match="quantiles"):
            quantile_returns(SIGNAL_3X6, OUTCOME_3X6, quantiles=bad, min_names=5)
        with pytest.raises(DataError, match="quantiles"):
            bucket_turnover(SIGNAL_3X6, quantiles=bad, min_names=5)


def test_quantiles_above_min_names_never_produce_empty_buckets() -> None:
    outcome = OUTCOME_3X6.copy()
    outcome[:, 0] = np.nan  # five names present, six requested: refused up front, never NaN
    with pytest.raises(DataError, match=r"quantiles must be an integer in \[2, min_names=5\]"):
        quantile_returns(SIGNAL_3X6, outcome, quantiles=6, min_names=5)
    signal = SIGNAL_3X6.copy()
    signal[1, 0] = np.nan
    with pytest.raises(DataError, match="quantiles"):
        bucket_turnover(signal, quantiles=6, min_names=5)


def test_bucket_turnover_hand_cases() -> None:
    up = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    assert bucket_turnover(np.array([up, up, up[::-1]]), quantiles=3, min_names=5) == pytest.approx(
        0.5
    )
    swapped = [1.0, 2.0, 3.0, 5.0, 4.0, 6.0]
    assert bucket_turnover(np.array([up, swapped, up]), quantiles=3, min_names=5) == pytest.approx(
        0.25
    )
    assert bucket_turnover(np.array([up, up, up]), quantiles=3, min_names=5) == 0.0
    assert bucket_turnover(np.array([up, up[::-1], up]), quantiles=3, min_names=5) == 1.0


def test_bucket_turnover_uses_names_present_on_both_dates() -> None:
    up = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    panel = np.array([up, up, up])
    panel[1, 1] = np.nan  # B absent on date 1: five names on both dates
    assert bucket_turnover(panel, quantiles=3, min_names=5) == pytest.approx(0.0)
    panel[1, 5] = 0.5  # F drops to the bottom on date 1
    # Names present on both dates: A,C,D,E,F; q=3 over 5 names -> bottom {A}, top {F}, middle 3.
    # Date 1 order F,A,C,D,E -> bottom {F}, top {E}: both slots turn over on each pair -> 1.0.
    assert bucket_turnover(panel, quantiles=3, min_names=5) == pytest.approx(1.0)


def test_uneven_buckets_keep_top_and_bottom_symmetric() -> None:
    signal = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]] * 3)
    outcome = signal / 100.0
    report = quantile_returns(signal, outcome, quantiles=2, min_names=5)
    # 7 names, q=2: bottom {A,B,C}, top {E,F,G}; D is unbucketed.
    assert report.mean_by_quantile == pytest.approx([0.02, 0.06], rel=REL)
    three = quantile_returns(signal, outcome, quantiles=3, min_names=5)
    assert three.mean_by_quantile == pytest.approx([0.015, 0.04, 0.065], rel=REL)


def test_cost_adjusted_spread_formula() -> None:
    # one-way 10 bp, half the slots replaced: traded notional 4 x 0.5 = 2 -> drag 20 bp
    assert cost_adjusted_spread(0.0133333333, 0.5, cost_bps=10.0) == pytest.approx(
        0.0113333333, rel=1e-8
    )
    # one top leaver of two top + two bottom slots (f = 0.25): the long leg sells $0.5 and buys
    # $0.5 -> $1 traded -> drag = one-way cost c, i.e. 4 x 0.25 x c
    assert cost_adjusted_spread(0.0, 0.25, cost_bps=10.0) == pytest.approx(-10.0 / 1e4, rel=REL)
    with pytest.raises(DataError, match="cost_bps"):
        cost_adjusted_spread(0.01, 0.5, cost_bps=-1.0)
    with pytest.raises(DataError, match="finite"):
        cost_adjusted_spread(math.nan, 0.5, cost_bps=1.0)


def test_fama_macbeth_recovers_noiseless_slopes() -> None:
    result = fama_macbeth([FACTOR_1, FACTOR_2], FM_OUTCOME, min_names=5)
    assert result.mean_slopes == pytest.approx([0.5, -0.2], rel=REL)
    assert result.t_stats == [None, None]
    assert result.n_dates == 3


def test_fama_macbeth_t_stat_with_varying_slopes() -> None:
    outcome = np.array([1.0 + s * FACTOR_1[0] for s in (0.5, 0.7, 0.6)])
    result = fama_macbeth([FACTOR_1], outcome, min_names=5)
    assert result.mean_slopes == pytest.approx([0.6], rel=REL)
    assert result.t_stats[0] == pytest.approx(6 * math.sqrt(3), rel=REL)


def test_fama_macbeth_rejects_collinear_and_underdetermined_dates() -> None:
    with pytest.raises(DataError, match="rank"):
        fama_macbeth([FACTOR_1, 7.0 - FACTOR_1], FM_OUTCOME, min_names=5)
    sparse = FM_OUTCOME.copy()
    sparse[1, :2] = np.nan
    result = fama_macbeth([FACTOR_1, FACTOR_2], sparse, min_names=5)
    assert result.n_dates == 2
    with pytest.raises(DataError, match="scorable"):
        fama_macbeth([FACTOR_1, FACTOR_2], np.full_like(FM_OUTCOME, np.nan), min_names=5)


def test_orthogonalize_residuals_hand_case() -> None:
    residual = orthogonalize(ORTH_SIGNAL, [CONTROL], min_names=5)
    assert residual == pytest.approx(NOISE, abs=1e-9)
    signal = ORTH_SIGNAL.copy()
    signal[0, 0] = np.nan
    residual = orthogonalize(signal, [CONTROL], min_names=5)
    assert math.isnan(residual[0, 0]) and not np.isnan(residual[0, 1:]).any()
    signal[0, :2] = np.nan  # four names left on date 0 -> below min_names -> all NaN row
    residual = orthogonalize(signal, [CONTROL], min_names=5)
    assert np.isnan(residual[0]).all() and not np.isnan(residual[1]).any()


def test_ic_half_life_cases() -> None:
    assert ic_half_life({1: 1.0, 5: 0.4, 10: 0.1, 21: 0.0}) == pytest.approx(13 / 3, rel=REL)
    assert ic_half_life({1: 1.0, 5: 0.6, 10: 0.5}) == pytest.approx(10.0, rel=REL)
    assert ic_half_life({1: 1.0, 5: 0.6, 10: 0.55, 21: 0.52}) is None
    assert ic_half_life({1: 0.2, 5: 0.3, 10: 0.05}) == pytest.approx(9.0, rel=REL)
    assert ic_half_life({1: 0.0, 5: -0.1}) is None
    assert ic_half_life({1: None, 5: 0.1}) is None
    assert ic_half_life({1: 1.0, 5: None, 10: 0.1}) is None
    with pytest.raises(DataError, match="^ic_half_life decay values must be finite or None$"):
        ic_half_life({1: 1.0, 5: math.nan})


def test_ic_decay_monotone_panel_and_horizon_validation() -> None:
    closes = geometric_close_panel()
    signal = np.tile(np.arange(6, dtype=float), (30, 1))
    decay = ic_decay(signal, closes, horizons=(1, 5, 10, 21), min_names=5)
    assert {h: s.mean for h, s in decay.items()} == {1: 1.0, 5: 1.0, 10: 1.0, 21: 1.0}
    assert {h: s.n_dates for h, s in decay.items()} == {1: 29, 5: 25, 10: 20, 21: 9}
    assert ic_half_life({h: s.mean for h, s in decay.items()}) is None
    for bad in ((5, 1), (1, 1), (0,), (30,), (True,)):
        with pytest.raises(DataError, match="horizons"):
            ic_decay(signal, closes, horizons=bad, min_names=5)


def test_forward_outcomes_index_rule() -> None:
    closes = geometric_close_panel(n_dates=5)
    out = forward_outcomes(closes, horizon=2)
    assert out[0] == pytest.approx(closes[2] / closes[0] - 1.0, rel=REL)
    assert np.isnan(out[3]).all() and np.isnan(out[4]).all()
    closes[1, 2] = np.nan
    out = forward_outcomes(closes, horizon=2)
    assert math.isnan(out[1, 2]) and not math.isnan(out[1, 1])
    with pytest.raises(DataError, match="horizon"):
        forward_outcomes(closes, horizon=0)
    closes[0, 0] = 0.0
    with pytest.raises(DataError, match="strictly positive"):
        forward_outcomes(closes, horizon=1)


def test_panel_primitives_are_deterministic() -> None:
    closes = geometric_close_panel()
    signal = np.tile(np.arange(6, dtype=float), (30, 1))
    first = (
        cross_sectional_ic(signal, forward_outcomes(closes, horizon=1)),
        ic_decay(signal, closes),
        quantile_returns(signal, forward_outcomes(closes, horizon=1)),
        bucket_turnover(signal),
    )
    second = (
        cross_sectional_ic(signal, forward_outcomes(closes, horizon=1)),
        ic_decay(signal, closes),
        quantile_returns(signal, forward_outcomes(closes, horizon=1)),
        bucket_turnover(signal),
    )
    assert first == second


def _five_name_panel() -> tuple[np.ndarray, np.ndarray]:
    signal = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]] * 3)
    outcome = np.array(
        [
            [0.01, 0.02, 0.03, 0.04, 0.05],  # rho = 1
            [0.02, 0.05, 0.03, 0.01, 0.04],  # ranks 2,5,3,1,4 -> sum d^2 = 20 -> rho = 0
            [0.02, 0.05, 0.03, 0.01, 0.04],
        ]
    )
    return signal, outcome


def test_defaults_score_exactly_five_names_and_hit_rate_excludes_zero_ic() -> None:
    signal, outcome = _five_name_panel()
    series = cross_sectional_ic(signal, outcome)
    assert series.values == pytest.approx([1.0, 0.0, 0.0], abs=1e-12)
    assert series.hit_rate == pytest.approx(1 / 3, rel=REL)
    assert series.std is not None and series.n_dates == 3
    assert len(quantile_returns(signal, outcome).mean_by_quantile) == 5
    assert bucket_turnover(signal) == 0.0
    assert fama_macbeth([signal], outcome).n_dates == 3
    assert not np.isnan(orthogonalize(outcome, [signal])).any()
    closes = geometric_close_panel(n_dates=30, n_names=5)
    assert list(ic_decay(np.tile(np.arange(5.0), (30, 1)), closes)) == [1, 5, 10, 21]
    assert len(quantile_returns(signal, outcome, quantiles=5).mean_by_quantile) == 5
    with pytest.raises(DataError, match="min_names"):
        cross_sectional_ic(signal, outcome, min_names=2)
    assert cross_sectional_ic(signal, outcome, min_names=3).n_dates == 3


def test_ic_decay_honours_min_names() -> None:
    closes = geometric_close_panel(n_dates=30, n_names=4)
    signal = np.tile(np.arange(4.0), (30, 1))
    assert ic_decay(signal, closes, horizons=(1,), min_names=3)[1].mean == pytest.approx(
        1.0, rel=REL
    )
    assert ic_decay(signal, closes, horizons=(1,))[1].mean is None
    with pytest.raises(DataError, match="share one shape"):
        ic_decay(signal[:, :3], closes)
    with pytest.raises(
        DataError, match=r"horizons must be strictly increasing integers in \[1, 29\]"
    ):
        ic_decay(signal, closes, horizons=(1, 29, 30), min_names=3)


def test_sparse_dates_in_the_middle_are_skipped_not_terminal() -> None:
    signal, outcome = _five_name_panel()
    outcome = np.vstack([outcome, outcome[0]])
    outcome[1, :2] = np.nan  # date 1 has three names: skipped, later dates still scored
    series = cross_sectional_ic(signal[:1].repeat(4, axis=0), outcome)
    assert series.values[1] is None and series.values[3] == pytest.approx(1.0)
    assert series.n_dates == 3
    assert quantile_returns(signal[:1].repeat(4, axis=0), outcome, quantiles=2).n_dates == 3
    turnover_panel = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]] * 4)
    turnover_panel[1, :2] = np.nan
    turnover_panel[3] = turnover_panel[3][::-1]
    # pairs (0,1) and (1,2) have three shared names and are skipped; pair (2,3) reverses -> 1.0
    assert bucket_turnover(turnover_panel, quantiles=2) == 1.0


def test_two_date_turnover_and_single_scorable_quantile_date() -> None:
    up = np.array([[1.0, 2.0, 3.0, 4.0, 5.0, 6.0]] * 2)
    assert bucket_turnover(up, quantiles=3) == 0.0
    with pytest.raises(DataError, match="^bucket_turnover requires at least two dates$"):
        bucket_turnover(up[:1], quantiles=3)
    with pytest.raises(DataError, match="^bucket_turnover has no consecutive date pair"):
        bucket_turnover(np.full((3, 6), np.nan), quantiles=3)
    outcome = OUTCOME_3X6.copy()
    outcome[1:, :] = np.nan
    assert quantile_returns(SIGNAL_3X6, outcome, quantiles=3).n_dates == 1
    with pytest.raises(DataError, match="^quantile_returns has no scorable dates$"):
        quantile_returns(SIGNAL_3X6, np.full_like(OUTCOME_3X6, np.nan), quantiles=3)


def test_stable_sort_keeps_tied_names_in_input_order() -> None:
    n = 40
    signal = np.array([[0.0] * (n // 2) + [1.0] * (n // 2)] * 3)
    outcome = np.tile(np.arange(n, dtype=float) / 100.0, (3, 1))
    report = quantile_returns(signal, outcome, quantiles=2)
    assert report.mean_by_quantile[0] == pytest.approx(
        float(np.mean(outcome[0, : n // 2])), rel=REL
    )
    distinct_then_tied = np.vstack([np.arange(n, dtype=float), signal[0]])
    assert bucket_turnover(distinct_then_tied, quantiles=2) == 0.0


def test_remaining_validation_messages() -> None:
    closes = geometric_close_panel(n_dates=5)
    with pytest.raises(DataError, match=r"^forward horizon must be an integer in \[1, 4\]"):
        forward_outcomes(closes, horizon=5)
    with pytest.raises(DataError, match="^fama_macbeth needs at least one factor panel$"):
        fama_macbeth([], FM_OUTCOME)
    with pytest.raises(DataError, match="^panel inputs must share one shape$"):
        fama_macbeth([FACTOR_1[:, :5]], FM_OUTCOME)
    with pytest.raises(DataError, match="^panel statistics require at least three dates$"):
        fama_macbeth([FACTOR_1[:2]], FM_OUTCOME[:2])
    with pytest.raises(DataError, match="^orthogonalize needs at least one control panel$"):
        orthogonalize(ORTH_SIGNAL, [])
    with pytest.raises(DataError, match="^panel inputs must share one shape$"):
        orthogonalize(ORTH_SIGNAL, [CONTROL[:, :5]])
    with pytest.raises(DataError, match="^ic_half_life needs at least one horizon$"):
        ic_half_life({})
    with pytest.raises(DataError, match="^panel inputs must be two-dimensional"):
        cross_sectional_ic(np.zeros((3, 2, 2)), np.zeros((3, 2, 2)))
    assert cost_adjusted_spread(0.01, 0.5, cost_bps=0.0) == pytest.approx(0.01)
    assert cost_adjusted_spread(0.01, 0.5, cost_bps=0.5) == pytest.approx(
        0.01 - 4 * 0.5 * 0.5 / 1e4
    )
    with pytest.raises(DataError, match="^cost_bps must be non-negative$"):
        cost_adjusted_spread(0.01, 0.5, cost_bps=-0.5)
    with pytest.raises(DataError, match="^cost_adjusted_spread inputs must be finite numbers$"):
        cost_adjusted_spread(0.01, math.inf, cost_bps=1.0)
    with pytest.raises(DataError, match="finite numbers"):
        cost_adjusted_spread(True, 0.5, cost_bps=1.0)
    with pytest.raises(DataError, match="^panel inputs must be numeric rectangular arrays$"):
        cross_sectional_ic("abc", "def")
    with pytest.raises(DataError, match="numeric rectangular"):
        cross_sectional_ic([[1.0, 2.0], [1.0]], [[1.0, 2.0], [1.0]])
