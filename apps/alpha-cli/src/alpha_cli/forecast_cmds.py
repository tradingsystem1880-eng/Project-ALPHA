"""``alpha forecast run`` / ``alpha forecast eval``: Kronos forecasting for one symbol.

``run`` samples future OHLCV paths over the trailing ``--context`` bars (outcome-cone
artifacts under ``data_dir/forecast/<run_id>/``); ``eval`` scores the forecaster at rolling
origins against realized outcomes and random-walk/bootstrap baselines, split pre/post the
assumed pretraining cutoff. ``--model fake`` selects the deterministic offline double used
by tests/demos. Pre-cutoff model inputs get a loud pretrain-overlap warning + manifest
flag (ADR-0009).
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping
from datetime import timedelta
from functools import partial
from pathlib import Path
from typing import Any, cast

import polars as pl
import typer

from alpha_cli import _artifacts, _forecast, _forecast_eval, _runner
from alpha_cli._artifacts import sanitize
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_research import (
    MarketSessionCloseV1,
    MarketStateContractV1,
    derive_market_state,
)
from alpha_validation import (
    ForecastCalibrationContractV1,
    ForecastCalibrationOriginV1,
    evaluate_frozen_calibration,
    fit_rolling_conformal_blend,
)

forecast_app = typer.Typer(
    help="Kronos foundation-model forecasting (probabilistic outcome cones)."
)

_load_bars = _runner.load_bars  # module seam: monkeypatched in tests

# shared with the strategy signal-cache precompute (alpha_cli._forecast_cache)
_forecaster_factory = _forecast._forecaster_factory
_provenance = _forecast._provenance


@forecast_app.command()
def run(
    symbol: str = typer.Argument(..., help="symbol in the store (run `alpha data pull` first)"),
    horizon: int = typer.Option(21, help="forecast steps (sessions)"),
    samples: int = typer.Option(100, help="Monte-Carlo sample paths"),
    context: int | None = typer.Option(
        None, help="trailing bars fed to the model (default: settings.forecast_context)"
    ),
    temperature: float = 1.0,
    top_p: float = 0.9,
    top_k: int = 0,
    model: str | None = typer.Option(
        None, help="HF id | local checkpoint path | 'fake' (default: settings.forecast_model)"
    ),
    model_revision: str | None = None,
    tokenizer: str | None = None,
    tokenizer_revision: str | None = None,
    device: str | None = typer.Option(
        None, help="cpu (bit-reproducible) | mps | cuda (default: settings.forecast_device)"
    ),
    as_of: str | None = typer.Option(
        None, "--as-of", help="ISO date: use only bars at/before this date (point-in-time)"
    ),
    seed: int | None = None,
    snapshot: str | None = None,
) -> None:
    """Sample future OHLCV paths for SYMBOL and write the outcome-cone artifacts."""
    settings = AlphaSettings()
    resolved_model = model if model is not None else settings.forecast_model
    resolved_model_rev = (
        model_revision if model_revision is not None else settings.forecast_model_revision
    )
    resolved_tokenizer = tokenizer if tokenizer is not None else settings.forecast_tokenizer
    resolved_tokenizer_rev = (
        tokenizer_revision
        if tokenizer_revision is not None
        else settings.forecast_tokenizer_revision
    )
    resolved_device = device if device is not None else settings.forecast_device
    resolved_context = context if context is not None else settings.forecast_context
    master_seed = seed if seed is not None else settings.random_seed
    sampling_seed = _forecast.forecast_seed(master_seed)

    try:
        as_of_dt = _runner.parse_as_of(as_of)
        bars, snapshot_id = _load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=as_of_dt,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    forecaster = _forecaster_factory(
        model=resolved_model,
        model_revision=resolved_model_rev,
        tokenizer=resolved_tokenizer,
        tokenizer_revision=resolved_tokenizer_rev,
        device=resolved_device,
        hub_cache=settings.forecast_hub_cache,
        local_files_only=settings.forecast_local_only,
    )

    try:
        out = _forecast.run_forecast(
            bars,
            forecaster=forecaster,
            context=resolved_context,
            horizon=horizon,
            sample_count=samples,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            seed=sampling_seed,
            as_of=as_of_dt,
            cutoff=settings.forecast_pretrain_cutoff,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    # The id pins everything the sampled paths depend on — incl. the model input recency
    # (context_last_ts), so a grown store cannot silently shift a fixed --as-of run.
    payload: dict[str, Any] = {
        "command": "forecast_run",
        "symbol": symbol,
        "snapshot": snapshot,
        "model": resolved_model,
        "model_revision": resolved_model_rev,
        "tokenizer": resolved_tokenizer,
        "tokenizer_revision": resolved_tokenizer_rev,
        "device": resolved_device,
        "context": resolved_context,
        "horizon": horizon,
        "samples": samples,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "seed": master_seed,
        "as_of": as_of,
        "last_bar_ts": out.context_last_ts.isoformat(),
    }
    observed_history = bars
    identity = _runner.run_identity_for(
        payload,
        source_fingerprint=_runner.source_fingerprint(observed_history),
        snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot_id),
    )
    run_id = identity.run_id
    rdir = settings.data_dir / "forecast" / run_id

    prov = _provenance(forecaster, model=resolved_model)
    manifest = sanitize(
        {
            "schema_version": 1,
            "run_id": run_id,
            "command": "forecast_run",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
            "research_cutoff": as_of,
            "model": prov,
            "params": {
                "context": resolved_context,
                "horizon": horizon,
                "samples": samples,
                "temperature": temperature,
                "top_p": top_p,
                "top_k": top_k,
                "seed": master_seed,
                "sampling_seed": sampling_seed,
            },
            "origin": {
                "origin_ts": out.result.origin_ts.isoformat(),
                "n_context": out.n_context,
                "first_ts": out.context_first_ts.isoformat(),
                "last_ts": out.context_last_ts.isoformat(),
                "as_of": as_of,
            },
            "pretrain": out.pretrain,
            "summary": {
                "median_end_return": out.median_end_return,
                "p05_end_return": out.p05_end_return,
                "p95_end_return": out.p95_end_return,
                "prob_up": out.prob_up,
            },
            **identity.manifest_fields(),
        }
    )
    _forecast.write_forecast_run(rdir, manifest=manifest, out=out, history=observed_history)

    typer.echo(
        f"forecast {symbol} -> run {run_id}: median {out.median_end_return:+.2%} "
        f"[p05 {out.p05_end_return:+.2%}, p95 {out.p95_end_return:+.2%}] over {horizon} steps "
        f"({samples} paths), P(up) {out.prob_up:.0%}\n"
        f"  model {prov.get('model_id')}@{prov.get('model_revision')} "
        f"device={prov.get('device')} determinism={prov.get('determinism')}\n"
        f"  manifest at {rdir / 'manifest.json'}"
    )
    if out.pretrain["overlap"]:
        typer.secho(
            f"WARNING: context bars overlap the assumed Kronos pretraining window "
            f"(<= {out.pretrain['cutoff']}) — results may be memorized, not predicted "
            f"(ADR-0009)",
            fg=typer.colors.YELLOW,
        )


def _summary_line(summary: Any) -> str:
    return (
        f"CRPS {summary.crps_mean:.4f} (skill vs RW {summary.skill_vs_rw:+.1%}, "
        f"vs bootstrap {summary.skill_vs_bootstrap:+.1%}), coverage 50/80/90 "
        f"{summary.coverage50:.0%}/{summary.coverage80:.0%}/{summary.coverage90:.0%}, "
        f"hit rate {summary.hit_rate:.0%}"
    )


def _write_json_artifact(path: Path, *, document: object) -> None:
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":"), allow_nan=False)
    path.write_text(encoded + "\n", encoding="utf-8")


def _row_mean(rows: list[dict[str, Any]], field: str) -> float:
    return sum(float(row[field]) for row in rows) / len(rows)


def _experiment(data_dir: Any, project_id: str, experiment_id: str) -> dict[str, object]:
    project = ControlStore(data_dir).get_project(project_id)
    experiments = project.get("experiments")
    if not isinstance(experiments, list):
        raise DataError(f"project {project_id!r} has corrupt experiment projections")
    for candidate in experiments:
        if isinstance(candidate, dict) and candidate.get("experiment_id") == experiment_id:
            return cast(dict[str, object], candidate)
    raise DataError(f"experiment {experiment_id!r} is not linked to project {project_id!r}")


def _governed_contracts(
    experiment: Mapping[str, object],
) -> tuple[MarketStateContractV1, ForecastCalibrationContractV1]:
    stage = experiment.get("stage_config")
    if not isinstance(stage, Mapping):
        raise DataError("governed calibration requires experiment stage_config")
    market = stage.get("market_state")
    calibration = stage.get("kronos_calibration")
    if not isinstance(market, Mapping) or not isinstance(calibration, Mapping):
        raise DataError("experiment must freeze both market_state and kronos_calibration contracts")
    return (
        MarketStateContractV1.from_dict(cast(Mapping[str, object], market)),
        ForecastCalibrationContractV1.from_dict(cast(Mapping[str, object], calibration)),
    )


def _calibrated_artifacts(
    *,
    out: _forecast_eval.ForecastEvalOutput,
    experiment: Mapping[str, object],
    market_contract: MarketStateContractV1,
    calibration_contract: ForecastCalibrationContractV1,
    settings: AlphaSettings,
    as_of: Any,
) -> tuple[dict[str, object], dict[str, pl.DataFrame], dict[str, object]]:
    snapshot_id = experiment.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise DataError("governed calibration experiment requires an immutable snapshot")
    close_maps: dict[str, dict[Any, Any]] = {}
    for symbol in market_contract.universe:
        bars, _ = _load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot_id,
            as_of=as_of,
        )
        close_maps[symbol] = {bar.ts.date(): bar for bar in bars}
    aligned = sorted(set.intersection(*(set(rows) for rows in close_maps.values())))
    observations = [
        MarketSessionCloseV1(
            session=session,
            available_at=close_maps[market_contract.benchmark][session].ts + timedelta(hours=23),
            closes=tuple(close_maps[symbol][session].close for symbol in market_contract.universe),
        )
        for session in aligned
    ]
    market_state = derive_market_state(market_contract, observations)
    state_by_session = {point.session: point for point in market_state.points}
    calibration_origins: list[ForecastCalibrationOriginV1] = []
    eligibility: dict[str, bool] = {}
    for origin in out.origins:
        point = state_by_session.get(origin.origin_ts.date())
        origin_id = origin.origin_ts.isoformat()
        state_key = point.state_key if point is not None else "unavailable"
        calibration_origins.append(
            ForecastCalibrationOriginV1(
                origin_id=origin_id,
                model_end_returns=origin.model_end_returns,
                random_walk_end_returns=origin.random_walk_end_returns,
                observed_end_return=origin.observed_end_return,
                state_key=state_key,
            )
        )
        eligibility[origin_id] = point.eligible if point is not None else False
    validation_count = calibration_contract.minimum_validation_origins
    if len(calibration_origins) <= validation_count:
        raise DataError(
            "governed calibration needs OOS origins after the frozen validation fit: "
            f"{len(calibration_origins)} <= {validation_count}"
        )
    fit = fit_rolling_conformal_blend(calibration_contract, calibration_origins[:validation_count])
    evaluated = evaluate_frozen_calibration(
        fit,
        calibration_origins[validation_count:],
        market_state_eligibility={
            origin.origin_id: eligibility[origin.origin_id]
            for origin in calibration_origins[validation_count:]
        },
    )
    by_id = {origin.origin_ts.isoformat(): origin for origin in out.origins}
    calibrated_rows: list[dict[str, Any]] = []
    for evaluated_row in evaluated:
        origin = by_id[evaluated_row.origin_id]
        assessment = evaluated_row.assessment
        calibrated_rows.append(
            {
                "origin_index": origin.origin_index,
                "origin_ts": origin.origin_ts,
                "state_key": evaluated_row.state_key,
                "market_state_eligible": evaluated_row.market_state_eligible,
                "raw_crps": evaluated_row.raw_crps,
                "calibrated_crps": evaluated_row.calibrated_crps,
                "raw_pinball": evaluated_row.raw_pinball,
                "calibrated_pinball": evaluated_row.calibrated_pinball,
                "raw_covered": evaluated_row.raw_covered,
                "calibrated_covered": evaluated_row.calibrated_covered,
                "candidate": assessment.candidate,
                "signal": assessment.signal,
                "blocker_codes": list(assessment.blocker_codes),
                "median_end_return": assessment.median_end_return,
                "interval_low": assessment.interval_low,
                "interval_high": assessment.interval_high,
                "interval_width": assessment.interval_width,
                "calibration_fit_sha256": assessment.calibration_fit_sha256,
                "market_state_artifact_sha256": market_state.artifact_sha256,
                "market_state_contract_sha256": market_state.contract_sha256,
            }
        )
    calibrated_frame = pl.DataFrame(calibrated_rows).sort("origin_index")
    eligible_rows = [row for row in calibrated_rows if row["market_state_eligible"]]
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in eligible_rows:
        grouped.setdefault(str(row["state_key"]), []).append(row)
    state_rows = []
    for state_key in sorted(grouped):
        state_group = grouped[state_key]
        fallback = len(state_group) < market_contract.minimum_state_samples
        selected = eligible_rows if fallback else state_group
        state_rows.append(
            {
                "state_key": state_key,
                "sample_count": len(state_group),
                "minimum_samples": market_contract.minimum_state_samples,
                "used_pooled_fallback": fallback,
                "evaluated_count": len(selected),
                "raw_crps": _row_mean(selected, "raw_crps"),
                "calibrated_crps": _row_mean(selected, "calibrated_crps"),
                "candidate_rate": sum(row["candidate"] is not None for row in selected)
                / len(selected),
            }
        )
    reliability = pl.DataFrame(
        [
            {
                "split": "validation",
                "nominal_coverage": calibration_contract.coverage_level,
                **fit.validation_metrics.to_dict(),
            },
            {
                "split": "oos",
                "nominal_coverage": calibration_contract.coverage_level,
                "evaluated_origins": len(calibrated_rows),
                "raw_crps": _row_mean(calibrated_rows, "raw_crps"),
                "calibrated_crps": _row_mean(calibrated_rows, "calibrated_crps"),
                "raw_pinball": _row_mean(calibrated_rows, "raw_pinball"),
                "calibrated_pinball": _row_mean(calibrated_rows, "calibrated_pinball"),
                "raw_coverage": sum(bool(row["raw_covered"]) for row in calibrated_rows)
                / len(calibrated_rows),
                "calibrated_coverage": sum(
                    bool(row["calibrated_covered"]) for row in calibrated_rows
                )
                / len(calibrated_rows),
            },
        ]
    )
    points = pl.DataFrame([point.to_dict() for point in market_state.points]).with_columns(
        pl.col("session").str.to_date(),
        pl.col("available_at").str.to_datetime(time_zone="UTC"),
    )
    documents: dict[str, object] = {
        "market_state.json": market_state.to_dict(),
        "calibration_fit.json": fit.to_dict(),
    }
    frames = {
        "market_state.parquet": points,
        "calibrated_origins.parquet": calibrated_frame,
        "state_performance.parquet": pl.DataFrame(
            state_rows,
            schema={
                "state_key": pl.String,
                "sample_count": pl.Int64,
                "minimum_samples": pl.Int64,
                "used_pooled_fallback": pl.Boolean,
                "evaluated_count": pl.Int64,
                "raw_crps": pl.Float64,
                "calibrated_crps": pl.Float64,
                "candidate_rate": pl.Float64,
            },
        ),
        "calibration_reliability.parquet": reliability,
    }
    candidate_origins = sum(row["candidate"] is not None for row in calibrated_rows)
    summary = {
        "market_state_artifact_sha256": market_state.artifact_sha256,
        "market_state_contract_sha256": market_state.contract_sha256,
        "calibration_fit_sha256": fit.fit_sha256,
        "calibration_contract_sha256": calibration_contract.contract_sha256,
        "validation_origins": validation_count,
        "oos_origins": len(calibrated_rows),
        "candidate_origins": candidate_origins,
        "candidate_status": (
            "candidate_available" if candidate_origins else "rejected_or_inconclusive"
        ),
        "authority": "research_candidate_only_no_paper_or_order_authority",
    }
    return documents, frames, summary


@forecast_app.command(name="eval")
def evaluate(
    symbol: str = typer.Argument(..., help="symbol in the store (run `alpha data pull` first)"),
    horizon: int = typer.Option(21, help="forecast steps per origin (sessions)"),
    stride: int = typer.Option(21, help="bars between rolling origins"),
    samples: int = typer.Option(30, help="Monte-Carlo sample paths per origin"),
    context: int | None = typer.Option(
        None, help="trailing bars fed to the model (default: settings.forecast_context)"
    ),
    temperature: float = 1.0,
    top_p: float = 0.9,
    top_k: int = 0,
    mean_block: float = typer.Option(5.0, help="stationary-bootstrap mean block (baseline)"),
    model: str | None = typer.Option(
        None, help="HF id | local checkpoint path | 'fake' (default: settings.forecast_model)"
    ),
    model_revision: str | None = None,
    tokenizer: str | None = None,
    tokenizer_revision: str | None = None,
    device: str | None = None,
    seed: int | None = None,
    snapshot: str | None = None,
    as_of: str | None = typer.Option(None, "--as-of", help="inclusive research cutoff YYYY-MM-DD"),
    project_id: str | None = typer.Option(
        None, "--project-id", help="governed project containing the immutable model experiment"
    ),
    experiment_id: str | None = typer.Option(
        None, "--experiment-id", help="experiment with frozen market-state/calibration contracts"
    ),
) -> None:
    """Score SYMBOL's forecaster at rolling origins vs realized outcomes + baselines."""
    settings = AlphaSettings()
    resolved_model = model if model is not None else settings.forecast_model
    resolved_model_rev = (
        model_revision if model_revision is not None else settings.forecast_model_revision
    )
    resolved_tokenizer = tokenizer if tokenizer is not None else settings.forecast_tokenizer
    resolved_tokenizer_rev = (
        tokenizer_revision
        if tokenizer_revision is not None
        else settings.forecast_tokenizer_revision
    )
    resolved_device = device if device is not None else settings.forecast_device
    resolved_context = context if context is not None else settings.forecast_context
    master_seed = seed if seed is not None else settings.random_seed
    experiment: dict[str, object] | None = None
    market_contract: MarketStateContractV1 | None = None
    calibration_contract: ForecastCalibrationContractV1 | None = None
    if (project_id is None) != (experiment_id is None):
        raise typer.BadParameter("--project-id and --experiment-id must be supplied together")
    if project_id is not None and experiment_id is not None:
        try:
            experiment = _experiment(settings.data_dir, project_id, experiment_id)
            market_contract, calibration_contract = _governed_contracts(experiment)
            experiment_snapshot = experiment.get("snapshot_id")
            if not isinstance(experiment_snapshot, str) or not experiment_snapshot:
                raise DataError("governed experiment has no immutable snapshot")
            if snapshot is not None and snapshot != experiment_snapshot:
                raise DataError("--snapshot differs from the governed experiment snapshot")
            if symbol not in market_contract.universe:
                raise DataError("forecast symbol is not in the frozen market-state universe")
            snapshot = experiment_snapshot
        except DataError as exc:
            raise typer.BadParameter(str(exc)) from exc

    try:
        as_of_dt = _runner.parse_as_of(as_of)
        bars, snapshot_id = _load_bars(
            symbol,
            data_dir=settings.data_dir,
            snapshot_id=snapshot,
            as_of=as_of_dt,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    forecaster = _forecaster_factory(
        model=resolved_model,
        model_revision=resolved_model_rev,
        tokenizer=resolved_tokenizer,
        tokenizer_revision=resolved_tokenizer_rev,
        device=resolved_device,
        hub_cache=settings.forecast_hub_cache,
        local_files_only=settings.forecast_local_only,
    )

    try:
        out = _forecast_eval.run_forecast_eval(
            bars,
            forecaster=forecaster,
            context=resolved_context,
            horizon=horizon,
            stride=stride,
            sample_count=samples,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            seed=master_seed,
            cutoff=settings.forecast_pretrain_cutoff,
            mean_block=mean_block,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc

    calibration_documents: dict[str, object] = {}
    calibration_frames: dict[str, pl.DataFrame] = {}
    calibration_summary: dict[str, object] | None = None
    if experiment is not None and market_contract is not None and calibration_contract is not None:
        try:
            calibration_documents, calibration_frames, calibration_summary = _calibrated_artifacts(
                out=out,
                experiment=experiment,
                market_contract=market_contract,
                calibration_contract=calibration_contract,
                settings=settings,
                as_of=as_of_dt,
            )
        except DataError as exc:
            raise typer.BadParameter(str(exc)) from exc

    payload: dict[str, Any] = {
        "command": "forecast_eval",
        "symbol": symbol,
        "snapshot": snapshot,
        "model": resolved_model,
        "model_revision": resolved_model_rev,
        "tokenizer": resolved_tokenizer,
        "tokenizer_revision": resolved_tokenizer_rev,
        "device": resolved_device,
        "context": resolved_context,
        "horizon": horizon,
        "stride": stride,
        "samples": samples,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "mean_block": mean_block,
        "seed": master_seed,
        "research_cutoff": as_of,
        "first_origin_ts": out.origins[0].origin_ts.isoformat(),
        "last_origin_ts": out.origins[-1].origin_ts.isoformat(),
    }
    if calibration_summary is not None:
        payload["governed_modeling"] = {
            "project_id": project_id,
            "experiment_id": experiment_id,
            "market_state_contract_sha256": calibration_summary["market_state_contract_sha256"],
            "calibration_contract_sha256": calibration_summary["calibration_contract_sha256"],
        }
    identity = _runner.run_identity_for(
        payload,
        source_fingerprint=_runner.source_fingerprint(bars),
        snapshot_hash=_runner.verified_snapshot_hash(settings.data_dir, snapshot_id),
    )
    run_id = identity.run_id
    rdir = settings.data_dir / "forecast" / run_id
    rdir.mkdir(parents=True, exist_ok=True)

    prov = _provenance(forecaster, model=resolved_model)
    manifest_payload: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "command": "forecast_eval",
        "symbol": symbol,
        "snapshot_id": snapshot_id,
        "research_cutoff": as_of,
        "model": prov,
        "params": {
            "context": resolved_context,
            "horizon": horizon,
            "stride": stride,
            "samples": samples,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "mean_block": mean_block,
            "seed": master_seed,
        },
        "origins": {
            "n": len(out.origins),
            "first_ts": out.origins[0].origin_ts.isoformat(),
            "last_ts": out.origins[-1].origin_ts.isoformat(),
        },
        "pretrain": out.pretrain,
        "summary": dataclasses.asdict(out.summary),
        "summary_pre_cutoff": (
            dataclasses.asdict(out.summary_pre) if out.summary_pre is not None else None
        ),
        "summary_post_cutoff": (
            dataclasses.asdict(out.summary_post) if out.summary_post is not None else None
        ),
        "n_origins_pre": out.n_pre,
        "n_origins_post": out.n_post,
        **identity.manifest_fields(),
    }
    if calibration_summary is not None:
        manifest_payload["governed_calibration"] = calibration_summary
    manifest = sanitize(manifest_payload)
    include_samples = calibration_summary is not None
    origins = pl.DataFrame(
        [
            {
                "origin_index": o.origin_index,
                "origin_ts": o.origin_ts,
                "pre_cutoff": o.pre_cutoff,
                **(
                    {
                        "model_end_returns": list(o.model_end_returns),
                        "random_walk_end_returns": list(o.random_walk_end_returns),
                        "observed_end_return": o.observed_end_return,
                    }
                    if include_samples
                    else {}
                ),
                **dataclasses.asdict(o.score),
            }
            for o in out.origins
        ]
    )
    _artifacts.publish_artifact(rdir / "origins.parquet", origins.write_parquet)
    for name, document in calibration_documents.items():
        _artifacts.publish_artifact(rdir / name, partial(_write_json_artifact, document=document))
    for name, frame in calibration_frames.items():
        _artifacts.publish_artifact(rdir / name, frame.write_parquet)
    _artifacts.write_manifest(rdir, manifest)

    typer.echo(
        f"forecast-eval {symbol} -> run {run_id}: {len(out.origins)} origins, "
        f"{_summary_line(out.summary)}\n"
        f"  model {prov.get('model_id')}@{prov.get('model_revision')} "
        f"device={prov.get('device')} determinism={prov.get('determinism')}\n"
        f"  manifest at {rdir / 'manifest.json'}"
    )
    if out.summary_pre is not None:
        typer.echo(f"  pre-cutoff  ({out.n_pre} origins): {_summary_line(out.summary_pre)}")
    if out.summary_post is not None:
        typer.echo(f"  post-cutoff ({out.n_post} origins): {_summary_line(out.summary_post)}")
    else:
        typer.secho(
            "WARNING: no post-cutoff origins — every skill number overlaps the assumed "
            "Kronos pretraining window (ADR-0009); extend the data past "
            f"{out.pretrain['cutoff']} for an honest read",
            fg=typer.colors.YELLOW,
        )
