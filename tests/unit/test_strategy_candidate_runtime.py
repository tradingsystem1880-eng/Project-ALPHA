from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli.strategy_candidate_runtime import (
    run_hedged_basis_candidate,
    validate_hedged_basis_candidate_artifacts,
)
from alpha_core import DataError
from alpha_strategies.hedged_basis import HedgedBasisObservationV1


def _observations() -> tuple[HedgedBasisObservationV1, ...]:
    rows: list[HedgedBasisObservationV1] = []
    start = datetime(2025, 1, 1, tzinfo=UTC)
    for index, exit_price in enumerate((99.0, 100.5, 98.0)):
        event = start + timedelta(hours=16 * index)
        rows.append(
            HedgedBasisObservationV1.create(
                event_time=event,
                event_available_at=event,
                entry_time=event + timedelta(hours=1),
                entry_available_at=event + timedelta(hours=1),
                exit_time=event + timedelta(hours=8),
                exit_available_at=event + timedelta(hours=8),
                bybit_perp_entry=100.0,
                bybit_perp_exit=exit_price,
                binance_spot_entry=100.0,
                binance_spot_exit=100.0,
                funding_rate=0.001,
                funding_available_at=event,
                perp_quantity_btc=-1.0,
                spot_quantity_btc=1.0,
                input_sha256=(("binance_spot", "a" * 64), ("bybit_linear", "b" * 64)),
                event_operator_fingerprint="c" * 64,
                correction_lineage=(),
            )
        )
    return tuple(rows)


def test_candidate_baseline_is_immutable_sandbox_evidence(tmp_path: Path) -> None:
    observations = _observations()
    manifest = run_hedged_basis_candidate(
        tmp_path,
        snapshot_id="d" * 64,
        snapshot_hash="e" * 64,
        research_contract_id=f"rc_{'f' * 64}",
        observations=observations,
        analysis="baseline",
        research_cutoff="2025-01-31",
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )

    assert manifest["command"] == "candidate_baseline"
    assert manifest["deployment_scope"] == "sandbox_only"
    assert manifest["execution_model"] == "two_leg_return_replay"
    assert manifest["places_orders"] is False
    assert manifest["paper_eligible"] is False
    assert manifest["broker_connection_attempted"] is False
    assert manifest["event_count"] == 3
    assert manifest["research_inheritance"] == {"contract_id": f"rc_{'f' * 64}"}
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    result = validate_hedged_basis_candidate_artifacts(
        run_dir,
        manifest,
        observations=observations,
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )
    assert result["event_count"] == 3
    assert set(manifest["artifacts"]) == {
        "candidate_evaluation.json",
        "report.md",
        "returns.parquet",
    }

    path = run_dir / "candidate_evaluation.json"
    original = path.read_bytes()
    os.chmod(path, 0o600)
    changed = json.loads(original)
    changed["cumulative_return"] = 99.0
    path.write_text(json.dumps(changed, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    with pytest.raises(DataError, match="(?:size|hash) mismatch"):
        validate_hedged_basis_candidate_artifacts(
            run_dir,
            manifest,
            observations=observations,
            as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
        )


def test_candidate_runtime_fails_before_publication_on_invalid_scope(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="promoted research contract"):
        run_hedged_basis_candidate(
            tmp_path,
            snapshot_id="d" * 64,
            snapshot_hash="e" * 64,
            research_contract_id="bad",
            observations=_observations(),
            analysis="baseline",
            research_cutoff=None,
            as_of=None,
        )
    assert not (tmp_path / "runs").exists()
