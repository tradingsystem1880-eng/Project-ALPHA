from __future__ import annotations

from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.strategy_candidate import (
    hedged_basis_paper_preflight,
    registered_hedged_basis_candidate,
    validate_hedged_basis_definition,
)
from alpha_core import DataError


def test_hedged_basis_candidate_definition_is_closed_and_sandbox_only() -> None:
    candidate = registered_hedged_basis_candidate()

    assert candidate.strategy_name == "hedged_basis_crowding_v1"
    assert candidate.required_venues == ("bybit", "binance")
    assert candidate.required_quote_asset == "USDT"
    assert candidate.periods_per_year == 1_095
    assert candidate.deployment_scope == "sandbox_only"
    assert candidate.places_orders is False
    validate_hedged_basis_definition(candidate.to_dict())

    changed = {**candidate.to_dict(), "total_round_trip_cost_bps": 4.0}
    try:
        validate_hedged_basis_definition(changed)
    except DataError as exc:
        assert "differs from the registered candidate" in str(exc)
    else:  # pragma: no cover - the fail-closed assertion above is the behavior under test.
        raise AssertionError("drifted candidate definition was accepted")


def test_hedged_basis_paper_preflight_is_actionably_blocked_without_side_effects() -> None:
    result = hedged_basis_paper_preflight()

    assert result["status"] == "BLOCKED"
    assert result["code"] == "UNSUPPORTED_MULTI_VENUE_PAPER"
    for field in (
        "broker_connection_attempted",
        "credentials_requested",
        "paper_readiness_credit",
        "order_created",
        "fill_created",
        "position_changed",
        "places_orders",
    ):
        assert result[field] is False

    invoked = CliRunner().invoke(app, ["strategy-candidate", "paper-preflight", "--json"])
    assert invoked.exit_code == 0, invoked.output
    assert "UNSUPPORTED_MULTI_VENUE_PAPER" in invoked.output
