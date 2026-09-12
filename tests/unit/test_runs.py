"""Runs test: textbook counts, degenerate windows are NaN, and the statistic plus its trailing
indicator reproduce the pinned upstream implementation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import geometric_brownian_series, rolling_runs_z, runs_z

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


class TestRunsZ:
    def test_textbook_example(self) -> None:
        # 4 positives, 4 negatives, 4 runs: mean = 5, var = 4*3/7
        s = np.array([1, 1, -1, -1, 1, 1, -1, -1], dtype=np.float64)
        assert runs_z(s) == pytest.approx((4 - 5.0) / np.sqrt(12.0 / 7.0))

    def test_alternating_is_positive_clustered_is_negative(self) -> None:
        assert runs_z(np.array([1.0, -1.0] * 10)) > 3.0
        assert runs_z(np.array([1.0] * 10 + [-1.0] * 10)) < -3.0

    def test_all_one_sign_is_nan(self) -> None:
        assert np.isnan(runs_z(np.ones(12)))

    def test_guards(self) -> None:
        with pytest.raises(DataError, match=">= 2"):
            runs_z(np.array([1.0]))
        with pytest.raises(DataError, match="non-finite"):
            runs_z(np.array([1.0, np.nan]))

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "runs.json").read_text())
        for case in fx["cases"]:
            assert runs_z(np.asarray(case["signs"])) == pytest.approx(case["z"], rel=1e-12)


class TestRollingRunsZ:
    def test_warmup_and_values(self) -> None:
        close = geometric_brownian_series(300, seed=2).close
        out = rolling_runs_z(close, lookback=24)
        assert np.all(np.isnan(out[:24])) and np.isfinite(out[24:]).sum() > 250

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="lookback"):
            rolling_runs_z(np.arange(10.0), lookback=1)

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "runs.json").read_text())
        s = fx["series"]
        close = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        ).close
        out = rolling_runs_z(close, lookback=int(fx["indicator"]["lookback"]))
        expected = np.array([np.nan if v is None else v for v in fx["indicator"]["values"]])
        np.testing.assert_allclose(out, expected, rtol=1e-12, equal_nan=True)
