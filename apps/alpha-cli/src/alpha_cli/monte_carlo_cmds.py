"""Immutable scenario/path-risk Monte Carlo commands.

The classical command consumes a completed validation run's canonical out-of-sample account
equity.  It does not rerun or reinterpret the existing randomized-price null tests.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import typer

from alpha_cli import _artifacts, _forecast, _forecast_cache, _runner
from alpha_cli._seeds import semantic_seed, semantic_seeds
from alpha_cli.artifact_contract import sha256_file
from alpha_core import Bar, DataError
from alpha_core.config import AlphaSettings
from alpha_validation import (
    MonteCarloFamilySummaryV1,
    ProportionInterval,
    empirical_return_paths,
    path_metric_arrays,
    regime_switching_return_paths,
    student_t_return_paths,
    summarize_path_family,
    to_returns,
)

monte_carlo_app = typer.Typer(
    help="Required scenario/path-risk Monte Carlo evidence from a completed validation run."
)

# Monkeypatchable seam for offline integration tests. Real runs resolve the pinned Kronos facade.
_forecaster_factory = _forecast._forecaster_factory


def _verified_validation_source(data_dir: Path, run_id: str) -> tuple[Path, dict[str, Any]]:
    rdir = _artifacts.find_run_dir(data_dir, run_id)
    if rdir is None:
        raise DataError(f"validation source run {run_id!r} was not found")
    manifest = _artifacts.read_manifest(rdir)
    if manifest.get("command") != "validate":
        raise DataError(f"source run {run_id!r} must be a completed validate run")
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict) or not isinstance(metadata.get("symbol"), str):
        raise DataError(f"source run {run_id!r} has invalid validation metadata")
    return rdir, manifest


def _verified_forecast_eval(
    data_dir: Path,
    run_id: str,
    *,
    source_manifest: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    rdir = _artifacts.find_run_dir(data_dir, run_id)
    if rdir is None:
        raise DataError(f"forecast evaluation run {run_id!r} was not found")
    manifest = _artifacts.read_manifest(rdir)
    if manifest.get("command") != "forecast_eval":
        raise DataError(f"run {run_id!r} must be a completed forecast_eval run")
    source_metadata = source_manifest["metadata"]
    for label, source_value, eval_value in (
        ("symbol", source_metadata.get("symbol"), manifest.get("symbol")),
        ("snapshot", source_metadata.get("snapshot_id"), manifest.get("snapshot_id")),
        (
            "research cutoff",
            source_manifest.get("research_cutoff"),
            manifest.get("research_cutoff"),
        ),
    ):
        if source_value != eval_value:
            raise DataError(
                f"forecast evaluation {label} {eval_value!r} differs from source {source_value!r}"
            )
    return rdir, manifest


def _spec_from_validation(manifest: dict[str, Any]) -> _runner.RunSpec:
    metadata = manifest["metadata"]
    raw_params = metadata.get("strategy_params", ())
    if not isinstance(raw_params, list | tuple):
        raise DataError("validation strategy_params must be a sequence")
    params = tuple((str(row[0]), float(row[1])) for row in raw_params)
    return _runner.RunSpec(
        lookback=int(metadata["lookback"]),
        skip=int(metadata["skip"]),
        vol_window=int(metadata["vol_window"]),
        target_vol=float(metadata["target_vol"]),
        rebalance_every=int(metadata["rebalance_every"]),
        max_leverage=float(metadata["max_leverage"]),
        allow_short=bool(metadata["allow_short"]),
        periods_per_year=int(metadata["periods_per_year"]),
        fee_bps=float(metadata["fee_bps"]),
        slippage_bps=float(metadata["slippage_bps"]),
        starting_cash=float(metadata["starting_cash"]),
        account_type=str(metadata["account_type"]),
        train_size=int(metadata["train_size"]),
        test_size=int(metadata["test_size"]),
        embargo=int(metadata["embargo"]),
        anchored=bool(metadata["anchored"]),
        strategy_name=str(metadata["strategy_name"]),
        strategy_params=params,
    )


def _calibration_assessment(manifest: dict[str, Any]) -> dict[str, Any]:
    summary = manifest.get("summary_post_cutoff")
    reasons: list[str] = []
    if not isinstance(summary, dict):
        reasons.append("no post-cutoff forecast origins")
        return {"status": "weak_or_insufficient", "reasons": reasons, "summary": None}
    n_origins = int(summary.get("n_origins", 0))
    skill_rw = float(summary.get("skill_vs_rw", math.nan))
    skill_bootstrap = float(summary.get("skill_vs_bootstrap", math.nan))
    if n_origins < 5:
        reasons.append(f"only {n_origins} post-cutoff origins")
    if not math.isfinite(skill_rw) or skill_rw <= 0.0:
        reasons.append("CRPS does not beat the random-walk baseline")
    if not math.isfinite(skill_bootstrap) or skill_bootstrap <= 0.0:
        reasons.append("CRPS does not beat the stationary-bootstrap baseline")
    for field, nominal, tolerance in (
        ("coverage50", 0.50, 0.15),
        ("coverage80", 0.80, 0.10),
        ("coverage90", 0.90, 0.10),
    ):
        coverage = float(summary.get(field, math.nan))
        lower = nominal - tolerance
        upper = min(1.0, nominal + tolerance)
        if not math.isfinite(coverage) or coverage < lower - 1e-12 or coverage > upper + 1e-12:
            reasons.append(
                f"empirical {nominal:.0%} interval coverage is outside {lower:.0%}-{upper:.0%}"
            )
    return {
        "status": "adequate" if not reasons else "weak_or_insufficient",
        "reasons": reasons,
        "summary": summary,
    }


def _project_forecast_path(
    *, symbol: str, timestamps: Sequence[datetime], sample: Any, path_index: int
) -> tuple[list[Bar], list[dict[str, object]], int]:
    horizon = len(timestamps)
    components: dict[str, Any] = {}
    for name in ("open", "high", "low", "close", "volume"):
        try:
            values = getattr(sample, name)
            count = len(values)
        except (AttributeError, TypeError) as exc:
            raise DataError(f"Kronos path {path_index} has no valid {name} sequence") from exc
        if count != horizon:
            raise DataError(
                f"Kronos path {path_index} {name} length {count} differs from horizon {horizon}"
            )
        components[name] = values
    bars: list[Bar] = []
    rows: list[dict[str, object]] = []
    adjustments = 0
    for step, timestamp in enumerate(timestamps):
        try:
            raw = {name: float(values[step]) for name, values in components.items()}
        except (IndexError, OverflowError, TypeError, ValueError) as exc:
            raise DataError(
                f"Kronos path {path_index} step {step} contains a non-numeric OHLCV value"
            ) from exc
        if any(
            not math.isfinite(raw[name]) or raw[name] <= 0.0
            for name in ("open", "high", "low", "close")
        ):
            raise DataError(f"Kronos path {path_index} step {step} contains an invalid price")
        if not math.isfinite(raw["volume"]) or raw["volume"] < 0.0:
            raise DataError(f"Kronos path {path_index} step {step} contains invalid volume")
        projected_high = max(raw["high"], raw["open"], raw["close"])
        projected_low = min(raw["low"], raw["open"], raw["close"])
        high_adjusted = projected_high != raw["high"]
        low_adjusted = projected_low != raw["low"]
        adjustments += int(high_adjusted) + int(low_adjusted)
        bar = Bar(
            symbol=symbol,
            ts=timestamp,
            open=raw["open"],
            high=projected_high,
            low=projected_low,
            close=raw["close"],
            volume=raw["volume"],
        )
        bars.append(bar)
        rows.append(
            {
                "path_index": path_index,
                "step": step,
                "ts": timestamp,
                **{f"raw_{name}": value for name, value in raw.items()},
                "projected_open": bar.open,
                "projected_high": bar.high,
                "projected_low": bar.low,
                "projected_close": bar.close,
                "projected_volume": bar.volume,
                "high_adjusted": high_adjusted,
                "low_adjusted": low_adjusted,
            }
        )
    return bars, rows, adjustments


def _causal_regime_states(
    bars: Sequence[Bar],
    return_timestamps: Sequence[datetime],
    *,
    train_size: int,
    window: int,
) -> tuple[np.ndarray, float, np.ndarray]:
    """Label OOS returns using only trailing volatility known before each realization."""
    if window < 2:
        raise DataError(f"regime_window must be >= 2, got {window}")
    if train_size <= window + 1 or train_size > len(bars):
        raise DataError(
            f"training prefix {train_size} cannot freeze a {window}-session volatility boundary"
        )
    closes = np.asarray([bar.close for bar in bars], dtype=np.float64)
    market_returns = closes[1:] / closes[:-1] - 1.0

    # volatility assigned to bar i uses market returns ending at bar i-1, so the bar-i outcome
    # cannot affect its own state.  The threshold is frozen wholly inside the training prefix.
    trailing = np.full(len(bars), np.nan, dtype=np.float64)
    for bar_index in range(window + 1, len(bars)):
        trailing[bar_index] = float(
            np.std(market_returns[bar_index - 1 - window : bar_index - 1], ddof=1)
        )
    training_values = trailing[window + 1 : train_size]
    training_values = training_values[np.isfinite(training_values)]
    if training_values.size < 2:
        raise DataError("training prefix has insufficient causal volatility observations")
    threshold = float(np.median(training_values))

    by_timestamp = {bar.ts: index for index, bar in enumerate(bars)}
    states: list[int] = []
    oos_volatility: list[float] = []
    for timestamp in return_timestamps:
        oos_index = by_timestamp.get(timestamp)
        if oos_index is None:
            raise DataError(
                f"OOS account return timestamp {timestamp.isoformat()} is absent from source"
            )
        volatility = trailing[oos_index]
        if not np.isfinite(volatility):
            raise DataError(
                f"OOS timestamp {timestamp.isoformat()} lacks {window} prior volatility sessions"
            )
        oos_volatility.append(float(volatility))
        states.append(int(volatility > threshold))
    return np.asarray(states, dtype=np.int8), threshold, np.asarray(oos_volatility)


def _path_frame(families: Sequence[tuple[str, np.ndarray]]) -> pl.DataFrame:
    frames: list[pl.DataFrame] = []
    for family, paths in families:
        if paths.ndim != 2:
            raise DataError(f"Monte Carlo path matrix for {family!r} must be two-dimensional")
        n_paths, horizon = paths.shape
        frame = pl.DataFrame(
            {
                "path_index": np.repeat(np.arange(n_paths, dtype=np.int64), horizon),
                "step": np.tile(np.arange(horizon, dtype=np.int64), n_paths),
                "account_return": np.asarray(paths, dtype=np.float64).reshape(-1),
            },
            schema={
                "path_index": pl.Int64,
                "step": pl.Int64,
                "account_return": pl.Float64,
            },
        ).with_columns(pl.lit(family).alias("family"))
        frames.append(frame.select("family", "path_index", "step", "account_return"))
    if not frames:
        raise DataError("at least one Monte Carlo path family is required")
    return pl.concat(frames, how="vertical")


def _metric_frame(families: Sequence[tuple[str, np.ndarray]]) -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for family, paths in families:
        metrics = path_metric_arrays(paths)
        rows.extend(
            {
                "family": family,
                "path_index": path_index,
                "terminal_return": float(metrics.terminal_return[path_index]),
                "maximum_drawdown": float(metrics.maximum_drawdown[path_index]),
                "longest_loss_streak": int(metrics.longest_loss_streak[path_index]),
                "loss": bool(metrics.loss[path_index]),
                "ruined": bool(metrics.ruined[path_index]),
            }
            for path_index in range(paths.shape[0])
        )
    return pl.DataFrame(
        rows,
        schema={
            "family": pl.String,
            "path_index": pl.Int64,
            "terminal_return": pl.Float64,
            "maximum_drawdown": pl.Float64,
            "longest_loss_streak": pl.Int64,
            "loss": pl.Boolean,
            "ruined": pl.Boolean,
        },
    )


def _report_text(
    *,
    source_run_id: str,
    summaries: Sequence[MonteCarloFamilySummaryV1],
    n_paths: int,
    horizon: int,
) -> str:
    rows = "\n".join(
        f"| {row.family} | {row.status} | {row.risk_grade} | "
        f"{row.terminal_return_q50:.6f} | {row.maximum_drawdown_q95:.6f} | "
        f"{row.ruin_probability.point:.6f} |"
        for row in summaries
    )
    return (
        "# Classical Monte Carlo path-risk report\n\n"
        "Question: how does the validated OOS account-return stream behave under alternate "
        "sequencing, causal volatility regimes, and a fitted heavy-tailed marginal model?\n\n"
        f"Source validation run: `{source_run_id}`. Paths per family: {n_paths}. "
        f"OOS horizon: {horizon}.\n\n"
        "| Family | Status | Risk grade | Median terminal return | "
        "95th percentile max drawdown | Ruin probability |\n"
        "|---|---:|---:|---:|---:|---:|\n"
        f"{rows}\n\n"
        "Interpretation: these simulations measure path and scenario risk. They do not establish "
        "edge, replace randomized-price null tests, authorize holdout access, or confer execution "
        "authority. Uncertainty for loss and ruin probabilities is reported with Wilson "
        "intervals.\n\n"
        "Assumptions: IID empirical resampling; a two-state first-order Markov chain with "
        "empirical "
        "state emissions and a training-frozen causal volatility boundary; and IID Student-t draws "
        "fitted to OOS log-account-return location, scale, and tail thickness, then mapped back "
        "to valid simple returns.\n"
    )


@monte_carlo_app.command("classical")
def classical(
    from_run: str = typer.Option(..., "--from-run", help="completed validation run id"),
    paths: int = typer.Option(10_000, "--paths", min=1),
    regime_window: int = typer.Option(63, "--regime-window", min=2),
    min_state_observations: int = typer.Option(20, min=1),
    min_state_transitions: int = typer.Option(10, min=1),
    confidence: float = typer.Option(0.95, min=0.5, max=0.999),
    seed: int | None = None,
) -> None:
    """Publish IID, causal regime-Markov, and Student-t OOS account-return paths."""
    settings = AlphaSettings()
    resolved_seed = settings.random_seed if seed is None else seed
    try:
        source_dir, source_manifest = _verified_validation_source(settings.data_dir, from_run)
        metadata = source_manifest["metadata"]
        equity = _artifacts.read_equity(source_dir)
        account_returns = to_returns([value for _, value in equity])
        if account_returns.size < 20:
            raise DataError(
                f"Monte Carlo requires at least 20 OOS account returns, got {account_returns.size}"
            )
        symbol = str(metadata["symbol"])
        snapshot_id = metadata.get("snapshot_id")
        cutoff = source_manifest.get("research_cutoff")
        bars, _ = _runner.load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=str(snapshot_id) if snapshot_id is not None else None,
            as_of=_runner.parse_as_of(str(cutoff) if cutoff is not None else None),
        )
        states, state_threshold, oos_volatility = _causal_regime_states(
            bars,
            [timestamp for timestamp, _ in equity][1:],
            train_size=int(metadata["train_size"]),
            window=regime_window,
        )
        seeds = semantic_seeds(
            resolved_seed,
            ("monte_carlo.iid", "monte_carlo.regime", "monte_carlo.student_t"),
        )
        iid_paths = empirical_return_paths(
            account_returns, n_paths=paths, seed=seeds["monte_carlo.iid"]
        )
        regime_failure: str | None = None
        try:
            regime = regime_switching_return_paths(
                account_returns,
                states,
                n_paths=paths,
                min_state_observations=min_state_observations,
                min_state_transitions=min_state_transitions,
                seed=seeds["monte_carlo.regime"],
            )
        except DataError as exc:
            regime = None
            regime_failure = str(exc)
        t_paths = student_t_return_paths(
            account_returns, n_paths=paths, seed=seeds["monte_carlo.student_t"]
        )
        simulated_families: list[tuple[str, np.ndarray]] = [("iid_empirical", iid_paths)]
        if regime is not None:
            simulated_families.append(("regime_switching", regime.paths))
        simulated_families.append(("student_t", t_paths))
        summaries_by_family = {
            name: summarize_path_family(name, values, confidence=confidence)
            for name, values in simulated_families
        }
        if regime is None:
            unavailable_interval = ProportionInterval(
                point=math.nan,
                lower=math.nan,
                upper=math.nan,
                confidence=confidence,
                successes=0,
                trials=0,
            )
            summaries_by_family["regime_switching"] = MonteCarloFamilySummaryV1(
                schema_version=1,
                family="regime_switching",
                status="not_estimable",
                n_paths=0,
                horizon=int(account_returns.size),
                terminal_return_q05=math.nan,
                terminal_return_q50=math.nan,
                terminal_return_q95=math.nan,
                maximum_drawdown_q50=math.nan,
                maximum_drawdown_q95=math.nan,
                longest_loss_streak_q95=math.nan,
                loss_probability=unavailable_interval,
                ruin_probability=unavailable_interval,
                risk_grade="F",
                explanation="The declared causal two-state support floor was not met.",
                caveats=(str(regime_failure),),
            )
        summaries = tuple(
            summaries_by_family[name] for name in ("iid_empirical", "regime_switching", "student_t")
        )

        source_equity_hash = sha256_file(source_dir / "equity_curve.parquet")
        source_fingerprint = _runner.combine_source_fingerprints(
            {
                "source_run": str(source_manifest["source_fingerprint"]),
                "source_oos_equity": source_equity_hash,
            }
        )
        payload: dict[str, object] = {
            "command": "monte_carlo_classical",
            "source_run_id": from_run,
            "source_equity_hash": source_equity_hash,
            "symbol": symbol,
            "strategy_name": str(metadata["strategy_name"]),
            "paths": paths,
            "horizon": int(account_returns.size),
            "regime_window": regime_window,
            "min_state_observations": min_state_observations,
            "min_state_transitions": min_state_transitions,
            "confidence": confidence,
            "master_seed": resolved_seed,
            "semantic_seeds": seeds,
            "generator_version": 1,
        }
        identity = _runner.run_identity_for(
            payload,
            source_fingerprint=source_fingerprint,
            snapshot_hash=source_manifest.get("snapshot_hash"),
        )
        rdir = _artifacts.run_dir(settings.data_dir, identity.run_id)
        paths_frame = _path_frame(simulated_families)
        metric_frame = _metric_frame(simulated_families)
        transition_counts = np.zeros((2, 2), dtype=np.int64)
        for current, following in zip(states[:-1], states[1:], strict=True):
            transition_counts[int(current), int(following)] += 1
        state_observations = (int(np.sum(states == 0)), int(np.sum(states == 1)))
        state_outbound = (
            int(np.sum(transition_counts[0])),
            int(np.sum(transition_counts[1])),
        )
        transition_rows: list[dict[str, object]] = []
        for from_state in (0, 1):
            state_volatility = oos_volatility[states == from_state]
            mean_state_volatility = (
                None if state_volatility.size == 0 else float(np.mean(state_volatility))
            )
            for to_state in (0, 1):
                transition_rows.append(
                    {
                        "from_state": from_state,
                        "to_state": to_state,
                        "transition_count": int(transition_counts[from_state, to_state]),
                        "transition_probability": (
                            None
                            if regime is None
                            else float(regime.transition_matrix[from_state, to_state])
                        ),
                        "state_observations": state_observations[from_state],
                        "state_outbound_transitions": state_outbound[from_state],
                        "frozen_volatility_threshold": state_threshold,
                        "mean_oos_trailing_volatility": mean_state_volatility,
                    }
                )
        diagnostics = pl.DataFrame(transition_rows)
        emissions = pl.DataFrame(
            {
                "step": range(account_returns.size),
                "state": states,
                "account_return": account_returns,
                "trailing_volatility": oos_volatility,
            },
            schema={
                "step": pl.Int64,
                "state": pl.Int8,
                "account_return": pl.Float64,
                "trailing_volatility": pl.Float64,
            },
        )
        observed_oos = pl.DataFrame(
            {
                "step": range(len(equity)),
                "ts": [timestamp for timestamp, _ in equity],
                "equity": [float(value) for _, value in equity],
            },
            schema={"step": pl.Int64, "ts": pl.Datetime("us", "UTC"), "equity": pl.Float64},
        )
        _artifacts.publish_artifact(rdir / "observed_oos.parquet", observed_oos.write_parquet)
        _artifacts.publish_artifact(rdir / "paths.parquet", paths_frame.write_parquet)
        _artifacts.publish_artifact(rdir / "path_metrics.parquet", metric_frame.write_parquet)
        _artifacts.publish_artifact(rdir / "regime_diagnostics.parquet", diagnostics.write_parquet)
        _artifacts.publish_artifact(rdir / "regime_emissions.parquet", emissions.write_parquet)
        report = _report_text(
            source_run_id=from_run,
            summaries=summaries,
            n_paths=paths,
            horizon=int(account_returns.size),
        )
        _artifacts.publish_artifact(
            rdir / "report.md", lambda path: path.write_text(report, encoding="utf-8")
        )
        manifest: dict[str, Any] = {
            **payload,
            "run_id": identity.run_id,
            "source_run_hash": sha256_file(source_dir / "manifest.json"),
            "source_snapshot_id": snapshot_id,
            "source_research_cutoff": cutoff,
            "snapshot_id": snapshot_id,
            "research_cutoff": cutoff,
            "families": [dataclasses.asdict(summary) for summary in summaries],
            "status": (
                "fail"
                if regime is None
                else (
                    "warning"
                    if any(summary.status == "warning" for summary in summaries)
                    else "clear"
                )
            ),
            "regime_diagnostics": {
                "state_boundary": "median trailing volatility frozen from training prefix",
                "state_threshold": state_threshold,
                "status": "not_estimable" if regime is None else "estimable",
                "failure": regime_failure,
                "state_observations": state_observations,
                "state_outbound_transitions": state_outbound,
                "transition_matrix": None if regime is None else regime.transition_matrix.tolist(),
                "causal_window": regime_window,
            },
            "explanation": (
                "Scenario and path-risk evidence only; this run neither proves edge nor replaces "
                "the source validation's randomized-price robustness tests."
            ),
            **identity.manifest_fields(),
        }
        _artifacts.write_manifest(rdir, manifest)
    except (DataError, KeyError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"monte-carlo classical -> run {identity.run_id}: "
        + ", ".join(f"{row.family}={row.status}/{row.risk_grade}" for row in summaries)
        + f"; manifest at {rdir / 'manifest.json'}"
    )


@monte_carlo_app.command("kronos")
def kronos(
    from_run: str = typer.Option(..., "--from-run", help="completed validation run id"),
    forecast_eval_run: str = typer.Option(
        ..., "--forecast-eval-run", help="matching rolling-origin Kronos evaluation run id"
    ),
    paths: int = typer.Option(128, "--paths", min=1),
    context: int | None = typer.Option(
        None, help="real training-prefix bars supplied to Kronos (default: settings value)"
    ),
    temperature: float = typer.Option(1.0, min=0.01),
    top_p: float = typer.Option(0.9, min=0.01, max=1.0),
    top_k: int = typer.Option(0, min=0),
    model: str | None = typer.Option(None, help="pinned model id/path or 'fake'"),
    model_revision: str | None = None,
    tokenizer: str | None = None,
    tokenizer_revision: str | None = None,
    device: str | None = None,
    seed: int | None = None,
) -> None:
    """Generate synthetic OHLCV tails and fully replay the unchanged canonical strategy."""
    settings = AlphaSettings()
    resolved_model = model if model is not None else settings.forecast_model
    resolved_model_revision = (
        model_revision if model_revision is not None else settings.forecast_model_revision
    )
    resolved_tokenizer = tokenizer if tokenizer is not None else settings.forecast_tokenizer
    resolved_tokenizer_revision = (
        tokenizer_revision
        if tokenizer_revision is not None
        else settings.forecast_tokenizer_revision
    )
    resolved_device = device if device is not None else settings.forecast_device
    resolved_context = context if context is not None else settings.forecast_context
    resolved_seed = settings.random_seed if seed is None else seed

    try:
        source_dir, source_manifest = _verified_validation_source(settings.data_dir, from_run)
        eval_dir, eval_manifest = _verified_forecast_eval(
            settings.data_dir, forecast_eval_run, source_manifest=source_manifest
        )
        metadata = source_manifest["metadata"]
        symbol = str(metadata["symbol"])
        snapshot_id = metadata.get("snapshot_id")
        cutoff = source_manifest.get("research_cutoff")
        as_of = _runner.parse_as_of(str(cutoff) if cutoff is not None else None)
        bars, _ = _runner.load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=str(snapshot_id) if snapshot_id is not None else None,
            as_of=as_of,
        )
        dividends = _runner.load_dividends(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=str(snapshot_id) if snapshot_id is not None else None,
            as_of=as_of,
        )
        if _runner.source_fingerprint(bars) != eval_manifest.get("source_fingerprint"):
            raise DataError("forecast evaluation does not hash the source run's exact bar history")
        spec = _spec_from_validation(source_manifest)
        if spec.train_size >= len(bars):
            raise DataError("source validation has no future tail after its training prefix")
        training_prefix = list(bars[: spec.train_size])
        future_timestamps = tuple(bar.ts for bar in bars[spec.train_size :])
        if resolved_context < 2 or resolved_context > len(training_prefix):
            raise DataError(
                f"Kronos context must be between 2 and training prefix {len(training_prefix)}, "
                f"got {resolved_context}"
            )
        model_input = training_prefix[-resolved_context:]
        forecaster = _forecaster_factory(
            model=resolved_model,
            model_revision=resolved_model_revision,
            tokenizer=resolved_tokenizer,
            tokenizer_revision=resolved_tokenizer_revision,
            device=resolved_device,
            hub_cache=settings.forecast_hub_cache,
            local_files_only=settings.forecast_local_only,
        )
        provenance = _forecast._provenance(forecaster, model=resolved_model)
        evaluated_model = eval_manifest.get("model")
        if not isinstance(evaluated_model, dict):
            raise DataError("forecast evaluation has no pinned model provenance")
        for field in (
            "model_id",
            "model_revision",
            "tokenizer_id",
            "tokenizer_revision",
            "device",
        ):
            if evaluated_model.get(field) != provenance.get(field):
                raise DataError(
                    f"Kronos generator {field} {provenance.get(field)!r} differs from "
                    f"forecast evaluation {evaluated_model.get(field)!r}"
                )
        synthetic_rows: list[dict[str, object]] = []
        engine_paths: list[np.ndarray] = []
        adjustment_count = 0
        path_seeds: list[int] = []
        for path_index in range(paths):
            path_seed = semantic_seed(resolved_seed, f"monte_carlo.kronos.path.{path_index}")
            path_seeds.append(path_seed)
            generated = forecaster.forecast(
                model_input,
                horizon=len(future_timestamps),
                sample_count=1,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                seed=path_seed,
                step_ts=future_timestamps,
            )
            if generated.step_ts != future_timestamps:
                raise DataError(f"Kronos path {path_index} changed the frozen future timestamps")
            if len(generated.samples) != 1:
                raise DataError(f"Kronos path {path_index} did not return exactly one sample")
            projected, rows, adjusted = _project_forecast_path(
                symbol=symbol,
                timestamps=future_timestamps,
                sample=generated.samples[0],
                path_index=path_index,
            )
            synthetic_rows.extend(rows)
            adjustment_count += adjusted
            scenario_bars = [*training_prefix, *projected]
            scenario_spec, _ = _forecast_cache.prepare_spec_for_engine(
                scenario_bars,
                spec,
                data_dir=settings.data_dir,
                seed=path_seed,
            )
            oos, _ = _runner.fresh_oos_execution(
                scenario_bars,
                scenario_spec,
                dividends=dividends,
            )
            engine_paths.append(oos.oos_returns)
        path_matrix = np.asarray(engine_paths, dtype=np.float64)
        source_horizon = len(_artifacts.read_equity(source_dir)) - 1
        if path_matrix.shape != (paths, source_horizon):
            raise DataError(
                f"Kronos engine path shape {path_matrix.shape} differs from source OOS geometry "
                f"({paths}, {source_horizon})"
            )

        calibration = _calibration_assessment(eval_manifest)
        pretrain = _forecast.pretrain_overlap(model_input, settings.forecast_pretrain_cutoff)
        caveats = ["Kronos pretraining overlap remains permanently disclosed when present"]
        warning = bool(pretrain["overlap"])
        if provenance.get("determinism") != "exact":
            caveats.append(
                f"{provenance.get('device')} inference is best-effort rather than bit-exact"
            )
            warning = True
        if provenance.get("model_id") != "fake" and provenance.get("model_revision") in {
            None,
            "main",
            "master",
        }:
            caveats.append(
                "model revision is a mutable branch name rather than an immutable commit"
            )
            warning = True
        if provenance.get("model_id") != "fake" and provenance.get("tokenizer_revision") in {
            None,
            "main",
            "master",
        }:
            caveats.append(
                "tokenizer revision is a mutable branch name rather than an immutable commit"
            )
            warning = True
        if calibration["status"] != "adequate":
            caveats.extend(str(reason) for reason in calibration["reasons"])
            warning = True
        summary = summarize_path_family(
            "kronos_synthetic",
            path_matrix,
            caveats=tuple(caveats),
        )
        if warning and summary.status != "warning":
            summary = dataclasses.replace(summary, status="warning")

        eval_manifest_hash = sha256_file(eval_dir / "manifest.json")
        eval_origins_hash = sha256_file(eval_dir / "origins.parquet")
        source_equity_hash = sha256_file(source_dir / "equity_curve.parquet")
        provenance_json = json.dumps(
            provenance, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        model_identity = hashlib.sha256(provenance_json.encode("utf-8")).hexdigest()
        payload: dict[str, object] = {
            "command": "monte_carlo_kronos",
            "source_run_id": from_run,
            "forecast_eval_run_id": forecast_eval_run,
            "source_equity_hash": source_equity_hash,
            "forecast_eval_manifest_hash": eval_manifest_hash,
            "forecast_eval_origins_hash": eval_origins_hash,
            "symbol": symbol,
            "strategy_name": spec.strategy_name,
            "paths": paths,
            "horizon": source_horizon,
            "synthetic_tail_horizon": len(future_timestamps),
            "context": resolved_context,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "master_seed": resolved_seed,
            "path_seeds": path_seeds,
            "generator_version": 1,
            "model_identity": model_identity,
            "model": provenance,
        }
        identity = _runner.run_identity_for(
            payload,
            source_fingerprint=_runner.combine_source_fingerprints(
                {
                    "source_run": str(source_manifest["source_fingerprint"]),
                    "source_oos_equity": source_equity_hash,
                    "forecast_evaluation": eval_manifest_hash,
                    "forecast_evaluation_origins": eval_origins_hash,
                }
            ),
            snapshot_hash=source_manifest.get("snapshot_hash"),
        )
        rdir = _artifacts.run_dir(settings.data_dir, identity.run_id)
        synthetic_frame = pl.DataFrame(synthetic_rows)
        family_paths = (("kronos_synthetic", path_matrix),)
        source_equity = _artifacts.read_equity(source_dir)
        observed_oos = pl.DataFrame(
            {
                "step": range(len(source_equity)),
                "ts": [timestamp for timestamp, _ in source_equity],
                "equity": [float(value) for _, value in source_equity],
            },
            schema={"step": pl.Int64, "ts": pl.Datetime("us", "UTC"), "equity": pl.Float64},
        )
        _artifacts.publish_artifact(rdir / "observed_oos.parquet", observed_oos.write_parquet)
        _artifacts.publish_artifact(rdir / "synthetic_bars.parquet", synthetic_frame.write_parquet)
        _artifacts.publish_artifact(rdir / "paths.parquet", _path_frame(family_paths).write_parquet)
        _artifacts.publish_artifact(
            rdir / "path_metrics.parquet", _metric_frame(family_paths).write_parquet
        )
        calibration_origins = pl.read_parquet(eval_dir / "origins.parquet")
        _artifacts.publish_artifact(
            rdir / "calibration_origins.parquet", calibration_origins.write_parquet
        )
        diagnostics: dict[str, object] = {
            "schema_version": 1,
            "model": provenance,
            "model_identity": model_identity,
            "determinism": provenance.get("determinism"),
            "pretrain": pretrain,
            "calibration": calibration,
            "forecast_eval_run_id": forecast_eval_run,
            "forecast_eval_manifest_hash": eval_manifest_hash,
            "forecast_eval_origins_hash": eval_origins_hash,
            "raw_values_preserved": True,
            "candle_projection": "expand high/low only to enclose open/close",
            "projection_adjustments": adjustment_count,
        }
        encoded_diagnostics = json.dumps(
            _artifacts.sanitize(diagnostics),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        _artifacts.publish_artifact(
            rdir / "model_diagnostics.json",
            lambda path: path.write_text(encoded_diagnostics, encoding="utf-8"),
        )
        report = (
            "# Kronos synthetic-OHLCV Monte Carlo report\n\n"
            "Question: how does the unchanged strategy behave when its future market tail is "
            "generated by the pinned Kronos forecaster and every path is replayed through a fresh "
            "canonical engine portfolio?\n\n"
            f"Source validation run: `{from_run}`. Forecast evaluation run: "
            f"`{forecast_eval_run}`. Paths: {paths}. OOS account-return horizon: "
            f"{source_horizon}. Status: {summary.status}; risk grade: {summary.risk_grade}.\n\n"
            "Interpretation: Kronos is a calibrated stochastic generator, not a market oracle. "
            "Signals are recomputed from each synthetic OHLCV path; observed signals are never "
            "replayed. Weak calibration is a review warning, not automatic rejection.\n\n"
            f"Caveats: {'; '.join(summary.caveats)}. Raw model values are retained alongside "
            f"projected candles; {adjustment_count} high/low enclosure adjustments were recorded.\n"
        )
        _artifacts.publish_artifact(
            rdir / "report.md", lambda path: path.write_text(report, encoding="utf-8")
        )
        manifest: dict[str, Any] = {
            **payload,
            "run_id": identity.run_id,
            "source_run_hash": sha256_file(source_dir / "manifest.json"),
            "source_snapshot_id": snapshot_id,
            "source_research_cutoff": cutoff,
            "snapshot_id": snapshot_id,
            "research_cutoff": cutoff,
            "family": dataclasses.asdict(summary),
            "status": summary.status,
            "calibration": calibration,
            "pretrain": pretrain,
            "projection_adjustments": adjustment_count,
            "explanation": (
                "Synthetic path-risk evidence only; Kronos is not an edge oracle and this run "
                "does not authorize holdout, paper, or execution activity."
            ),
            **identity.manifest_fields(),
        }
        _artifacts.write_manifest(rdir, manifest)
    except (DataError, KeyError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        f"monte-carlo kronos -> run {identity.run_id}: "
        f"{summary.status}/{summary.risk_grade}, {paths} full-engine paths; "
        f"manifest at {rdir / 'manifest.json'}"
    )
