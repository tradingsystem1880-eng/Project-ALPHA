"""Future-poison guards for every trailing-window indicator and for the wedge detector.

The method: compute the indicator over a series, then **replace everything after bar ``k`` with
garbage** and recompute. Any value at or before ``k`` that changes was reading the future. A
peeking indicator is the one defect this project's statistics cannot detect or repair — a lookahead
of a single bar produces confident, well-intervalled, entirely false findings — so the check is
mechanical and applies to every function that claims to be causal.

The poison is deliberately violent (a 10x jump plus noise) rather than subtle: an indicator that
survives this is not merely insensitive to small perturbations, it genuinely never touched them.
"""

from __future__ import annotations

import numpy as np
import pytest

from alpha_patterns import (
    OHLCV,
    WedgeConfig,
    atr,
    bollinger_bandwidth,
    consolidation_length,
    detect_wedges,
    geometric_brownian_series,
    log_returns,
    percentile_rank,
    realized_volatility,
    rolling_correlation,
    rolling_mean,
    rolling_std,
    rsi,
    volume_ratio,
    wedge_panel,
)

CUT = 300  # the bar after which everything is poisoned


def _series(seed: int = 7, n: int = 600) -> OHLCV:
    return geometric_brownian_series(n, seed=seed, vol_per_bar=0.02, start=1.0)


def _poison(bars: OHLCV, cut: int = CUT) -> OHLCV:
    """Replace every bar strictly after ``cut`` with a violently different path.

    Bars at or before ``cut`` are copied through **byte for byte**. That matters more than it looks:
    an earlier version of this helper rebuilt the whole OHLC array from the poisoned closes, which
    perturbed the pre-cut highs and lows too and made three causal indicators appear to fail. The
    guard is only meaningful if the untouched region is genuinely untouched.
    """
    rng = np.random.default_rng(999)
    n = len(bars)
    tail = n - cut - 1
    close = bars.close.copy()
    open_ = bars.open.copy()
    high = bars.high.copy()
    low = bars.low.copy()
    volume = bars.volume.copy()

    close[cut + 1 :] = bars.close[cut] * (10.0 + rng.random(tail) * 5.0)
    open_[cut + 1 :] = np.concatenate(([bars.close[cut]], close[cut + 1 : -1]))
    high[cut + 1 :] = np.maximum(open_[cut + 1 :], close[cut + 1 :]) * 1.02
    low[cut + 1 :] = np.minimum(open_[cut + 1 :], close[cut + 1 :]) * 0.98
    volume[cut + 1 :] *= 50.0

    return OHLCV(
        ts=bars.ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        symbol=bars.symbol,
    )


@pytest.mark.bias_guard
class TestIndicatorsAreCausal:
    @pytest.mark.parametrize(
        "fn",
        [
            pytest.param(lambda b: rolling_mean(b.close, 20), id="rolling_mean"),
            pytest.param(lambda b: rolling_std(b.close, 20), id="rolling_std"),
            pytest.param(lambda b: log_returns(b.close), id="log_returns"),
            pytest.param(lambda b: realized_volatility(b.close, 30), id="realized_volatility"),
            pytest.param(lambda b: bollinger_bandwidth(b.close, 20), id="bollinger_bandwidth"),
            pytest.param(lambda b: rsi(b.close, 14), id="rsi"),
            pytest.param(lambda b: percentile_rank(b.close, 100), id="percentile_rank"),
            pytest.param(lambda b: atr(b, 14), id="atr"),
            pytest.param(lambda b: volume_ratio(b, 20), id="volume_ratio"),
            pytest.param(
                lambda b: consolidation_length(b.close, 20, threshold=0.15).astype(np.float64),
                id="consolidation_length",
            ),
            pytest.param(
                lambda b: rolling_correlation(log_returns(b.close), log_returns(b.high), 60),
                id="rolling_correlation",
            ),
        ],
    )
    def test_future_bars_cannot_change_the_past(self, fn) -> None:  # type: ignore[no-untyped-def]
        clean = _series()
        before = fn(clean)
        after = fn(_poison(clean))
        assert before[: CUT + 1] == pytest.approx(after[: CUT + 1], nan_ok=True), (
            "values at or before the cut changed when the future was poisoned"
        )

    def test_rolling_std_is_bit_identical_not_merely_close(self) -> None:
        """``rolling_std`` must not read the future even for numerical conditioning.

        An earlier implementation centred the whole series on its own mean before windowing. That
        is algebraically exact — a constant shift cancels out of a variance — but it made the
        output depend on bars that had not printed, and in floating point the last digits actually
        moved. Both are unacceptable under this project's no-look-ahead rule, so the assertion here
        is exact equality rather than a tolerance.
        """
        clean = _series()
        before = rolling_std(clean.close, 20)[: CUT + 1]
        after = rolling_std(_poison(clean).close, 20)[: CUT + 1]
        assert np.array_equal(before, after)


@pytest.mark.bias_guard
class TestWedgeDetectionIsPointInTime:
    def test_wedges_confirmed_before_the_cut_are_unchanged(self) -> None:
        clean = _series(seed=3, n=800)
        cfg = WedgeConfig()

        def geometry(bars: OHLCV) -> set[tuple[int, int, int, int, int]]:
            return {
                (
                    w.upper_indices[0],
                    w.upper_indices[1],
                    w.lower_indices[0],
                    w.lower_indices[1],
                    w.confirmed_index,
                )
                for w in detect_wedges(bars, cfg)
                if w.confirmed_index <= CUT
            }

        assert geometry(clean) == geometry(_poison(clean, CUT))

    def test_confirmation_always_follows_the_last_anchor(self) -> None:
        """A wedge cannot be known before its final pivot is confirmed, by construction."""
        bars = _series(seed=5, n=900)
        wedges = detect_wedges(bars, WedgeConfig())
        assert wedges, "no wedges detected — the guard would be vacuous"
        for w in wedges:
            assert w.confirmed_index >= w.end_index
            assert w.confirmed_index >= max(w.upper_indices[1], w.lower_indices[1])
            # A break is only ever attributed after confirmation.
            assert w.break_index == -1 or w.break_index > w.confirmed_index

    def test_panel_activity_starts_at_confirmation_not_at_the_anchors(self) -> None:
        bars = _series(seed=11, n=900)
        wedges = detect_wedges(bars, WedgeConfig())
        panel = wedge_panel(bars, wedges)
        earliest = min(w.confirmed_index for w in wedges)
        assert not panel.active[:earliest].any(), (
            "the panel marked a wedge active before any wedge had been confirmed"
        )
