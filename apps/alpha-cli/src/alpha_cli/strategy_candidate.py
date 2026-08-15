"""Closed registry for development candidates that are not single-instrument engine strategies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Literal

from alpha_core import DataError
from alpha_strategies.hedged_basis import registered_hedged_basis_plan


@dataclass(frozen=True, slots=True)
class DevelopmentCandidateV1:
    strategy_name: str
    deployment_scope: Literal["sandbox_only"]
    execution_model: Literal["two_leg_return_replay"]
    required_venues: tuple[str, str]
    required_instrument: str
    required_quote_asset: str
    total_round_trip_cost_bps: float
    periods_per_year: int
    paper_blocker: str
    places_orders: bool
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def registered_hedged_basis_candidate() -> DevelopmentCandidateV1:
    plan = registered_hedged_basis_plan()
    return DevelopmentCandidateV1(
        strategy_name=plan.strategy_name,
        deployment_scope=plan.deployment_scope,
        execution_model="two_leg_return_replay",
        required_venues=(plan.perp_venue, plan.spot_venue),
        required_instrument=plan.instrument,
        required_quote_asset=plan.quote_asset,
        total_round_trip_cost_bps=plan.total_round_trip_cost_bps,
        periods_per_year=plan.periods_per_year,
        paper_blocker=plan.paper_blocker,
        places_orders=False,
    )


def validate_hedged_basis_definition(definition: Mapping[str, object]) -> None:
    """Fail closed when an immutable strategy version drifts from ADR-0033."""
    expected = registered_hedged_basis_candidate().to_dict()
    if dict(definition) != expected:
        raise DataError("hedged basis strategy definition differs from the registered candidate")


def hedged_basis_paper_preflight() -> dict[str, object]:
    """Return the permanent, non-authorizing paper boundary without probing a venue."""
    candidate = registered_hedged_basis_candidate()
    return {
        "schema": "CandidatePaperPreflightV1",
        "schema_version": 1,
        "strategy_name": candidate.strategy_name,
        "status": "BLOCKED",
        "code": candidate.paper_blocker,
        "recovery_action": (
            "Keep this candidate in deterministic local sandbox evaluation; ALPHA has no "
            "qualified atomic multi-venue paper adapter."
        ),
        "deployment_scope": candidate.deployment_scope,
        "broker_connection_attempted": False,
        "credentials_requested": False,
        "paper_readiness_credit": False,
        "order_created": False,
        "fill_created": False,
        "position_changed": False,
        "places_orders": False,
    }


__all__ = [
    "DevelopmentCandidateV1",
    "hedged_basis_paper_preflight",
    "registered_hedged_basis_candidate",
    "validate_hedged_basis_definition",
]
