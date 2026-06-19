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
    strategy: str = "ts_momentum",
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
    param: list[str] | None = None,
    snapshot: str | None = None,
) -> None:
    """Backtest SYMBOL with the fixed-parameter strategy; write the run artifacts.

    ``--strategy`` selects the registered strategy; ``--param name=value`` (repeatable) supplies any
    strategy-specific parameters beyond the shared ones.
    """
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
        train_size=504,  # walk-forward fields are unused by a plain backtest; kept coherent
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(param),
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


@backtest_app.command()
def portfolio(
    symbols: list[str],
    strategy: str = "ts_momentum",
    weighting: str = "equal",
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
    train_size: int = 504,
    test_size: int = 63,
    embargo: int = 5,
    anchored: bool = False,
    param: list[str] | None = None,
) -> None:
    """Backtest a diversified basket: run the strategy across SYMBOLS and combine the OOS streams.

    ``--weighting`` is ``equal`` or ``inverse_vol``. Reports the basket's headline metrics +
    Probabilistic Sharpe and each leg's OOS Sharpe; writes a manifest under ``data_dir/portfolio``.
    """
    import json

    from alpha_cli import _portfolio
    from alpha_core import DataError

    settings = AlphaSettings()
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
        train_size=train_size,
        test_size=test_size,
        embargo=embargo,
        anchored=anchored,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(param),
    )
    try:
        result = _portfolio.run_portfolio(
            symbols, spec, data_dir=settings.data_dir, weighting=weighting
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    run_id = _runner.run_id_for(
        {
            "command": "backtest_portfolio",
            "symbols": sorted(symbols),
            "weighting": weighting,
            **vars(spec),
        }
    )
    rdir = settings.data_dir / "portfolio" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "backtest_portfolio",
        "symbols": list(result.symbols),
        "weighting": result.weighting,
        "n_periods": result.n_periods,
        "metrics": {k: (v if v == v else None) for k, v in result.metrics.items()},
        "psr": result.psr if result.psr == result.psr else None,
        "dsr": result.dsr if result.dsr == result.dsr else None,
        "legs": [
            {
                "symbol": leg.symbol,
                "n_oos": leg.n_oos,
                "oos_sharpe": leg.oos_sharpe if leg.oos_sharpe == leg.oos_sharpe else None,
                "weight": leg.weight,
            }
            for leg in result.legs
        ],
    }
    (rdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    typer.echo(
        f"portfolio [{', '.join(result.symbols)}] ({weighting}) -> run {run_id}: "
        f"OOS Sharpe {result.metrics['sharpe']:.3f}, CAGR {result.metrics['cagr']:.3f}, "
        f"maxDD {result.metrics['max_drawdown']:.3f}, PSR {result.psr:.3f} "
        f"over {result.n_periods} periods; manifest at {rdir / 'manifest.json'}"
    )
