"""Diversified-basket portfolio backtest (``alpha_cli._portfolio``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from alpha_cli._portfolio import run_portfolio
from alpha_cli._runner import RunSpec
from alpha_core import DataError
from tests.fixtures.cli_fixtures import seed_store


def _spec() -> RunSpec:
    return RunSpec(
        lookback=5,
        skip=1,
        vol_window=3,
        target_vol=0.15,
        rebalance_every=2,
        max_leverage=1.0,
        allow_short=False,  # long-flat: coherent with CASH
        periods_per_year=252,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=100_000.0,
        account_type="CASH",
        train_size=15,
        test_size=5,
        embargo=1,
        anchored=False,
    )


def _seed_universe(data_dir: Path) -> list[str]:
    symbols = ["SPY", "QQQ", "IWM"]
    for i, sym in enumerate(symbols):
        seed_store(data_dir, symbol=sym, n=80, seed=i, drift=0.0015 + 0.0005 * i)
    return symbols


def test_equal_weight_basket_combines_legs(tmp_path: Path) -> None:
    symbols = _seed_universe(tmp_path)
    res = run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="equal")
    assert res.symbols == ("SPY", "QQQ", "IWM")
    assert res.n_periods > 0
    assert res.portfolio_returns.size == res.n_periods
    assert len(res.legs) == 3
    assert all(leg.weight == pytest.approx(1 / 3) for leg in res.legs)
    assert res.metrics["sharpe"] == res.metrics["sharpe"]  # finite (not NaN)
    assert 0.0 <= res.psr <= 1.0
    assert res.sharpe_ci.lower <= res.sharpe_ci.point <= res.sharpe_ci.upper
    assert res.cagr_ci.lower <= res.cagr_ci.upper


def test_inverse_vol_weights_differ_and_sum_to_one(tmp_path: Path) -> None:
    symbols = _seed_universe(tmp_path)
    res = run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="inverse_vol")
    weights = [leg.weight for leg in res.legs]
    assert sum(weights) == pytest.approx(1.0)
    assert len(set(round(w, 6) for w in weights)) > 1  # not all identical


def test_deterministic(tmp_path: Path) -> None:
    symbols = _seed_universe(tmp_path)
    a = run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="equal")
    b = run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="equal")
    assert (a.portfolio_returns == b.portfolio_returns).all()


def test_fails_loud(tmp_path: Path) -> None:
    symbols = _seed_universe(tmp_path)
    with pytest.raises(DataError):
        run_portfolio(symbols[:1], _spec(), data_dir=tmp_path)  # < 2 symbols
    with pytest.raises(DataError):
        run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="nope")
    with pytest.raises(DataError):
        run_portfolio(["SPY", "SPY"], _spec(), data_dir=tmp_path)  # duplicates


def test_inverse_vol_weights_are_causal_no_lookahead(tmp_path: Path) -> None:
    # Future poison (golden rule: no look-ahead, ever): appending FUTURE bars to one leg must not
    # change the portfolio's returns on earlier dates. The old implementation set one static
    # weight per leg from its FULL OOS volatility, so future data re-weighted the past.
    symbols = _seed_universe(tmp_path)
    before = run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="inverse_vol")

    # extend one leg with 12 extra future bars (same seed/params -> identical first 80 bars,
    # since the rng draws are sequential and the extension only appends)
    seed_store(tmp_path, symbol="QQQ", n=92, seed=1, drift=0.0020)
    after = run_portfolio(symbols, _spec(), data_dir=tmp_path, weighting="inverse_vol")

    overlap = {d: r for d, r in zip(before.portfolio_timestamps, before.portfolio_returns)}
    changed = {d: r for d, r in zip(after.portfolio_timestamps, after.portfolio_returns)}
    common = [d for d in overlap if d in changed]
    assert len(common) > 5
    for d in common:
        assert changed[d] == pytest.approx(overlap[d]), f"return at {d} changed with future data"
