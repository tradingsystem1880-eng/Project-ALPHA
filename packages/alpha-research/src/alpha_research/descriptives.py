"""Pure pre-hypothesis descriptive analytics (spec §8.3, ADR-0023).

Deterministic, engine-free, core-only functions that DESCRIBE a dataset before any
hypothesis-specific computation: coverage and gap structure, return distributions,
autocorrelation, weekday seasonality, causal volatility-regime tags, and effective
sample size. Audits report data problems instead of crashing on them; only inputs that
make description itself meaningless (empty, non-finite, non-positive prices) fail loud.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

import numpy as np

from alpha_core import DataError

_WEEKDAY_BUCKETS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION = "ar1-conservative-cap-v2"


def _finite_array(values: Sequence[float], label: str) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise DataError(f"{label} must be one-dimensional")
    if not np.all(np.isfinite(array)):
        raise DataError(f"{label} must contain only finite values")
    return array


def coverage_summary(
    timestamps: Sequence[datetime], *, expected_interval_seconds: float
) -> dict[str, object]:
    """Describe coverage: span, gaps vs the expected cadence, duplicates, disorder."""
    if not timestamps:
        raise DataError("coverage summary requires a non-empty timestamp sequence")
    if (
        not isinstance(expected_interval_seconds, int | float)
        or isinstance(expected_interval_seconds, bool)
        or not math.isfinite(expected_interval_seconds)
        or expected_interval_seconds <= 0
    ):
        raise DataError("coverage expected_interval_seconds must be a positive finite number")
    duplicate_count = 0
    disorder_count = 0
    gap_count = 0
    max_gap_seconds = 0.0
    ordered = sorted(timestamps)
    for previous, current in zip(timestamps, timestamps[1:], strict=False):
        if current == previous:
            duplicate_count += 1
        elif current < previous:
            disorder_count += 1
    for previous, current in zip(ordered, ordered[1:], strict=False):
        delta = (current - previous).total_seconds()
        # Weekend/holiday spacing beyond twice the cadence counts as a gap; the audit
        # reports it and the owner judges whether the calendar explains it.
        if delta > 2 * expected_interval_seconds:
            gap_count += 1
        max_gap_seconds = max(max_gap_seconds, delta)
    return {
        "n": len(timestamps),
        "start": timestamps[0].isoformat(),
        "end": timestamps[-1].isoformat(),
        "expected_interval_seconds": float(expected_interval_seconds),
        "gap_count": gap_count,
        "max_gap_seconds": max_gap_seconds,
        "duplicate_count": duplicate_count,
        "disorder_count": disorder_count,
    }


def return_distribution(closes: Sequence[float]) -> dict[str, float | int]:
    """Moments and quantiles of simple returns derived from a positive close series."""
    array = _finite_array(closes, "return distribution closes")
    if array.size < 2:
        raise DataError("return distribution requires at least two closes")
    if np.any(array <= 0):
        raise DataError("return distribution requires strictly positive closes")
    returns = array[1:] / array[:-1] - 1.0
    mean = float(np.mean(returns))
    std = float(np.std(returns, ddof=1)) if returns.size > 1 else 0.0
    if std > 0:
        centered = returns - mean
        skewness = float(np.mean(centered**3) / np.std(returns) ** 3)
        excess_kurtosis = float(np.mean(centered**4) / np.std(returns) ** 4 - 3.0)
    else:
        skewness = 0.0
        excess_kurtosis = 0.0
    q05, q25, median, q75, q95 = (
        float(value) for value in np.quantile(returns, (0.05, 0.25, 0.5, 0.75, 0.95))
    )
    return {
        "n": int(returns.size),
        "mean": mean,
        "std": std,
        "skewness": skewness,
        "excess_kurtosis": excess_kurtosis,
        "min": float(np.min(returns)),
        "q05": q05,
        "q25": q25,
        "median": median,
        "q75": q75,
        "q95": q95,
        "max": float(np.max(returns)),
    }


def autocorrelation(
    values: Sequence[float], *, lags: Sequence[int]
) -> list[dict[str, float | int]]:
    """Sample autocorrelation at explicit lags (full-sample descriptive, not a signal)."""
    array = _finite_array(values, "autocorrelation values")
    rows: list[dict[str, float | int]] = []
    for lag in lags:
        if isinstance(lag, bool) or not isinstance(lag, int) or lag < 1 or lag >= array.size:
            raise DataError(f"autocorrelation lag must satisfy 1 <= lag < n; got {lag!r}")
        left = array[:-lag]
        right = array[lag:]
        left_std = float(np.std(left))
        right_std = float(np.std(right))
        if left_std == 0.0 or right_std == 0.0:
            raise DataError("autocorrelation is undefined for a constant series")
        value = float(
            np.mean((left - np.mean(left)) * (right - np.mean(right))) / (left_std * right_std)
        )
        rows.append({"lag": lag, "autocorrelation": value})
    return rows


def seasonality_by_weekday(
    timestamps: Sequence[datetime], returns: Sequence[float]
) -> list[dict[str, object]]:
    """Per-weekday return count/mean/std; buckets with no observations stay visible."""
    if len(timestamps) != len(returns):
        raise DataError("seasonality timestamps and returns must share one length")
    array = _finite_array(returns, "seasonality returns")
    buckets: dict[str, list[float]] = {name: [] for name in _WEEKDAY_BUCKETS}
    for stamp, value in zip(timestamps, array, strict=True):
        buckets[_WEEKDAY_BUCKETS[stamp.weekday()]].append(float(value))
    rows: list[dict[str, object]] = []
    for name in _WEEKDAY_BUCKETS:
        values = buckets[name]
        if not values and name in {"Sat", "Sun"}:
            continue  # weekday sessions: silent weekend rows would imply missing data
        rows.append(
            {
                "bucket": name,
                "count": len(values),
                "mean": float(np.mean(values)) if values else 0.0,
                "std": float(np.std(values, ddof=1)) if len(values) > 1 else 0.0,
            }
        )
    return rows


def volatility_regime_tags(returns: Sequence[float], *, window: int) -> list[str]:
    """Causal regime tags: trailing-window vol ranked against its own expanding history.

    Tag ``i`` reads returns ``[.. i]`` only — thresholds are expanding terciles of the
    trailing vols observed so far, never full-sample quantiles, so poisoning the future
    cannot rewrite the past (bias-guarded).
    """
    if isinstance(window, bool) or not isinstance(window, int) or window < 2:
        raise DataError("volatility regime window must be an integer >= 2")
    array = _finite_array(returns, "volatility regime returns")
    tags: list[str] = []
    history: list[float] = []
    for index in range(array.size):
        if index < window - 1:
            tags.append("warmup")
            continue
        trailing = array[index - window + 1 : index + 1]
        vol = float(np.std(trailing, ddof=1))
        history.append(vol)
        if len(history) < 3:
            tags.append("mid")
            continue
        low, high = (float(value) for value in np.quantile(history[:-1], (1 / 3, 2 / 3)))
        if vol <= low:
            tags.append("low")
        elif vol >= high:
            tags.append("high")
        else:
            tags.append("mid")
    return tags


def effective_sample_size(n: int, first_lag_autocorrelation: float) -> float:
    """Conservative AR(1) effective sample size, capped at the observation count."""
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise DataError("effective sample size requires a positive integer sample count")
    rho = first_lag_autocorrelation
    if (
        isinstance(rho, bool)
        or not isinstance(rho, int | float)
        or not math.isfinite(rho)
        or not -1.0 < rho < 1.0
    ):
        raise DataError("effective sample size autocorrelation must lie in (-1, 1)")
    raw = float(n) * (1.0 - rho) / (1.0 + rho)
    return min(float(n), raw)


__all__ = [
    "AR1_EFFECTIVE_SAMPLE_SIZE_METHOD_VERSION",
    "autocorrelation",
    "coverage_summary",
    "effective_sample_size",
    "return_distribution",
    "seasonality_by_weekday",
    "volatility_regime_tags",
]
