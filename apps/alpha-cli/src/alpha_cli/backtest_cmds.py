"""``alpha backtest run``: run the v1 strategy once and persist the trade log + equity curve.

Satisfies spec §11.1. Shares ``_runner.run_full_backtest`` (and the ``RunSpec``) with the
validation gauntlet, so both drive the engine through one code path.
"""

from __future__ import annotations

import typer

from alpha_cli import _artifacts, _runner, _strategies
from alpha_core import DataError
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
    try:
        bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
        warnings = _strategies.pre_run_warnings(spec, bars)
        for warning in warnings:
            typer.secho(warning, err=True, fg="yellow")
        result = _runner.run_full_backtest(bars, spec)
    except DataError as exc:  # no bars stored, unknown strategy, bad account-type, etc.
        raise typer.BadParameter(str(exc)) from exc
    # Fail loud (golden rule): a run that submitted orders but filled none — every order rejected —
    # would otherwise report a misleading flat equity. The usual cause is a vol-targeted notional
    # that exceeds CASH buying power once fees apply.
    if result.fills == 0 and result.rejected > 0:
        raise typer.BadParameter(
            f"all {result.rejected} orders were rejected (no fills) for {symbol}: the vol-targeted "
            f"notional exceeds buying power. Use --account-type MARGIN, lower --target-vol, or set "
            f"--max-leverage below 1."
        )
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
        "rejected": result.rejected,
        "n_trades": len(result.trades),
        "starting_equity": result.starting_equity,
        "final_equity": result.final_equity,
        "leakage_warning": warnings[0] if warnings else None,
    }
    _artifacts.write_run(rdir, manifest=manifest, equity=result.equity_curve, trades=result.trades)
    warn = f" ({result.rejected} orders rejected)" if result.rejected else ""
    typer.echo(
        f"backtest {symbol} -> run {run_id}: {result.orders} orders, {result.fills} fills, "
        f"{len(result.trades)} trades, final equity {result.final_equity:.2f}{warn}"
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
    from alpha_cli import _portfolio

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
        "sharpe_ci": {"lower": result.sharpe_ci.lower, "upper": result.sharpe_ci.upper},
        "cagr_ci": {"lower": result.cagr_ci.lower, "upper": result.cagr_ci.upper},
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
    _artifacts.write_manifest(rdir, manifest)
    from alpha_validation import render_returns_tearsheet

    render_returns_tearsheet(
        result.portfolio_returns,
        result.portfolio_timestamps,
        title=f"ALPHA Portfolio — {', '.join(result.symbols)} ({weighting})",
        summary_rows=[
            ("OOS Sharpe", f"{result.metrics['sharpe']:.3f}"),
            ("Sharpe 95% CI", f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}]"),
            ("CAGR", f"{result.metrics['cagr']:.3f}"),
            ("Max drawdown", f"{result.metrics['max_drawdown']:.3f}"),
            ("Probabilistic Sharpe", f"{result.psr:.3f}"),
            ("Periods", str(result.n_periods)),
            ("Legs", ", ".join(f"{leg.symbol}={leg.weight:.2f}" for leg in result.legs)),
        ],
        output_path=rdir / "tearsheet.html",
    )
    typer.echo(
        f"portfolio [{', '.join(result.symbols)}] ({weighting}) -> run {run_id}: "
        f"OOS Sharpe {result.metrics['sharpe']:.3f} "
        f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}], "
        f"CAGR {result.metrics['cagr']:.3f}, maxDD {result.metrics['max_drawdown']:.3f}, "
        f"PSR {result.psr:.3f} over {result.n_periods} periods; "
        f"manifest at {rdir / 'manifest.json'}"
    )


@backtest_app.command(name="cross-sectional")
def cross_sectional(
    symbols: list[str],
    lookback: int = 252,
    skip: int = 21,
    vol_window: int = 63,
    target_vol: float = 0.15,
    rebalance_every: int = 21,
    top_quantile: float = 0.3,
    long_short: bool = True,
    max_leverage: float = 2.0,
) -> None:
    """Backtest a cross-sectional momentum book: long the universe's winners, short its losers.

    Ranks SYMBOLS each rebalance by trailing return; longs the top ``--top-quantile`` and (unless
    ``--no-long-short``) shorts the bottom, vol-targeted. Reports OOS metrics + PSR + BCa intervals
    and writes a manifest under ``data_dir/cross_sectional``.
    """
    from alpha_cli import _cross_sectional

    settings = AlphaSettings()
    try:
        result = _cross_sectional.run_cross_sectional(
            symbols,
            data_dir=settings.data_dir,
            lookback=lookback,
            skip=skip,
            vol_window=vol_window,
            target_vol=target_vol,
            rebalance_every=rebalance_every,
            top_quantile=top_quantile,
            long_short=long_short,
            max_leverage=max_leverage,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    run_id = _runner.run_id_for(
        {
            "command": "cross_sectional",
            "symbols": sorted(symbols),
            "lookback": lookback,
            "skip": skip,
            "vol_window": vol_window,
            "target_vol": target_vol,
            "rebalance_every": rebalance_every,
            "top_quantile": top_quantile,
            "long_short": long_short,
            "max_leverage": max_leverage,
        }
    )
    rdir = settings.data_dir / "cross_sectional" / run_id
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "cross_sectional",
        "symbols": list(result.symbols),
        "long_short": result.long_short,
        "n_long": result.n_long,
        "n_periods": result.n_periods,
        "metrics": {k: (v if v == v else None) for k, v in result.metrics.items()},
        "psr": result.psr if result.psr == result.psr else None,
        "dsr": result.dsr if result.dsr == result.dsr else None,
        "sharpe_ci": {"lower": result.sharpe_ci.lower, "upper": result.sharpe_ci.upper},
        "cagr_ci": {"lower": result.cagr_ci.lower, "upper": result.cagr_ci.upper},
    }
    _artifacts.write_manifest(rdir, manifest)
    book = "long-short" if long_short else "long-only"
    from alpha_validation import render_returns_tearsheet

    render_returns_tearsheet(
        result.returns,
        result.timestamps,
        title=f"ALPHA Cross-Sectional — {', '.join(result.symbols)} ({book}, {result.n_long}/leg)",
        summary_rows=[
            ("OOS Sharpe", f"{result.metrics['sharpe']:.3f}"),
            ("Sharpe 95% CI", f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}]"),
            ("CAGR", f"{result.metrics['cagr']:.3f}"),
            ("Max drawdown", f"{result.metrics['max_drawdown']:.3f}"),
            ("Probabilistic Sharpe", f"{result.psr:.3f}"),
            ("Book", f"{book}, {result.n_long} names/leg"),
            ("Periods", str(result.n_periods)),
        ],
        output_path=rdir / "tearsheet.html",
    )
    typer.echo(
        f"cross-sectional [{', '.join(result.symbols)}] ({book}, {result.n_long}/leg) -> "
        f"run {run_id}: OOS Sharpe {result.metrics['sharpe']:.3f} "
        f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}], "
        f"CAGR {result.metrics['cagr']:.3f}, PSR {result.psr:.3f} "
        f"over {result.n_periods} periods; manifest at {rdir / 'manifest.json'}"
    )
