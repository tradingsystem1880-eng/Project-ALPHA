from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli import _runner, strategy_candidate_cmds
from alpha_cli.main import app
from alpha_cli.strategy_candidate import (
    hedged_basis_paper_preflight,
    registered_hedged_basis_candidate,
    validate_hedged_basis_definition,
)
from alpha_core import DataError
from alpha_strategies.hedged_basis import HedgedBasisObservationV1, HedgedBasisPlanV1


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


def test_hedged_basis_typed_contracts_reject_boundary_drift() -> None:
    with pytest.raises(DataError, match="differs from the registered sandbox candidate"):
        HedgedBasisPlanV1(total_round_trip_cost_bps=20.0)
    with pytest.raises(DataError, match="must be timezone-aware"):
        HedgedBasisObservationV1.create(event_time=datetime(2025, 1, 1))


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

    text = CliRunner().invoke(app, ["strategy-candidate", "paper-preflight"])
    assert text.exit_code == 0
    assert "no broker connection or order was attempted" in text.output


def test_candidate_run_cli_forwards_only_typed_frozen_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(strategy_candidate_cmds, "crypto_hedged_basis_observations", lambda _: ())
    monkeypatch.setattr(_runner, "verified_snapshot_hash", lambda *_: "e" * 64)
    captured: dict[str, object] = {}

    def fake_run(data_dir: Path, **kwargs: object) -> dict[str, object]:
        captured.update({"data_dir": data_dir, **kwargs})
        return {"run_id": "1234567890abcdef", "command": "candidate_holdout"}

    monkeypatch.setattr(strategy_candidate_cmds, "run_hedged_basis_candidate", fake_run)
    invoked = CliRunner().invoke(
        app,
        [
            "strategy-candidate",
            "run",
            "d" * 64,
            "--research-contract-id",
            f"rc_{'f' * 64}",
            "--analysis",
            "holdout",
            "--holdout-start",
            "2025-01-01",
            "--holdout-end",
            "2025-01-31",
            "--holdout-spec-hash",
            "1" * 64,
            "--json",
        ],
    )

    assert invoked.exit_code == 0, invoked.output
    assert json.loads(invoked.output)["run_id"] == "1234567890abcdef"
    assert captured["data_dir"] == tmp_path
    assert str(captured["holdout_start"]) == "2025-01-01"
    assert str(captured["holdout_end"]) == "2025-01-31"
    assert captured["holdout_spec_hash"] == "1" * 64
    assert captured["observations"] == ()

    text = CliRunner().invoke(
        app,
        [
            "strategy-candidate",
            "run",
            "d" * 64,
            "--research-contract-id",
            f"rc_{'f' * 64}",
        ],
    )
    assert text.exit_code == 0
    assert "SANDBOX ONLY" in text.output

    invalid = CliRunner().invoke(
        app,
        [
            "strategy-candidate",
            "run",
            "d" * 64,
            "--research-contract-id",
            f"rc_{'f' * 64}",
            "--holdout-start",
            "not-a-date",
        ],
    )
    assert invalid.exit_code != 0
    assert "Invalid value" in invalid.output
