"""Frozen owner decisions and promotion governance for the v3 development lifecycle."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from alpha_cli.control_store import ControlStore, StageState
from alpha_core import DataError
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

type TestRun = tuple[str, str, StageState, bool | None, str | None]


def _setup(tmp_path: Path) -> tuple[ControlStore, str, str, str]:
    snapshot_dir = tmp_path / "snapshots" / "frozen-snapshot"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps({"snapshot_id": "frozen-snapshot", "symbols": {}}, sort_keys=True),
        encoding="utf-8",
    )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Candidate",
        hypothesis="A causal edge survives costs.",
        falsification_criterion="Reject on a failed locked holdout.",
        at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="ts_momentum",
        source_fingerprint="git:0123456789abcdef-clean",
        definition={"lookback": 20, "skip": 2, "vol_window": 10},
        parameter_space={"lookback": [10, 20, 40]},
    )
    version_id = str(version["version_id"])
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=version_id,
        snapshot_id="frozen-snapshot",
        universe=["SPY", "QQQ"],
        split_policy={"train": 504, "test": 63, "embargo": 5},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
    )
    return store, project_id, version_id, str(experiment["experiment_id"])


def _run(
    tmp_path: Path,
    run_id: str,
    command: str,
    *,
    passed: bool | None = True,
    holdout_spec_hash: str | None = None,
    null_model: str | None = None,
) -> None:
    rdir = tmp_path / "runs" / run_id
    rdir.mkdir(parents=True)
    manifest: dict[str, object] = {
        "schema_version": 3,
        "artifact_contract_version": 3,
        "run_identity_version": 3,
        "run_id": run_id,
        "command": command,
        "snapshot_id": "frozen-snapshot",
        "snapshot_hash": hashlib.sha256(
            (tmp_path / "snapshots" / "frozen-snapshot" / "manifest.json").read_bytes()
        ).hexdigest(),
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": "b" * 64,
        "source_fingerprint": "c" * 64,
        "research_cutoff": "2026-03-31",
        "artifacts": {},
    }
    if passed is not None:
        manifest["passed"] = passed
    if holdout_spec_hash is not None:
        manifest["holdout_spec_hash"] = holdout_spec_hash
    if null_model is not None:
        manifest["metadata"] = {"null_model": null_model}
    if command.startswith("monte_carlo_"):
        manifest["status"] = "clear"
    (rdir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def _link_required_runs(
    store: ControlStore, tmp_path: Path, project_id: str, experiment_id: str
) -> None:
    evidence: dict[str, tuple[str, list[TestRun]]] = {
        "baseline": (
            "baseline",
            [("0000000000000001", "backtest_run", "pass", None, None)],
        ),
        "inner_oos": (
            "oos",
            [("0000000000000002", "backtest_oos", "pass", None, None)],
        ),
        "three_null_families": (
            "robustness",
            [
                ("0000000000000003", "validate", "pass", True, "bootstrap"),
                ("0000000000000008", "validate", "warning", None, "student_t"),
                ("0000000000000009", "validate", "warning", None, "garch"),
            ],
        ),
        "monte_carlo": (
            "monte_carlo",
            [
                ("000000000000000a", "monte_carlo_classical", "pass", None, None),
                ("000000000000000b", "monte_carlo_kronos", "pass", None, None),
            ],
        ),
        "optimize_grid": (
            "optimization",
            [("0000000000000004", "optim_grid", "pass", True, None)],
        ),
        "portfolio_cross_asset": (
            "portfolio",
            [
                ("0000000000000005", "backtest_portfolio", "pass", None, None),
                ("0000000000000007", "cross_sectional", "pass", None, None),
            ],
        ),
    }
    for action, (stage, runs) in evidence.items():
        current = next(
            row["state"]
            for row in cast(list[dict[str, object]], store.get_project(project_id)["stage_states"])
            if row["experiment_id"] == experiment_id and row["stage"] == stage
        )
        if current == "not_started":
            store.append_experiment_stage_state(
                project_id, experiment_id, stage, "ready", reason="suite ready"
            )
        store.append_experiment_stage_state(
            project_id, experiment_id, stage, "queued", reason="suite queued"
        )
        store.append_experiment_stage_state(
            project_id, experiment_id, stage, "running", reason="suite running"
        )
        for run_id, command, state, passed, null_model in runs:
            _run(tmp_path, run_id, command, passed=passed, null_model=null_model)
            store.link_suite_stage_run(
                project_id,
                experiment_id,
                suite_action=action,
                stage=stage,
                state=state,
                run_id=run_id,
            )
        store.complete_suite_stage(
            project_id,
            experiment_id,
            suite_action=action,
            stage=stage,
            state="pass",
            reason="verified test evidence",
        )


def _pass_non_run_stage(
    store: ControlStore, project_id: str, experiment_id: str, stage: str
) -> None:
    for state in ("ready", "queued", "running", "pass"):
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            stage,
            state,
            reason=f"test {stage} {state}",
        )


def _ready_for_decision(
    store: ControlStore,
    tmp_path: Path,
    project_id: str,
    experiment_id: str,
) -> str:
    store.seal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="reserved before model selection",
        start_date="2026-04-01",
        end_date="2026-06-30",
    )
    _link_required_runs(store, tmp_path, project_id, experiment_id)
    _pass_non_run_stage(store, project_id, experiment_id, "candidate")
    store.reveal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="candidate frozen",
    )
    sealed = store.get_holdout_spec(project_id, experiment_id)
    assert sealed is not None
    _run(
        tmp_path,
        "0000000000000006",
        "backtest_holdout",
        passed=True,
        holdout_spec_hash=str(sealed["spec_hash"]),
    )
    for state in ("ready", "queued", "running"):
        store.append_experiment_stage_state(
            project_id, experiment_id, "holdout", state, reason="holdout suite"
        )
    store.link_suite_stage_run(
        project_id,
        experiment_id,
        suite_action="holdout_reveal",
        stage="holdout",
        state="pass",
        run_id="0000000000000006",
    )
    store.complete_suite_stage(
        project_id,
        experiment_id,
        suite_action="holdout_reveal",
        stage="holdout",
        state="pass",
        reason="locked holdout passed",
    )
    for state in ("ready", "queued", "running"):
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            "paper",
            cast(StageState, state),
            reason="paper suite",
        )
    job = store.create_suite_job(
        kind="suite:paper_preflight",
        request={"action": "paper_preflight", "stage": "paper", "steps": [{"index": 1}]},
        project_id=project_id,
        experiment_id=experiment_id,
    )
    job_id = str(job["job_id"])
    store.set_job_status(job_id, "running")
    store.record_attempt(
        project_id,
        experiment_id,
        stage="paper",
        status="passed",
        config_fingerprint="paper:preflight",
        details={"action": "paper_preflight", "job_id": job_id, "step": 1},
    )
    store.complete_suite_journal_stage(
        project_id,
        experiment_id,
        suite_action="paper_preflight",
        stage="paper",
        state="pass",
        job_id=job_id,
        reason="sandbox preflight passed",
    )
    failed = store.record_attempt(
        project_id,
        experiment_id,
        stage="robustness",
        status="failed",
        config_fingerprint="cfg:rejected:1",
        error="failed fixed stress",
        details={"kept": True},
    )
    return str(failed["attempt_id"])


def test_accept_freezes_exact_evidence_and_never_deploys(tmp_path: Path) -> None:
    store, project_id, version_id, experiment_id = _setup(tmp_path)
    negative_id = _ready_for_decision(store, tmp_path, project_id, experiment_id)

    packet = store.freeze_decision_packet(
        project_id,
        experiment_id,
        verdict="accept",
        actor="owner",
        reason="All locked gates cleared; retain sandbox-only scope.",
        negative_results_acknowledged=True,
    )

    assert str(packet["packet_id"]).startswith("dp_")
    assert packet["packet_hash"] == str(packet["packet_id"])[3:]
    assert packet["verdict"] == "accept"
    assert packet["strategy_version_id"] == version_id
    assert packet["negative_result_attempt_ids"] == [negative_id]
    assert packet["deployment_scope"] == "sandbox_only"
    assert packet["places_real_orders"] is False
    assert set(cast(dict[str, object], packet["stage_evidence"])) >= {
        "baseline",
        "oos",
        "robustness",
        "optimization",
        "portfolio",
        "holdout",
        "paper",
    }
    detail = store.get_project(project_id)
    assert detail["status"] == "accepted"
    assert (
        cast(list[dict[str, object]], detail["decision_packets"])[0]["packet_id"]
        == packet["packet_id"]
    )
    decision = next(
        row
        for row in cast(list[dict[str, object]], detail["stage_states"])
        if row["experiment_id"] == experiment_id and row["stage"] == "decision"
    )
    assert decision["state"] == "pass"

    with pytest.raises(DataError, match="already has a frozen decision"):
        store.freeze_decision_packet(
            project_id,
            experiment_id,
            verdict="accept",
            actor="owner",
            reason="duplicate",
            negative_results_acknowledged=True,
        )


def test_accept_fails_closed_on_missing_ack_bad_provenance_or_fake_stage_link(
    tmp_path: Path,
) -> None:
    store, project_id, _version_id, experiment_id = _setup(tmp_path)
    _ready_for_decision(store, tmp_path, project_id, experiment_id)

    with pytest.raises(DataError, match="negative results must be explicitly acknowledged"):
        store.freeze_decision_packet(
            project_id,
            experiment_id,
            verdict="accept",
            actor="owner",
            reason="no acknowledgement",
            negative_results_acknowledged=False,
        )

    # A passed stage state cannot substitute an exact canonical command/artifact citation.
    other_root = tmp_path / "other"
    other_store, other_project, _other_version, other_experiment = _setup(other_root)
    _ready_for_decision(other_store, other_root, other_project, other_experiment)
    robustness = other_root / "runs" / "0000000000000003" / "manifest.json"
    manifest = json.loads(robustness.read_text(encoding="utf-8"))
    manifest["command"] = "backtest_run"
    robustness.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    with pytest.raises(DataError, match="verified canonical suite evidence"):
        other_store.freeze_decision_packet(
            other_project,
            other_experiment,
            verdict="accept",
            actor="owner",
            reason="bypass",
            negative_results_acknowledged=True,
        )


def test_reject_and_revise_freeze_negative_decisions_without_promotion(tmp_path: Path) -> None:
    for verdict in ("reject", "revise"):
        root = tmp_path / verdict
        store, project_id, _version_id, experiment_id = _setup(root)
        attempt = store.record_attempt(
            project_id,
            experiment_id,
            stage="baseline",
            status="rejected",
            config_fingerprint=f"cfg:{verdict}",
            details={"reason": verdict},
        )
        packet = store.freeze_decision_packet(
            project_id,
            experiment_id,
            verdict=verdict,
            actor="owner",
            reason=f"owner chose {verdict}",
            negative_results_acknowledged=True,
        )
        assert packet["negative_result_attempt_ids"] == [attempt["attempt_id"]]
        expected = "rejected" if verdict == "reject" else "active"
        assert store.get_project(project_id)["status"] == expected
