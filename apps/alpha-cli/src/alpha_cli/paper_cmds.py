"""``alpha paper`` — opt-in Binance public data with local sandbox execution and journaling."""

from __future__ import annotations

import json
import math
import os
import uuid
from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import typer

from alpha_cli import (
    _ibkr_paper,
    _paper,
    _runner,
    _strategies,
    daily_scheduler,
    paper_acceptance,
    paper_readiness,
    paper_store,
)
from alpha_core import DataError
from alpha_core.config import AlphaSettings

paper_app = typer.Typer(
    help="Nautilus paper trading: local crypto sandbox and fail-closed IBKR Paper."
)


@paper_app.command("ibkr-what-if-plan")
def ibkr_what_if_plan(
    limit_price: float = typer.Option(..., min=0.01),
    collar_low: float = typer.Option(..., min=0.01),
    collar_high: float = typer.Option(..., min=0.01),
    expires_at: str = typer.Option(..., help="future ISO-8601 instant with timezone"),
    json_out: bool = typer.Option(False, "--json"),
) -> None:
    """Freeze the exact offline SPY what-if contract; never connects or submits an order."""
    try:
        expiry = _utc_timestamp(expires_at, "expires_at")
        plan = paper_acceptance.create_ibkr_what_if_plan(
            AlphaSettings().data_dir,
            account_id=_required_value(None, "ALPHA_IBKR_PAPER_ACCOUNT"),
            gateway_image=_required_value(None, "ALPHA_IBKR_GATEWAY_IMAGE"),
            limit_price=limit_price,
            collar_low=collar_low,
            collar_high=collar_high,
            expires_at=expiry,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(plan, sort_keys=True, allow_nan=False))
    else:
        typer.echo(
            f"IBKR what-if plan {plan['plan_hash']} frozen for SPY 1-share DAY LIMIT; "
            "whatIf=true, transmit=false. No broker connection was made."
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


def _ibkr_spec(
    *,
    strategy: str,
    param: list[str] | None,
    nav: float,
    lookback: int,
    skip: int,
    vol_window: int,
    target_vol: float,
    rebalance_every: int,
) -> _runner.RunSpec:
    base = _spec(
        strategy=strategy,
        param=param,
        starting_cash=nav,
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        rebalance_every=rebalance_every,
        max_leverage=0.10,
    )
    return replace(
        base,
        allow_short=False,
        periods_per_year=252,
        account_type="CASH",
        max_leverage=0.10,
    )


def _required_value(value: str | None, env_name: str) -> str:
    resolved = os.environ.get(env_name, "") if value is None else value
    if not resolved.strip():
        raise DataError(f"IBKR Paper requires {env_name}")
    return resolved.strip()


def _utc_timestamp(value: str, field: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DataError(f"{field} must include an explicit UTC offset")
    return parsed.astimezone(UTC)


def _decision_parameters(spec: _runner.RunSpec, *, nav: float) -> dict[str, int | float]:
    parameters: dict[str, int | float] = {
        "paper_nav": nav,
        "lookback": spec.lookback,
        "skip": spec.skip,
        "vol_window": spec.vol_window,
        "target_vol": spec.target_vol,
        "rebalance_every": spec.rebalance_every,
    }
    parameters.update(dict(spec.strategy_params))
    return parameters


def _expected_ibkr_position(data_dir: Path, instrument_id: str) -> float:
    """Recover the last journaled position; ambiguity blocks the next broker session."""
    matches = [
        row
        for row in paper_store.list_sessions(data_dir)
        if row["execution_mode"] == "ibkr_paper" and row["instrument_id"] == instrument_id
    ]
    if not matches:
        return 0.0
    latest = matches[0]
    if latest["status"] == "failed" or latest["reconciliation_state"] in {
        "mismatch",
        "halted",
    }:
        raise DataError("latest IBKR paper session requires reconciliation before a new release")
    events = paper_store.read_events(data_dir, str(latest["session_id"]))
    positions = [event for event in events if event["event_type"] == "position"]
    if positions:
        payload = positions[-1]["payload"]
        if not isinstance(payload, Mapping):
            raise DataError("latest IBKR paper position event is invalid")
        value = payload.get("net_units")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DataError("latest IBKR paper position event is invalid")
        return float(value)
    if any(event["event_type"] in {"order", "fill"} for event in events):
        raise DataError("latest IBKR paper order state lacks a final position event")
    return 0.0


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


@paper_app.command("ibkr-preflight")
def ibkr_preflight(
    instrument_id: str,
    asset_class: Literal["stock", "etf", "future"] = typer.Option("stock"),
    account: str | None = typer.Option(None, help="DU paper account; defaults to environment"),
    gateway_image: str | None = typer.Option(
        None, help="approved digest-pinned gateway image; defaults to environment"
    ),
    client_id: int = typer.Option(20, min=0),
) -> None:
    """Construct native IB clients offline in read-only paper mode; never connects or orders."""
    try:
        boundary = _ibkr_paper.IBKRPaperBoundary.create(
            account_id=_required_value(account, "ALPHA_IBKR_PAPER_ACCOUNT"),
            gateway_image=_required_value(gateway_image, "ALPHA_IBKR_GATEWAY_IMAGE"),
            allowed_instruments=(instrument_id,),
            client_id=client_id,
            paper_enabled=False,
            ibkr_paper_enabled=False,
            execution_requested=False,
        )
        approved = boundary.require_instrument(
            instrument_id,
            asset_class=asset_class,
            strategy_generated=asset_class != "future",
        )
        data_config, exec_config = _ibkr_paper.build_ibkr_client_configs(boundary, read_only=True)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    account_alias = f"DU…{boundary.account_id[-4:]}"
    typer.echo(
        f"IBKR Paper preflight OK for {approved} ({asset_class}):\n"
        f"  account: {account_alias} allowlisted\n"
        f"  gateway: loopback:{boundary.port}, paper, read-only, digest pinned\n"
        f"  clients: data={data_config.ibg_client_id}, exec={exec_config.ibg_client_id}\n"
        "  execution remains disabled; order authority requires both ALPHA_PAPER_ENABLED=true "
        "and ALPHA_IBKR_PAPER_ENABLED=true."
    )


@paper_app.command("ibkr-run")
def ibkr_run(
    symbol: str,
    instrument_id: str = typer.Option(..., help="approved Nautilus ID, e.g. SPY.ARCA"),
    snapshot: str = typer.Option(..., help="verified authoritative Tiingo snapshot"),
    expected_session: str = typer.Option(..., help="latest completed exchange session YYYY-MM-DD"),
    next_session: str = typer.Option(..., help="authorized next exchange session YYYY-MM-DD"),
    order_cutoff: str = typer.Option(..., help="fail-closed UTC cutoff, ISO-8601 with timezone"),
    intent: str | None = typer.Option(None, help="approved immutable scheduler intent SHA-256"),
    account: str | None = typer.Option(None, help="DU paper account; defaults to environment"),
    gateway_image: str | None = typer.Option(
        None, help="approved digest-pinned gateway image; defaults to environment"
    ),
    strategy: str = typer.Option("ts_momentum"),
    param: list[str] | None = None,
    nav: float = typer.Option(..., min=0.01, help="reconciled paper NAV used for hard limits"),
    lookback: int = typer.Option(252, min=1),
    skip: int = typer.Option(21, min=0),
    vol_window: int = typer.Option(63, min=2),
    target_vol: float = typer.Option(0.15, min=0.000001),
    rebalance_every: int = typer.Option(21, min=1),
    client_id: int = typer.Option(20, min=0),
) -> None:
    """Run one long-only stock/ETF decision cycle through native IBKR Paper execution."""
    settings = AlphaSettings()
    try:
        completed = date.fromisoformat(expected_session)
        authorized = date.fromisoformat(next_session)
        if completed.isoformat() != expected_session or authorized.isoformat() != next_session:
            raise ValueError
        if authorized <= completed:
            raise DataError("next_session must follow expected_session")
        cutoff = _utc_timestamp(order_cutoff, "order_cutoff")
        if cutoff.date() != authorized or cutoff <= datetime.now(UTC):
            raise DataError(
                "order_cutoff must be a future UTC instant on the authorized next_session"
            )
        boundary = _ibkr_paper.IBKRPaperBoundary.create(
            account_id=_required_value(account, "ALPHA_IBKR_PAPER_ACCOUNT"),
            gateway_image=_required_value(gateway_image, "ALPHA_IBKR_GATEWAY_IMAGE"),
            allowed_instruments=(instrument_id,),
            client_id=client_id,
            paper_enabled=settings.paper_enabled,
            ibkr_paper_enabled=settings.ibkr_paper_enabled,
            execution_requested=True,
        )
        boundary.require_instrument(instrument_id, asset_class="stock", strategy_generated=True)
        spec = _ibkr_spec(
            strategy=strategy,
            param=param,
            nav=nav,
            lookback=lookback,
            skip=skip,
            vol_window=vol_window,
            target_vol=target_vol,
            rebalance_every=rebalance_every,
        )
        warmup = _ibkr_paper.load_ibkr_warmup(
            settings.data_dir,
            snapshot,
            symbol,
            spec,
            expected_session=completed,
        )
        if intent is None:
            raise DataError("IBKR Paper execution requires --intent from the daily scheduler")
        approved_intent = _ibkr_paper.load_order_intent(settings.data_dir, intent)
        approved_intent.require_releasable(datetime.now(UTC))
        from alpha_cli._identity import strategy_fingerprint

        expected_version = strategy_fingerprint(spec.strategy_name)
        if (
            approved_intent.strategy != spec.strategy_name
            or approved_intent.strategy_version != expected_version
            or dict(approved_intent.parameters) != _decision_parameters(spec, nav=nav)
            or approved_intent.snapshot_id != snapshot
            or approved_intent.snapshot_sha256 != warmup.snapshot_sha256
            or approved_intent.instrument_id != instrument_id.strip().upper()
            or approved_intent.next_session != authorized.isoformat()
            or approved_intent.expires_at != cutoff
            or approved_intent.risk_profile != _ibkr_paper.EQUITY_RISK_PROFILE
        ):
            raise DataError("IBKR release arguments do not match the immutable approved intent")
        expected_position_units = _expected_ibkr_position(
            settings.data_dir, instrument_id.strip().upper()
        )
    except ValueError as exc:
        raise typer.BadParameter(
            "session dates and order cutoff must be canonical ISO values"
        ) from exc
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    session_id = str(uuid.uuid4())
    try:
        _ibkr_paper.claim_order_intent_release(
            settings.data_dir, approved_intent.intent_id, session_id
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    paper_store.create_session(
        settings.data_dir,
        provider="ibkr",
        symbol=symbol.strip().upper(),
        instrument_id=instrument_id.strip().upper(),
        strategy=strategy,
        strategy_params=_session_params(spec),
        snapshot_id=snapshot,
        pid=os.getpid(),
        execution_mode="ibkr_paper",
        account_alias=f"DU…{boundary.account_id[-4:]}",
        risk_profile_id=_ibkr_paper.EQUITY_RISK_PROFILE.id,
        decision_artifact_id=approved_intent.intent_id,
        session_id=session_id,
    )
    sink = paper_store.PaperEventSink(settings.data_dir, session_id)
    typer.echo(f"-> session {session_id}: IBKR PAPER {symbol.upper()} (live capital unavailable)")
    try:
        sink.emit("lifecycle", {"status": "starting", "sandbox": False, "paper": True})
        paper_store.set_session_status(settings.data_dir, session_id, "running", pid=os.getpid())
        completed_run = _ibkr_paper.run_ibkr_paper(
            spec,
            boundary=boundary,
            symbol=symbol.strip().upper(),
            instrument_id=instrument_id.strip().upper(),
            warmup=warmup,
            order_intent=approved_intent,
            order_cutoff=cutoff,
            expected_position_units=expected_position_units,
            event_sink=sink,
            trader_id=f"IBP-{session_id[:8].upper()}",
            heartbeat=lambda: paper_store.heartbeat_session(settings.data_dir, session_id),
            stop_requested=lambda: paper_store.safe_stop_requested(settings.data_dir, session_id),
        )
        terminal: Literal["completed", "cancelled"] = "completed" if completed_run else "cancelled"
        sink.emit("lifecycle", {"status": terminal, "sandbox": False, "paper": True})
        paper_store.finish_session(settings.data_dir, session_id, status=terminal)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        try:
            sink.emit("lifecycle", {"status": "failed", "error": error, "paper": True})
            paper_store.finish_session(
                settings.data_dir, session_id, status="failed", terminal_error=error
            )
        except Exception as journal_exc:
            typer.echo(f"IBKR paper journal terminal update failed: {journal_exc}", err=True)
        typer.echo(f"IBKR paper session failed: {error}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"IBKR paper session {session_id} {terminal}")


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
        mode = "SANDBOX" if row["execution_mode"] == "local_sandbox" else "IBKR_PAPER"
        typer.echo(
            f"{row['session_id']} {row['status']}{stale} {row['symbol']} {row['strategy']} {mode}"
        )


@paper_app.command("stop")
def stop(session_id: str) -> None:
    """Request safe cooperative stop: cancel ALPHA orders, never flatten positions."""
    try:
        row = paper_store.request_safe_stop(AlphaSettings().data_dir, session_id)
    except (DataError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(
        f"safe stop requested for {session_id}: status={row['status']}; "
        "open DAY orders will be cancelled, positions will not be flattened"
    )


@paper_app.command("reconcile")
def reconcile(session_id: str, json_out: bool = typer.Option(False, "--json")) -> None:
    """Report the machine-derived reconciliation state; this command cannot approve it."""
    try:
        row = paper_store.read_session(AlphaSettings().data_dir, session_id)
        events = paper_store.read_events(AlphaSettings().data_dir, session_id)
    except (DataError, FileNotFoundError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    reconciliation_events = [event for event in events if event["event_type"] == "reconciliation"]
    report = {
        "session_id": session_id,
        "execution_mode": row["execution_mode"],
        "reconciliation_state": row["reconciliation_state"],
        "machine_events": reconciliation_events,
        "operator_approval_supported": False,
    }
    if json_out:
        typer.echo(json.dumps(report, sort_keys=True, allow_nan=False))
    else:
        typer.echo(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


@paper_app.command("readiness")
def readiness(json_out: bool = typer.Option(False, "--json")) -> None:
    """Generate the evidence-only paper acceptance report; elapsed time never passes it."""
    try:
        report = paper_readiness.readiness_report(AlphaSettings().data_dir)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if json_out:
        typer.echo(json.dumps(report, sort_keys=True, allow_nan=False))
    else:
        typer.echo(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


@paper_app.command("scheduler-tick")
def scheduler_tick(
    config: Path = typer.Option(..., exists=True, dir_okay=False),  # noqa: B008
) -> None:
    """Run one short wake-safe daily scheduler tick (intended for launchd every five minutes)."""
    try:
        rows = daily_scheduler.scheduler_tick(config, AlphaSettings().data_dir)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps({"executed": rows}, sort_keys=True, allow_nan=False))


@paper_app.command("scheduler-status")
def scheduler_status(
    config: Path = typer.Option(..., exists=True, dir_okay=False),  # noqa: B008
) -> None:
    """Inspect due/completed/interrupted daily work without contacting providers."""
    try:
        rows = daily_scheduler.scheduler_status(config, AlphaSettings().data_dir)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(rows, indent=2, sort_keys=True, allow_nan=False))


@paper_app.command("scheduler-repair")
def scheduler_repair(
    symbol: str,
    session: str,
    config: Path = typer.Option(..., exists=True, dir_okay=False),  # noqa: B008
    acknowledge: bool = typer.Option(False, "--acknowledge"),
) -> None:
    """Clear one known crash marker; immutable outcomes and canonical promotions are untouched."""
    try:
        session_date = date.fromisoformat(session)
        item = next(
            (
                candidate
                for candidate in daily_scheduler.load_schedule(config)
                if candidate.symbol == symbol.strip().upper()
            ),
            None,
        )
        if item is None:
            raise DataError(f"symbol {symbol!r} is not configured")
        daily_scheduler.repair_interrupted_cycle(
            AlphaSettings().data_dir,
            item,
            session_date,
            acknowledge=acknowledge,
        )
    except (DataError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"cleared interrupted daily cycle marker for {item.symbol} {session_date}")


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
