"""Forecast-run glue: PIT slice -> Forecaster -> summary + byte-stable artifacts.

The DAG's sanctioned composition point for alpha_forecast + the CLI store. The model
consumes only the trailing ``context`` bars at/<= the as-of instant; the ``pretrain`` block
records whether that window overlaps Kronos's assumed pretraining period (ADR-0009 leakage
policy: warn + flag, never block). Artifacts: ``manifest.json`` (byte-stable) +
``paths.parquet`` (per-sample OHLCV, long) + ``quantiles.parquet`` (per-step close bands)
+ ``history.parquet`` (as-of-filtered close tail for the web fan chart).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl

from alpha_cli._artifacts import write_manifest
from alpha_cli._atomic import publish
from alpha_core import Bar, DataError
from alpha_forecast import Forecaster, ForecastResult, close_quantiles

FORECAST_SEED_NS = 0x464F5243  # "FORC": forecast children of the master seed (spec §11.4)
_HISTORY_TAIL = 120  # closes stored for the fan chart's history segment


def _forecaster_factory(
    *,
    model: str,
    model_revision: str,
    tokenizer: str,
    tokenizer_revision: str,
    device: str,
    hub_cache: Path | None = None,
    local_files_only: bool = False,
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
        cache_dir=hub_cache,
        local_files_only=local_files_only,
    )


def _provenance(forecaster: Forecaster, *, model: str) -> dict[str, Any]:
    """The forecaster's manifest block (a stub for doubles without ``provenance()``)."""
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


def forecast_seed(master: int) -> int:
    """Derive the forecast-sampling child seed from the master seed (independent stream)."""
    return int(np.random.SeedSequence([master, FORECAST_SEED_NS]).generate_state(1)[0])


def pretrain_overlap(bars: Sequence[Bar], cutoff: date) -> dict[str, Any]:
    """The leakage block for a model input window: which bars fall inside pretraining."""
    inside = [b for b in bars if b.ts.date() <= cutoff]
    return {
        "cutoff": cutoff.isoformat(),
        "overlap": bool(inside),
        "overlap_start": inside[0].ts.date().isoformat() if inside else None,
        "overlap_end": inside[-1].ts.date().isoformat() if inside else None,
    }


@dataclass(frozen=True)
class ForecastRunOutput:
    """One completed forecast: sampled paths + derived bands + leakage + summary scalars."""

    result: ForecastResult
    quantiles: dict[float, tuple[float, ...]]
    pretrain: dict[str, Any]
    n_context: int
    context_first_ts: datetime
    context_last_ts: datetime
    prob_up: float
    median_end_return: float
    p05_end_return: float
    p95_end_return: float


def run_forecast(
    bars: Sequence[Bar],
    *,
    forecaster: Forecaster,
    context: int,
    horizon: int,
    sample_count: int,
    temperature: float,
    top_p: float,
    top_k: int,
    seed: int,
    as_of: datetime | None,
    cutoff: date,
) -> ForecastRunOutput:
    """Slice the PIT window, sample the forecaster, summarize. Fails loud on thin data."""
    if as_of is not None:
        bars = [b for b in bars if b.ts <= as_of]
        if not bars:
            raise DataError(f"no bars at or before as-of {as_of.isoformat()}")
    if len(bars) < context:
        raise DataError(f"need >= {context} context bars, got {len(bars)}")
    window = list(bars[-context:])

    result = forecaster.forecast(
        window,
        horizon=horizon,
        sample_count=sample_count,
        temperature=temperature,
        top_p=top_p,
        top_k=top_k,
        seed=seed,
    )
    quantiles = close_quantiles(result)
    origin_close = window[-1].close
    end_closes = np.array([p.close[-1] for p in result.samples], dtype=np.float64)
    return ForecastRunOutput(
        result=result,
        quantiles=quantiles,
        pretrain=pretrain_overlap(window, cutoff),
        n_context=len(window),
        context_first_ts=window[0].ts,
        context_last_ts=window[-1].ts,
        prob_up=float(np.mean(end_closes > origin_close)),
        median_end_return=quantiles[0.5][-1] / origin_close - 1.0,
        p05_end_return=quantiles[0.05][-1] / origin_close - 1.0,
        p95_end_return=quantiles[0.95][-1] / origin_close - 1.0,
    )


def write_forecast_run(
    rdir: Path, *, manifest: dict[str, Any], out: ForecastRunOutput, history: Sequence[Bar]
) -> None:
    """Write the run's artifacts. ``history`` must already be as-of-filtered (PIT)."""
    rdir.mkdir(parents=True, exist_ok=True)
    r = out.result
    paths = pl.DataFrame(
        [
            {
                "sample": s,
                "step": i + 1,
                "ts": r.step_ts[i],
                "open": p.open[i],
                "high": p.high[i],
                "low": p.low[i],
                "close": p.close[i],
                "volume": p.volume[i],
            }
            for s, p in enumerate(r.samples)
            for i in range(r.horizon)
        ]
    )
    publish(rdir / "paths.parquet", paths.write_parquet)

    q = out.quantiles
    means = np.array([p.close for p in r.samples], dtype=np.float64).mean(axis=0)
    quantiles = pl.DataFrame(
        [
            {
                "step": i + 1,
                "ts": r.step_ts[i],
                "q05": q[0.05][i],
                "q25": q[0.25][i],
                "q50": q[0.5][i],
                "q75": q[0.75][i],
                "q95": q[0.95][i],
                "mean": float(means[i]),
            }
            for i in range(r.horizon)
        ]
    )
    publish(rdir / "quantiles.parquet", quantiles.write_parquet)

    tail = list(history)[-_HISTORY_TAIL:]
    history_frame = pl.DataFrame({"ts": [b.ts for b in tail], "close": [b.close for b in tail]})
    publish(rdir / "history.parquet", history_frame.write_parquet)
    write_manifest(rdir, manifest)
