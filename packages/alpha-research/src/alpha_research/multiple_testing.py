"""Holm adjustment for one immutable, preregistered secondary hypothesis family."""

from __future__ import annotations

import math
from dataclasses import dataclass

from alpha_core import DataError
from alpha_research._canonical import canonical_sha256


@dataclass(frozen=True, slots=True)
class SecondaryHypothesis:
    hypothesis_id: str
    p_value: float

    def __post_init__(self) -> None:
        if not isinstance(self.hypothesis_id, str) or not self.hypothesis_id.strip():
            raise DataError("SecondaryHypothesis.hypothesis_id must be non-empty")
        if not math.isfinite(self.p_value) or not 0.0 <= self.p_value <= 1.0:
            raise DataError("SecondaryHypothesis.p_value must be finite in [0, 1]")

    def to_dict(self) -> dict[str, float | str]:
        return {"hypothesis_id": self.hypothesis_id, "p_value": self.p_value}


@dataclass(frozen=True, slots=True)
class FrozenSecondaryFamily:
    family_id: str
    hypotheses: tuple[SecondaryHypothesis, ...]
    alpha: float = 0.05

    def __post_init__(self) -> None:
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise DataError("FrozenSecondaryFamily.family_id must be non-empty")
        if not isinstance(self.hypotheses, tuple) or not self.hypotheses:
            raise DataError("FrozenSecondaryFamily.hypotheses must be a non-empty tuple")
        ids = [item.hypothesis_id for item in self.hypotheses]
        if len(ids) != len(set(ids)):
            raise DataError("secondary hypothesis IDs must be unique within the frozen family")
        if not math.isfinite(self.alpha) or not 0.0 < self.alpha < 0.5:
            raise DataError("FrozenSecondaryFamily.alpha must be finite in (0, 0.5)")

    def to_dict(self) -> dict[str, object]:
        return {
            "alpha": self.alpha,
            "family_id": self.family_id,
            "hypotheses": [item.to_dict() for item in self.hypotheses],
            "method": "holm",
            "schema_version": 1,
        }

    @property
    def contract_hash(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class HolmAdjustedHypothesis:
    hypothesis_id: str
    p_value: float
    adjusted_p_value: float
    rejected: bool


def holm_adjust_secondary_family(
    family: FrozenSecondaryFamily,
) -> tuple[HolmAdjustedHypothesis, ...]:
    """Return Holm-adjusted p-values in the family's original registered order."""
    count = len(family.hypotheses)
    ordered = sorted(family.hypotheses, key=lambda item: (item.p_value, item.hypothesis_id))
    adjusted_by_id: dict[str, float] = {}
    prior = 0.0
    for rank, hypothesis in enumerate(ordered):
        candidate = min(1.0, (count - rank) * hypothesis.p_value)
        adjusted = max(prior, candidate)
        adjusted_by_id[hypothesis.hypothesis_id] = adjusted
        prior = adjusted
    return tuple(
        HolmAdjustedHypothesis(
            hypothesis_id=item.hypothesis_id,
            p_value=item.p_value,
            adjusted_p_value=adjusted_by_id[item.hypothesis_id],
            rejected=adjusted_by_id[item.hypothesis_id] <= family.alpha,
        )
        for item in family.hypotheses
    )
