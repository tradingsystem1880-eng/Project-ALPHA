"""Window trendline fitting: the optimised lines start from the least-squares fit, touch their pivot
and never cross price; breakouts are decided from the bars before the decision bar; meta-label
trades are settled and internally consistent; and the pure-numpy parts reproduce the pinned
upstream implementation exactly."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from alpha_core import DataError
from alpha_patterns import (
    OHLCV,
    breakout_features,
    fit_trendlines_high_low,
    fit_trendlines_single,
    geometric_brownian_series,
    trendline_breakout,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "neurotrader"
TOL = 1e-5  # the fitter's own crossing tolerance


def _log_bars(n: int = 600, seed: int = 7) -> OHLCV:
    return geometric_brownian_series(n, vol_per_bar=0.02, seed=seed, start=1.0)


class TestSingleFit:
    def test_lines_touch_pivot_and_never_cross(self) -> None:
        y = np.log(_log_bars().close[100:130])
        x = np.arange(y.size)
        pair = fit_trendlines_single(y)
        s = pair.support.slope * x + pair.support.intercept
        r = pair.resistance.slope * x + pair.resistance.intercept
        assert (s - y).max() <= TOL and np.isclose((s - y).max(), 0.0, atol=TOL)
        assert (r - y).min() >= -TOL and np.isclose((r - y).min(), 0.0, atol=TOL)

    def test_pivots_are_the_least_squares_extremes(self) -> None:
        y = np.log(_log_bars(seed=3).close[40:80])
        x = np.arange(y.size)
        slope, intercept = np.polyfit(x, y, 1)
        resid = y - (slope * x + intercept)
        pair = fit_trendlines_single(y)
        assert pair.resistance.value_at(int(resid.argmax())) == pytest.approx(y[resid.argmax()])
        assert pair.support.value_at(int(resid.argmin())) == pytest.approx(y[resid.argmin()])

    def test_straight_line_is_its_own_trendlines(self) -> None:
        y = 0.5 + 0.01 * np.arange(20, dtype=np.float64)
        pair = fit_trendlines_single(y)
        assert pair.support.slope == pytest.approx(0.01, abs=1e-6)
        assert pair.resistance.slope == pytest.approx(0.01, abs=1e-6)

    @pytest.mark.parametrize("bad", [np.array([1.0, 2.0]), np.array([1.0, np.nan, 2.0, 3.0])])
    def test_guards(self, bad: np.ndarray) -> None:
        with pytest.raises(DataError):
            fit_trendlines_single(bad)

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "trendline_fit.json").read_text())
        lo, hi = fx["window"]
        bars = _log_bars()
        pair = fit_trendlines_single(np.log(bars.close[lo:hi]))
        assert [pair.support.slope, pair.support.intercept] == pytest.approx(
            fx["single"]["support"], rel=1e-12
        )
        assert [pair.resistance.slope, pair.resistance.intercept] == pytest.approx(
            fx["single"]["resistance"], rel=1e-12
        )
        hl = fit_trendlines_high_low(
            np.log(bars.high[lo:hi]), np.log(bars.low[lo:hi]), np.log(bars.close[lo:hi])
        )
        assert [hl.support.slope, hl.support.intercept] == pytest.approx(
            fx["high_low"]["support"], rel=1e-12
        )
        assert [hl.resistance.slope, hl.resistance.intercept] == pytest.approx(
            fx["high_low"]["resistance"], rel=1e-12
        )


class TestHighLowFit:
    def test_resistance_on_highs_support_on_lows(self) -> None:
        bars = _log_bars(seed=5)
        h, lo, c = (np.log(a[50:90]) for a in (bars.high, bars.low, bars.close))
        pair = fit_trendlines_high_low(h, lo, c)
        x = np.arange(h.size)
        assert (pair.resistance.slope * x + pair.resistance.intercept - h).min() >= -TOL
        assert (pair.support.slope * x + pair.support.intercept - lo).max() <= TOL

    def test_length_mismatch(self) -> None:
        with pytest.raises(DataError, match="same length"):
            fit_trendlines_high_low(np.ones(5), np.ones(4), np.ones(5))


class TestBreakout:
    def test_signal_persists_and_lines_are_projected(self) -> None:
        close = np.log(_log_bars(200, seed=9).close)
        out = trendline_breakout(close, lookback=20)
        assert np.all(np.isnan(out.support[:20])) and np.all(np.isfinite(out.support[20:]))
        assert set(np.unique(out.signal)) <= {-1, 0, 1}
        # a bar strictly between its lines keeps the previous signal
        between = [i for i in range(21, 200) if out.support[i] < close[i] < out.resistance[i]]
        assert between and all(out.signal[i] == out.signal[i - 1] for i in between)

    def test_lines_come_from_the_previous_window_only(self) -> None:
        close = np.log(_log_bars(120, seed=2).close)
        out = trendline_breakout(close, lookback=15)
        i = 60
        pair = fit_trendlines_single(close[i - 15 : i])
        assert out.resistance[i] == pytest.approx(pair.resistance.value_at(15))
        assert out.support[i] == pytest.approx(pair.support.value_at(15))

    @pytest.mark.parametrize("lookback", [2, 200])
    def test_lookback_bounds(self, lookback: int) -> None:
        with pytest.raises(DataError, match="lookback"):
            trendline_breakout(np.linspace(0.0, 1.0, 200), lookback=lookback)

    def test_matches_pinned_upstream(self) -> None:
        fx = json.loads((FIXTURES / "trendline_fit.json").read_text())["breakout"]
        out = trendline_breakout(np.log(_log_bars().close), lookback=int(fx["lookback"]))
        exp_s = np.array([np.nan if v is None else v for v in fx["support"]])
        exp_r = np.array([np.nan if v is None else v for v in fx["resistance"]])
        np.testing.assert_allclose(out.support, exp_s, rtol=1e-12, equal_nan=True)
        np.testing.assert_allclose(out.resistance, exp_r, rtol=1e-12, equal_nan=True)
        assert list(out.signal) == fx["signal"]


class TestBreakoutFeatures:
    def test_trades_are_settled_and_consistent(self) -> None:
        bars = _log_bars(900, seed=21)
        trades = breakout_features(bars, lookback=24, hold_period=12, atr_lookback=48)
        assert len(trades) > 5
        close = np.log(bars.close)
        for t in trades:
            assert 48 <= t.entry_index < t.exit_index <= t.entry_index + 12
            assert t.entry_price == pytest.approx(close[t.entry_index])
            assert t.exit_price == pytest.approx(close[t.exit_index])
            assert t.label == (t.log_return > 0.0)
            assert t.resist_slope_atr == pytest.approx(t.resist_slope / t.atr)
            assert np.isfinite([t.tl_err_atr, t.max_dist_atr, t.vol_ratio, t.adx]).all()
            assert t.max_dist_atr >= -TOL / t.atr  # resistance sits on or above the window
            # the exit is the first bar hitting take-profit, stop-loss or the holding limit
            for j in range(t.entry_index + 1, t.exit_index):
                assert t.entry_price - 3.0 * t.atr < close[j] < t.entry_price + 3.0 * t.atr
        # trades never overlap
        assert all(
            b.entry_index > a.exit_index - 1 for a, b in zip(trades, trades[1:], strict=False)
        )

    def test_entries_match_the_breakout_series(self) -> None:
        bars = _log_bars(500, seed=4)
        close = np.log(bars.close)
        trades = breakout_features(bars, lookback=20, hold_period=6, atr_lookback=40)
        series = trendline_breakout(close, lookback=20)
        for t in trades:
            assert close[t.entry_index] > series.resistance[t.entry_index]

    def test_guards(self) -> None:
        bars = _log_bars(200)
        with pytest.raises(DataError, match="atr_lookback"):
            breakout_features(bars, lookback=30, atr_lookback=20)
        with pytest.raises(DataError, match="hold_period"):
            breakout_features(bars, lookback=10, hold_period=0, atr_lookback=20)
        assert breakout_features(bars, lookback=10, atr_lookback=500) == []
