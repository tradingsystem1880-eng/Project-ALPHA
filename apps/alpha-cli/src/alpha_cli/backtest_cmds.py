"""``alpha backtest run``: run the v1 strategy once and persist the trade log + equity curve.

Satisfies spec §11.1. Shares ``_runner.run_full_backtest`` (and the ``RunSpec``) with the
validation gauntlet, so both drive the engine through one code path.
"""

from __future__ import annotations

import typer

from alpha_cli import _artifacts, _runner
from alpha_core.config import AlphaSettings

backtest_app = typer.Typer(help="Run the v1 strategy through the backtest engine.")

# monkeypatchable bar-load seam (mirrors data_cmds._ADAPTERS); tests point it at a fixture store
_load_bars = _runner.load_bars


@backtest_app.command()
def run(
    symbol: str,
    lookback: int = 252,
    skip: int = 21,
    vol_window: int = 63,
    target_vol: float = 0.15,
    rebalance_every: int = 21,
    max_leverage: float = 1.0,
    allow_short: bool = True,
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    starting_cash: float = 1_000_000.0,
    account_type: str = "CASH",
    snapshot: str | None = None,
) -> None:
    """Backtest SYMBOL with the fixed-parameter TS-momentum strategy; write the run artifacts."""
    settings = AlphaSettings()
    # walk-forward fields are unused by a plain backtest; carry coherent defaults
    spec = _runner.RunSpec(
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        rebalance_every=rebalance_every,
        max_leverage=max_leverage,
        allow_short=allow_short,
        periods_per_year=252,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        starting_cash=starting_cash,
        account_type=account_type,
        train_size=252,
        test_size=63,
        embargo=5,
        anchored=False,
    )
    bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
    result = _runner.run_full_backtest(bars, spec)
    run_id = _runner.run_id_for(
        {"command": "backtest_run", "symbol": symbol, "snapshot_id": snapshot_id, **vars(spec)}
    )
    rdir = _artifacts.run_dir(settings.data_dir, run_id)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "backtest_run",
        "symbol": symbol,
        "snapshot_id": snapshot_id,
        "params": vars(spec),
        "orders": result.orders,
        "fills": result.fills,
        "n_trades": len(result.trades),
        "starting_equity": result.starting_equity,
        "final_equity": result.final_equity,
    }
    _artifacts.write_run(rdir, manifest=manifest, equity=result.equity_curve, trades=result.trades)
    typer.echo(
        f"backtest {symbol} -> run {run_id}: {result.orders} orders, "
        f"{len(result.trades)} trades, final equity {result.final_equity:.2f}"
    )
