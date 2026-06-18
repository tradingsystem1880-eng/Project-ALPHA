"""``alpha paper``: run a paper-trading session through the sandbox and inspect its artifacts.

``run`` replays a symbol's stored history through the *same* live ``TradingNode`` + sandbox exec
client as a dry-run of the paper pipeline (a real-time websocket feed is a later increment), writing
a session under ``data_dir/paper/<session_id>/``. ``status`` lists sessions; ``report`` prints a
stored session's headline metrics (computed here, at the validation edge, from the equity curve).

Engine/node imports are lazy so importing this module stays cheap and network-free.
"""

from __future__ import annotations

import asyncio
from typing import Any

import typer

from alpha_cli import _runner
from alpha_core.config import AlphaSettings

paper_app = typer.Typer(help="Paper-trade the v1 strategy through the nautilus sandbox.")

# monkeypatchable bar-load seam (mirrors backtest_cmds); tests point it at a fixture store
_load_bars = _runner.load_bars


@paper_app.command()
def run(
    symbol: str,
    asset_class: str = "equity",
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
    account_type: str = "MARGIN",
    exchange: str = "coinbase",
    max_notional: float | None = None,
    feed_interval: float = 0.02,
    snapshot: str | None = None,
) -> None:
    """Replay SYMBOL's stored history through the paper sandbox; write the session artifacts."""
    from alpha_backtest.feed import daily_bar_type, to_execution_feed
    from alpha_execution import crypto_instrument, equity_instrument
    from alpha_paper.config import PaperSpec
    from alpha_paper.session import run_paper_session
    from alpha_strategies.ts_momentum import TimeSeriesMomentum

    settings = AlphaSettings()
    instrument = crypto_instrument(symbol) if asset_class == "crypto" else equity_instrument(symbol)
    bar_type = daily_bar_type(str(instrument.id.symbol), str(instrument.id.venue))
    periods_per_year = 365 if asset_class == "crypto" else 252

    spec = PaperSpec(
        symbol=symbol,
        exchange=exchange,
        venue=str(instrument.id.venue),
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        rebalance_every=rebalance_every,
        max_leverage=max_leverage,
        allow_short=allow_short,
        periods_per_year=periods_per_year,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        starting_cash=starting_cash,
        account_type=account_type,
        max_notional_per_order=max_notional,
    )
    bars, _ = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
    feed = to_execution_feed(
        bars, bar_type, size_precision=instrument.size_precision, slippage_bps=slippage_bps
    )
    strategy = TimeSeriesMomentum(
        instrument_id=instrument.id,
        bar_type=bar_type,
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        capital=starting_cash,
        max_leverage=max_leverage,
        rebalance_every=rebalance_every,
        periods_per_year=periods_per_year,
        allow_short=allow_short,
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = run_paper_session(
            spec,
            instrument,
            feed,
            strategy,
            data_dir=settings.data_dir,
            loop=loop,
            feed_interval=feed_interval,
        )
    finally:
        asyncio.set_event_loop(None)
    typer.echo(
        f"paper {symbol} -> session {result.session_id}: {result.n_orders} orders, "
        f"{result.n_fills} fills, final equity {result.final_equity:.2f}"
    )


@paper_app.command()
def status() -> None:
    """List paper sessions under ``data_dir/paper`` with their headline equity."""
    from alpha_paper.artifacts import read_session

    settings = AlphaSettings()
    root = settings.data_dir / "paper"
    sessions = sorted(p for p in root.glob("*/session.json")) if root.exists() else []
    if not sessions:
        typer.echo(f"no paper sessions under {root}")
        return
    for path in sessions:
        s = read_session(path.parent)
        typer.echo(
            f"{s.get('session_id', path.parent.name)}  symbol={s.get('symbol', '?')}  "
            f"orders={s.get('n_orders', '?')}  "
            f"final_equity={s.get('final_equity', float('nan')):.2f}"
        )


@paper_app.command()
def report(session_id: str) -> None:
    """Print a stored paper session's headline metrics (computed from its equity curve)."""
    import polars as pl

    from alpha_paper.artifacts import read_session, session_dir
    from alpha_validation.metrics import cagr, max_drawdown, sharpe_ratio, to_returns

    settings = AlphaSettings()
    sdir = session_dir(settings.data_dir, session_id)
    if not (sdir / "session.json").exists():
        raise typer.BadParameter(f"no session {session_id!r} under {settings.data_dir / 'paper'}")
    s = read_session(sdir)
    ppy = int(s.get("params", {}).get("periods_per_year", 252))
    typer.echo(
        f"session {session_id}  symbol={s.get('symbol', '?')}  "
        f"orders={s.get('n_orders', '?')}  fills={s.get('n_fills', '?')}"
    )

    equity = pl.read_parquet(sdir / "equity_curve.parquet")["equity"].to_numpy()
    if equity.size >= 2:
        returns = to_returns(equity)
        metrics: dict[str, Any] = {
            "total_return": float(equity[-1] / equity[0] - 1.0),
            "sharpe": sharpe_ratio(returns, periods_per_year=ppy) if returns.size >= 2 else None,
            "cagr": cagr(equity, periods_per_year=ppy),
            "max_drawdown": max_drawdown(equity),
        }
        rendered = ", ".join(f"{k}={v:.4f}" for k, v in metrics.items() if isinstance(v, float))
        typer.echo(f"metrics: {rendered}")
    else:
        typer.echo("metrics: n/a (no equity curve recorded)")
