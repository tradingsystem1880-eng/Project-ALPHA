"""Confirmation classification and prospective known-sigma power primitives."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from alpha_core import DataError
from alpha_research import (
    ClaimDirection,
    ConfirmationEvidence,
    ConfirmationStatus,
    classify_confirmation,
    projected_confirmation_power,
    required_observations_known_sigma,
    simulate_prospective_power_known_sigma,
)


@pytest.mark.parametrize(
    ("direction", "estimate", "lower", "upper"),
    [
        (ClaimDirection.POSITIVE, 0.03, 0.021, 0.04),
        (ClaimDirection.NEGATIVE, -0.03, -0.04, -0.021),
    ],
)
def test_supported_requires_significance_and_ci_beyond_minimum_effect(
    direction: ClaimDirection, estimate: float, lower: float, upper: float
) -> None:
    evidence = ConfirmationEvidence(
        direction=direction,
        estimate=estimate,
        ci_lower=lower,
        ci_upper=upper,
        adjusted_p_value=0.01,
        alpha=0.05,
        minimum_effect=0.02,
    )

    assert classify_confirmation(evidence).status is ConfirmationStatus.SUPPORTED


def test_inconclusive_and_contradicted_are_not_conflated() -> None:
    inconclusive = ConfirmationEvidence(
        ClaimDirection.POSITIVE, 0.015, 0.005, 0.025, 0.01, 0.05, 0.02
    )
    contradicted = ConfirmationEvidence(
        ClaimDirection.POSITIVE, -0.02, -0.03, -0.01, 0.01, 0.05, 0.02
    )

    assert classify_confirmation(inconclusive).status is ConfirmationStatus.INCONCLUSIVE
    assert classify_confirmation(contradicted).status is ConfirmationStatus.CONTRADICTED


def test_reliability_floor_forces_an_inconclusive_classification() -> None:
    evidence = ConfirmationEvidence(
        ClaimDirection.POSITIVE,
        0.02,
        0.01,
        0.03,
        0.001,
        0.05,
        0.005,
        reliability_passed=False,
    )

    outcome = classify_confirmation(evidence)

    assert outcome.status is ConfirmationStatus.INCONCLUSIVE
    assert "reliability floor" in outcome.reason


@pytest.mark.parametrize(
    ("direction", "estimate", "lower", "upper"),
    [
        (ClaimDirection.POSITIVE, -0.02, -0.03, -0.01),
        (ClaimDirection.NEGATIVE, 0.02, 0.01, 0.03),
    ],
)
def test_wholly_opposite_interval_is_contradicted_even_when_directional_p_is_large(
    direction: ClaimDirection, estimate: float, lower: float, upper: float
) -> None:
    evidence = ConfirmationEvidence(direction, estimate, lower, upper, 0.99, 0.05, 0.01)

    assert classify_confirmation(evidence).status is ConfirmationStatus.CONTRADICTED


def test_explicit_contract_violation_is_invalid() -> None:
    evidence = ConfirmationEvidence(
        ClaimDirection.POSITIVE,
        0.03,
        0.02,
        0.04,
        0.01,
        0.05,
        0.01,
        invalid_reason="confirmation data was visible before freeze",
    )
    outcome = classify_confirmation(evidence)

    assert outcome.status is ConfirmationStatus.INVALID
    assert outcome.reason == "confirmation data was visible before freeze"


def test_malformed_confirmation_evidence_fails_loud() -> None:
    with pytest.raises(DataError, match="ordered"):
        ConfirmationEvidence(ClaimDirection.POSITIVE, 0.02, 0.03, 0.01, 0.01, 0.05, 0.0)
    with pytest.raises(DataError, match="adjusted_p_value"):
        ConfirmationEvidence(ClaimDirection.POSITIVE, 0.02, 0.01, 0.03, 1.5, 0.05, 0.0)


@pytest.mark.parametrize(
    "evidence",
    [
        lambda: ConfirmationEvidence("positive", 0.02, 0.01, 0.03, 0.1, 0.05, 0.0),  # type: ignore[arg-type]
        lambda: ConfirmationEvidence(
            ClaimDirection.POSITIVE, float("nan"), 0.01, 0.03, 0.1, 0.05, 0.0
        ),
        lambda: ConfirmationEvidence(ClaimDirection.POSITIVE, 0.02, 0.01, 0.03, 0.1, 0.5, 0.0),
        lambda: ConfirmationEvidence(ClaimDirection.POSITIVE, 0.02, 0.01, 0.03, 0.1, 0.05, -0.1),
        lambda: ConfirmationEvidence(ClaimDirection.POSITIVE, 0.02, 0.01, 0.03, 0.1, 0.05, 0.0, ""),
    ],
)
def test_confirmation_contract_rejects_invalid_fields(evidence: Callable[[], object]) -> None:
    with pytest.raises(DataError):
        evidence()


def test_non_significant_directional_result_is_inconclusive() -> None:
    evidence = ConfirmationEvidence(ClaimDirection.POSITIVE, 0.02, 0.0, 0.04, 0.20, 0.05, 0.01)

    assert classify_confirmation(evidence).status is ConfirmationStatus.INCONCLUSIVE


def test_known_sigma_sample_size_and_simulation_are_deterministic() -> None:
    required = required_observations_known_sigma(
        alternative_effect=0.03,
        minimum_effect=0.01,
        standard_deviation=0.08,
        alpha=0.05,
        target_power=0.90,
    )
    first = simulate_prospective_power_known_sigma(
        sample_size=required,
        alternative_effect=0.03,
        minimum_effect=0.01,
        standard_deviation=0.08,
        alpha=0.05,
        simulations=50_000,
        seed=7,
    )
    second = simulate_prospective_power_known_sigma(
        sample_size=required,
        alternative_effect=0.03,
        minimum_effect=0.01,
        standard_deviation=0.08,
        alpha=0.05,
        simulations=50_000,
        seed=7,
    )

    assert required >= 2
    assert first == second
    assert first.estimated_power >= 0.89
    assert first.monte_carlo_standard_error < 0.002


def test_power_inputs_fail_loud() -> None:
    with pytest.raises(DataError, match="greater than minimum_effect"):
        required_observations_known_sigma(0.01, 0.01, 0.08)
    with pytest.raises(DataError, match="simulations"):
        simulate_prospective_power_known_sigma(10, 0.03, 0.01, 0.08, simulations=0)


@pytest.mark.parametrize(
    "call",
    [
        lambda: required_observations_known_sigma(float("nan"), 0.01, 0.08),
        lambda: required_observations_known_sigma(0.03, -0.01, 0.08),
        lambda: required_observations_known_sigma(0.03, 0.01, 0.0),
        lambda: required_observations_known_sigma(0.03, 0.01, 0.08, alpha=0.5),
        lambda: required_observations_known_sigma(0.03, 0.01, 0.08, target_power=0.5),
        lambda: simulate_prospective_power_known_sigma(1, 0.03, 0.01, 0.08),
        lambda: simulate_prospective_power_known_sigma(10, 0.03, 0.01, 0.08, seed=-1),
    ],
)
def test_additional_power_input_guards(call: Callable[[], object]) -> None:
    with pytest.raises(DataError):
        call()


def test_projected_confirmation_power_inverts_the_discovery_interval() -> None:
    """R6c (ADR-0026): one-shot D2 power projected from an admitted D1 estimate."""
    report = projected_confirmation_power(
        matched_estimate=0.014,
        ci_lower=0.012,
        ci_upper=0.016,
        confidence=0.95,
        sample_size=12,
        projected_sample_size=4,
        minimum_effect=0.005,
    )
    again = projected_confirmation_power(
        matched_estimate=0.014,
        ci_lower=0.012,
        ci_upper=0.016,
        confidence=0.95,
        sample_size=12,
        projected_sample_size=4,
        minimum_effect=0.005,
    )
    assert report == again  # deterministic under the protocol-frozen seed
    assert report.sample_size == 4
    assert report.seed == 7
    assert report.estimated_power >= 0.90


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"ci_lower": 0.014, "ci_upper": 0.014}, "non-degenerate"),
        ({"confidence": 1.0}, "confidence"),
        ({"sample_size": 1}, "sample_size"),
        ({"matched_estimate": 0.004}, "greater than minimum_effect"),
        ({"matched_estimate": float("nan")}, "finite"),
    ],
)
def test_projected_confirmation_power_guards(override: dict[str, float], message: str) -> None:
    arguments: dict[str, float | int] = {
        "matched_estimate": 0.014,
        "ci_lower": 0.012,
        "ci_upper": 0.016,
        "confidence": 0.95,
        "sample_size": 12,
        "projected_sample_size": 4,
        "minimum_effect": 0.005,
    }
    arguments.update(override)
    with pytest.raises(DataError, match=message):
        projected_confirmation_power(**arguments)  # type: ignore[arg-type]
