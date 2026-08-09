"""The preregistered per-hypothesis D1 analysis plan (spec §9.2, ADR-0025).

An exploration contract selects the registered test families that THIS hypothesis and its
data-generating process demand — never a blanket battery. Every family, grid, and
multiplicity assignment is frozen at exploration approval; anything outside the plan is
exploratory-by-declaration and can never headline. Validation is pure and fail-loud; it
never rewrites the frozen plan.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any, Final

from alpha_core import DataError

ANALYSIS_PLAN_SCHEMA: Final = "ResearchAnalysisPlanV1"
REGISTERED_ANALYSIS_FAMILIES: Final = frozenset(
    {
        "event_study",
        "conditional_returns",
        "quantile_breakdown",
        "rank_ic",
        "temporal_stability",
        "subsample_consistency",
        "leadlag_leakage",
        "shuffled_event_null",
    }
)
FALSIFICATION_ANALYSIS_FAMILIES: Final = frozenset({"leadlag_leakage", "shuffled_event_null"})
_MULTIPLICITY_ASSIGNMENTS: Final = frozenset({"primary", "secondary_holm", "falsification"})
# The blanket-battery ceiling: a plan must SELECT families, not enumerate the registry.
_MAX_PLAN_FAMILIES: Final = 6
_MAX_GRID_AXES: Final = 4
_MAX_AXIS_VALUES: Final = 16
_MAX_RATIONALE_CHARS: Final = 500
_FAMILY_FIELDS: Final = frozenset({"family", "rationale", "grid", "multiplicity"})


def _grid_cells(grid: object, family: str) -> int:
    if not isinstance(grid, Mapping) or not all(isinstance(key, str) for key in grid):
        raise DataError(f"analysis family {family!r} grid must be a JSON object of axes")
    if len(grid) > _MAX_GRID_AXES:
        raise DataError(f"analysis family {family!r} grid exceeds the {_MAX_GRID_AXES}-axis bound")
    cells = 1
    for axis, values in grid.items():
        if not isinstance(values, list) or not values or len(values) > _MAX_AXIS_VALUES:
            raise DataError(
                f"analysis family {family!r} grid axis {axis!r} must be a list of "
                f"1..{_MAX_AXIS_VALUES} registered values"
            )
        for value in values:
            if (
                isinstance(value, bool)
                or not isinstance(value, int | float)
                or not math.isfinite(float(value))
            ):
                raise DataError(
                    f"analysis family {family!r} grid axis {axis!r} must contain only "
                    "finite numbers"
                )
        cells *= len(values)
    return cells


def validate_analysis_plan(plan: Mapping[str, object], *, max_grid_cells: int) -> dict[str, Any]:
    """Fail loud unless ``plan`` is a bounded, registered, frozen analysis plan."""
    if (
        isinstance(max_grid_cells, bool)
        or not isinstance(max_grid_cells, int)
        or max_grid_cells < 1
    ):
        raise DataError("analysis plan validation requires a positive grid-cell budget")
    if not isinstance(plan, Mapping) or plan.get("schema") != ANALYSIS_PLAN_SCHEMA:
        raise DataError(f"analysis plan requires schema {ANALYSIS_PLAN_SCHEMA}")
    unknown = set(plan) - {"schema", "families"}
    if unknown:
        raise DataError(f"analysis plan has unsupported fields: {', '.join(sorted(unknown))}")
    families = plan.get("families")
    if not isinstance(families, list) or not families:
        raise DataError("analysis plan requires at least one registered family")
    if len(families) > _MAX_PLAN_FAMILIES:
        raise DataError(
            f"analysis plan registers {len(families)} families; more than "
            f"{_MAX_PLAN_FAMILIES} is a blanket battery, not a hypothesis-driven selection"
        )
    seen: set[str] = set()
    primary_families: list[str] = []
    total_cells = 0
    for entry in families:
        if not isinstance(entry, Mapping) or set(entry) != _FAMILY_FIELDS:
            raise DataError(
                "analysis plan family entries require exactly the fields "
                f"{', '.join(sorted(_FAMILY_FIELDS))}"
            )
        family = entry["family"]
        if not isinstance(family, str) or family not in REGISTERED_ANALYSIS_FAMILIES:
            raise DataError(f"analysis plan names unregistered family {family!r}")
        if family in seen:
            raise DataError(f"analysis plan registers duplicate family {family!r}")
        seen.add(family)
        rationale = entry["rationale"]
        if (
            not isinstance(rationale, str)
            or not rationale.strip()
            or len(rationale) > _MAX_RATIONALE_CHARS
        ):
            raise DataError(
                f"analysis family {family!r} requires a non-empty rationale of at most "
                f"{_MAX_RATIONALE_CHARS} characters"
            )
        multiplicity = entry["multiplicity"]
        if multiplicity not in _MULTIPLICITY_ASSIGNMENTS:
            raise DataError(
                f"analysis family {family!r} multiplicity must be one of "
                f"{', '.join(sorted(_MULTIPLICITY_ASSIGNMENTS))}"
            )
        is_falsifier = family in FALSIFICATION_ANALYSIS_FAMILIES
        if is_falsifier != (multiplicity == "falsification"):
            raise DataError(
                f"analysis family {family!r} must use the falsification multiplicity "
                "exactly when it is a registered falsification family"
            )
        if multiplicity == "primary":
            primary_families.append(family)
        total_cells += _grid_cells(entry["grid"], family)
    if len(primary_families) != 1:
        raise DataError("analysis plan requires exactly one primary family")
    if total_cells > max_grid_cells:
        raise DataError(
            f"analysis plan registers {total_cells} grid cells, exceeding the approved "
            f"budget of {max_grid_cells}"
        )
    return dict(plan)


def default_analysis_plan(*, horizon_bars: int) -> dict[str, Any]:
    """The registered default plan for the event-conditioned forward-return hypothesis."""
    if isinstance(horizon_bars, bool) or not isinstance(horizon_bars, int) or horizon_bars < 1:
        raise DataError("default analysis plan requires a positive integer horizon in bars")
    return {
        "schema": ANALYSIS_PLAN_SCHEMA,
        "families": [
            {
                "family": "event_study",
                "multiplicity": "primary",
                "rationale": (
                    "The primary claim is an event-conditioned forward-return association "
                    "against pre-event matched controls."
                ),
                "grid": {"horizon_bars": [horizon_bars]},
            },
            {
                "family": "conditional_returns",
                "multiplicity": "secondary_holm",
                "rationale": (
                    "Quantify the conditional forward-return distribution behind the "
                    "primary contrast."
                ),
                "grid": {"horizon_bars": [horizon_bars]},
            },
            {
                "family": "temporal_stability",
                "multiplicity": "secondary_holm",
                "rationale": "The effect must not concentrate in one chronological sub-period.",
                "grid": {"n_periods": [2]},
            },
            {
                "family": "subsample_consistency",
                "multiplicity": "secondary_holm",
                "rationale": "The effect sign must agree across deterministic subsamples.",
                "grid": {"n_splits": [4]},
            },
            {
                "family": "shuffled_event_null",
                "multiplicity": "falsification",
                "rationale": "Shuffled event dates must not reproduce the observed effect.",
                "grid": {"shuffles": [200]},
            },
            {
                "family": "leadlag_leakage",
                "multiplicity": "falsification",
                "rationale": "The event indicator must not echo past outcomes (leakage screen).",
                "grid": {"max_lag": [3]},
            },
        ],
    }


__all__ = [
    "ANALYSIS_PLAN_SCHEMA",
    "FALSIFICATION_ANALYSIS_FAMILIES",
    "REGISTERED_ANALYSIS_FAMILIES",
    "default_analysis_plan",
    "validate_analysis_plan",
]
