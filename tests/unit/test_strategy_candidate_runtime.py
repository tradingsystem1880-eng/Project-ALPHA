from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from alpha_cli import strategy_candidate_runtime
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
        "candidate_analysis.json",
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


@pytest.mark.parametrize(
    ("analysis", "command"),
    [
        ("inner_oos", "candidate_oos"),
        ("null_bootstrap", "candidate_null_bootstrap"),
        ("null_student_t", "candidate_null_student_t"),
        ("null_garch", "candidate_null_garch"),
    ],
)
def test_candidate_pre_holdout_analyses_recompute_exactly(
    tmp_path: Path, analysis: str, command: str
) -> None:
    observations = _observations()
    manifest = run_hedged_basis_candidate(
        tmp_path,
        snapshot_id="d" * 64,
        snapshot_hash="e" * 64,
        research_contract_id=f"rc_{'f' * 64}",
        observations=observations,
        analysis=analysis,
        research_cutoff="2025-01-31",
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )

    assert manifest["command"] == command
    assert isinstance(manifest["passed"], bool)
    assert isinstance(manifest["metadata"], dict)
    if analysis.startswith("null_"):
        metadata = manifest["metadata"]
        assert isinstance(metadata, dict)
        assert metadata["null_model"] == analysis.removeprefix("null_")
        method_token = {
            "null_bootstrap": "sign_randomization",
            "null_student_t": "student_t",
            "null_garch": "garch_1_1",
        }[analysis]
        assert method_token in str(metadata["method"])
    validate_hedged_basis_candidate_artifacts(
        tmp_path / "runs" / str(manifest["run_id"]),
        manifest,
        observations=observations,
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("analysis", "command", "model"),
    [
        ("monte_carlo_classical", "candidate_monte_carlo_classical", "classical_iid"),
        ("monte_carlo_kronos_fixture", "candidate_monte_carlo_kronos", "fake"),
    ],
)
def test_candidate_monte_carlo_binds_source_and_discloses_model_role(
    tmp_path: Path, analysis: str, command: str, model: str
) -> None:
    observations = _observations()
    manifest = run_hedged_basis_candidate(
        tmp_path,
        snapshot_id="d" * 64,
        snapshot_hash="e" * 64,
        research_contract_id=f"rc_{'f' * 64}",
        observations=observations,
        analysis=analysis,
        source_run_id="1234567890abcdef",
        research_cutoff="2025-01-31",
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )

    assert manifest["command"] == command
    assert manifest["source_run_id"] == "1234567890abcdef"
    assert manifest["status"] in {"clear", "warning"}
    metadata = manifest["metadata"]
    assert isinstance(metadata, dict) and metadata["model"] == model
    validate_hedged_basis_candidate_artifacts(
        tmp_path / "runs" / str(manifest["run_id"]),
        manifest,
        observations=observations,
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )


@pytest.mark.parametrize(
    ("analysis", "command"),
    [
        ("optimize_cost_sensitivity", "candidate_optim"),
        ("portfolio_concentration", "candidate_portfolio"),
        ("cross_asset_scope", "candidate_cross_asset"),
        ("fixed_stress", "candidate_fixed_stress"),
        ("qlib_fixture", "candidate_qlib"),
        ("kronos_forecast_fixture", "candidate_kronos_forecast"),
        ("kronos_eval_fixture", "candidate_kronos_eval"),
    ],
)
def test_candidate_fixed_development_diagnostics_are_exact(
    tmp_path: Path, analysis: str, command: str
) -> None:
    observations = _observations()
    manifest = run_hedged_basis_candidate(
        tmp_path,
        snapshot_id="d" * 64,
        snapshot_hash="e" * 64,
        research_contract_id=f"rc_{'f' * 64}",
        observations=observations,
        analysis=analysis,
        research_cutoff="2025-01-31",
        as_of=datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    )

    assert manifest["command"] == command
    assert manifest["passed"] is True
    metadata = manifest["metadata"]
    assert isinstance(metadata, dict)
    if analysis == "optimize_cost_sensitivity":
        assert [row["total_round_trip_cost_bps"] for row in metadata["trials"]] == [20, 40, 60]
        assert [row["selected"] for row in metadata["trials"]] == [False, True, False]
    if analysis == "cross_asset_scope":
        assert metadata["status"] == "completed_not_applicable_single_registered_asset"


def test_candidate_holdout_binds_exact_window_and_hash(tmp_path: Path) -> None:
    observations = _observations()
    manifest = run_hedged_basis_candidate(
        tmp_path,
        snapshot_id="d" * 64,
        snapshot_hash="e" * 64,
        research_contract_id=f"rc_{'f' * 64}",
        observations=observations,
        analysis="holdout",
        holdout_start=datetime(2025, 1, 1, tzinfo=UTC).date(),
        holdout_end=datetime(2025, 1, 3, tzinfo=UTC).date(),
        holdout_spec_hash="1" * 64,
        research_cutoff=None,
        as_of=None,
    )

    assert manifest["command"] == "candidate_holdout"
    assert manifest["holdout_spec_hash"] == "1" * 64
    assert manifest["passed"] is True
    validate_hedged_basis_candidate_artifacts(
        tmp_path / "runs" / str(manifest["run_id"]),
        manifest,
        observations=observations,
        as_of=None,
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"analysis": "unknown"}, "unsupported hedged basis analysis"),
        ({"snapshot_id": "bad"}, "exact snapshot identities"),
        ({"analysis": "monte_carlo_classical"}, "exact source validation run"),
        ({"analysis": "holdout"}, "exact sealed window"),
        (
            {
                "analysis": "holdout",
                "holdout_start": datetime(2024, 1, 1, tzinfo=UTC).date(),
                "holdout_end": datetime(2024, 1, 31, tzinfo=UTC).date(),
                "holdout_spec_hash": "1" * 64,
                "as_of": None,
                "research_cutoff": None,
            },
            "no events inside the sealed window",
        ),
        (
            {
                "as_of": datetime(2024, 1, 1, tzinfo=UTC),
                "research_cutoff": "2024-01-01",
            },
            "no causally available admitted events",
        ),
    ],
)
def test_candidate_runtime_denials_fail_before_publication(
    tmp_path: Path, changes: dict[str, object], message: str
) -> None:
    kwargs: dict[str, object] = {
        "snapshot_id": "d" * 64,
        "snapshot_hash": "e" * 64,
        "research_contract_id": f"rc_{'f' * 64}",
        "observations": _observations(),
        "analysis": "baseline",
        "research_cutoff": "2025-01-31",
        "as_of": datetime(2025, 1, 31, 23, 59, 59, tzinfo=UTC),
    }
    kwargs.update(changes)

    with pytest.raises(DataError, match=message):
        run_hedged_basis_candidate(tmp_path, **kwargs)  # type: ignore[arg-type]


def test_candidate_validator_rejects_corrupt_typed_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    run_dir = tmp_path / "runs" / str(manifest["run_id"])
    monkeypatch.setattr(strategy_candidate_runtime, "verify_manifest_artifacts", lambda *_: None)
    evaluation_path = run_dir / "candidate_evaluation.json"
    analysis_path = run_dir / "candidate_analysis.json"
    exact_evaluation = evaluation_path.read_text(encoding="utf-8")

    with pytest.raises(DataError, match="not a registered sandbox candidate"):
        validate_hedged_basis_candidate_artifacts(
            run_dir,
            {**manifest, "command": "forged"},
            observations=observations,
            as_of=datetime(2025, 2, 1, tzinfo=UTC),
        )
    with pytest.raises(DataError, match="does not bind"):
        validate_hedged_basis_candidate_artifacts(
            run_dir,
            {**manifest, "source_fingerprint": "0" * 64},
            observations=observations,
            as_of=datetime(2025, 2, 1, tzinfo=UTC),
        )

    holdout = run_hedged_basis_candidate(
        tmp_path,
        snapshot_id="d" * 64,
        snapshot_hash="e" * 64,
        research_contract_id=f"rc_{'f' * 64}",
        observations=observations,
        analysis="holdout",
        holdout_start=datetime(2025, 1, 1, tzinfo=UTC).date(),
        holdout_end=datetime(2025, 1, 3, tzinfo=UTC).date(),
        holdout_spec_hash="1" * 64,
        research_cutoff=None,
        as_of=None,
    )
    holdout_dir = tmp_path / "runs" / str(holdout["run_id"])
    with pytest.raises(DataError, match="holdout window is invalid"):
        validate_hedged_basis_candidate_artifacts(
            holdout_dir,
            {**holdout, "holdout_start": "bad"},
            observations=observations,
            as_of=None,
        )
    with pytest.raises(DataError, match="contains no events"):
        validate_hedged_basis_candidate_artifacts(
            holdout_dir,
            {**holdout, "holdout_start": "2024-01-01", "holdout_end": "2024-01-31"},
            observations=observations,
            as_of=None,
        )

    evaluation_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(DataError, match="evaluation is unreadable"):
        validate_hedged_basis_candidate_artifacts(
            run_dir, manifest, observations=observations, as_of=datetime(2025, 2, 1, tzinfo=UTC)
        )
    evaluation_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="evaluation fails exact recomputation"):
        validate_hedged_basis_candidate_artifacts(
            run_dir, manifest, observations=observations, as_of=datetime(2025, 2, 1, tzinfo=UTC)
        )
    evaluation_path.write_text(exact_evaluation, encoding="utf-8")
    analysis_path.write_text("not-json", encoding="utf-8")
    with pytest.raises(DataError, match="analysis is unreadable"):
        validate_hedged_basis_candidate_artifacts(
            run_dir, manifest, observations=observations, as_of=datetime(2025, 2, 1, tzinfo=UTC)
        )
    analysis_path.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="analysis fails exact recomputation"):
        validate_hedged_basis_candidate_artifacts(
            run_dir, manifest, observations=observations, as_of=datetime(2025, 2, 1, tzinfo=UTC)
        )
