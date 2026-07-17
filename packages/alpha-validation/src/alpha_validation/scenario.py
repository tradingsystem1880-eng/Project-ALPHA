"""Stress / what-if scenarios over a strategy's realized return stream.

Applies interpretable transforms — mean-preserving volatility scaling and appended tail shocks —
to a return series and re-evaluates the risk metrics under each, so a run can be checked against
"what if vol doubled?" or "what if a -5σ day hit?" without re-running the engine. Reuses the same
metric primitives the gauntlet uses (pure numpy, fail-loud); depends only on ``alpha_core``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_validation.metrics import (
    FloatArray,
    FloatSeq,
    _as_returns,
    annualized_volatility,
    expected_shortfall,
    max_drawdown,
    sharpe_ratio,
    value_at_risk,
)


@dataclass(frozen=True)
class ScenarioSummary:
    """Risk metrics for one stress scenario (``sharpe`` is ``None`` for a degenerate series)."""

    name: str
    sharpe: float | None
    annual_vol: float
    max_drawdown: float
    value_at_risk: float
    expected_shortfall: float
    total_return: float


def scale_volatility(returns: FloatArray, factor: float) -> FloatArray:
    """Mean-preserving vol scaling: ``mean + (r - mean) * factor`` (drift kept, spread scaled)."""
    mean = float(np.mean(returns))
    return mean + (returns - mean) * factor


def append_shock(returns: FloatArray, sigmas: float) -> FloatArray:
    """Append a single crash day of ``-sigmas × std`` to the series."""
    std = float(np.std(returns, ddof=1))
    return np.concatenate([returns, np.array([-sigmas * std], dtype=np.float64)])


def _equity(returns: FloatArray) -> FloatArray:
    return np.concatenate([np.array([1.0]), np.cumprod(1.0 + returns)])


def _summary(
    name: str, returns: FloatArray, *, periods_per_year: int, confidence: float
) -> ScenarioSummary:
    equity = _equity(returns)
    # Sharpe is undefined for a zero-variance series — report None rather than fail the whole panel
    sharpe = (
        sharpe_ratio(returns, periods_per_year=periods_per_year)
        if float(np.std(returns, ddof=1)) > 0.0
        else None
    )
    return ScenarioSummary(
        name=name,
        sharpe=sharpe,
        annual_vol=annualized_volatility(returns, periods_per_year=periods_per_year),
        max_drawdown=max_drawdown(equity),
        value_at_risk=value_at_risk(returns, confidence=confidence),
        expected_shortfall=expected_shortfall(returns, confidence=confidence),
        total_return=float(equity[-1] / equity[0] - 1.0),
    )


def scenario_metrics(
    returns: FloatSeq, *, periods_per_year: int = 252, confidence: float = 0.95
) -> list[ScenarioSummary]:
    """Risk metrics for the base return stream and a fixed panel of stress scenarios."""
    base = _as_returns(returns, "scenario_metrics")
    scenarios: list[tuple[str, FloatArray]] = [
        ("base", base),
        ("vol +50%", scale_volatility(base, 1.5)),
        ("vol +100%", scale_volatility(base, 2.0)),
        ("-3σ shock", append_shock(base, 3.0)),
        ("-5σ shock", append_shock(base, 5.0)),
    ]
    return [
        _summary(name, ret, periods_per_year=periods_per_year, confidence=confidence)
        for name, ret in scenarios
    ]
