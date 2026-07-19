"""``alpha paper`` — opt-in Binance public data with local sandbox execution and journaling."""

from __future__ import annotations

import json
import math
import os
from typing import Literal

import typer

from alpha_cli import _paper, _runner, _strategies, paper_store
from alpha_core import DataError
from alpha_core.config import AlphaSettings

paper_app = typer.Typer(
    help="Crypto paper trading: public Binance data, local Nautilus sandbox orders only."
)


def _spec(
    *,
    strategy: str,
    param: list[str] | None,
    starting_cash: float,
    lookback: int,
    skip: int,
    vol_window: int,
    target_vol: float,
    rebalance_every: int,
    max_leverage: float,
) -> _runner.RunSpec:
    finite_positive = {
        "starting_cash": starting_cash,
        "target_vol": target_vol,
        "max_leverage": max_leverage,
    }
    for name, value in finite_positive.items():
        if not math.isfinite(value) or value <= 0.0:
            raise DataError(f"{name} must be finite and > 0, got {value!r}")
    if lookback < 1:
        raise DataError(f"lookback must be >= 1, got {lookback}")
    if skip < 0:
        raise DataError(f"skip must be >= 0, got {skip}")
    if vol_window < 2:
        raise DataError(f"vol_window must be >= 2, got {vol_window}")
    if rebalance_every < 1:
        raise DataError(f"rebalance_every must be >= 1, got {rebalance_every}")
    if strategy not in _strategies.known_strategies():
        raise DataError(f"unknown strategy {strategy!r}; known: {_strategies.known_strategies()}")
    if not _strategies.STRATEGIES[strategy].supports_live_paper:
        raise DataError(f"strategy {strategy!r} does not support live paper execution")
    return _runner.RunSpec(
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        rebalance_every=rebalance_every,
        max_leverage=max_leverage,
        allow_short=True,
        periods_per_year=365,
        fee_bps=0.0,
        slippage_bps=0.0,
        starting_cash=starting_cash,
        account_type="MARGIN",
        train_size=max(504, lookback + skip + 1, vol_window + 1),
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(strategy, param),
    )


def _session_params(spec: _runner.RunSpec) -> dict[str, int | float | bool | None]:
    params: dict[str, int | float | bool | None] = {
        "lookback": spec.lookback,
        "skip": spec.skip,
        "vol_window": spec.vol_window,
        "target_vol": spec.target_vol,
        "rebalance_every": spec.rebalance_every,
        "max_leverage": spec.max_leverage,
        "allow_short": spec.allow_short,
    }
    params.update(dict(spec.strategy_params))
    return params


@paper_app.command()
def preflight(
    symbol: str,
    strategy: str = "ts_momentum",
    starting_cash: float = 100_000.0,
    param: list[str] | None = None,
) -> None:
    """Construct the Binance-data/sandbox-execution wiring offline without connecting."""
    try:
        spec = _spec(
            strategy=strategy,
            param=param,
            starting_cash=starting_cash,
            lookback=252,
            skip=21,
            vol_window=63,
            target_vol=0.15,
            rebalance_every=21,
            max_leverage=1.0,
        )
        instrument_id = _paper.binance_instrument_id(symbol)
        data_config = _paper.build_binance_data_config(symbol)
        exec_config = _paper.build_sandbox_exec_config(
            venue="BINANCE",
            account_type="MARGIN",
            starting_cash=starting_cash,
            currency="USDT",
        )
        node_config = _paper.build_paper_node_config(
            trader_id="PAPER-001",
            exec_config=exec_config,
            data_clients={"BINANCE": data_config},
        )
        from alpha_backtest.feed import daily_bar_type

        strat = _strategies.build_strategy(
            spec,
            instrument_id,
            daily_bar_type(str(instrument_id.symbol), venue="BINANCE"),
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"paper preflight OK for {symbol.upper()} [{strategy}]:\n"
        "  market data: public Binance LIVE data (no credentials)\n"
        f"  execution: local SANDBOX execution on {exec_config.venue} "
        f"({starting_cash:.0f} USDT, bar_execution=False)\n"
        f"  node: trader_id={node_config.trader_id}, "
        f"data_clients={list(node_config.data_clients)}, "
        f"exec_clients={list(node_config.exec_clients)}\n"
        f"  strategy: {type(strat).__name__} constructed (same class as backtest)\n"
        "  run requires ALPHA_PAPER_ENABLED=true and a verified same-symbol ccxt:binance snapshot."
    )


@paper_app.command("run")
def run_session(
    symbol: str,
    provider: str = typer.Option("binance", help="live market-data provider (binance only)"),
    snapshot: str = typer.Option(..., help="verified ccxt:binance warmup snapshot id"),
    strategy: str = typer.Option("ts_momentum", help="registered live-paper strategy"),
    param: list[str] | None = None,
    starting_cash: float = typer.Option(100_000.0, min=0.01),
    lookback: int = typer.Option(252, min=1),
    skip: int = typer.Option(21, min=0),
    vol_window: int = typer.Option(63, min=2),
    target_vol: float = typer.Option(0.15, min=0.000001),
    rebalance_every: int = typer.Option(21, min=1),
    max_leverage: float = typer.Option(1.0, min=0.000001),
) -> None:
    """Run ``BASE/USDT`` on Binance public data with local sandbox fills only."""
    settings = AlphaSettings()
    if not settings.paper_enabled:
        raise typer.BadParameter(
            "paper trading is disabled; set ALPHA_PAPER_ENABLED=true for this process"
        )
    if provider != "binance":
        raise typer.BadParameter("--provider must be 'binance' (the only approved live-data path)")
    canonical = symbol.strip().upper()
    try:
        spec = _spec(
            strategy=strategy,
            param=param,
            starting_cash=starting_cash,
            lookback=lookback,
            skip=skip,
            vol_window=vol_window,
            target_vol=target_vol,
            rebalance_every=rebalance_every,
            max_leverage=max_leverage,
        )
        instrument_id = _paper.binance_instrument_id(canonical)
        warmup = _paper.load_paper_warmup(
            settings.data_dir,
            snapshot,
            canonical,
            spec,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    session = paper_store.create_session(
        settings.data_dir,
        provider="binance",
        symbol=canonical,
        instrument_id=str(instrument_id),
        strategy=strategy,
        strategy_params=_session_params(spec),
        snapshot_id=snapshot,
        pid=os.getpid(),
    )
    session_id = str(session["session_id"])
    sink = paper_store.PaperEventSink(settings.data_dir, session_id)
    typer.echo(f"-> session {session_id}: SANDBOX {canonical} via Binance public data")

    try:
        sink.emit("lifecycle", {"status": "starting", "sandbox": True})
        paper_store.set_session_status(settings.data_dir, session_id, "running", pid=os.getpid())
        completed = _paper.run_paper(
            spec,
            symbol=canonical,
            warmup_bars=warmup,
            event_sink=sink,
            trader_id=f"PAPER-{session_id[:8].upper()}",
            heartbeat=lambda: paper_store.heartbeat_session(settings.data_dir, session_id),
        )
        terminal: Literal["completed", "cancelled"] = "completed" if completed else "cancelled"
        sink.emit("lifecycle", {"status": terminal, "sandbox": True})
        paper_store.finish_session(settings.data_dir, session_id, status=terminal)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        try:
            sink.emit("lifecycle", {"status": "failed", "error": error, "sandbox": True})
            paper_store.finish_session(
                settings.data_dir,
                session_id,
                status="failed",
                terminal_error=error,
            )
        except Exception as journal_exc:
            typer.echo(f"paper journal terminal update failed: {journal_exc}", err=True)
        typer.echo(f"paper session failed: {error}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"paper session {session_id} {terminal}")


@paper_app.command("sessions")
def sessions(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List durable operational paper sessions, newest first."""
    try:
        rows = paper_store.list_sessions(AlphaSettings().data_dir)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(rows, sort_keys=True, allow_nan=False))
        return
    if not rows:
        typer.echo("no paper sessions")
        return
    for row in rows:
        stale = " STALE" if row["stale"] else ""
        typer.echo(
            f"{row['session_id']} {row['status']}{stale} {row['symbol']} {row['strategy']} SANDBOX"
        )


@paper_app.command("show")
def show(
    session_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Show one durable paper session (never signals its recorded PID)."""
    try:
        row = paper_store.read_session(AlphaSettings().data_dir, session_id)
    except (DataError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(row, sort_keys=True, allow_nan=False))
        return
    typer.echo(json.dumps(row, indent=2, sort_keys=True, allow_nan=False))
