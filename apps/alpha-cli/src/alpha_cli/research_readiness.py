"""Mechanical, Python-authoritative readiness projections for governed research gates."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypedDict


class ReadinessBlocker(TypedDict):
    code: str
    evidence_refs: list[str]


class ReadinessProjection(TypedDict):
    state: str
    blockers: list[ReadinessBlocker]


class ResearchReadiness(TypedDict):
    confirmation_readiness: ReadinessProjection
    promotion_readiness: ReadinessProjection


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _status(value: object) -> str:
    status = _mapping(value).get("status")
    return status if isinstance(status, str) else "NOT_TESTED"


def _blocker(code: str, *evidence_refs: str) -> ReadinessBlocker:
    return {"code": code, "evidence_refs": list(evidence_refs)}


def _projection(blockers: list[ReadinessBlocker]) -> ReadinessProjection:
    return {"state": "blocked" if blockers else "ready", "blockers": blockers}


def derive_research_readiness(
    evidence: Mapping[str, object],
    *,
    required_falsifiers: Sequence[str] = (),
    skipped_required_families: Sequence[str] = (),
) -> ResearchReadiness:
    """Derive confirmation and promotion authority without a numeric aggregate.

    ``required_falsifiers`` and ``skipped_required_families`` come from the immutable
    analysis plan and its raw execution record. Blocker order and codes are stable API
    semantics; evidence references identify the authoritative record behind each block.
    """
    primary = _mapping(evidence.get("primary_result"))
    magnitude = _mapping(primary.get("practical_magnitude"))
    multiplicity = _status(evidence.get("multiplicity"))
    power = _status(evidence.get("power"))
    controls = _status(evidence.get("negative_controls"))

    confirmation_blockers: list[ReadinessBlocker] = []
    if primary.get("status") != "TESTED":
        confirmation_blockers.append(
            _blocker("primary_result_not_passed", "research_gate_evidence.primary_result")
        )
    if magnitude.get("status") != "CLEARS_HURDLE":
        confirmation_blockers.append(
            _blocker(
                "economic_hurdle_not_passed",
                "research_gate_evidence.primary_result.practical_magnitude",
            )
        )
    if multiplicity != "PASSED":
        confirmation_blockers.append(
            _blocker("multiplicity_not_passed", "research_gate_evidence.multiplicity")
        )
    if power != "PASSED":
        confirmation_blockers.append(_blocker("power_not_passed", "research_gate_evidence.power"))
    if required_falsifiers and controls != "PASSED":
        confirmation_blockers.append(
            _blocker(
                "required_falsifier_not_passed",
                "research_gate_evidence.negative_controls",
                *(
                    f"research_contract.analysis_plan.families.{family}"
                    for family in sorted(set(required_falsifiers))
                ),
            )
        )
    for family in sorted(set(skipped_required_families)):
        confirmation_blockers.append(
            _blocker(
                "required_family_skipped",
                f"research_contract.analysis_plan.families.{family}",
                f"d1_analyses.measurements.skipped_families.{family}",
            )
        )

    promotion_blockers: list[ReadinessBlocker] = []
    if evidence.get("confirmation_classification") != "SUPPORTED":
        promotion_blockers.append(
            _blocker(
                "confirmation_not_supported",
                "research_gate_evidence.confirmation_classification",
            )
        )
    if multiplicity != "PASSED":
        promotion_blockers.append(
            _blocker("multiplicity_not_passed", "research_gate_evidence.multiplicity")
        )
    if power != "PASSED":
        promotion_blockers.append(_blocker("power_not_passed", "research_gate_evidence.power"))

    return {
        "confirmation_readiness": _projection(confirmation_blockers),
        "promotion_readiness": _projection(promotion_blockers),
    }


__all__ = [
    "ReadinessBlocker",
    "ReadinessProjection",
    "ResearchReadiness",
    "derive_research_readiness",
]
