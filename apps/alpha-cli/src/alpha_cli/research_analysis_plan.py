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
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Final

from alpha_core import DataError

ANALYSIS_PLAN_SCHEMA: Final = "ResearchAnalysisPlanV1"
ANALYSIS_PLAN_SCHEMA_V2: Final = "ResearchAnalysisPlanV2"


@dataclass(frozen=True)
class AnalysisAxis:
    name: str
    default: int
    minimum: int


@dataclass(frozen=True)
class AnalysisFamily:
    runner: str
    finding_role: str
    axes: tuple[AnalysisAxis, ...] = ()


# This registry describes the existing D1 runners, not a new executor. Families without
# a horizon axis use the plan's maximum event/conditional-return horizon, as in V1.
ANALYSIS_FAMILIES: Final = MappingProxyType(
    {
        "event_study": AnalysisFamily(
            "_family_event_study", "primary", (AnalysisAxis("horizon_bars", 1, 1),)
        ),
        "conditional_returns": AnalysisFamily(
            "_family_conditional_returns",
            "secondary_holm",
            (AnalysisAxis("horizon_bars", 1, 1),),
        ),
        "quantile_breakdown": AnalysisFamily(
            "_family_quantile_breakdown",
            "diagnostic",
            (AnalysisAxis("quantiles", 4, 2),),
        ),
        "rank_ic": AnalysisFamily("_family_rank_ic", "diagnostic"),
        "temporal_stability": AnalysisFamily(
            "_family_temporal_stability",
            "robustness",
            (AnalysisAxis("n_periods", 2, 2),),
        ),
        "subsample_consistency": AnalysisFamily(
            "_family_subsample_consistency",
            "robustness",
            (AnalysisAxis("n_splits", 4, 2),),
        ),
        "leadlag_leakage": AnalysisFamily(
            "_family_leadlag_leakage",
            "falsification",
            (AnalysisAxis("max_lag", 3, 1),),
        ),
        "shuffled_event_null": AnalysisFamily(
            "_family_shuffled_event_null",
            "falsification",
            (AnalysisAxis("shuffles", 200, 10),),
        ),
    }
)
REGISTERED_ANALYSIS_FAMILIES: Final = frozenset(ANALYSIS_FAMILIES)
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


def _validate_analysis_plan_v1(
    plan: Mapping[str, object], *, max_grid_cells: int
) -> dict[str, Any]:
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


def validate_analysis_plan(plan: Mapping[str, object], *, max_grid_cells: int) -> dict[str, Any]:
    """Resolve V2 parameters; preserve V1's exact historical validation semantics."""
    if not isinstance(plan, Mapping) or plan.get("schema") != ANALYSIS_PLAN_SCHEMA_V2:
        return _validate_analysis_plan_v1(plan, max_grid_cells=max_grid_cells)
    structural = deepcopy(dict(plan))
    entries = structural.get("families")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict) and entry.get("multiplicity") in (
                "robustness",
                "diagnostic",
            ):
                entry["multiplicity"] = "secondary_holm"
    legacy = _validate_analysis_plan_v1(
        {**structural, "schema": ANALYSIS_PLAN_SCHEMA}, max_grid_cells=max_grid_cells
    )
    original_entries = plan["families"]
    assert isinstance(original_entries, list)
    for entry, original in zip(legacy["families"], original_entries, strict=True):
        family = str(entry["family"])
        descriptor = ANALYSIS_FAMILIES[family]
        if original["multiplicity"] != descriptor.finding_role:
            raise DataError(f"analysis family {family!r} requires role {descriptor.finding_role!r}")
        axes = descriptor.axes
        supplied = entry["grid"]
        unknown = set(supplied) - {axis.name for axis in axes}
        if unknown:
            raise DataError(f"analysis family {family!r} has unsupported axes: {sorted(unknown)}")
        resolved: dict[str, list[int]] = {}
        for axis in axes:
            values = supplied.get(axis.name, [axis.default])
            if any(type(value) is not int or value < axis.minimum for value in values):
                raise DataError(f"{family}.{axis.name} requires integers >= {axis.minimum}")
            if len(set(values)) != len(values):
                raise DataError(f"{family}.{axis.name} contains duplicate trial values")
            resolved[axis.name] = sorted(values)
        entry["grid"] = resolved
        if descriptor.finding_role == "primary" and _grid_cells(resolved, family) != 1:
            raise DataError("primary event_study requires exactly one prespecified horizon")
    _validate_analysis_plan_v1(legacy, max_grid_cells=max_grid_cells)
    for entry in legacy["families"]:
        entry["multiplicity"] = ANALYSIS_FAMILIES[entry["family"]].finding_role
    legacy["families"].sort(key=lambda entry: entry["family"])
    return {**legacy, "schema": ANALYSIS_PLAN_SCHEMA_V2}


def analysis_family_catalog() -> list[dict[str, object]]:
    """Expose actual supported axes/defaults without importing the numerical executor."""
    return [
        {
            "id": name,
            "schema": ANALYSIS_PLAN_SCHEMA_V2,
            "axes": [
                {
                    "name": axis.name,
                    "type": "integer",
                    "default": axis.default,
                    "minimum": axis.minimum,
                }
                for axis in family.axes
            ],
            "multiplicity": [family.finding_role],
            "finding_role": family.finding_role,
            "primary_grid_cells": 1 if family.finding_role == "primary" else None,
            "outcome_horizon": "family_axis"
            if any(axis.name == "horizon_bars" for axis in family.axes)
            else "maximum_plan_horizon",
        }
        for name, family in sorted(ANALYSIS_FAMILIES.items())
    ]


def validate_new_exploration_plan(plan: Mapping[str, object], *, max_grid_cells: int) -> None:
    """New-approval policy only; never use for historical execution or verification."""
    if plan.get("schema") == ANALYSIS_PLAN_SCHEMA:
        raise DataError(
            "new exploration approval requires ResearchAnalysisPlanV2; create a new draft"
        )
    if plan.get("schema") == ANALYSIS_PLAN_SCHEMA_V2:
        resolved = validate_analysis_plan(plan, max_grid_cells=max_grid_cells)
        if resolved != plan:
            raise DataError(
                "exploration analysis_plan must freeze resolved defaults before approval"
            )


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


def default_analysis_plan_v2(*, horizon_bars: int) -> dict[str, Any]:
    plan = default_analysis_plan(horizon_bars=horizon_bars)
    plan["schema"] = ANALYSIS_PLAN_SCHEMA_V2
    for entry in plan["families"]:
        entry["multiplicity"] = ANALYSIS_FAMILIES[entry["family"]].finding_role
    return validate_analysis_plan(plan, max_grid_cells=64)


__all__ = [
    "ANALYSIS_FAMILIES",
    "ANALYSIS_PLAN_SCHEMA_V2",
    "analysis_family_catalog",
    "default_analysis_plan_v2",
    "validate_new_exploration_plan",
    "ANALYSIS_PLAN_SCHEMA",
    "FALSIFICATION_ANALYSIS_FAMILIES",
    "REGISTERED_ANALYSIS_FAMILIES",
    "default_analysis_plan",
    "validate_analysis_plan",
]
