"""Scenario/path-risk Monte Carlo over canonical out-of-sample account returns.

These simulations do not test a no-edge null. They keep the observed strategy-return process as
the object of study and ask how alternate sequencing, regimes, or heavy tails change terminal
equity and drawdown. Engine/model composition remains in ``alpha_cli``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from alpha_core import DataError
from alpha_validation.metrics import FloatArray, FloatSeq
from alpha_validation.montecarlo import student_t_paths
from alpha_validation.proportion import ProportionInterval, wilson_interval
from alpha_validation.verdict import grade_tail_risk


@dataclass(frozen=True)
class RegimePathResult:
    """Simulated returns/states plus the fitted two-state transition matrix."""

    paths: FloatArray
    states: np.ndarray
    transition_matrix: FloatArray
    state_observations: tuple[int, int]
    state_transitions: tuple[int, int]


@dataclass(frozen=True)
class MonteCarloFamilySummaryV1:
    """Versioned decision summary for one path-risk family."""

    schema_version: int
    family: str
    status: str
    n_paths: int
    horizon: int
    terminal_return_q05: float
    terminal_return_q50: float
    terminal_return_q95: float
    maximum_drawdown_q50: float
    maximum_drawdown_q95: float
    longest_loss_streak_q95: float
    loss_probability: ProportionInterval
    ruin_probability: ProportionInterval
    risk_grade: str
    explanation: str
    caveats: tuple[str, ...] = ()


@dataclass(frozen=True)
class MonteCarloReviewV1:
    """Append-only owner disposition over one exact combined Monte Carlo evidence set."""

    schema_version: int
    decision: str
    actor: str
    rationale: str
    evidence_hashes: tuple[tuple[str, str], ...]
    recorded_at: str


@dataclass(frozen=True)
class PathMetricArrays:
    """Per-path raw outcomes persisted by the CLI for independent summary verification."""

    terminal_return: FloatArray
    maximum_drawdown: FloatArray
    longest_loss_streak: FloatArray
    loss: np.ndarray
    ruined: np.ndarray


def _returns(values: FloatSeq, *, name: str = "returns") -> FloatArray:
    result = np.asarray(values, dtype=np.float64)
    if result.ndim != 1 or result.size < 2:
        raise DataError(f"{name} needs at least 2 one-dimensional observations, got {result.shape}")
    if not bool(np.all(np.isfinite(result))):
        raise DataError(f"{name} must be finite")
    if bool(np.any(result <= -1.0)):
        raise DataError(f"{name} must be greater than -1 for compound equity")
    return result


def empirical_return_paths(
    returns: FloatSeq,
    *,
    n_paths: int = 10_000,
    length: int | None = None,
    seed: int | None = None,
) -> FloatArray:
    """IID empirical bootstrap paths drawn with replacement from account returns."""
    values = _returns(returns)
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    horizon = values.size if length is None else length
    if horizon < 1:
        raise DataError(f"length must be >= 1, got {horizon}")
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, values.size, size=(n_paths, horizon))
    return np.asarray(values[indices], dtype=np.float64)


def student_t_return_paths(
    returns: FloatSeq,
    *,
    n_paths: int = 10_000,
    seed: int | None = None,
) -> FloatArray:
    """Heavy-tailed log-account-return scenarios mapped back to valid simple returns.

    This uses the same deterministic Student-t generator as the randomized-price module but the
    object being simulated is explicitly the validated account-return stream, not a no-edge price
    process. The sample log-return excess kurtosis determines the degrees of freedom. Fitting in
    log space guarantees every simulated simple return stays above -100%.
    """
    values = _returns(returns)
    log_values = np.log1p(values)
    log_paths = student_t_paths(log_values, n_paths=n_paths, seed=seed)
    paths = np.expm1(log_paths)
    if not bool(np.all(np.isfinite(paths))):
        raise DataError("Student-t log-return simulation produced a non-finite simple return")
    return np.asarray(paths, dtype=np.float64)


def regime_switching_return_paths(
    returns: FloatSeq,
    states: np.ndarray,
    *,
    n_paths: int = 10_000,
    length: int | None = None,
    min_state_observations: int = 20,
    min_state_transitions: int = 10,
    seed: int | None = None,
) -> RegimePathResult:
    """Two-state empirical-emission Markov paths fitted from causal state labels."""
    values = _returns(returns)
    labels = np.asarray(states, dtype=np.int8)
    if labels.ndim != 1 or labels.shape != values.shape:
        raise DataError(f"states shape {labels.shape} must match returns shape {values.shape}")
    if not bool(np.all((labels == 0) | (labels == 1))):
        raise DataError("states must contain only 0 (calm) and 1 (volatile)")
    if n_paths < 1:
        raise DataError(f"n_paths must be >= 1, got {n_paths}")
    if min_state_observations < 1 or min_state_transitions < 1:
        raise DataError("minimum state observations/transitions must be >= 1")
    horizon = values.size if length is None else length
    if horizon < 1:
        raise DataError(f"length must be >= 1, got {horizon}")

    emissions = (values[labels == 0], values[labels == 1])
    observation_counts = (int(emissions[0].size), int(emissions[1].size))
    for state, count in enumerate(observation_counts):
        if count < min_state_observations:
            raise DataError(
                f"state {state} needs at least {min_state_observations} observations, got {count}"
            )

    counts = np.zeros((2, 2), dtype=np.int64)
    for current, following in zip(labels[:-1], labels[1:], strict=True):
        counts[int(current), int(following)] += 1
    transition_counts = (int(np.sum(counts[0])), int(np.sum(counts[1])))
    for state, count in enumerate(transition_counts):
        if count < min_state_transitions:
            raise DataError(
                f"state {state} needs at least {min_state_transitions} outbound transitions, "
                f"got {count}"
            )
    matrix = counts / counts.sum(axis=1, keepdims=True)

    rng = np.random.default_rng(seed)
    simulated_states = np.empty((n_paths, horizon), dtype=np.int8)
    paths = np.empty((n_paths, horizon), dtype=np.float64)
    initial_probability = observation_counts[1] / values.size
    simulated_states[:, 0] = (rng.random(n_paths) < initial_probability).astype(np.int8)
    for step in range(horizon):
        current = simulated_states[:, step]
        for state in (0, 1):
            selected = np.flatnonzero(current == state)
            if selected.size:
                draws = rng.integers(0, emissions[state].size, size=selected.size)
                paths[selected, step] = emissions[state][draws]
        if step + 1 < horizon:
            volatile_probability = matrix[current, 1]
            simulated_states[:, step + 1] = (rng.random(n_paths) < volatile_probability).astype(
                np.int8
            )

    return RegimePathResult(
        paths=paths,
        states=simulated_states,
        transition_matrix=np.asarray(matrix, dtype=np.float64),
        state_observations=observation_counts,
        state_transitions=transition_counts,
    )


def _longest_loss_streaks(paths: FloatArray) -> FloatArray:
    """Calculate every path's longest loss streak with one vector operation per timestep."""
    current = np.zeros(paths.shape[0], dtype=np.int64)
    longest = np.zeros(paths.shape[0], dtype=np.int64)
    for step in range(paths.shape[1]):
        current = np.where(paths[:, step] < 0.0, current + 1, 0)
        longest = np.maximum(longest, current)
    return np.asarray(longest, dtype=np.float64)


def summarize_path_family(
    family: str,
    paths: FloatArray,
    *,
    ruin_drawdown: float = 0.5,
    confidence: float = 0.95,
    caveats: tuple[str, ...] = (),
) -> MonteCarloFamilySummaryV1:
    """Summarize terminal/drawdown path risk with Wilson uncertainty on probabilities."""
    values = np.asarray(paths, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 1:
        raise DataError(f"paths must be a non-empty 2-D matrix, got {values.shape}")
    if not bool(np.all(np.isfinite(values))):
        raise DataError("paths must be finite")
    if bool(np.any(values <= -1.0)):
        raise DataError("path returns must be greater than -1 for compound equity")
    if not 0.0 < ruin_drawdown <= 1.0:
        raise DataError(f"ruin_drawdown must be in (0, 1], got {ruin_drawdown}")

    metrics = path_metric_arrays(values, ruin_drawdown=ruin_drawdown)
    terminal = metrics.terminal_return
    maximum_drawdown = metrics.maximum_drawdown
    longest = metrics.longest_loss_streak
    loss_count = int(np.sum(metrics.loss))
    ruin_count = int(np.sum(metrics.ruined))
    loss_probability = wilson_interval(loss_count, values.shape[0], confidence=confidence)
    ruin_probability = wilson_interval(ruin_count, values.shape[0], confidence=confidence)
    drawdown_q95 = float(np.quantile(maximum_drawdown, 0.95))
    risk_grade = grade_tail_risk(
        maximum_drawdown=drawdown_q95,
        risk_of_ruin=ruin_probability.point,
    )
    terminal_q50 = float(np.quantile(terminal, 0.50))
    status = "warning" if risk_grade in {"D", "F"} or terminal_q50 <= 0.0 else "clear"
    return MonteCarloFamilySummaryV1(
        schema_version=1,
        family=family,
        status=status,
        n_paths=int(values.shape[0]),
        horizon=int(values.shape[1]),
        terminal_return_q05=float(np.quantile(terminal, 0.05)),
        terminal_return_q50=terminal_q50,
        terminal_return_q95=float(np.quantile(terminal, 0.95)),
        maximum_drawdown_q50=float(np.quantile(maximum_drawdown, 0.50)),
        maximum_drawdown_q95=drawdown_q95,
        longest_loss_streak_q95=float(np.quantile(longest, 0.95)),
        loss_probability=loss_probability,
        ruin_probability=ruin_probability,
        risk_grade=risk_grade,
        explanation=(
            "Alternate paths preserve this family's stated return-process assumptions; "
            "they describe scenario risk and do not establish strategy edge."
        ),
        caveats=caveats,
    )


def path_metric_arrays(paths: FloatArray, *, ruin_drawdown: float = 0.5) -> PathMetricArrays:
    """Return auditable per-path outcomes used by :func:`summarize_path_family`."""
    values = np.asarray(paths, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] < 1 or values.shape[1] < 1:
        raise DataError(f"paths must be a non-empty 2-D matrix, got {values.shape}")
    if not bool(np.all(np.isfinite(values))) or bool(np.any(values <= -1.0)):
        raise DataError("path returns must be finite and greater than -1")
    if not 0.0 < ruin_drawdown <= 1.0:
        raise DataError(f"ruin_drawdown must be in (0, 1], got {ruin_drawdown}")
    equity = np.cumprod(1.0 + values, axis=1)
    equity = np.concatenate((np.ones((values.shape[0], 1)), equity), axis=1)
    terminal = equity[:, -1] - 1.0
    drawdowns = 1.0 - equity / np.maximum.accumulate(equity, axis=1)
    maximum_drawdown = np.max(drawdowns, axis=1)
    longest = _longest_loss_streaks(values)
    return PathMetricArrays(
        terminal_return=np.asarray(terminal, dtype=np.float64),
        maximum_drawdown=np.asarray(maximum_drawdown, dtype=np.float64),
        longest_loss_streak=longest,
        loss=terminal < 0.0,
        ruined=maximum_drawdown >= ruin_drawdown,
    )
