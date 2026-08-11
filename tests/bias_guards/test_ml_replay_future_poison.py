"""Future market bars cannot alter already-executed ML replay decisions or fills."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_backtest.portfolio_replay import PortfolioReplayResult, WeightTarget, run_weight_replay
from alpha_core import Bar


def _run(last_open: float) -> PortfolioReplayResult:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    bars: dict[str, list[Bar]] = {}
    for offset, symbol in enumerate(("AAA", "BBB")):
        series: list[Bar] = []
        for index, price in enumerate((100.0 + offset, 101.0 + offset, 102.0 + offset, last_open)):
            series.append(
                Bar(
                    symbol=symbol,
                    ts=start + timedelta(days=index),
                    open=price,
                    high=price + 1.0,
                    low=price - 1.0,
                    close=price,
                    volume=1_000.0,
                )
            )
        bars[symbol] = series
    targets = [
        WeightTarget(
            symbol=symbol,
            origin_ts=start + timedelta(days=origin),
            available_at=start + timedelta(days=origin, hours=23),
            target_ts=start + timedelta(days=origin + 1),
            target_weight=1.0 if symbol == "AAA" else 0.0,
            score=1.0 if symbol == "AAA" else 0.0,
            fold=0,
        )
        for origin in (0, 1)
        for symbol in ("AAA", "BBB")
    ]
    return run_weight_replay(bars, targets, starting_cash=10_000.0)


@pytest.mark.bias_guard
def test_future_open_poison_does_not_change_replay_prefix() -> None:
    baseline = _run(103.0)
    poisoned = _run(10_000.0)
    cutoff = datetime(2024, 1, 4, tzinfo=UTC)

    assert [fill for fill in baseline.backtest.fill_trace if fill.ts <= cutoff] == [
        fill for fill in poisoned.backtest.fill_trace if fill.ts <= cutoff
    ]
    assert [point for point in baseline.backtest.equity_curve if point[0] <= cutoff] == [
        point for point in poisoned.backtest.equity_curve if point[0] <= cutoff
    ]
