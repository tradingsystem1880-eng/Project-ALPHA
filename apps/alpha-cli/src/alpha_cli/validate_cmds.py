"""``alpha validate <symbol>``: run the validation gauntlet and emit a tear sheet (spec §11.2).

Walk-forward OOS (net of costs) + the two-tier randomized-price null + block-bootstrap BCa CIs,
written as a byte-stable JSON manifest, an equity/trade Parquet pair, and a quantstats HTML tear
sheet under ``data_dir/runs/<run_id>/``.
"""

from __future__ import annotations

import typer

from alpha_cli import _artifacts, _gauntlet, _runner
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_validation import render_tearsheet_html, report_to_manifest

# monkeypatchable load seams (mirror backtest_cmds); tests point them at fixture stores
_load_bars = _runner.load_bars
_load_dividends = _runner.load_dividends


def validate(
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
    train_size: int = 504,  # >= warmup floor for the default 252/21/63 params (max=274); ~2y train
    test_size: int = 63,
    embargo: int = 5,
    anchored: bool = False,
    param: list[str] | None = None,
    tier1_paths: int = 1000,
    tier2_paths: int = 64,
    n_resamples: int = 2000,
    mean_block: float = 5.0,
    threshold: float = 0.95,
    null_model: str = "bootstrap",
    tier1_divergence_tol: float = 0.25,
    seed: int | None = None,
    max_workers: int | None = None,
    snapshot: str | None = None,
) -> None:
    """Validate SYMBOL end-to-end and write the run artifacts (manifest, parquet, tear sheet).

    ``--strategy`` selects the registered strategy; ``--param name=value`` (repeatable) supplies any
    strategy-specific parameters beyond the shared ones.
    """
    settings = AlphaSettings()
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
        strategy_params=_runner.parse_strategy_params(param),
    )
    gparams = _gauntlet.GauntletParams(
        seed=resolved_seed,
        tier1_paths=tier1_paths,
        tier2_paths=tier2_paths,
        n_resamples=n_resamples,
        mean_block=mean_block,
        threshold=threshold,
        null_model=null_model,
        max_workers=max_workers,
        tier1_divergence_tol=tier1_divergence_tol,
    )
    try:
        bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
        dividends = _load_dividends(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
        # max_workers is an execution-only knob (results are order-preserving and identical
        # serial or pooled), so it must NOT change the run id (same params -> same id).
        gauntlet_knobs = {k: v for k, v in vars(gparams).items() if k != "max_workers"}
        run_id = _runner.run_id_for(
            {
                "command": "validate",
                "symbol": symbol,
                "snapshot_id": snapshot_id,
                **vars(spec),
                **gauntlet_knobs,
            }
        )
        out = _gauntlet.run_gauntlet(
            bars, spec, gparams, run_id=run_id, snapshot_id=snapshot_id, dividends=dividends
        )
    except DataError as exc:  # no bars, unknown strategy/null-model, train < warmup floor, etc.
        raise typer.BadParameter(str(exc)) from exc

    rdir = _artifacts.run_dir(settings.data_dir, run_id)
    equity = list(zip(out.oos.oos_timestamps, out.oos.oos_equity.tolist(), strict=True))
    _artifacts.write_run(
        rdir, manifest=report_to_manifest(out.report), equity=equity, trades=out.result.trades
    )
    render_tearsheet_html(
        out.report,
        oos_returns=out.oos.oos_returns,
        oos_timestamps=out.oos.oos_timestamps[1:],
        output_path=rdir / "tearsheet.html",
        periods_per_year=spec.periods_per_year,
    )

    status = "PASS" if out.report.passed else "FAIL"
    sharpe = out.report.oos_metrics["sharpe"]
    v = out.report.verdict
    grade = (
        f"Verdict {v.overall} "
        f"(edge {v.edge}/robustness {v.robustness}/risk {v.risk}/sample {v.sample}), "
        if v is not None
        else ""
    )
    typer.echo(
        f"validate {symbol} -> run {run_id}: {status} "
        f"({grade}OOS Sharpe {sharpe:.3f}, "
        f"null pct {out.report.nulls[0].percentile:.2f}/{out.report.nulls[1].percentile:.2f}); "
        f"tear sheet at {rdir / 'tearsheet.html'}"
    )
