"""Synchronized cross-sectional weight replay through the ALPHA execution ledger."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from alpha_backtest.portfolio_replay import WeightTarget, run_weight_replay
from alpha_core import Bar, DataError


def _bars(*, poison_last_open: float | None = None) -> dict[str, list[Bar]]:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    values = {
        "AAA": [(100.0, 100.0), (110.0, 112.0), (115.0, 114.0), (116.0, 116.0)],
        "BBB": [(50.0, 50.0), (51.0, 50.0), (49.0, 48.0), (54.0, 54.0)],
    }
    if poison_last_open is not None:
        values["AAA"][-1] = (poison_last_open, poison_last_open)
        values["BBB"][-1] = (poison_last_open, poison_last_open)
    return {
        symbol: [
            Bar(
                symbol=symbol,
                ts=start + timedelta(days=index),
                open=open_,
                high=max(open_, close) + 1.0,
                low=min(open_, close) - 1.0,
                close=close,
                volume=1_000_000.0,
            )
            for index, (open_, close) in enumerate(series)
        ]
        for symbol, series in values.items()
    }


def _targets() -> list[WeightTarget]:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    rows: list[WeightTarget] = []
    for origin_index, selected in ((0, "AAA"), (1, "BBB")):
        origin = start + timedelta(days=origin_index)
        target = origin + timedelta(days=1)
        for symbol in ("AAA", "BBB"):
            rows.append(
                WeightTarget(
                    symbol=symbol,
                    origin_ts=origin,
                    available_at=origin + timedelta(hours=23),
                    target_ts=target,
                    target_weight=1.0 if symbol == selected else 0.0,
                    score=1.0 if symbol == selected else 0.0,
                    fold=0,
                )
            )
    return rows


def test_weight_replay_decides_at_close_and_fills_at_next_open() -> None:
    result = run_weight_replay(
        _bars(),
        _targets(),
        starting_cash=1_000.0,
        fee_bps=0.0,
        slippage_bps=0.0,
    )

    aaa_entry = next(fill for fill in result.backtest.fill_trace if fill.instrument_id == "AAA.SIM")
    bbb_entry = next(
        fill
        for fill in result.backtest.fill_trace
        if fill.instrument_id == "BBB.SIM" and fill.side == "BUY"
    )
    assert aaa_entry.ts == datetime(2024, 1, 3, tzinfo=UTC)
    assert aaa_entry.price == 110.0
    assert bbb_entry.ts == datetime(2024, 1, 4, tzinfo=UTC)
    assert bbb_entry.price == 49.0
    assert all(order.ts < fill.ts for order, fill in result.reconciled_order_fills())
    assert result.backtest.equity_curve[0] == (datetime(2024, 1, 3, tzinfo=UTC), 1_000.0)
    assert result.backtest.equity_curve[-1][0] == datetime(2024, 1, 5, tzinfo=UTC)
    assert len(result.periods) == 2
    assert result.periods[0].gross_return == pytest.approx(115.0 / 110.0 - 1.0)
    assert result.periods[1].benchmark_return == pytest.approx(
        ((116.0 / 115.0 - 1.0) + (54.0 / 49.0 - 1.0)) / 2.0
    )
    assert result.backtest.final_equity > result.backtest.starting_equity


def test_weight_replay_applies_declared_fee_and_side_aware_slippage() -> None:
    clean = run_weight_replay(_bars(), _targets(), starting_cash=1_000.0)
    costed = run_weight_replay(
        _bars(),
        _targets(),
        starting_cash=1_000.0,
        fee_bps=10.0,
        slippage_bps=20.0,
    )

    first_buy = next(fill for fill in costed.backtest.fill_trace if fill.side == "BUY")
    first_sell = next(fill for fill in costed.backtest.fill_trace if fill.side == "SELL")
    assert first_buy.price == pytest.approx(110.0 * 1.002)
    assert first_sell.price == pytest.approx(115.0 * 0.998)
    assert sum(period.fees for period in costed.periods) > 0.0
    assert sum(period.slippage_cost for period in costed.periods) > 0.0
    assert costed.backtest.final_equity < clean.backtest.final_equity


def test_weight_replay_rejects_incomplete_or_noncausal_cross_sections() -> None:
    with pytest.raises(DataError, match="complete universe"):
        run_weight_replay(_bars(), _targets()[:-1])

    bad = _targets()
    bad[0] = replace(bad[0], available_at=bad[0].target_ts)
    with pytest.raises(DataError, match="available"):
        run_weight_replay(_bars(), bad)
