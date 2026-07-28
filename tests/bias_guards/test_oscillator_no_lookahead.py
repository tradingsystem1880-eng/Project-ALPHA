"""Future-poison guards for the oscillator, cycle and level layers.

Same method as ``test_indicator_no_lookahead``: compute, replace every bar after ``CUT`` with a
violently different path, recompute, and assert nothing at or before ``CUT`` moved.

Three functions here are *designed* to look like they leak and do not, which is the whole reason
this file exists rather than being folded into the indicator guards:

* **Ichimoku's senkou spans** are drawn 26 bars forward on a chart. The implementation returns the
  cloud *in force at* each bar — computed 26 bars earlier — so the guard passes. An implementation
  that returned the cloud stamped at the bar it was computed from would fail here loudly, which is
  the point.
* **Ichimoku's chikou span** is the close shifted backwards. Stamped where the information exists
  it is causal; stamped where a chart draws it, it is 26 bars of pure future.
* **Fibonacci grids** are anchored on swings, and a swing is not knowable until ``index + lookback``
  bars have passed. Anchoring on the raw swing index instead is the classic way a retracement study
  finds fake support. That one is pinned structurally rather than by poisoning — whether poison
  moves a raw-index anchor depends on where swings happen to fall relative to the cut, which is a
  property of the seed, not of the code.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    chaikin_money_flow,
    directional_index,
    donchian_channel,
    ema,
    fib_levels_at,
    find_swings,
    geometric_brownian_series,
    ichimoku,
    keltner_channel,
    log_returns,
    macd,
    money_flow_index,
    nearest_fib_distance,
    on_balance_volume,
    rolling_autocorrelation,
    rolling_hurst,
    rolling_variance_ratio,
    round_number_distance,
    stochastic,
    typical_price,
    wilder_smooth,
    williams_r,
)

CUT = 300


def _series(seed: int = 7, n: int = 600) -> OHLCV:
    return geometric_brownian_series(n, seed=seed, vol_per_bar=0.02, start=1.0)


def _poison(bars: OHLCV, cut: int = CUT) -> OHLCV:
    """Replace every bar strictly after ``cut``; copy everything at or before it byte for byte."""
    rng = np.random.default_rng(999)
    n = len(bars)
    tail = n - cut - 1
    close, open_ = bars.close.copy(), bars.open.copy()
    high, low, volume = bars.high.copy(), bars.low.copy(), bars.volume.copy()

    close[cut + 1 :] = bars.close[cut] * (10.0 + rng.random(tail) * 5.0)
    open_[cut + 1 :] = np.concatenate(([bars.close[cut]], close[cut + 1 : -1]))
    high[cut + 1 :] = np.maximum(open_[cut + 1 :], close[cut + 1 :]) * 1.02
    low[cut + 1 :] = np.minimum(open_[cut + 1 :], close[cut + 1 :]) * 0.98
    volume[cut + 1 :] *= 50.0
    return OHLCV(bars.ts, open_, high, low, close, volume, bars.symbol)


def _same(clean: np.ndarray, dirty: np.ndarray, label: str) -> None:
    a, b = np.asarray(clean)[: CUT + 1], np.asarray(dirty)[: CUT + 1]
    both_nan = np.isnan(a.astype(np.float64)) & np.isnan(b.astype(np.float64))
    assert np.array_equal(a[~both_nan], b[~both_nan]), f"{label} changed before the cut"


@pytest.mark.bias_guard
class TestOscillatorsAreCausal:
    @pytest.mark.parametrize(
        ("label", "fn"),
        [
            ("ema", lambda b: ema(b.close, 21)),
            ("wilder_smooth", lambda b: wilder_smooth(b.close, 14)),
            ("obv", lambda b: on_balance_volume(b.close, b.volume)),
            ("typical_price", lambda b: typical_price(b)),
            ("macd.line", lambda b: macd(b.close).line),
            ("macd.signal", lambda b: macd(b.close).signal),
            ("macd.histogram", lambda b: macd(b.close).histogram),
            ("stochastic.k", lambda b: stochastic(b).k),
            ("stochastic.d", lambda b: stochastic(b).d),
            ("williams_r", lambda b: williams_r(b)),
            ("mfi", lambda b: money_flow_index(b)),
            ("cmf", lambda b: chaikin_money_flow(b)),
            ("plus_di", lambda b: directional_index(b).plus_di),
            ("minus_di", lambda b: directional_index(b).minus_di),
            ("adx", lambda b: directional_index(b).adx),
            ("keltner.upper", lambda b: keltner_channel(b).upper),
            ("keltner.position", lambda b: keltner_channel(b).position),
            ("donchian.upper", lambda b: donchian_channel(b).upper),
            ("donchian.position", lambda b: donchian_channel(b).position),
            ("round_number_distance", lambda b: round_number_distance(b.close)),
        ],
    )
    def test_indicator_ignores_the_future(self, label: str, fn) -> None:  # type: ignore[no-untyped-def]
        bars = _series()
        _same(fn(bars), fn(_poison(bars)), label)


@pytest.mark.bias_guard
class TestIchimokuDisplacementIsCausal:
    """The displaced spans are the whole reason this class exists."""

    @pytest.mark.parametrize(
        "field", ["tenkan", "kijun", "span_a", "span_b", "above_cloud", "chikou_above"]
    )
    def test_every_line_ignores_the_future(self, field: str) -> None:
        bars = _series()
        _same(getattr(ichimoku(bars), field), getattr(ichimoku(_poison(bars)), field), field)

    def test_cloud_is_the_one_in_force_not_the_one_being_computed(self) -> None:
        """span_a at bar i must equal the raw tenkan/kijun midpoint from bar i-26."""
        bars = _series()
        ich = ichimoku(bars)
        raw = (ich.tenkan + ich.kijun) / 2.0
        assert ich.span_a[400] == pytest.approx(raw[400 - 26])
        # And it must NOT equal the value computed at its own bar, or the shift did nothing.
        assert ich.span_a[400] != pytest.approx(raw[400])


@pytest.mark.bias_guard
class TestCycleStatisticsAreCausal:
    @pytest.mark.parametrize(
        ("label", "fn"),
        [
            (
                "rolling_autocorrelation",
                lambda b: rolling_autocorrelation(log_returns(b.close), window=128),
            ),
            (
                "rolling_variance_ratio",
                lambda b: rolling_variance_ratio(np.log(b.close), window=128, q=5),
            ),
            ("rolling_hurst", lambda b: rolling_hurst(log_returns(b.close), window=128)),
        ],
    )
    def test_rolling_statistic_ignores_the_future(self, label: str, fn) -> None:  # type: ignore[no-untyped-def]
        bars = _series()
        _same(fn(bars), fn(_poison(bars)), label)


@pytest.mark.bias_guard
class TestFibAnchorsOnConfirmedSwingsOnly:
    def test_distance_series_ignores_the_future(self) -> None:
        bars = _series()
        clean = nearest_fib_distance(bars.close, _swings(bars))
        dirty = nearest_fib_distance(_poison(bars).close, _swings(_poison(bars)))
        _same(clean, dirty, "nearest_fib_distance")

    def test_the_confirmation_gate_is_what_makes_it_causal(self) -> None:
        """The passing guard above must be *because of* the gate, not incidental to this seed.

        Poisoning is the wrong instrument for that claim: whether it moves a raw-index anchor
        depends on whether a swing happens to fall in the confirmation shadow of the cut, which is
        a property of the seed rather than of the code. The structural version has no such
        dependence — it asks directly whether the naive construction ever reaches for a swing that
        was not yet knowable, and whether the real one ever does.
        """
        bars = _series()
        swings = sorted(_swings(bars), key=lambda s: s.index)

        naive_uses_unconfirmed = sum(
            1
            for i in range(bars.close.size)
            for s in [_latest_by_index(swings, i)]
            if s is not None and s.confirmed_index > i
        )
        assert naive_uses_unconfirmed > 0, (
            "anchoring on the raw swing index never reached an unconfirmed swing on this series, "
            "so this test is not exercising the gate it claims to"
        )

        real_uses_unconfirmed = sum(
            1
            for i in range(bars.close.size)
            for grid in [fib_levels_at(swings, i)]
            if grid is not None and grid.known_at > i
        )
        assert real_uses_unconfirmed == 0, (
            f"fib_levels_at anchored on {real_uses_unconfirmed} swing(s) before their confirmation "
            "bar — the retracement grid is reading the future"
        )


def _swings(bars: OHLCV):  # type: ignore[no-untyped-def]
    return find_swings(bars, lookback=5, kind="high") + find_swings(bars, lookback=5, kind="low")


def _latest_by_index(swings: list, index: int):  # type: ignore[no-untyped-def]
    """The naive anchor: most recent swing by *occurrence*, ignoring when it became knowable."""
    known = [s for s in swings if s.index <= index]
    highs = [s for s in known if s.kind == "high"]
    lows = [s for s in known if s.kind == "low"]
    if not highs or not lows:
        return None
    return max((highs[-1], lows[-1]), key=lambda s: s.confirmed_index)
