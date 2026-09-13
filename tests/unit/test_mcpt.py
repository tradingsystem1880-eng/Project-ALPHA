"""Unit tests for the bar-permutation Monte Carlo test (alpha_validation.mcpt)."""

from __future__ import annotations

import numpy as np
import pytest

from alpha_core import DataError
from alpha_validation.bar_permutation import OHLC
from alpha_validation.mcpt import permutation_test, permutation_test_multi
from alpha_validation.metrics import profit_factor


def _bars(n: int, seed: int) -> OHLC:
    rng = np.random.default_rng(seed)
    close = 50.0 * np.exp(np.cumsum(rng.normal(0.0, 0.01, size=n)))
    open_ = np.concatenate([[50.0], close[:-1]])
    return OHLC(
        open=open_,
        high=np.maximum(open_, close) * 1.002,
        low=np.minimum(open_, close) * 0.998,
        close=close,
    )


def _trend_score(bars: OHLC) -> float:
    """Autocorrelation of close-to-close log returns: an order-sensitive statistic."""
    rets = np.diff(np.log(bars.close))
    return float(np.corrcoef(rets[:-1], rets[1:])[0, 1])


def test_a_trending_series_beats_its_permutations() -> None:
    n = 300
    close = 50.0 * np.exp(np.cumsum(0.01 * np.sin(np.arange(n) / 6.0)))  # smooth cycles
    bars = OHLC(open=close, high=close * 1.001, low=close * 0.999, close=close)
    result = permutation_test(bars, _trend_score, n_perms=99, seed=1, threshold=0.95)
    assert result.passed and result.p_value < 0.05
    assert result.observed > float(np.max(result.null)) - 1e-12


def test_start_index_restricts_the_permuted_region() -> None:
    bars = _bars(200, 2)
    seen: list[np.ndarray] = []

    def recording_score(b: OHLC) -> float:
        seen.append(b.close.copy())
        return float(b.close[-1])

    permutation_test(bars, recording_score, n_perms=3, start_index=150, seed=5)
    assert len(seen) == 4  # observed + three permutations
    for permuted in seen[1:]:
        assert np.array_equal(permuted[:151], bars.close[:151])
        assert not np.array_equal(permuted[151:], bars.close[151:])


def test_fails_loud_on_bad_parameters_and_non_finite_scores() -> None:
    bars = _bars(50, 3)
    with pytest.raises(DataError, match=r"^n_perms must be >= 1, got 0$"):
        permutation_test(bars, _trend_score, n_perms=0, seed=1)
    with pytest.raises(DataError, match=r"^threshold must be in \(0, 1\), got 1.0$"):
        permutation_test(bars, _trend_score, n_perms=2, seed=1, threshold=1.0)
    with pytest.raises(DataError, match=r"^permutation test observed statistic is not finite$"):
        permutation_test(bars, lambda b: float("nan"), n_perms=2, seed=1)
    calls = {"n": 0}

    def flaky(b: OHLC) -> float:
        calls["n"] += 1
        return float("inf") if calls["n"] == 3 else 1.0

    with pytest.raises(DataError, match=r"^permutation test produced a non-finite statistic"):
        permutation_test(bars, flaky, n_perms=4, seed=1)
    with pytest.raises(DataError, match=r"^every market must have 50 bars; market 1 has 40$"):
        permutation_test_multi([bars, _bars(40, 4)], lambda markets: 1.0, n_perms=1, seed=1)


def test_profit_factor_validates_and_promotes_integer_input() -> None:
    assert profit_factor([2, -1, 3]) == pytest.approx(5.0)
    assert profit_factor([0.0, 0.0]) is None
    with pytest.raises(DataError, match=r"^profit factor needs at least one return$"):
        profit_factor([])
    with pytest.raises(DataError, match=r"^profit factor returns must be a finite 1-D array$"):
        profit_factor(np.array([[1.0, -1.0]]))
    with pytest.raises(DataError, match=r"^profit factor returns must be a finite 1-D array$"):
        profit_factor([1.0, float("inf")])


def test_every_public_name_of_alpha_validation_resolves() -> None:
    import alpha_validation

    for name in alpha_validation.__all__:
        assert hasattr(alpha_validation, name), name
    assert alpha_validation.profit_factor is profit_factor
    assert alpha_validation.permutation_test is permutation_test
