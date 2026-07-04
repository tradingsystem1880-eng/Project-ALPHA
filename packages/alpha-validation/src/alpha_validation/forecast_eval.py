"""Forecast-skill primitives: sample-based CRPS, pinball, coverage, and honest baselines.

Everything operates in horizon end-return space (scale-free): a forecaster's sampled
end-of-horizon returns vs the realized one, judged against random-walk-with-drift and
stationary-bootstrap baselines built from the SAME context window (no look-ahead). Pure
numpy, fail-loud — the engine-agnostic layer the CLI's rolling-origin eval composes.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_validation.bootstrap import stationary_bootstrap_indices
from alpha_validation.metrics import FloatArray


def _check_samples(samples: FloatArray, name: str) -> FloatArray:
    arr = np.asarray(samples, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"{name} needs >= 2 samples, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} must be finite")
    return arr


def crps_sample(samples: FloatArray, observed: float) -> float:
    """Sample-based CRPS: ``E|X - y| - 0.5 E|X - X'|`` (lower = sharper + better calibrated)."""
    arr = _check_samples(samples, "crps samples")
    if not np.isfinite(observed):
        raise DataError(f"observed must be finite, got {observed!r}")
    term1 = float(np.mean(np.abs(arr - observed)))
    term2 = float(np.mean(np.abs(arr[:, None] - arr[None, :]))) / 2.0
    return term1 - term2


def pinball_loss(samples: FloatArray, observed: float, q: float) -> float:
    """Pinball loss of the empirical ``q``-quantile forecast against ``observed``."""
    arr = _check_samples(samples, "pinball samples")
    if not 0.0 < q < 1.0:
        raise DataError(f"pinball q must be in (0, 1), got {q}")
    forecast = float(np.quantile(arr, q))
    diff = observed - forecast
    return q * diff if diff >= 0.0 else (q - 1.0) * diff


def central_coverage(samples: FloatArray, observed: float, level: float) -> bool:
    """Whether ``observed`` falls inside the central ``level`` interval of the samples."""
    arr = _check_samples(samples, "coverage samples")
    if not 0.0 < level < 1.0:
        raise DataError(f"coverage level must be in (0, 1), got {level}")
    tail = (1.0 - level) / 2.0
    lo, hi = np.quantile(arr, [tail, 1.0 - tail])
    return bool(lo <= observed <= hi)


def _check_context_returns(context_returns: FloatArray) -> FloatArray:
    arr = np.asarray(context_returns, dtype=np.float64)
    if arr.ndim != 1 or arr.size < 2:
        raise DataError(f"context returns need >= 2 observations, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))) or bool(np.any(arr <= -1.0)):
        raise DataError("context returns must be finite and > -1")
    return arr


def rw_drift_end_returns(
    context_returns: FloatArray, *, horizon: int, n_samples: int, rng: np.random.Generator
) -> FloatArray:
    """Random-walk-with-drift baseline: iid normal log-steps fit on the context window."""
    arr = _check_context_returns(context_returns)
    if horizon < 1 or n_samples < 2:
        raise DataError(f"horizon >= 1 and n_samples >= 2 required, got {horizon}/{n_samples}")
    log_returns = np.log1p(arr)
    mu, sigma = float(np.mean(log_returns)), float(np.std(log_returns))
    steps = rng.normal(mu, sigma, size=(n_samples, horizon))
    result: FloatArray = np.expm1(np.sum(steps, axis=1))
    return result


def bootstrap_end_returns(
    context_returns: FloatArray,
    *,
    horizon: int,
    n_samples: int,
    mean_block: float,
    rng: np.random.Generator,
) -> FloatArray:
    """Stationary-bootstrap baseline: resample context return blocks, compound ``horizon``."""
    arr = _check_context_returns(context_returns)
    if horizon < 1 or n_samples < 2:
        raise DataError(f"horizon >= 1 and n_samples >= 2 required, got {horizon}/{n_samples}")
    idx = stationary_bootstrap_indices(
        arr.size, mean_block=mean_block, n_resamples=n_samples, rng=rng, length=horizon
    )
    result: FloatArray = np.prod(1.0 + arr[idx], axis=1) - 1.0
    return result


@dataclass(frozen=True)
class OriginScore:
    """All skill metrics for one rolling-origin forecast (end-return space)."""

    realized_end_return: float
    median_end_return: float
    crps: float
    crps_rw: float
    crps_bootstrap: float
    pinball_q25: float
    pinball_q75: float
    cover50: bool
    cover80: bool
    cover90: bool
    hit: bool


def score_origin(
    model_end_returns: FloatArray,
    realized_end_return: float,
    *,
    rw_end_returns: FloatArray,
    bootstrap_end_returns_: FloatArray,
) -> OriginScore:
    """Score one origin's sampled end returns against the realized one + both baselines."""
    model = _check_samples(model_end_returns, "model end returns")
    if not np.isfinite(realized_end_return):
        raise DataError(f"realized end return must be finite, got {realized_end_return!r}")
    median = float(np.median(model))
    return OriginScore(
        realized_end_return=float(realized_end_return),
        median_end_return=median,
        crps=crps_sample(model, realized_end_return),
        crps_rw=crps_sample(rw_end_returns, realized_end_return),
        crps_bootstrap=crps_sample(bootstrap_end_returns_, realized_end_return),
        pinball_q25=pinball_loss(model, realized_end_return, 0.25),
        pinball_q75=pinball_loss(model, realized_end_return, 0.75),
        cover50=central_coverage(model, realized_end_return, 0.5),
        cover80=central_coverage(model, realized_end_return, 0.8),
        cover90=central_coverage(model, realized_end_return, 0.9),
        hit=(median > 0.0) == (realized_end_return > 0.0),
    )


@dataclass(frozen=True)
class ForecastEvalSummary:
    """Aggregate forecast skill over a set of rolling origins."""

    n_origins: int
    crps_mean: float
    crps_rw_mean: float
    crps_bootstrap_mean: float
    skill_vs_rw: float  # 1 - crps/crps_rw: > 0 means the model beats the baseline
    skill_vs_bootstrap: float
    coverage50: float
    coverage80: float
    coverage90: float
    hit_rate: float


def _skill(crps_mean: float, baseline_mean: float) -> float:
    return 1.0 - crps_mean / baseline_mean if baseline_mean > 0.0 else float("nan")


def summarize_scores(scores: Sequence[OriginScore]) -> ForecastEvalSummary:
    """Aggregate per-origin scores. Fails loud on zero origins (nothing was evaluated)."""
    if not scores:
        raise DataError("no origins to summarize — the eval produced zero forecasts")
    crps_mean = float(np.mean([s.crps for s in scores]))
    crps_rw_mean = float(np.mean([s.crps_rw for s in scores]))
    crps_boot_mean = float(np.mean([s.crps_bootstrap for s in scores]))
    return ForecastEvalSummary(
        n_origins=len(scores),
        crps_mean=crps_mean,
        crps_rw_mean=crps_rw_mean,
        crps_bootstrap_mean=crps_boot_mean,
        skill_vs_rw=_skill(crps_mean, crps_rw_mean),
        skill_vs_bootstrap=_skill(crps_mean, crps_boot_mean),
        coverage50=float(np.mean([s.cover50 for s in scores])),
        coverage80=float(np.mean([s.cover80 for s in scores])),
        coverage90=float(np.mean([s.cover90 for s in scores])),
        hit_rate=float(np.mean([s.hit for s in scores])),
    )
