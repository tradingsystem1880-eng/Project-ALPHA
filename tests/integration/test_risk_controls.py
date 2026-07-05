"""Opt-in risk controls: equity-based vol sizing + the max-drawdown kill-switch.

Both default OFF (fixed-capital, no-halt — every prior result is unchanged); these tests pin the
opt-in behaviors against the real engine: the kill-switch flattens after a breach and never
re-enters, and equity-based sizing de-levers a drawn-down book relative to fixed-capital sizing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from alpha_backtest.engine import run_backtest
from alpha_backtest.feed import daily_bar_type, to_execution_feed
from alpha_backtest.instruments import equity_instrument
from alpha_core import Bar, DataError
from alpha_strategies.ts_momentum import TimeSeriesMomentum


def _bars(closes: list[float]) -> list[Bar]:
    start = datetime(2020, 1, 1, tzinfo=UTC)
    bars = []
    prev = closes[0]
    for i, c in enumerate(closes):
        o = prev
        hi, lo = max(o, c) * 1.001, min(o, c) * 0.999
        bars.append(
            Bar(
                symbol="X",
                ts=start + timedelta(days=i),
                open=o,
                high=hi,
                low=lo,
                close=c,
                volume=1e3,
            )
        )
        prev = c
    return bars


def _boom_bust() -> list[Bar]:
    # 40 bars up 2%/day (strategy goes long), then 40 bars down 3%/day (deep drawdown)
    closes = [100.0]
    for _ in range(40):
        closes.append(closes[-1] * 1.02)
    for _ in range(40):
        closes.append(closes[-1] * 0.97)
    return _bars(closes)


def _strat(**over: object) -> TimeSeriesMomentum:
    inst = equity_instrument("X")
    kw: dict[str, object] = dict(
        instrument_id=inst.id,
        bar_type=daily_bar_type("X"),
        lookback=35,  # slow signal: stays long ~14 bars into the crash before flipping flat
        skip=1,
        vol_window=8,
        target_vol=0.5,
        capital=1_000_000.0,
        max_leverage=0.9,
        rebalance_every=2,
        allow_short=False,
    )
    kw.update(over)
    return TimeSeriesMomentum(**kw)  # type: ignore[arg-type]


def _run(strat: TimeSeriesMomentum, bars: list[Bar]) -> tuple[TimeSeriesMomentum, float]:
    inst = equity_instrument("X")
    res = run_backtest(
        inst, to_execution_feed(bars, daily_bar_type("X")), strat, starting_cash=1_000_000.0
    )
    return strat, res.final_equity


def test_kill_switch_halts_early_and_preserves_equity() -> None:
    no_halt, eq_no_halt = _run(_strat(), _boom_bust())
    halted, eq_halted = _run(_strat(halt_drawdown=0.10), _boom_bust())
    assert not no_halt.halted  # the plain book only exits when the slow signal finally flips
    assert halted.halted and halted.net_units == 0  # kill-switch flattened for good
    assert eq_halted > eq_no_halt  # halting at ~-10% beats riding ~-35% to the signal flip


def _boom_only() -> list[Bar]:
    import numpy as np

    rng = np.random.default_rng(1)
    closes = [100.0]
    for _ in range(90):
        closes.append(closes[-1] * float(1.0 + 0.02 + rng.normal(0.0, 0.01)))
    return _bars(closes)


def test_equity_sizing_compounds_a_winning_book() -> None:
    # Fixed-capital sizing keeps notional pinned to the STARTING 1M while equity doubles;
    # equity-based sizing re-bases on current net-liq, so the winning book compounds.
    _, eq_fixed = _run(_strat(), _boom_only())
    _, eq_scaled = _run(_strat(size_on_equity=True), _boom_only())
    assert eq_scaled > eq_fixed


def test_halt_drawdown_validated() -> None:
    with pytest.raises(DataError, match="halt_drawdown"):
        _strat(halt_drawdown=1.5)


def test_gauntlet_and_optimizer_reject_equity_path_knobs() -> None:
    import numpy as np

    from alpha_cli._gauntlet import GauntletParams, run_gauntlet
    from alpha_cli._optim import run_optimization
    from alpha_cli._runner import RunSpec

    spec = RunSpec(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=False,
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=15,
        test_size=5,
        embargo=1,
        anchored=False,
        size_on_equity=True,
    )
    closes = 100.0 * np.cumprod(1 + np.random.default_rng(0).normal(0.002, 0.01, 60))
    bars = _bars(closes.tolist())
    with pytest.raises(DataError, match="size_on_equity"):
        run_gauntlet(bars, spec, GauntletParams(), run_id="x" * 16, snapshot_id=None)
    with pytest.raises(DataError, match="size_on_equity"):
        run_optimization(bars, spec, {"lookback": [4, 5]})
