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
from datetime import UTC, date, datetime, time
from typing import Any

import polars as pl
import typer

from alpha_cli import _forecast, _forecast_eval, _runner
from alpha_cli._artifacts import sanitize
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_forecast import Forecaster

forecast_app = typer.Typer(
    help="Kronos foundation-model forecasting (probabilistic outcome cones)."
)

_load_bars = _runner.load_bars  # module seam: monkeypatched in tests


def _forecaster_factory(
    *,
    model: str,
    model_revision: str,
    tokenizer: str,
    tokenizer_revision: str,
    device: str,
) -> Forecaster:
    """``fake`` -> the offline double; anything else -> a HF id / local checkpoint path."""
    if model == "fake":
        from alpha_forecast import FakeForecaster

        return FakeForecaster()
    from alpha_forecast import KronosForecaster

    return KronosForecaster(
        model_id=model,
        model_revision=model_revision,
        tokenizer_id=tokenizer,
        tokenizer_revision=tokenizer_revision,
        device=device,
    )


def _provenance(forecaster: Forecaster, *, model: str) -> dict[str, Any]:
    prov = getattr(forecaster, "provenance", None)
    if callable(prov):
        result: dict[str, Any] = dict(prov())
        return result
    return {
        "model_id": model,
        "model_revision": None,
        "tokenizer_id": None,
        "tokenizer_revision": None,
        "device": None,
        "torch_version": None,
        "vendor_sha": None,
        "determinism": "exact",
    }


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

    as_of_dt: datetime | None = None
    if as_of is not None:
        try:
            as_of_dt = datetime.combine(date.fromisoformat(as_of), time(23, 59, 59), tzinfo=UTC)
        except ValueError:
            raise typer.BadParameter(f"--as-of must be an ISO date, got {as_of!r}") from None

    bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
    forecaster = _forecaster_factory(
        model=resolved_model,
        model_revision=resolved_model_rev,
        tokenizer=resolved_tokenizer,
        tokenizer_revision=resolved_tokenizer_rev,
        device=resolved_device,
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
    run_id = _runner.run_id_for(payload)
    rdir = settings.data_dir / "forecast" / run_id

    prov = _provenance(forecaster, model=resolved_model)
    manifest = sanitize(
        {
            "schema_version": 1,
            "run_id": run_id,
            "command": "forecast_run",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
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
        }
    )
    history = [b for b in bars if as_of_dt is None or b.ts <= as_of_dt]
    _forecast.write_forecast_run(rdir, manifest=manifest, out=out, history=history)

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

    bars, snapshot_id = _load_bars(symbol, data_dir=settings.data_dir, snapshot_id=snapshot)
    forecaster = _forecaster_factory(
        model=resolved_model,
        model_revision=resolved_model_rev,
        tokenizer=resolved_tokenizer,
        tokenizer_revision=resolved_tokenizer_rev,
        device=resolved_device,
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
        "first_origin_ts": out.origins[0].origin_ts.isoformat(),
        "last_origin_ts": out.origins[-1].origin_ts.isoformat(),
    }
    run_id = _runner.run_id_for(payload)
    rdir = settings.data_dir / "forecast" / run_id
    rdir.mkdir(parents=True, exist_ok=True)

    prov = _provenance(forecaster, model=resolved_model)
    manifest = sanitize(
        {
            "schema_version": 1,
            "run_id": run_id,
            "command": "forecast_eval",
            "symbol": symbol,
            "snapshot_id": snapshot_id,
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
        }
    )
    (rdir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False), encoding="utf-8"
    )
    pl.DataFrame(
        [
            {
                "origin_index": o.origin_index,
                "origin_ts": o.origin_ts,
                "pre_cutoff": o.pre_cutoff,
                **dataclasses.asdict(o.score),
            }
            for o in out.origins
        ]
    ).write_parquet(rdir / "origins.parquet")

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
