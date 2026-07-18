"""``alpha propfirm run``: Monte-Carlo a strategy against a funded-trader evaluation.

Resamples a strategy's daily return stream (a fresh backtest of SYMBOL, or ``--from-run RUN_ID``)
and walks it through a prop firm's eval -> funded -> payout rules, reporting pass / bust / payout
probabilities and expected payout. ``--firm`` selects an (illustrative, overridable) preset; any
rule flag overrides it. Artifacts land under ``data_dir/propfirm/<run_id>/manifest.json``.

The simulation is end-of-day granularity (the honest limit of a daily-bar backtest); the preset
numbers are approximate, not authoritative firm terms.
"""

from __future__ import annotations

import json
import math
from typing import Any

import typer

from alpha_cli import _artifacts, _propfirm, _runner
from alpha_cli._artifacts import sanitize
from alpha_core import DataError
from alpha_core.config import AlphaSettings

propfirm_app = typer.Typer(
    help="Prop-firm Monte Carlo: pass/payout probabilities for a funded-trader evaluation."
)


@propfirm_app.command()
def run(
    symbol: str | None = typer.Argument(
        None, help="symbol to backtest; omit when using --from-run"
    ),
    strategy: str = "ts_momentum",
    firm: str | None = typer.Option(None, help="preset: topstep | apex | takeprofit (else custom)"),
    from_run: str | None = typer.Option(
        None, "--from-run", help="reuse a prior run's equity curve"
    ),
    # rule overrides (override the selected preset / the default custom rules)
    account_size: float | None = None,
    profit_target: float | None = None,
    max_drawdown: float | None = None,
    daily_loss: float | None = None,
    profit_split: float | None = None,
    min_trading_days: int | None = None,
    # Monte-Carlo knobs
    n_paths: int = 5000,
    mean_block: float = 5.0,
    horizon: int | None = typer.Option(
        None, help="cap the simulation to N trading days (default: the full return series)"
    ),
    seed: int | None = None,
    # backtest knobs (used only for a fresh inline backtest of SYMBOL)
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
) -> None:
    """Score SYMBOL (or --from-run RUN_ID) against a prop firm and write a verdict manifest."""
    if (symbol is None) == (from_run is None):
        raise typer.BadParameter("provide exactly one of SYMBOL or --from-run RUN_ID")

    settings = AlphaSettings()
    resolved_seed = seed if seed is not None else settings.random_seed
    overrides = {
        name: value
        for name, value in (
            ("account_size", account_size),
            ("profit_target", profit_target),
            ("max_drawdown", max_drawdown),
            ("daily_loss", daily_loss),
            ("profit_split", profit_split),
            ("min_trading_days", min_trading_days),
        )
        if value is not None
    }
    # walk-forward fields are unused by propfirm (it reads the full equity curve); carry coherent
    # defaults so the RunSpec stays one fixed shape.
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
        strategy_params=_runner.parse_strategy_params(param),
        size_on_equity=size_on_equity,
        halt_drawdown=halt_drawdown,
    )
    # The run id pins only what the result depends on: the source, the firm + overrides, and the MC
    # knobs. A fresh backtest also depends on the strategy/cost spec; --from-run depends on the run.
    payload: dict[str, Any] = {
        "command": "propfirm",
        "firm": firm,
        "overrides": dict(sorted(overrides.items())),
        "n_paths": n_paths,
        "mean_block": mean_block,
        "horizon": horizon,
        "seed": resolved_seed,
    }
    if from_run is not None:
        payload["from_run"] = from_run
    else:
        payload["symbol"] = symbol
        payload["snapshot"] = snapshot
        payload.update(vars(spec))
    run_id = _runner.run_id_for(payload)

    try:
        out = _propfirm.run_propfirm(
            data_dir=settings.data_dir,
            symbol=symbol,
            from_run=from_run,
            spec=spec,
            snapshot=snapshot,
            firm=firm,
            overrides=overrides,
            n_paths=n_paths,
            mean_block=mean_block,
            seed=resolved_seed,
            horizon_days=horizon,
        )
    except DataError as exc:  # missing run, unknown firm, degenerate returns, bad rule override
        raise typer.BadParameter(str(exc)) from exc

    rdir = settings.data_dir / "propfirm" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    # per-path outcomes BEFORE the manifest (manifest.json is the run-exists marker)
    _artifacts.write_propfirm_paths(
        rdir,
        passed=out.result.path_passed,
        busted=out.result.path_busted,
        days_to_pass=out.result.path_days_to_pass,
        payout=out.result.path_payout,
    )
    manifest = _manifest(out, run_id=run_id, seed=resolved_seed)
    (rdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )

    res = out.result
    days = "n/a" if math.isnan(res.median_days_to_pass) else f"{res.median_days_to_pass:.0f}"
    label = symbol if symbol is not None else f"run {from_run}"
    typer.echo(
        f"propfirm {label} -> run {run_id}: {out.firm}\n"
        f"  pass {res.pass_probability:.1%}, bust {res.bust_probability:.1%}, "
        f"payout {res.payout_probability:.1%}, median days-to-pass {days}\n"
        f"  expected payout ${res.expected_payout:,.0f} over {res.horizon_days} days "
        f"({res.n_paths} paths)\n"
        f"  manifest at {rdir / 'manifest.json'}"
    )


def _manifest(out: _propfirm.PropFirmRunResult, *, run_id: str, seed: int) -> dict[str, Any]:
    """Byte-stable summary manifest (resolved rules + the simulation metrics)."""
    res = out.result
    rules = out.rules
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "propfirm",
        "firm": out.firm,
        "source": out.source,
        "rules": {
            "account_size": rules.account_size,
            "profit_target": rules.profit_target,
            "max_drawdown": rules.max_drawdown,
            "trailing": rules.trailing,
            "lock_at_profit": rules.lock_at_profit,
            "daily_loss_limit": rules.daily_loss_limit,
            "min_trading_days": rules.min_trading_days,
            "profit_split": rules.profit_split,
            "min_payout": rules.min_payout,
            "min_funded_days": rules.min_funded_days,
            "eval_fee": rules.eval_fee,
        },
        "metrics": {
            "pass_probability": res.pass_probability,
            "bust_probability": res.bust_probability,
            "payout_probability": res.payout_probability,
            "median_days_to_pass": res.median_days_to_pass,
            "expected_payout": res.expected_payout,
        },
        "n_paths": res.n_paths,
        "horizon_days": res.horizon_days,
        "seed": seed,
    }
    return {k: sanitize(v) for k, v in manifest.items()}
