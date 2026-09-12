"""Hawkes volatility: the recursion has the closed form on constant input, restarts after a NaN,
and both the process and the regime signal reproduce the pinned upstream implementation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import geometric_brownian_series, hawkes_process, hawkes_vol_signal

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"


class TestProcess:
    def test_constant_input_closed_form(self) -> None:
        kappa = 0.3
        out = hawkes_process(np.ones(50), kappa=kappa)
        a = np.exp(-kappa)
        assert np.isnan(out[0])
        for i in range(1, 50):
            expected = kappa * (1 - a**i) / (1 - a)  # sum_{k=0}^{i-1} a^k, scaled
            assert out[i] == pytest.approx(expected, rel=1e-12)

    def test_nan_restarts_the_recursion(self) -> None:
        x = np.array([1.0, 1.0, np.nan, 2.0, 2.0])
        out = hawkes_process(x, kappa=1.0)
        assert np.isnan(out[2]) and out[3] == pytest.approx(2.0)
        assert out[4] == pytest.approx(2.0 * np.exp(-1.0) + 2.0)

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="kappa"):
            hawkes_process(np.ones(5), kappa=0.0)
        with pytest.raises(DataError, match=">= 2"):
            hawkes_process(np.ones(1), kappa=0.1)


class TestSignal:
    def test_values_and_warmup(self) -> None:
        bars = geometric_brownian_series(600, vol_per_bar=0.02, seed=5)
        rng_series = np.log(bars.high) - np.log(bars.low)
        h = hawkes_process(rng_series, kappa=0.1)
        sig = hawkes_vol_signal(bars.close, h, lookback=48)
        assert set(np.unique(sig)) <= {-1, 0, 1}
        assert not np.any(sig[:48])
        assert np.any(sig != 0)

    def test_guards(self) -> None:
        with pytest.raises(DataError, match="equal length"):
            hawkes_vol_signal(np.ones(5), np.ones(4), lookback=2)
        with pytest.raises(DataError, match="lookback"):
            hawkes_vol_signal(np.ones(5), np.ones(5), lookback=1)


class TestUpstreamParity:
    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "hawkes.json").read_text())
        s = fx["series"]
        bars = geometric_brownian_series(
            int(s["n_bars"]),
            vol_per_bar=float(s["vol_per_bar"]),
            seed=int(s["seed"]),
            start=float(s["start"]),
        )
        x = np.array([np.nan if v is None else v for v in fx["input"]])
        h = hawkes_process(x, kappa=float(fx["kappa"]))
        expected = np.array([np.nan if v is None else v for v in fx["hawkes"]])
        np.testing.assert_allclose(h, expected, rtol=1e-12, equal_nan=True)
        sig = hawkes_vol_signal(bars.close, h, lookback=int(fx["lookback"]))
        assert list(sig) == fx["signal"]
