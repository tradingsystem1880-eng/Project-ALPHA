"""Mechanical classification of one frozen confirmatory claim."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from alpha_core import DataError


class ClaimDirection(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class ConfirmationStatus(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    INVALID = "invalid"


@dataclass(frozen=True, slots=True)
class ConfirmationEvidence:
    """Frozen adjusted-p and confidence-interval evidence for one directional claim."""

    direction: ClaimDirection
    estimate: float
    ci_lower: float
    ci_upper: float
    adjusted_p_value: float
    alpha: float
    minimum_effect: float
    invalid_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.direction, ClaimDirection):
            raise DataError("direction must be a registered ClaimDirection")
        for name in ("estimate", "ci_lower", "ci_upper", "adjusted_p_value", "alpha"):
            value = getattr(self, name)
            if not math.isfinite(value):
                raise DataError(f"ConfirmationEvidence.{name} must be finite")
        if not self.ci_lower <= self.estimate <= self.ci_upper:
            raise DataError("confirmation interval must be ordered around the estimate")
        if not 0.0 <= self.adjusted_p_value <= 1.0:
            raise DataError("adjusted_p_value must be in [0, 1]")
        if not 0.0 < self.alpha < 0.5:
            raise DataError("alpha must be in (0, 0.5)")
        if not math.isfinite(self.minimum_effect) or self.minimum_effect < 0.0:
            raise DataError("minimum_effect must be finite and non-negative")
        if self.invalid_reason is not None and not self.invalid_reason.strip():
            raise DataError("invalid_reason must be non-empty when supplied")


@dataclass(frozen=True, slots=True)
class ConfirmationOutcome:
    status: ConfirmationStatus
    reason: str


def classify_confirmation(evidence: ConfirmationEvidence) -> ConfirmationOutcome:
    """Classify without silently treating low power or weak effects as a failed hypothesis."""
    if evidence.invalid_reason is not None:
        return ConfirmationOutcome(ConfirmationStatus.INVALID, evidence.invalid_reason)
    if evidence.direction is ClaimDirection.POSITIVE and evidence.ci_upper < 0.0:
        return ConfirmationOutcome(
            ConfirmationStatus.CONTRADICTED,
            "confidence interval lies wholly against the positive claim",
        )
    if evidence.direction is ClaimDirection.NEGATIVE and evidence.ci_lower > 0.0:
        return ConfirmationOutcome(
            ConfirmationStatus.CONTRADICTED,
            "confidence interval lies wholly against the negative claim",
        )
    if evidence.adjusted_p_value > evidence.alpha:
        return ConfirmationOutcome(
            ConfirmationStatus.INCONCLUSIVE,
            "adjusted primary test did not clear the frozen alpha",
        )
    if evidence.direction is ClaimDirection.POSITIVE:
        if evidence.ci_lower > evidence.minimum_effect:
            return ConfirmationOutcome(
                ConfirmationStatus.SUPPORTED,
                "confidence interval clears the positive minimum effect",
            )
    else:
        if evidence.ci_upper < -evidence.minimum_effect:
            return ConfirmationOutcome(
                ConfirmationStatus.SUPPORTED,
                "confidence interval clears the negative minimum effect",
            )
    return ConfirmationOutcome(
        ConfirmationStatus.INCONCLUSIVE,
        "evidence is statistically or economically too imprecise",
    )
