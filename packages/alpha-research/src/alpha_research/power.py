"""Prospective one-sided power under an explicit known-sigma mean model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from alpha_core import DataError


def _validate_model(
    alternative_effect: float,
    minimum_effect: float,
    standard_deviation: float,
    alpha: float,
) -> None:
    for name, value in (
        ("alternative_effect", alternative_effect),
        ("minimum_effect", minimum_effect),
        ("standard_deviation", standard_deviation),
        ("alpha", alpha),
    ):
        if not math.isfinite(value):
            raise DataError(f"{name} must be finite")
    if alternative_effect <= minimum_effect:
        raise DataError("alternative_effect must be greater than minimum_effect")
    if minimum_effect < 0.0:
        raise DataError("minimum_effect must be non-negative")
    if standard_deviation <= 0.0:
        raise DataError("standard_deviation must be positive")
    if not 0.0 < alpha < 0.5:
        raise DataError("alpha must be in (0, 0.5)")


def required_observations_known_sigma(
    alternative_effect: float,
    minimum_effect: float,
    standard_deviation: float,
    *,
    alpha: float = 0.05,
    target_power: float = 0.90,
) -> int:
    """Normal-theory sample size for ``H0: effect <= minimum_effect``.

    The caller supplies positive magnitudes; a negative directional hypothesis is handled by
    sign-flipping its observations before using this primitive.
    """
    _validate_model(alternative_effect, minimum_effect, standard_deviation, alpha)
    if not math.isfinite(target_power) or not 0.5 < target_power < 1.0:
        raise DataError("target_power must be finite in (0.5, 1)")
    gap = alternative_effect - minimum_effect
    z_alpha = float(norm.ppf(1.0 - alpha))
    z_power = float(norm.ppf(target_power))
    required = math.ceil(((z_alpha + z_power) * standard_deviation / gap) ** 2)
    return max(2, required)


@dataclass(frozen=True, slots=True)
class ProspectivePowerResult:
    sample_size: int
    simulations: int
    seed: int
    rejection_threshold: float
    estimated_power: float
    monte_carlo_standard_error: float


def simulate_prospective_power_known_sigma(
    sample_size: int,
    alternative_effect: float,
    minimum_effect: float,
    standard_deviation: float,
    *,
    alpha: float = 0.05,
    simulations: int = 20_000,
    seed: int = 7,
) -> ProspectivePowerResult:
    """Deterministically simulate the registered known-sigma one-sided mean test."""
    _validate_model(alternative_effect, minimum_effect, standard_deviation, alpha)
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 2:
        raise DataError("sample_size must be an integer >= 2")
    if isinstance(simulations, bool) or not isinstance(simulations, int) or simulations < 1:
        raise DataError("simulations must be an integer >= 1")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise DataError("seed must be a non-negative integer")
    standard_error = standard_deviation / math.sqrt(sample_size)
    threshold = minimum_effect + float(norm.ppf(1.0 - alpha)) * standard_error
    rng = np.random.default_rng(seed)
    sample_means = rng.normal(alternative_effect, standard_error, simulations)
    estimated = float(np.mean(sample_means > threshold))
    monte_carlo_se = math.sqrt(estimated * (1.0 - estimated) / simulations)
    return ProspectivePowerResult(
        sample_size=sample_size,
        simulations=simulations,
        seed=seed,
        rejection_threshold=threshold,
        estimated_power=estimated,
        monte_carlo_standard_error=monte_carlo_se,
    )


def projected_confirmation_power(
    *,
    matched_estimate: float,
    ci_lower: float,
    ci_upper: float,
    confidence: float,
    sample_size: int,
    projected_sample_size: int,
    minimum_effect: float,
    alpha: float = 0.05,
    simulations: int = 20_000,
    seed: int = 7,
) -> ProspectivePowerResult:
    """Project one-shot confirmation power from an admitted discovery-share estimate.

    The discovery interval is inverted into the known-sigma model: the bootstrap CI
    half-width gives the discovery standard error, scaled by ``sqrt(sample_size)`` to a
    per-observation sigma, and the registered one-sided mean test is simulated at the
    confirmation share's projected sample size. A degenerate (zero-width) interval cannot
    estimate dispersion and fails loud rather than fabricating certainty. The caller
    supplies positive magnitudes; a negative directional claim is sign-flipped first.
    """
    for name, value in (
        ("matched_estimate", matched_estimate),
        ("ci_lower", ci_lower),
        ("ci_upper", ci_upper),
    ):
        if not math.isfinite(value):
            raise DataError(f"{name} must be finite")
    if ci_upper <= ci_lower:
        raise DataError(
            "confirmation power projection requires an ordered, non-degenerate discovery interval"
        )
    if not math.isfinite(confidence) or not 0.5 <= confidence < 1.0:
        raise DataError("confidence must be finite in [0.5, 1)")
    if isinstance(sample_size, bool) or not isinstance(sample_size, int) or sample_size < 2:
        raise DataError("sample_size must be an integer >= 2")
    z_confidence = float(norm.ppf(0.5 + confidence / 2.0))
    standard_error = (ci_upper - ci_lower) / (2.0 * z_confidence)
    standard_deviation = standard_error * math.sqrt(sample_size)
    return simulate_prospective_power_known_sigma(
        projected_sample_size,
        matched_estimate,
        minimum_effect,
        standard_deviation,
        alpha=alpha,
        simulations=simulations,
        seed=seed,
    )
