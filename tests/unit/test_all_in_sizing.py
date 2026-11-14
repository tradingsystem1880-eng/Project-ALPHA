"""All-in books execute once per long/flat transition, through the real engine."""

import dataclasses
import math
from datetime import UTC, datetime, timedelta

import pytest

from alpha_cli._runner import RunSpec, run_full_backtest, run_identity_for
from alpha_cli._strategies import surrogate_for
from alpha_core import Bar, DataError


@pytest.fixture
def spec() -> RunSpec:
    return RunSpec(
        lookback=2,
        skip=0,
        vol_window=63,
        target_vol=0.15,
        rebalance_every=1,
        max_leverage=1.0,
        allow_short=False,
        periods_per_year=252,
        fee_bps=10.0,
        slippage_bps=5.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=100,
        test_size=20,
        embargo=0,
        anchored=True,
        strategy_name="ma_crossover",
        strategy_params=(("fast", 1.0), ("slow", 3.0)),
    )


def _bars(closes: list[float]) -> list[Bar]:
    return [
        Bar(
            symbol="SPY",
            ts=datetime(2020, 1, 1, tzinfo=UTC) + timedelta(days=i),
            open=(closes[i - 1] if i else close) * 1.001,
            high=max(close, (closes[i - 1] if i else close) * 1.001) + 0.01,
            low=min(close, (closes[i - 1] if i else close) * 1.001) - 0.01,
            close=close,
            volume=1_000_000.0,
        )
        for i, close in enumerate(closes)
    ]


@pytest.mark.parametrize(
    "strategy,params",
    [
        ("ma_crossover", (("fast", 1.0), ("slow", 3.0))),
        ("ts_momentum", ()),
        ("breakout", (("window", 2.0),)),
    ],
)
def test_all_in_holds_units_until_exit(
    spec: RunSpec, strategy: str, params: tuple[tuple[str, float], ...]
) -> None:
    spec = dataclasses.replace(
        spec, sizing="all_in", strategy_name=strategy, strategy_params=params
    )
    bars = _bars([100.0 + i for i in range(12)] + [90.0 - i for i in range(8)])
    result = run_full_backtest(bars, spec)
    expected = math.floor(100_000 * 0.998 / (102 * 1.001 * 1.0005))
    assert result.orders == result.fills == 2
    assert result.rejected == 0
    assert [row.side for row in result.fill_trace] == ["BUY", "SELL"]
    assert [row.quantity for row in result.fill_trace] == pytest.approx([expected, expected])
    long_targets = [row.target_quantity for row in result.decision_trace if row.signal == 1]
    assert long_targets == pytest.approx([expected] * len(long_targets))
    assert all(row.target_quantity >= 0 for row in result.decision_trace)
    assert result.decision_trace[-1].target_quantity == pytest.approx(0)
    assert len(result.trades) == 1
    assert result.fill_trace[0].ts.date() == bars[3].ts.date()
    assert result.fill_trace[0].ts > result.decision_trace[0].ts
    assert spec.min_train == 3


def test_all_in_reentry_uses_current_equity(spec: RunSpec) -> None:
    spec = dataclasses.replace(spec, sizing="all_in")
    bars = _bars(
        [100.0 + i for i in range(12)]
        + [90.0 - i for i in range(8)]
        + [100.0 + i for i in range(8)]
    )
    result = run_full_backtest(bars, spec)
    assert result.orders == result.fills == 3
    assert result.rejected == 0
    entry = result.fill_trace[2]
    decision = next(row for row in result.decision_trace if row.ts.date() == bars[20].ts.date())
    expected = math.floor(
        (spec.starting_cash + result.trades[0].realized_pnl) * 0.998 / (100 * 1.001 * 1.0005)
    )
    assert entry.quantity == pytest.approx(expected)
    assert decision.target_quantity == pytest.approx(expected)


def test_all_in_rejects_short_and_unknown_sizing(spec: RunSpec) -> None:
    bars = _bars([100.0 + i for i in range(10)])
    with pytest.raises(DataError, match="all_in.*allow_short"):
        run_full_backtest(bars, dataclasses.replace(spec, sizing="all_in", allow_short=True))
    with pytest.raises(DataError, match="sizing"):
        run_full_backtest(bars, dataclasses.replace(spec, sizing="typo"))


def test_all_in_surrogate_holds_weight_one_or_zero(spec: RunSpec) -> None:
    import numpy as np

    closes = np.array([100.0 + i for i in range(12)] + [110.0 - 2 * i for i in range(12)])
    price_returns = closes[1:] / closes[:-1] - 1.0
    surrogate = surrogate_for(dataclasses.replace(spec, sizing="all_in"))
    weights, costs = surrogate.weights_and_costs(price_returns)
    assert set(np.unique(weights)) == {0.0, 1.0}
    changes = int(np.count_nonzero(np.diff(np.concatenate([[0.0], weights]))))
    assert changes == 2  # one entry, one exit: no re-sizing while long
    assert np.count_nonzero(costs) == changes
    assert costs.max() == pytest.approx((spec.fee_bps + spec.slippage_bps) / 10_000.0)


def test_default_sizing_unchanged(spec: RunSpec) -> None:
    bars = _bars([100.0 + i + (i % 3) for i in range(100)] + [180.0 - i for i in range(20)])
    implicit = run_full_backtest(bars, spec)
    explicit = run_full_backtest(bars, dataclasses.replace(spec, sizing="vol_target"))
    assert implicit == explicit
    assert implicit.orders > 0


def test_default_sizing_omitted_from_identity(spec: RunSpec) -> None:
    legacy = dataclasses.asdict(spec)
    legacy.pop("sizing", None)
    assert run_identity_for(legacy) == run_identity_for({**legacy, "sizing": "vol_target"})
    assert (
        run_identity_for(legacy).run_id != run_identity_for({**legacy, "sizing": "all_in"}).run_id
    )


def test_all_in_fractional_instrument_precision(
    spec: RunSpec, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_backtest import instruments

    monkeypatch.setattr(
        instruments,
        "instrument_for",
        lambda symbol: instruments.crypto_instrument(symbol, size_precision=2, size_increment=0.01),
    )
    bars = [
        bar.model_copy(update={"symbol": "BTC/USD"})
        for bar in _bars([100.0 + i for i in range(12)] + [90.0 - i for i in range(8)])
    ]
    result = run_full_backtest(
        bars, dataclasses.replace(spec, sizing="all_in", account_type="MARGIN")
    )
    expected = math.floor(100_000 * 0.998 / (102 * 1.001 * 1.0005) * 100) / 100
    assert result.orders == result.fills == 2
    assert result.rejected == 0
    assert [fill.quantity for fill in result.fill_trace] == pytest.approx([expected, expected])
