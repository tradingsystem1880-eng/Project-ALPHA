"""Fat-tailed parametric null generators: Student-t i.i.d. + GARCH(1,1)."""

from __future__ import annotations

import numpy as np
import pytest
from scipy import stats

from alpha_core import DataError
from alpha_validation.montecarlo import (
    garch_paths,
    parametric_price_null,
    student_t_paths,
)


def _sample(n: int = 500, seed: int = 0) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0005, 0.01, n)


class TestStudentTPaths:
    def test_shape_and_moments(self) -> None:
        pr = _sample()
        paths = student_t_paths(pr, n_paths=200, df=6.0, seed=1)
        assert paths.shape == (200, pr.size)
        assert float(np.mean(paths)) == pytest.approx(np.mean(pr), abs=0.0015)
        assert float(np.std(paths)) == pytest.approx(np.std(pr, ddof=1), rel=0.1)

    def test_has_fat_tails(self) -> None:
        paths = student_t_paths(_sample(), n_paths=200, df=5.0, seed=2)
        assert float(stats.kurtosis(paths.ravel(), fisher=True)) > 1.0  # heavier than Gaussian (0)

    def test_deterministic(self) -> None:
        pr = _sample()
        assert np.array_equal(
            student_t_paths(pr, n_paths=50, df=6.0, seed=3),
            student_t_paths(pr, n_paths=50, df=6.0, seed=3),
        )

    def test_fails_loud(self) -> None:
        with pytest.raises(DataError):
            student_t_paths(_sample(), n_paths=10, df=2.0)  # variance undefined
        with pytest.raises(DataError):
            student_t_paths(_sample(), n_paths=0, df=6.0)


class TestGarchPaths:
    def test_shape_and_unconditional_variance(self) -> None:
        pr = _sample()
        paths = garch_paths(pr, n_paths=80, alpha=0.1, beta=0.85, df=8.0, seed=4)
        assert paths.shape == (80, pr.size)
        assert float(np.var(paths)) == pytest.approx(np.var(pr, ddof=1), rel=0.4)

    def test_exhibits_volatility_clustering(self) -> None:
        pr = _sample(n=600)
        paths = garch_paths(pr, n_paths=40, alpha=0.12, beta=0.85, df=8.0, seed=5)
        # lag-1 autocorrelation of squared returns should be clearly positive under GARCH
        acf1 = []
        for path in paths:
            sq = (path - path.mean()) ** 2
            acf1.append(np.corrcoef(sq[:-1], sq[1:])[0, 1])
        assert float(np.nanmean(acf1)) > 0.05

    def test_deterministic(self) -> None:
        pr = _sample()
        assert np.array_equal(
            garch_paths(pr, n_paths=20, df=8.0, seed=6),
            garch_paths(pr, n_paths=20, df=8.0, seed=6),
        )

    def test_non_stationary_fails_loud(self) -> None:
        with pytest.raises(DataError):
            garch_paths(_sample(), n_paths=10, alpha=0.5, beta=0.6)  # alpha+beta >= 1


class TestParametricPriceNull:
    def test_returns_a_valid_null_result(self) -> None:
        pr = _sample()
        res = parametric_price_null(pr, lambda r: r, model="student_t", n_paths=100, seed=7)
        assert 0.0 <= res.percentile <= 1.0
        assert 0.0 < res.p_value <= 1.0
        assert res.n_paths == 100

    def test_garch_model_runs(self) -> None:
        pr = _sample()
        res = parametric_price_null(pr, lambda r: r, model="garch", n_paths=64, seed=8)
        assert res.n_paths == 64

    def test_deterministic(self) -> None:
        pr = _sample()
        a = parametric_price_null(pr, lambda r: r, model="student_t", n_paths=50, seed=9)
        b = parametric_price_null(pr, lambda r: r, model="student_t", n_paths=50, seed=9)
        assert a.p_value == b.p_value and a.percentile == b.percentile

    def test_unknown_model_fails_loud(self) -> None:
        with pytest.raises(DataError):
            parametric_price_null(_sample(), lambda r: r, model="nope", n_paths=10)


def test_garch_df_at_or_below_two_fails_loud() -> None:
    import numpy as np
    import pytest

    from alpha_core import DataError
    from alpha_validation import garch_paths

    pr = np.random.default_rng(0).normal(0.0, 0.01, 100)
    for bad in (2.0, 1.5):
        with pytest.raises(DataError, match="df"):
            garch_paths(pr, n_paths=2, df=bad, seed=1)
