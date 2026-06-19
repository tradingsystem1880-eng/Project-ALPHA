"""Conditional-volatility (GARCH-family) estimation for the validation / research layer.

Pure, fail-loud wrappers over ``arch``. Two entry points with deliberately different causality
guarantees:

- :func:`garch_conditional_volatility` — the in-sample per-period conditional volatility of a
  GARCH(p, q) fit. This is a **diagnostic**: parameters are estimated from the whole sample, so it
  is NOT causal and must never be used as a per-bar trading signal.
- :func:`garch_volatility_forecast` — a one-step-ahead **annualized** conditional-volatility
  forecast computed from a return window. This IS causal (a pure function of the window) and is the
  value intended to feed vol-aware sizing through the CLI seam (strategies cannot import validation
  under the architecture DAG).

Both fail loud (``DataError``) on degenerate input, consistent with :mod:`alpha_validation.metrics`.
GARCH fitting is maximum-likelihood with no RNG, so results are deterministic given the input.
"""

from __future__ import annotations

import math
import warnings

import numpy as np
from arch import arch_model
from arch.univariate.base import ARCHModelResult

from alpha_core import DataError
from alpha_validation.metrics import FloatArray, FloatSeq

# GARCH(1,1) with three free parameters needs a non-trivial sample to estimate meaningfully;
# below this we fail loud rather than return an unreliable fit.
_MIN_RETURNS = 20
# arch fits most stably on percent-scaled returns; we scale in and unscale out.
_PCT = 100.0


def _as_garch_returns(returns: FloatSeq, name: str) -> FloatArray:
    arr = np.asarray(returns, dtype=np.float64)
    if arr.ndim != 1 or arr.size < _MIN_RETURNS:
        raise DataError(f"{name} needs >= {_MIN_RETURNS} returns, got shape {arr.shape}")
    if not bool(np.all(np.isfinite(arr))):
        raise DataError(f"{name} requires finite returns")
    if float(np.std(arr, ddof=1)) <= 0.0:
        raise DataError(f"{name} is undefined for a zero-variance return series")
    return arr


def _fit(returns: FloatArray, *, p: int, q: int) -> ARCHModelResult:
    if p < 1 or q < 1:
        raise DataError(f"GARCH orders must be >= 1, got p={p}, q={q}")
    model = arch_model(returns * _PCT, mean="Zero", vol="GARCH", p=p, q=q, dist="normal")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # convergence chatter; we validate the result below
        result = model.fit(disp="off", show_warning=False)
    return result


def garch_conditional_volatility(returns: FloatSeq, *, p: int = 1, q: int = 1) -> FloatArray:
    """In-sample per-period conditional volatility from a GARCH(p, q) fit (diagnostic, not causal).

    Returns an array the same length as ``returns``, in the same (per-period, fractional) units.
    Fails loud on degenerate input or a fit that produces non-finite / non-positive volatility.
    """
    arr = _as_garch_returns(returns, "garch_conditional_volatility")
    result = _fit(arr, p=p, q=q)
    cond_vol = np.asarray(result.conditional_volatility, dtype=np.float64) / _PCT
    if cond_vol.shape != arr.shape:
        raise DataError("GARCH conditional volatility length does not match the input")
    if not bool(np.all(np.isfinite(cond_vol)) and np.all(cond_vol > 0.0)):
        raise DataError("GARCH fit produced non-finite or non-positive conditional volatility")
    return cond_vol


def garch_volatility_forecast(
    returns: FloatSeq, *, p: int = 1, q: int = 1, periods_per_year: int = 252
) -> float:
    """One-step-ahead annualized conditional-volatility forecast from a return window (causal).

    A pure function of ``returns``: fits GARCH(p, q) on the window and forecasts the next period's
    conditional volatility, annualized by ``sqrt(periods_per_year)``. Fails loud on degenerate
    input or a non-finite / non-positive forecast.
    """
    if periods_per_year < 1:
        raise DataError(f"periods_per_year must be >= 1, got {periods_per_year}")
    arr = _as_garch_returns(returns, "garch_volatility_forecast")
    result = _fit(arr, p=p, q=q)
    next_var_pct = float(
        np.asarray(result.forecast(horizon=1, reindex=False).variance).reshape(-1)[-1]
    )
    forecast = math.sqrt(next_var_pct) / _PCT * math.sqrt(periods_per_year)
    if not math.isfinite(forecast) or forecast <= 0.0:
        raise DataError(f"GARCH volatility forecast is non-finite or non-positive: {forecast!r}")
    return forecast
