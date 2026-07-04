"""Rolling-origin forecast-skill evaluation glue.

For each origin ``t`` (bar index) the forecaster sees ONLY ``bars[t-context+1 .. t]``; the
realized outcome is ``close[t+horizon]/close[t] - 1``; both baselines are fit on the SAME
context window (no look-ahead anywhere). Per-origin child seeds are keyed on the ABSOLUTE
origin index, so an origin's score is independent of the stride that visits it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np

from alpha_cli._forecast import FORECAST_SEED_NS, pretrain_overlap
from alpha_core import Bar, DataError
from alpha_forecast import Forecaster
from alpha_validation import (
    ForecastEvalSummary,
    OriginScore,
    bootstrap_end_returns,
    rw_drift_end_returns,
    score_origin,
    summarize_scores,
)


def origin_indices(n_bars: int, *, context: int, horizon: int, stride: int) -> list[int]:
    """The evaluated origin bar indices: ``context-1, +stride, ...`` while the outcome fits."""
    if stride < 1:
        raise DataError(f"stride must be >= 1, got {stride}")
    if context < 2 or horizon < 1:
        raise DataError(f"context >= 2 and horizon >= 1 required, got {context}/{horizon}")
    out = list(range(context - 1, n_bars - horizon, stride))
    if not out:
        raise DataError(
            f"no origins fit: n={n_bars}, context={context}, horizon={horizon} "
            "(need context-1+horizon <= n-1)"
        )
    return out


@dataclass(frozen=True)
class OriginResult:
    """One scored origin: where it sat, which side of the pretrain cutoff, its metrics."""

    origin_index: int
    origin_ts: datetime
    pre_cutoff: bool
    score: OriginScore


@dataclass(frozen=True)
class ForecastEvalOutput:
    """The full rolling-origin evaluation: per-origin scores + overall and split summaries."""

    origins: tuple[OriginResult, ...]
    summary: ForecastEvalSummary
    summary_pre: ForecastEvalSummary | None
    summary_post: ForecastEvalSummary | None
    n_pre: int
    n_post: int
    pretrain: dict[str, Any]


def run_forecast_eval(
    bars: Sequence[Bar],
    *,
    forecaster: Forecaster,
    context: int,
    horizon: int,
    stride: int,
    sample_count: int,
    temperature: float,
    top_p: float,
    top_k: int,
    seed: int,
    cutoff: date,
    mean_block: float,
) -> ForecastEvalOutput:
    """Score the forecaster at every rolling origin against realized outcomes + baselines."""
    if sample_count < 2:
        raise DataError(
            f"eval needs sample_count >= 2 for distributional scores, got {sample_count}"
        )
    series = list(bars)
    indices = origin_indices(len(series), context=context, horizon=horizon, stride=stride)

    origins: list[OriginResult] = []
    master = seed & 0xFFFFFFFF
    for t in indices:
        window = series[t - context + 1 : t + 1]
        origin_seed = int(
            np.random.SeedSequence([master, FORECAST_SEED_NS, t]).generate_state(1)[0]
        )
        result = forecaster.forecast(
            window,
            horizon=horizon,
            sample_count=sample_count,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            seed=origin_seed,
        )
        origin_close = window[-1].close
        model_end = np.array(
            [p.close[-1] / origin_close - 1.0 for p in result.samples], dtype=np.float64
        )
        realized = series[t + horizon].close / origin_close - 1.0

        closes = np.array([b.close for b in window], dtype=np.float64)
        context_returns = closes[1:] / closes[:-1] - 1.0
        rw = rw_drift_end_returns(
            context_returns,
            horizon=horizon,
            n_samples=sample_count,
            rng=np.random.default_rng([master, FORECAST_SEED_NS, t, 1]),
        )
        boot = bootstrap_end_returns(
            context_returns,
            horizon=horizon,
            n_samples=sample_count,
            mean_block=mean_block,
            rng=np.random.default_rng([master, FORECAST_SEED_NS, t, 2]),
        )
        origins.append(
            OriginResult(
                origin_index=t,
                origin_ts=series[t].ts,
                pre_cutoff=series[t].ts.date() <= cutoff,
                score=score_origin(
                    model_end, realized, rw_end_returns=rw, bootstrap_end_returns_=boot
                ),
            )
        )

    pre = [o.score for o in origins if o.pre_cutoff]
    post = [o.score for o in origins if not o.pre_cutoff]
    evaluated = series[indices[0] - context + 1 : indices[-1] + horizon + 1]
    return ForecastEvalOutput(
        origins=tuple(origins),
        summary=summarize_scores([o.score for o in origins]),
        summary_pre=summarize_scores(pre) if pre else None,
        summary_post=summarize_scores(post) if post else None,
        n_pre=len(pre),
        n_post=len(post),
        pretrain=pretrain_overlap(evaluated, cutoff),
    )
