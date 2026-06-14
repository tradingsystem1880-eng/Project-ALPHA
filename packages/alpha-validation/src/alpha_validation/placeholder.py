"""Phase-0 placeholder proving the alpha_validation -> alpha_core dependency edge."""

from __future__ import annotations

from alpha_core.types import ValidationOutcome


def always_passes(name: str) -> ValidationOutcome:
    return ValidationOutcome(name=name, passed=True)
