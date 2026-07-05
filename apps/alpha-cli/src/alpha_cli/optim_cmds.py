"""``alpha optim grid``: sweep a strategy's parameters and judge the winner for overfitting.

Unlike a naive sweep that reports the best Sharpe, this reports the *selected* config together with
its Deflated Sharpe, PBO, and Hansen-SPA verdict — so a config that only won the in-sample lottery
is flagged rather than trusted. Artifacts land under ``data_dir/optim/<run_id>/manifest.json``.
"""

from __future__ import annotations

import json
import math
from typing import Annotated, Any

import typer

from alpha_cli import _optim, _runner
from alpha_core import DataError
from alpha_core.config import AlphaSettings

optim_app = typer.Typer(
    help="Parameter sweeps judged for overfitting (Deflated Sharpe + PBO + SPA)."
)

# monkeypatchable bar-load seam (mirrors validate_cmds); tests point it at a fixture store
_load_bars = _runner.load_bars


def _parse_axes(axes: list[str] | None) -> dict[str, list[float]]:
    """Parse repeatable ``--grid name=v1,v2,...`` options into a ``{name: [values]}`` grid."""
    grid: dict[str, list[float]] = {}
    for item in axes or []:
        if "=" not in item:
            raise typer.BadParameter(f"--grid must be name=v1,v2,..., got {item!r}")
        name, _, raw = item.partition("=")
        # Accept CLI-conventional hyphens (e.g. `vol-window`) and map to the canonical snake_case
        # RunSpec field (`vol_window`); else the axis silently becomes an ignored strategy param.
        name = name.strip().replace("-", "_")
        try:
            values = [float(v) for v in raw.split(",") if v != ""]
        except ValueError as exc:
            raise typer.BadParameter(f"--grid {name!r} values must be numeric: {raw!r}") from exc
        if not name or not values:
            raise typer.BadParameter(f"--grid axis is empty: {item!r}")
        grid[name] = values
    if not grid:
        raise typer.BadParameter("provide at least one --grid name=v1,v2,... axis")
    return grid


def _sanitize(value: Any) -> Any:
    """Non-finite floats → None so the manifest is strict-JSON valid (like the gauntlet writer)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_sanitize(v) for v in value]
    return value


@optim_app.command()
def grid(
    symbol: str,
    axis: Annotated[
        list[str] | None, typer.Option("--grid", help="sweep axis: name=v1,v2,...")
    ] = None,
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
    train_size: int = 504,
    test_size: int = 63,
    embargo: int = 5,
    anchored: bool = False,
    param: list[str] | None = None,
    pbo_blocks: int = 10,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    dsr_threshold: float = 0.95,
    alpha: float = 0.05,
    seed: int | None = None,
    max_workers: int | None = None,
    snapshot: str | None = None,
) -> None:
    """Sweep SYMBOL over the ``--grid`` axes and report the overfitting-aware best config."""
    settings = AlphaSettings()
    resolved_seed = seed if seed is not None else settings.random_seed
    grid_axes = _parse_axes(axis)
    base = _runner.RunSpec(
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
        strategy_params=_runner.parse_strategy_params(param),
    )
    bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
    run_id = _runner.run_id_for(
        {
            "command": "optim_grid",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "grid": {k: list(v) for k, v in grid_axes.items()},
            "pbo_blocks": pbo_blocks,
            "n_resamples": n_resamples,
            "mean_block": mean_block,
            "dsr_threshold": dsr_threshold,
            "alpha": alpha,
            "seed": resolved_seed,
            **vars(base),
        }
    )
    try:
        result = _optim.run_optimization(
            bars,
            base,
            grid_axes,
            pbo_blocks=pbo_blocks,
            n_resamples=n_resamples,
            mean_block=mean_block,
            dsr_threshold=dsr_threshold,
            alpha=alpha,
            seed=resolved_seed,
            max_workers=max_workers,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    rdir = settings.data_dir / "optim" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    manifest = _manifest(result, run_id=run_id, symbol=symbol, snapshot_id=snapshot_id)
    (rdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )

    verdict = "PASS" if result.passed else "FAIL"
    best = ", ".join(f"{k}={v:g}" for k, v in result.best_config)
    typer.echo(
        f"optim {symbol} -> run {run_id}: {verdict} over {result.n_configs} configs\n"
        f"  best: {best} (OOS Sharpe {result.best_sharpe:.3f})\n"
        f"  deflated Sharpe {result.dsr.dsr:.3f} (>= {dsr_threshold}? {result.dsr.passed}); "
        f"PBO {result.pbo.pbo:.3f}; SPA p {result.spa.p_value:.3f}; "
        f"RC p {result.reality_check.p_value:.3f}\n"
        f"  manifest at {rdir / 'manifest.json'}"
    )


def _manifest(
    result: _optim.OptimResult, *, run_id: str, symbol: str, snapshot_id: str | None
) -> dict[str, Any]:
    """Byte-stable summary manifest for a sweep (configs, per-config Sharpe, the four verdicts)."""
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "optim_grid",
        "symbol": symbol,
        "snapshot_id": snapshot_id,
        "n_configs": result.n_configs,
        "n_oos": result.n_oos,
        "best_config": [list(pair) for pair in result.best_config],
        "best_sharpe": result.best_sharpe,
        "dsr": {
            "psr": result.dsr.psr,
            "dsr": result.dsr.dsr,
            "expected_max_sharpe": result.dsr.expected_max_sharpe,
            "n_trials": result.dsr.n_trials,
            "passed": result.dsr.passed,
        },
        "pbo": {
            "pbo": result.pbo.pbo,
            "n_splits": result.pbo.n_splits,
            "passed": result.pbo.passed,
        },
        "reality_check": {
            "p_value": result.reality_check.p_value,
            "passed": result.reality_check.passed,
        },
        "spa": {"p_value": result.spa.p_value, "passed": result.spa.passed},
        "configs": [[list(pair) for pair in c] for c in result.configs],
        "sharpes": result.sharpes.tolist(),
        "passed": result.passed,
    }
    return {k: _sanitize(v) for k, v in manifest.items()}
