"""Metamorphic relations for ``alpha_research.panel`` (edge-first Phase C).

Each relation follows from the textbook definition: Spearman IC is invariant to monotone
transforms and antisymmetric under negation (Grinold & Kahn ch. 6); bucket turnover is 0 for a
constant ranking and 1 for a full reversal (Grinold & Kahn ch. 16); Fama & MacBeth (1973) slopes
are exact on noiseless data; an OLS residual is orthogonal to its regressors and the projection is
idempotent; IC decay is the mean IC against independently transcribed forward returns (Qian, Hua &
Sorensen 2007, ch. 4).
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from alpha_research.panel import (
    bucket_turnover,
    cross_sectional_ic,
    fama_macbeth,
    forward_outcomes,
    ic_decay,
    ic_half_life,
    orthogonalize,
    quantile_returns,
)
from tests.fixtures.panel_fixtures import geometric_close_panel
from tests.oracles._reference.tolerances import FLOAT64_REL

pytestmark = pytest.mark.oracle

# A coarse grid keeps distinct cells distinct under exp() and cubing (no float collapse).
_CELL = st.integers(min_value=-50, max_value=50).map(lambda v: v / 10.0)


def _rows(n_dates: int, n_names: int) -> st.SearchStrategy[list[list[float]]]:
    """Dates × names with distinct cells per date (by construction, never by filtering)."""
    row = st.lists(_CELL, min_size=n_names, max_size=n_names, unique=True)
    return st.lists(row, min_size=n_dates, max_size=n_dates)


def _panel_strategy(min_names: int = 5, max_names: int = 12) -> st.SearchStrategy[np.ndarray]:
    return st.integers(min_value=3, max_value=8).flatmap(
        lambda t: st.integers(min_value=min_names, max_value=max_names).flatmap(
            lambda n: _rows(t, n).map(np.asarray)
        )
    )


_PAIR = st.integers(min_value=3, max_value=8).flatmap(
    lambda t: st.integers(min_value=5, max_value=12).flatmap(
        lambda n: st.tuples(_rows(t, n), _rows(t, n)).map(
            lambda pair: (np.asarray(pair[0]), np.asarray(pair[1]))
        )
    )
)


@given(_PAIR)
@settings(max_examples=60, deadline=None)
def test_ic_is_invariant_to_monotone_transforms_of_signal_and_outcome(
    pair: tuple[np.ndarray, np.ndarray],
) -> None:
    signal, outcome = pair
    base = cross_sectional_ic(signal, outcome)
    assert cross_sectional_ic(np.exp(signal), outcome).values == pytest.approx(
        base.values, rel=FLOAT64_REL, abs=1e-12
    )
    assert cross_sectional_ic(signal, outcome**3).values == pytest.approx(
        base.values, rel=FLOAT64_REL, abs=1e-12
    )


@given(_PAIR)
@settings(max_examples=60, deadline=None)
def test_ic_flips_sign_when_the_signal_is_negated(pair: tuple[np.ndarray, np.ndarray]) -> None:
    signal, outcome = pair
    base = cross_sectional_ic(signal, outcome)
    flipped = cross_sectional_ic(-signal, outcome)
    assert base.mean is not None and base.hit_rate is not None
    negated = [-v for v in base.values if v is not None]
    assert len(negated) == len(base.values)
    assert flipped.values == pytest.approx(negated, rel=FLOAT64_REL, abs=1e-12)
    assert flipped.mean == pytest.approx(-base.mean, rel=FLOAT64_REL, abs=1e-12)
    if all(v != 0.0 for v in base.values):
        assert flipped.hit_rate == pytest.approx(1.0 - base.hit_rate, abs=1e-12)


def test_ic_perfect_reversed_and_noise_bounds() -> None:
    closes = geometric_close_panel(n_dates=40, n_names=8)
    outcome = forward_outcomes(closes, horizon=1)
    ranks = np.tile(np.arange(8, dtype=float), (40, 1))
    assert cross_sectional_ic(ranks, outcome).mean == pytest.approx(1.0, rel=FLOAT64_REL)
    assert cross_sectional_ic(-ranks, outcome).mean == pytest.approx(-1.0, rel=FLOAT64_REL)
    rng = np.random.default_rng(7)
    noise_signal = rng.standard_normal((200, 50))
    noise_outcome = rng.standard_normal((200, 50))
    noise_mean = cross_sectional_ic(noise_signal, noise_outcome).mean
    # Null std of the mean IC is about 1/sqrt(49)/sqrt(200) ~ 0.01; 0.05 is a five-sigma band.
    assert noise_mean is not None and abs(noise_mean) < 0.05


@given(_PAIR, st.integers(min_value=2, max_value=5))
@settings(max_examples=60, deadline=None)
def test_quantile_spread_equals_top_minus_bottom(
    pair: tuple[np.ndarray, np.ndarray], quantiles: int
) -> None:
    signal, outcome = pair
    report = quantile_returns(signal, outcome, quantiles=quantiles)
    assert report.spread == pytest.approx(
        report.mean_by_quantile[-1] - report.mean_by_quantile[0], rel=1e-12, abs=1e-12
    )


def test_monotone_panel_scores_one_and_reversed_scores_minus_one() -> None:
    closes = geometric_close_panel(n_dates=10, n_names=10)
    outcome = forward_outcomes(closes, horizon=1)
    ranks = np.tile(np.arange(10, dtype=float), (10, 1))
    assert quantile_returns(ranks, outcome, quantiles=5).monotonicity == pytest.approx(1.0)
    assert quantile_returns(-ranks, outcome, quantiles=5).monotonicity == pytest.approx(-1.0)


@given(st.integers(min_value=6, max_value=20), st.sampled_from([2, 3, 5]))
@settings(max_examples=30, deadline=None)
def test_turnover_is_zero_for_constant_ranking_and_one_for_full_reversal(
    n_names: int, quantiles: int
) -> None:
    ranking = np.arange(n_names, dtype=float)
    constant = np.tile(ranking, (4, 1))
    assert bucket_turnover(constant, quantiles=quantiles) == 0.0
    reversing = np.array([ranking, ranking[::-1], ranking, ranking[::-1]])
    assert bucket_turnover(reversing, quantiles=quantiles) == 1.0


@given(_panel_strategy(), st.sampled_from([2, 3, 5]))
@settings(max_examples=40, deadline=None)
def test_turnover_is_invariant_to_monotone_signal_transforms(
    panel: np.ndarray, quantiles: int
) -> None:
    assert bucket_turnover(np.exp(panel), quantiles=quantiles) == pytest.approx(
        bucket_turnover(panel, quantiles=quantiles), rel=FLOAT64_REL
    )


@given(
    st.integers(min_value=3, max_value=6),
    st.lists(
        st.tuples(
            st.floats(-3.0, 3.0, allow_nan=False),
            st.floats(-3.0, 3.0, allow_nan=False),
            st.floats(-3.0, 3.0, allow_nan=False),
        ),
        min_size=3,
        max_size=3,
    ),
)
@settings(max_examples=40, deadline=None)
def test_fama_macbeth_recovers_known_slopes_exactly_on_noiseless_data(
    seed: int, coefficients: list[tuple[float, float, float]]
) -> None:
    rng = np.random.default_rng(seed)
    f1 = rng.standard_normal((3, 8))
    f2 = rng.standard_normal((3, 8))
    outcome = np.array([a + b * f1[t] + c * f2[t] for t, (a, b, c) in enumerate(coefficients)])
    result = fama_macbeth([f1, f2], outcome)
    expected = np.mean([[b, c] for _, b, c in coefficients], axis=0)
    assert result.mean_slopes == pytest.approx(list(expected), rel=1e-9, abs=1e-9)
    assert result.n_dates == 3


@given(_panel_strategy(min_names=6), st.integers(min_value=0, max_value=1000))
@settings(max_examples=40, deadline=None)
def test_orthogonalize_residual_is_uncorrelated_with_every_control(
    signal: np.ndarray, seed: int
) -> None:
    rng = np.random.default_rng(seed)
    controls = [rng.standard_normal(signal.shape), rng.standard_normal(signal.shape)]
    residual = orthogonalize(signal, controls)
    for t in range(signal.shape[0]):
        assert abs(float(np.mean(residual[t]))) < 1e-9
        for control in controls:
            assert abs(float(np.dot(residual[t], control[t] - control[t].mean()))) < 1e-8
    again = orthogonalize(residual, controls)
    assert again == pytest.approx(residual, abs=1e-9)


def test_ic_decay_matches_independently_computed_forward_returns() -> None:
    closes = geometric_close_panel(n_dates=30, n_names=6, step=0.003)
    rng = np.random.default_rng(3)
    signal = rng.standard_normal(closes.shape)
    decay = ic_decay(signal, closes, horizons=(1, 5, 10))
    for h, series in decay.items():
        transcribed = np.full(closes.shape, np.nan)
        for t in range(30 - h):
            transcribed[t] = closes[t + h] / closes[t] - 1.0
        assert series.mean == pytest.approx(
            cross_sectional_ic(signal, transcribed).mean, rel=FLOAT64_REL, abs=1e-12
        )
        assert series.n_dates == 30 - h


@given(
    st.floats(min_value=0.05, max_value=1.0, allow_nan=False),
    st.floats(min_value=-1.0, max_value=1.0, allow_nan=False),
)
@settings(max_examples=60, deadline=None)
def test_ic_half_life_closed_form_for_two_horizons(a: float, b: float) -> None:
    result = ic_half_life({1: a, 5: b})
    if b <= a / 2.0:
        assert result == pytest.approx(1.0 + 4.0 * (a / 2.0 - a) / (b - a), rel=1e-9)
    else:
        assert result is None
