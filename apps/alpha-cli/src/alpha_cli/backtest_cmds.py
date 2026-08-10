"""``alpha backtest run``: run the v1 strategy once and persist the trade log + equity curve.

Satisfies spec §11.1. Shares ``_runner.run_full_backtest`` (and the ``RunSpec``) with the
validation gauntlet, so both drive the engine through one code path.
"""

from __future__ import annotations

import re
from datetime import date

import numpy as np
import typer

from alpha_cli import _artifacts, _forecast_cache, _runner
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_validation import annualized_volatility, cagr, max_drawdown, sharpe_ratio

backtest_app = typer.Typer(help="Run the v1 strategy through the backtest engine.")

# monkeypatchable load seams (mirror data_cmds._ADAPTERS); tests point them at fixture stores
_load_bars = _runner.load_bars
_load_dividends = _runner.load_dividends

# Suite-injected when a governed project's research gate was owner-overridden (spec §15,
# ADR-0026). Safe on the public CLI: it only ever downgrades the run's presentation (adds the
# EXPLORATORY watermark and forks run identity), never upgrades or grants authority.
_RESEARCH_GATE_OVERRIDE_HELP = (
    "watermark this run EXPLORATORY / RESEARCH GATE NOT COMPLETED "
    "(launched under an owner research-gate override)"
)


def _holdout_date(value: str, label: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise DataError(f"{label} must be canonical YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise DataError(f"{label} must be canonical YYYY-MM-DD")
    return parsed


@backtest_app.command()
def holdout(
    symbol: str,
    strategy: str = "ts_momentum",
    lookback: int = 252,
    skip: int = 21,
    vol_window: int = 63,
    target_vol: float = 0.15,
    rebalance_every: int = 21,
    max_leverage: float = 1.0,
    allow_short: bool | None = None,
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    starting_cash: float = 1_000_000.0,
    account_type: str = "CASH",
    periods_per_year: int = 252,
    param: list[str] | None = None,
    snapshot: str = typer.Option(..., help="frozen market-data snapshot"),
    holdout_start: str = typer.Option(..., help="revealed inclusive YYYY-MM-DD boundary"),
    holdout_end: str = typer.Option(..., help="revealed inclusive YYYY-MM-DD boundary"),
    holdout_spec_hash: str = typer.Option(..., help="sealed holdout specification SHA-256"),
    min_sharpe: float = typer.Option(0.0, help="predeclared pass threshold"),
    research_gate_override: bool = typer.Option(
        False, "--research-gate-override", help=_RESEARCH_GATE_OVERRIDE_HELP
    ),
) -> None:
    """Evaluate one frozen fixed-parameter candidate on its revealed final holdout once."""
    settings = AlphaSettings()
    try:
        start = _holdout_date(holdout_start, "holdout_start")
        end = _holdout_date(holdout_end, "holdout_end")
        if start > end:
            raise DataError("holdout_start must not follow holdout_end")
        if re.fullmatch(r"[0-9a-f]{64}", holdout_spec_hash) is None:
            raise DataError("holdout_spec_hash must be a 64-hex SHA-256 digest")
        if not np.isfinite(min_sharpe):
            raise DataError("min_sharpe must be finite")
        spec = _runner.RunSpec(
            lookback=lookback,
            skip=skip,
            vol_window=vol_window,
            target_vol=target_vol,
            rebalance_every=rebalance_every,
            max_leverage=max_leverage,
            allow_short=_runner.resolve_allow_short(allow_short, account_type),
            periods_per_year=periods_per_year,
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            starting_cash=starting_cash,
            account_type=account_type,
            train_size=504,
            test_size=63,
            embargo=5,
            anchored=False,
            strategy_name=strategy,
            strategy_params=_runner.parse_strategy_params(strategy, param),
        )
        holdout_cutoff = _runner.parse_as_of(holdout_end)
        bars, snapshot_id = _load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=holdout_cutoff,
        )
        if len(bars) < 2:
            raise DataError("holdout end leaves fewer than two causal bars")
        dividends = [
            action
            for action in _load_dividends(
                symbol,
                data_dir=settings.data_dir,
                snapshot_id=snapshot,
                as_of=holdout_cutoff,
            )
            if action.knowledge_time <= end and (action.pay_date or action.ex_date) <= end
        ]
        spec, forecast_meta = _forecast_cache.prepare_spec_for_engine(
            bars, spec, data_dir=settings.data_dir, seed=settings.random_seed
        )
        first_index = next(
            (index for index, bar in enumerate(bars) if bar.ts.date() >= start),
            None,
        )
        if first_index is None or first_index == 0:
            raise DataError("revealed holdout requires at least one prior causal decision bar")
        final_index = len(bars) - 1
        scoped = _runner.fresh_scored_execution(
            bars,
            spec,
            first_scored_index=first_index,
            final_scored_index=final_index,
            dividends=dividends,
            normalize_equity=False,
        )
        equity = scoped.equity_curve
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    values = np.asarray([value for _, value in equity], dtype=np.float64)
    normalized = values / values[0]
    returns = normalized[1:] / normalized[:-1] - 1.0
    volatility = annualized_volatility(returns, periods_per_year=periods_per_year)
    sharpe = (
        sharpe_ratio(returns, periods_per_year=periods_per_year)
        if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0
        else None
    )
    passed = sharpe is not None and sharpe >= min_sharpe

    scoped_trades = scoped.trades
    identity = _runner.run_identity_for(
        {
            "command": "backtest_holdout",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "holdout_start": holdout_start,
            "holdout_end": holdout_end,
            "holdout_spec_hash": holdout_spec_hash,
            "min_sharpe": min_sharpe,
            **_artifacts.research_gate_override_identity(research_gate_override),
            **vars(spec),
        },
        source_fingerprint=_runner.source_fingerprint(bars, dividends=dividends),
        snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot_id),
    )
    run_id = identity.run_id
    manifest = _artifacts.sanitize(
        {
            "schema_version": 1,
            "run_id": run_id,
            "command": "backtest_holdout",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "params": vars(spec),
            "holdout_start": holdout_start,
            "holdout_end": holdout_end,
            "holdout_spec_hash": holdout_spec_hash,
            "holdout_policy": "fixed_candidate_one_shot_after_owner_reveal",
            "warmup_history_included": True,
            "holdout_execution_boundary": "fresh_portfolio_after_causal_indicator_priming",
            "holdout_trace_scope": (
                "scored_holdout_sessions_plus_originating_prior_close_decision"
            ),
            "min_sharpe": min_sharpe,
            "passed": passed,
            "metrics": {
                "total_return": float(normalized[-1] - 1.0),
                "cagr": cagr(normalized, periods_per_year=periods_per_year),
                "annual_volatility": volatility,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown(normalized),
            },
            "n_scored_sessions": len(equity),
            "n_trades": len(scoped_trades),
            **_artifacts.research_gate_override_fields(research_gate_override),
            **identity.manifest_fields(),
        }
    )
    if forecast_meta is not None:
        manifest["forecast"] = forecast_meta
    rdir = _artifacts.run_dir(settings.data_dir, run_id)
    _artifacts.write_run(
        rdir,
        manifest=manifest,
        equity=equity,
        trades=scoped_trades,
        trace_result=scoped,
        periods_per_year=periods_per_year,
    )
    verdict = "PASS" if passed else "FAIL"
    typer.echo(
        f"locked holdout {symbol} -> run {run_id}: {verdict}, "
        f"Sharpe {sharpe if sharpe is not None else 'unavailable'} over {len(equity)} sessions"
    )


@backtest_app.command()
def oos(
    symbol: str,
    strategy: str = "ts_momentum",
    lookback: int = 252,
    skip: int = 21,
    vol_window: int = 63,
    target_vol: float = 0.15,
    rebalance_every: int = 21,
    max_leverage: float = 1.0,
    allow_short: bool | None = None,
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    starting_cash: float = 1_000_000.0,
    account_type: str = "CASH",
    periods_per_year: int = 252,
    train_size: int = 504,
    test_size: int = 63,
    embargo: int = 5,
    anchored: bool = False,
    param: list[str] | None = None,
    snapshot: str | None = None,
    as_of: str | None = typer.Option(None, "--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    research_gate_override: bool = typer.Option(
        False, "--research-gate-override", help=_RESEARCH_GATE_OVERRIDE_HELP
    ),
) -> None:
    """Evaluate one fixed rule over causal walk-forward OOS windows; no model is refit."""
    settings = AlphaSettings()
    spec = _runner.RunSpec(
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        rebalance_every=rebalance_every,
        max_leverage=max_leverage,
        allow_short=_runner.resolve_allow_short(allow_short, account_type),
        periods_per_year=periods_per_year,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        starting_cash=starting_cash,
        account_type=account_type,
        train_size=train_size,
        test_size=test_size,
        embargo=embargo,
        anchored=anchored,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(strategy, param),
    )
    try:
        research_cutoff = _runner.parse_as_of(as_of)
        bars, snapshot_id = _load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=research_cutoff,
        )
        dividends = _load_dividends(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=research_cutoff,
        )
        spec, forecast_meta = _forecast_cache.prepare_spec_for_engine(
            bars, spec, data_dir=settings.data_dir, seed=settings.random_seed
        )
        oos_result, scoped = _runner.fresh_oos_execution(bars, spec, dividends=dividends)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    identity = _runner.run_identity_for(
        {
            "command": "backtest_oos",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "research_cutoff": as_of,
            **_artifacts.research_gate_override_identity(research_gate_override),
            **vars(spec),
        },
        source_fingerprint=_runner.source_fingerprint(bars, dividends=dividends),
        snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot_id),
    )
    run_id = identity.run_id
    equity = scoped.equity_curve
    equity_values = np.asarray([value for _, value in equity], dtype=np.float64)
    returns = oos_result.oos_returns
    folds = oos_result.folds
    volatility = annualized_volatility(returns, periods_per_year=periods_per_year)
    sharpe = (
        sharpe_ratio(returns, periods_per_year=periods_per_year)
        if returns.size >= 2 and float(np.std(returns, ddof=1)) > 0.0
        else None
    )
    manifest = _artifacts.sanitize(
        {
            "schema_version": 1,
            "run_id": run_id,
            "command": "backtest_oos",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "research_cutoff": as_of,
            "params": vars(spec),
            "oos_semantics": "fixed_rule_evaluation_no_refit",
            "folds": [_runner.fold_manifest(fold, bars) for fold in folds],
            "oos_execution_boundary": "fresh_portfolio_after_causal_indicator_priming",
            "oos_trace_scope": "scored_test_sessions_plus_originating_prior_close_decision",
            "oos_metrics": {
                "total_return": float(equity_values[-1] - 1.0),
                "cagr": cagr(equity_values, periods_per_year=periods_per_year),
                "annual_volatility": volatility,
                "sharpe": sharpe,
                "max_drawdown": max_drawdown(equity_values),
            },
            **_artifacts.research_gate_override_fields(research_gate_override),
            **identity.manifest_fields(),
        }
    )
    if forecast_meta is not None:
        manifest["forecast"] = forecast_meta
    rdir = _artifacts.run_dir(settings.data_dir, run_id)
    _artifacts.write_run_sidecars(
        rdir,
        equity=equity,
        trades=scoped.trades,
        trace_result=scoped,
        periods_per_year=periods_per_year,
    )
    _artifacts.write_manifest(rdir, manifest)
    typer.echo(
        f"rule OOS {symbol} (fixed parameters, no refit) -> run {run_id}: "
        f"{len(folds)} folds, {returns.size} scored sessions"
    )


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
    allow_short: bool | None = None,  # default: MARGIN->True, CASH->False
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    starting_cash: float = 1_000_000.0,
    account_type: str = "CASH",
    periods_per_year: int = 252,
    size_on_equity: bool = False,
    halt_drawdown: float | None = None,
    param: list[str] | None = None,
    snapshot: str | None = None,
    as_of: str | None = typer.Option(None, "--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    research_gate_override: bool = typer.Option(
        False, "--research-gate-override", help=_RESEARCH_GATE_OVERRIDE_HELP
    ),
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
        allow_short=_runner.resolve_allow_short(allow_short, account_type),
        periods_per_year=periods_per_year,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        starting_cash=starting_cash,
        account_type=account_type,
        train_size=504,  # walk-forward fields are unused by a plain backtest; kept coherent
        test_size=63,
        embargo=5,
        anchored=False,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(strategy, param),
        size_on_equity=size_on_equity,
        halt_drawdown=halt_drawdown,
    )
    try:
        research_cutoff = _runner.parse_as_of(as_of)
        bars, snapshot_id = _load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=research_cutoff,
        )
        dividends = _load_dividends(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=research_cutoff,
        )
        # kronos: precompute the signal cache (slow model, runs once) and pin its key on the
        # spec; every other strategy passes through untouched.
        spec, forecast_meta = _forecast_cache.prepare_spec_for_engine(
            bars, spec, data_dir=settings.data_dir, seed=settings.random_seed
        )
        result = _runner.run_full_backtest(bars, spec, dividends=dividends)
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
    identity = _runner.run_identity_for(
        {
            "command": "backtest_run",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "research_cutoff": as_of,
            **_artifacts.research_gate_override_identity(research_gate_override),
            **vars(spec),
        },
        source_fingerprint=_runner.source_fingerprint(bars, dividends=dividends),
        snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot_id),
    )
    run_id = identity.run_id
    rdir = _artifacts.run_dir(settings.data_dir, run_id)
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "backtest_run",
        "symbol": symbol,
        "snapshot_id": snapshot_id,
        "research_cutoff": as_of,
        "params": vars(spec),
        "orders": result.orders,
        "fills": result.fills,
        "rejected": result.rejected,
        "n_trades": len(result.trades),
        "starting_equity": result.starting_equity,
        "final_equity": result.final_equity,
        **_artifacts.research_gate_override_fields(research_gate_override),
        **identity.manifest_fields(),
    }
    if forecast_meta is not None:
        manifest["forecast"] = forecast_meta
    _artifacts.write_run(
        rdir,
        manifest=manifest,
        equity=result.equity_curve,
        trades=result.trades,
        trace_result=result,
        periods_per_year=spec.periods_per_year,
    )
    warn = f" ({result.rejected} orders rejected)" if result.rejected else ""
    typer.echo(
        f"backtest {symbol} -> run {run_id}: {result.orders} orders, {result.fills} fills, "
        f"{len(result.trades)} trades, final equity {result.final_equity:.2f}{warn}"
    )
    if forecast_meta is not None and forecast_meta["pretrain"]["overlap"]:
        typer.secho(
            "WARNING: the forecast windows overlap the assumed Kronos pretraining period "
            f"(<= {forecast_meta['pretrain']['cutoff']}) — backtest may reflect memorization "
            "(ADR-0009)",
            fg=typer.colors.YELLOW,
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
    allow_short: bool | None = None,  # default: MARGIN->True, CASH->False
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    starting_cash: float = 1_000_000.0,
    account_type: str = "CASH",
    periods_per_year: int = 252,
    size_on_equity: bool = False,
    halt_drawdown: float | None = None,
    train_size: int = 504,
    test_size: int = 63,
    embargo: int = 5,
    anchored: bool = False,
    seed: int | None = None,
    param: list[str] | None = None,
    snapshot: str | None = None,
    as_of: str | None = typer.Option(None, "--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    research_gate_override: bool = typer.Option(
        False, "--research-gate-override", help=_RESEARCH_GATE_OVERRIDE_HELP
    ),
) -> None:
    """Backtest a diversified basket: run the strategy across SYMBOLS and combine the OOS streams.

    ``--weighting`` is ``equal`` or ``inverse_vol``. Reports the basket's headline metrics +
    Probabilistic Sharpe and each leg's OOS Sharpe; writes a manifest under ``data_dir/portfolio``.
    """

    from alpha_cli import _portfolio

    settings = AlphaSettings()
    # canonical (sorted) symbol order: the run_id already sorts, and rank ties / float-summation
    # order must not depend on how the shell happened to order the arguments
    symbols = sorted(symbols)
    resolved_seed = seed if seed is not None else settings.random_seed
    spec = _runner.RunSpec(
        lookback=lookback,
        skip=skip,
        vol_window=vol_window,
        target_vol=target_vol,
        rebalance_every=rebalance_every,
        max_leverage=max_leverage,
        allow_short=_runner.resolve_allow_short(allow_short, account_type),
        periods_per_year=periods_per_year,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        starting_cash=starting_cash,
        account_type=account_type,
        train_size=train_size,
        test_size=test_size,
        embargo=embargo,
        anchored=anchored,
        strategy_name=strategy,
        strategy_params=_runner.parse_strategy_params(strategy, param),
        size_on_equity=size_on_equity,
        halt_drawdown=halt_drawdown,
    )
    try:
        research_cutoff = _runner.parse_as_of(as_of)
        result = _portfolio.run_portfolio(
            symbols,
            spec,
            data_dir=settings.data_dir,
            weighting=weighting,
            seed=resolved_seed,
            snapshot_id=snapshot,
            as_of=research_cutoff,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    snapshot_hash = _runner.verified_snapshot_hash(settings.data_dir, snapshot)
    identity = _runner.run_identity_for(
        {
            "command": "backtest_portfolio",
            "symbols": symbols,
            "weighting": weighting,
            "seed": resolved_seed,
            "snapshot_id": snapshot,
            "research_cutoff": as_of,
            **_artifacts.research_gate_override_identity(research_gate_override),
            **vars(spec),
        },
        source_fingerprint=result.source_fingerprint,
        snapshot_hash=snapshot_hash,
    )
    run_id = identity.run_id
    rdir = settings.data_dir / "portfolio" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    # the combined OOS stream as an equity curve (validate-run schema, base 1.0), written BEFORE
    # the manifest — manifest.json is the run-exists marker (see _artifacts.write_run)
    _artifacts.write_equity_curve(
        rdir,
        baseline_ts=result.baseline_ts,
        timestamps=result.portfolio_timestamps,
        returns=result.portfolio_returns.tolist(),
        periods_per_year=spec.periods_per_year,
        gross_exposure=result.portfolio_gross_exposure.tolist(),
        net_exposure=result.portfolio_net_exposure.tolist(),
    )
    _artifacts.write_portfolio_analytics(
        rdir,
        source_run_id=run_id,
        snapshot_id=snapshot,
        snapshot_hash=snapshot_hash,
        research_cutoff=as_of,
        allocations=result.allocations,
        correlations=result.correlations,
    )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "backtest_portfolio",
        "seed": resolved_seed,
        "snapshot_id": snapshot,
        "research_cutoff": as_of,
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
        **_artifacts.research_gate_override_fields(research_gate_override),
        **identity.manifest_fields(),
    }
    from alpha_validation import render_returns_tearsheet

    _artifacts.publish_artifact(
        rdir / "tearsheet.html",
        lambda path: render_returns_tearsheet(
            result.portfolio_returns,
            result.portfolio_timestamps,
            title=f"ALPHA Portfolio — {', '.join(result.symbols)} ({weighting})",
            summary_rows=[
                ("OOS Sharpe", f"{result.metrics['sharpe']:.3f}"),
                (
                    "Sharpe 95% CI",
                    f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}]",
                ),
                ("CAGR", f"{result.metrics['cagr']:.3f}"),
                ("Max drawdown", f"{result.metrics['max_drawdown']:.3f}"),
                ("Probabilistic Sharpe", f"{result.psr:.3f}"),
                ("Periods", str(result.n_periods)),
                ("Legs", ", ".join(f"{leg.symbol}={leg.weight:.2f}" for leg in result.legs)),
            ],
            output_path=path,
        ),
    )
    _artifacts.write_manifest(rdir, manifest)
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
    fee_bps: float = 1.0,
    slippage_bps: float = 2.0,
    periods_per_year: int = 252,
    seed: int | None = None,
    snapshot: str | None = None,
    as_of: str | None = typer.Option(None, "--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    research_gate_override: bool = typer.Option(
        False, "--research-gate-override", help=_RESEARCH_GATE_OVERRIDE_HELP
    ),
) -> None:
    """Backtest a cross-sectional momentum book: long the universe's winners, short its losers.

    Ranks SYMBOLS each rebalance by trailing return; longs the top ``--top-quantile`` and (unless
    ``--no-long-short``) shorts the bottom, vol-targeted. Reports OOS metrics + PSR + BCa intervals
    and writes a manifest under ``data_dir/cross_sectional``.
    """

    from alpha_cli import _cross_sectional

    settings = AlphaSettings()
    symbols = sorted(symbols)  # canonical order (see portfolio)
    resolved_seed = seed if seed is not None else settings.random_seed
    try:
        research_cutoff = _runner.parse_as_of(as_of)
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
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            periods_per_year=periods_per_year,
            seed=resolved_seed,
            snapshot_id=snapshot,
            as_of=research_cutoff,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    identity = _runner.run_identity_for(
        {
            "command": "cross_sectional",
            "symbols": symbols,
            "lookback": lookback,
            "skip": skip,
            "vol_window": vol_window,
            "target_vol": target_vol,
            "rebalance_every": rebalance_every,
            "top_quantile": top_quantile,
            "long_short": long_short,
            "max_leverage": max_leverage,
            "fee_bps": fee_bps,
            "slippage_bps": slippage_bps,
            "periods_per_year": periods_per_year,
            "seed": resolved_seed,
            "snapshot_id": snapshot,
            "research_cutoff": as_of,
            **_artifacts.research_gate_override_identity(research_gate_override),
        },
        source_fingerprint=result.source_fingerprint,
        snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot),
    )
    run_id = identity.run_id
    rdir = settings.data_dir / "cross_sectional" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    # the OOS stream as an equity curve (validate-run schema, base 1.0), written BEFORE the
    # manifest — manifest.json is the run-exists marker (see _artifacts.write_run)
    _artifacts.write_equity_curve(
        rdir,
        baseline_ts=result.baseline_ts,
        timestamps=result.timestamps,
        returns=result.returns.tolist(),
        periods_per_year=periods_per_year,
    )
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "cross_sectional",
        "seed": resolved_seed,
        "snapshot_id": snapshot,
        "research_cutoff": as_of,
        "symbols": list(result.symbols),
        "long_short": result.long_short,
        "n_long": result.n_long,
        "n_periods": result.n_periods,
        "metrics": {k: (v if v == v else None) for k, v in result.metrics.items()},
        "psr": result.psr if result.psr == result.psr else None,
        "dsr": result.dsr if result.dsr == result.dsr else None,
        "sharpe_ci": {"lower": result.sharpe_ci.lower, "upper": result.sharpe_ci.upper},
        "cagr_ci": {"lower": result.cagr_ci.lower, "upper": result.cagr_ci.upper},
        **_artifacts.research_gate_override_fields(research_gate_override),
        **identity.manifest_fields(),
    }
    book = "long-short" if long_short else "long-only"
    from alpha_validation import render_returns_tearsheet

    _artifacts.publish_artifact(
        rdir / "tearsheet.html",
        lambda path: render_returns_tearsheet(
            result.returns,
            result.timestamps,
            title=(
                f"ALPHA Cross-Sectional — {', '.join(result.symbols)} ({book}, {result.n_long}/leg)"
            ),
            summary_rows=[
                ("OOS Sharpe", f"{result.metrics['sharpe']:.3f}"),
                (
                    "Sharpe 95% CI",
                    f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}]",
                ),
                ("CAGR", f"{result.metrics['cagr']:.3f}"),
                ("Max drawdown", f"{result.metrics['max_drawdown']:.3f}"),
                ("Probabilistic Sharpe", f"{result.psr:.3f}"),
                ("Book", f"{book}, {result.n_long} names/leg"),
                ("Periods", str(result.n_periods)),
            ],
            output_path=path,
        ),
    )
    _artifacts.write_manifest(rdir, manifest)
    typer.echo(
        f"cross-sectional [{', '.join(result.symbols)}] ({book}, {result.n_long}/leg) -> "
        f"run {run_id}: OOS Sharpe {result.metrics['sharpe']:.3f} "
        f"[{result.sharpe_ci.lower:.2f}, {result.sharpe_ci.upper:.2f}], "
        f"CAGR {result.metrics['cagr']:.3f}, PSR {result.psr:.3f} "
        f"over {result.n_periods} periods; manifest at {rdir / 'manifest.json'}"
    )
