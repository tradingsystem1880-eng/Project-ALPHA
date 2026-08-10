"""Workstation v3 control-plane storage invariants."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import polars as pl
import pytest

from alpha_cli import _artifacts
from alpha_cli.control_store import (
    DATABASE_NAME,
    AttemptStatus,
    AuthorKind,
    ControlStore,
    EvidenceStatus,
    JobStatus,
    ProjectStatus,
    StageState,
    parse_timestamp,
)
from alpha_cli.project_cmds import _agent_brief
from alpha_core import DataError
from alpha_research import MarketStateContractV1
from tests.fixtures.control_store_fixtures import (
    mark_project_as_migrated_legacy,
    publish_decision_grade_run,
)

PROJECT_ID = "8458c871-8c13-412d-8332-40e90b2041fd"
JOB_ID = "d5429915-8f7a-430b-b575-0667873179ab"
EVIDENCE_ID = "74312554-5131-4b2e-8434-c80151573166"
EVIDENCE_ID_2 = "555d7db4-5265-4adf-8989-cbd936ed7602"
START = datetime(2026, 7, 19, 10, 0, tzinfo=UTC)
RUN_ID = "0123456789abcdef"
type TestRun = tuple[str, str, StageState, bool | None, str | None]


def _store(tmp_path: Path) -> ControlStore:
    return ControlStore(tmp_path)


def _project(store: ControlStore) -> dict[str, object]:
    project = store.create_project(
        name="AAPL mean reversion",
        hypothesis="Large daily deviations mean-revert after costs.",
        falsification_criterion="Reject when locked OOS Sharpe is non-positive.",
        project_id=PROJECT_ID,
        at=START,
    )
    mark_project_as_migrated_legacy(store, PROJECT_ID)
    return project


def _version(
    store: ControlStore,
    *,
    source: str = "git:1111111",
    window: int = 20,
    at: datetime = START,
) -> dict[str, object]:
    return store.create_strategy_version(
        PROJECT_ID,
        strategy_name="mean_reversion",
        source_fingerprint=source,
        definition={"signal": "zscore", "window": window},
        parameter_space={"window": [10, 20, 40]},
        at=at,
    )


def _experiment(store: ControlStore, version_id: str, *, at: datetime = START) -> dict[str, object]:
    return store.create_experiment_spec(
        PROJECT_ID,
        strategy_version_id=version_id,
        snapshot_id="snap-aapl-2026q2",
        universe=["SPY", "AAPL", "AAPL"],
        split_policy={"train": 504, "test": 63, "embargo": 5},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
        stage_config={"null_families": ["bootstrap", "student_t", "garch"]},
        at=at,
    )


def test_agent_brief_context_reconstructs_scope_and_stage_state_at_cutoff(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    _project(store)
    first_version = _version(store, window=20, at=START + timedelta(minutes=1))
    first_experiment = _experiment(
        store,
        str(first_version["version_id"]),
        at=START + timedelta(minutes=2),
    )
    historical_cutoff = START + timedelta(minutes=2, seconds=30)

    second_version = _version(
        store,
        source="git:2222222",
        window=40,
        at=START + timedelta(minutes=3),
    )
    second_experiment = _experiment(
        store,
        str(second_version["version_id"]),
        at=START + timedelta(minutes=4),
    )
    store.append_experiment_stage_state(
        PROJECT_ID,
        str(second_experiment["experiment_id"]),
        "baseline",
        "queued",
        reason="later work must not enter the earlier brief",
        at=START + timedelta(minutes=5),
    )
    # Re-selecting already-linked content proves that append-only selection events, rather than
    # first-link timestamps or today's mutable project pointers, drive the historical projection.
    _version(store, window=20, at=START + timedelta(minutes=6))

    historical = store.get_agent_brief_context(PROJECT_ID, as_of=historical_cutoff)
    assert historical["version_id"] == first_version["version_id"]
    assert historical["experiment_id"] == first_experiment["experiment_id"]
    historical_stages = cast(list[dict[str, object]], historical["stage_statuses"])
    assert next(row for row in historical_stages if row["stage"] == "baseline") == {
        "stage": "baseline",
        "state": "ready",
        "run_id": None,
    }
    assert historical["holdout_events"] == []

    current = store.get_agent_brief_context(PROJECT_ID)
    assert current["version_id"] == first_version["version_id"]
    assert current["experiment_id"] == second_experiment["experiment_id"]


def test_agent_brief_uses_the_latest_authoritative_stage_transition_across_runs(
    tmp_path: Path,
) -> None:
    second_run_id = "fedcba9876543210"
    _publish_run(tmp_path)
    second_run_dir = tmp_path / "runs" / second_run_id
    second_run_dir.mkdir(parents=True)
    (second_run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    experiment = _experiment(store, str(version["version_id"]))
    experiment_id = str(experiment["experiment_id"])
    first = store.link_stage_run(
        PROJECT_ID,
        experiment_id,
        stage="baseline",
        state="queued",
        run_id=RUN_ID,
        at=START + timedelta(minutes=1),
    )
    store.link_stage_run(
        PROJECT_ID,
        experiment_id,
        stage="baseline",
        state="queued",
        run_id=second_run_id,
        at=START + timedelta(minutes=2),
    )
    store.append_stage_state(
        str(first["link_id"]),
        "running",
        reason="the first run acquired the worker",
        at=START + timedelta(minutes=3),
    )

    context = store.get_agent_brief_context(
        PROJECT_ID,
        as_of=START + timedelta(minutes=4),
    )
    baseline = next(
        row
        for row in cast(list[dict[str, object]], context["stage_statuses"])
        if row["stage"] == "baseline"
    )
    assert baseline == {"stage": "baseline", "state": "running", "run_id": RUN_ID}


def test_agent_brief_scope_and_evidence_share_one_sqlite_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    _project(store)
    version = _version(store, at=START + timedelta(minutes=1))
    experiment = _experiment(
        store,
        str(version["version_id"]),
        at=START + timedelta(minutes=2),
    )
    reader_started = threading.Event()
    release_reader = threading.Event()
    original = ControlStore._require_project

    def pause_reader(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
        row = original(connection, project_id)
        if threading.current_thread().name == "agent-brief-snapshot-reader":
            reader_started.set()
            assert release_reader.wait(timeout=5)
        return row

    monkeypatch.setattr(ControlStore, "_require_project", staticmethod(pause_reader))
    outcome: dict[str, object] = {}

    def read_brief() -> None:
        try:
            outcome["brief"] = _agent_brief(
                store,
                PROJECT_ID,
                evidence_limit=10,
                as_of="2026-07-19T10:10:00Z",
            )
        except Exception as exc:  # pragma: no cover - asserted below for a useful thread handoff.
            outcome["error"] = exc

    reader = threading.Thread(target=read_brief, name="agent-brief-snapshot-reader")
    reader.start()
    assert reader_started.wait(timeout=5)
    store.create_evidence(
        claim="Committed after the brief snapshot began.",
        assets=["AAPL"],
        frozen_universe=["AAPL", "SPY"],
        timeframe="1d",
        method="walk_forward_oos",
        knowledge_at=START + timedelta(minutes=3),
        author="owner",
        author_kind="human",
        project_id=PROJECT_ID,
        strategy_version_id=str(version["version_id"]),
        experiment_id=str(experiment["experiment_id"]),
        source_run_id=RUN_ID,
        source_artifact="manifest.json",
        source_field="outcomes.walk_forward_oos",
        at=START + timedelta(minutes=3),
    )
    release_reader.set()
    reader.join(timeout=5)

    assert not reader.is_alive()
    assert "error" not in outcome
    brief = cast(dict[str, object], outcome["brief"])
    assert brief["evidence"] == []
    later = _agent_brief(
        store,
        PROJECT_ID,
        evidence_limit=10,
        as_of="2026-07-19T10:10:00Z",
    )
    assert [row["claim"] for row in cast(list[dict[str, object]], later["evidence"])] == [
        "Committed after the brief snapshot began."
    ]


def test_legacy_agent_brief_scope_fails_closed_before_last_pointer_mutation(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    _project(store)
    version = _version(store, at=START + timedelta(minutes=1))
    experiment = _experiment(
        store,
        str(version["version_id"]),
        at=START + timedelta(minutes=2),
    )
    database = tmp_path / "control" / DATABASE_NAME
    with sqlite3.connect(database) as connection:
        connection.execute("DELETE FROM project_scope_events WHERE project_id = ?", (PROJECT_ID,))

    before_mutation = store.get_agent_brief_context(
        PROJECT_ID,
        as_of=START + timedelta(minutes=1, seconds=30),
    )
    assert before_mutation["version_id"] is None
    assert before_mutation["experiment_id"] is None
    assert before_mutation["scope_history_complete"] is False

    after_mutation = store.get_agent_brief_context(
        PROJECT_ID,
        as_of=START + timedelta(minutes=3),
    )
    assert after_mutation["version_id"] == version["version_id"]
    assert after_mutation["experiment_id"] == experiment["experiment_id"]
    assert after_mutation["scope_history_complete"] is False


def _publish_run(tmp_path: Path) -> None:
    publish_decision_grade_run(
        tmp_path,
        manifest_fields={
            "outcomes": {
                "randomized_price_null": {"passed": False},
                "walk_forward_oos": {"sharpe": 0.4},
                "locked_holdout": {"sharpe": -0.1},
            },
            "cost_sensitivity": {"passed": False},
        },
    )


def _publish_correlation_run(
    tmp_path: Path, *, metric_name: str = "pearson_correlation"
) -> dict[str, object]:
    run_dir = tmp_path / "runs" / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_hash = "b" * 64
    row = {
        "asset_a": "AAPL",
        "asset_b": "MSFT",
        "sample_count": 252,
        "aligned_oos": True,
        "frequency": "1d",
        "snapshot_hash": snapshot_hash,
        "association_not_causation": True,
        "oos_start": "2025-01-01",
        "oos_end": "2025-12-31",
        "correlation": 0.42,
        "metric_name": metric_name,
        "unit": "coefficient",
    }
    pl.DataFrame([row]).write_parquet(run_dir / "correlations.parquet")
    publish_decision_grade_run(
        tmp_path,
        manifest_fields={"snapshot_id": "snap-correlation", "snapshot_hash": snapshot_hash},
    )
    return row


def _association_selector(row: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in row.items()
        if key not in {"correlation", "metric_name", "unit"}
    }


def _publish_metric_run(
    tmp_path: Path,
    *,
    unit: str | None = "ratio",
) -> None:
    run_dir = tmp_path / "runs" / RUN_ID
    run_dir.mkdir(parents=True, exist_ok=True)
    columns: dict[str, list[object]] = {
        "symbol": ["AAPL"],
        "metric_name": ["annualized_sharpe"],
        "value": [1.25],
    }
    if unit is not None:
        columns["unit"] = [unit]
    pl.DataFrame(columns).write_parquet(run_dir / "metrics.parquet")
    publish_decision_grade_run(
        tmp_path,
        manifest_fields={
            "metrics": {
                "sharpe": 1.25,
                "sharpe_name": "annualized_sharpe",
                "sharpe_unit": "ratio",
            }
        },
    )


def _rewrite_run_manifest(
    run_dir: Path,
    *,
    changes: Mapping[str, object] | None = None,
    remove: tuple[str, ...] = (),
) -> None:
    path = run_dir / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)
    for field in remove:
        manifest.pop(field, None)
    if changes is not None:
        manifest.update(changes)
    path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def _attempt_evidence_admission(
    store: ControlStore,
    *,
    operation: str,
) -> None:
    if operation == "create":
        _draft(store, evidence_id=EVIDENCE_ID)
        return
    if operation != "revise":  # pragma: no cover - closed test parameter set
        raise AssertionError(f"unsupported test operation {operation!r}")
    store.revise_evidence(
        EVIDENCE_ID,
        status="corroborated",
        author="owner",
        author_kind="human",
        at=START + timedelta(minutes=1),
    )


def _prepare_evidence_admission(
    tmp_path: Path,
    *,
    operation: str,
) -> tuple[ControlStore, Path]:
    run_dir = publish_decision_grade_run(
        tmp_path,
        manifest_fields={"outcomes": {"randomized_price_null": {"passed": False}}},
    )
    store = _store(tmp_path)
    if operation == "revise":
        _draft(store, evidence_id=EVIDENCE_ID)
    return store, run_dir


def _complete_pre_holdout(store: ControlStore, experiment_id: str, *, at: datetime = START) -> None:
    snapshot_dir = store._data_dir / "snapshots" / "snap-aapl-2026q2"  # noqa: SLF001
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_manifest = snapshot_dir / "manifest.json"
    snapshot_manifest.write_text(
        json.dumps({"snapshot_id": "snap-aapl-2026q2", "symbols": {}}, sort_keys=True),
        encoding="utf-8",
    )
    snapshot_hash = hashlib.sha256(snapshot_manifest.read_bytes()).hexdigest()

    action_runs: dict[str, list[TestRun]] = {
        "baseline": [("1000000000000001", "backtest_run", "pass", None, None)],
        "inner_oos": [("1000000000000002", "backtest_oos", "pass", None, None)],
        "three_null_families": [
            ("1000000000000003", "validate", "pass", True, "bootstrap"),
            ("1000000000000004", "validate", "warning", None, "student_t"),
            ("1000000000000005", "validate", "warning", None, "garch"),
        ],
        "optimize_grid": [("1000000000000006", "optim_grid", "pass", True, None)],
        "portfolio_cross_asset": [
            ("1000000000000007", "backtest_portfolio", "pass", None, None),
            ("1000000000000008", "cross_sectional", "pass", None, None),
        ],
    }
    stages = {
        "baseline": "baseline",
        "inner_oos": "oos",
        "three_null_families": "robustness",
        "optimize_grid": "optimization",
        "portfolio_cross_asset": "portfolio",
    }
    for action, runs in action_runs.items():
        stage = stages[action]
        detail = store.get_project(PROJECT_ID)
        current = next(
            row["state"]
            for row in cast(list[dict[str, object]], detail["stage_states"])
            if row["experiment_id"] == experiment_id and row["stage"] == stage
        )
        if current == "not_started":
            store.append_experiment_stage_state(
                PROJECT_ID, experiment_id, stage, "ready", reason="test suite ready", at=at
            )
        store.append_experiment_stage_state(
            PROJECT_ID, experiment_id, stage, "queued", reason="test suite queued", at=at
        )
        store.append_experiment_stage_state(
            PROJECT_ID, experiment_id, stage, "running", reason="test suite running", at=at
        )
        for run_id, command, state, passed, null_model in runs:
            run_dir = store._data_dir / "runs" / run_id  # noqa: SLF001
            run_dir.mkdir(parents=True)
            manifest: dict[str, object] = {
                "schema_version": 3,
                "artifact_contract_version": 3,
                "run_identity_version": 3,
                "run_id": run_id,
                "command": command,
                "snapshot_id": "snap-aapl-2026q2",
                "snapshot_hash": snapshot_hash,
                "execution_fingerprint": "a" * 64,
                "strategy_fingerprint": "b" * 64,
                "source_fingerprint": "c" * 64,
                "research_cutoff": "2026-03-31",
                "artifacts": {},
            }
            if passed is not None:
                manifest["passed"] = passed
            if null_model is not None:
                manifest["metadata"] = {"null_model": null_model}
            (run_dir / "manifest.json").write_text(
                json.dumps(manifest, sort_keys=True), encoding="utf-8"
            )
            store.link_suite_stage_run(
                PROJECT_ID,
                experiment_id,
                suite_action=action,
                stage=stage,
                state=state,
                run_id=run_id,
                at=at,
            )
        store.complete_suite_stage(
            PROJECT_ID,
            experiment_id,
            suite_action=action,
            stage=stage,
            state="pass",
            reason="verified test suite evidence",
            at=at,
        )
    for state in ("ready", "queued", "running", "pass"):
        store.append_experiment_stage_state(
            PROJECT_ID,
            experiment_id,
            "candidate",
            state,
            reason="candidate frozen from verified evidence",
            at=at,
        )


def _draft(
    store: ControlStore,
    *,
    evidence_id: str,
    assets: tuple[str, ...] = ("AAPL",),
    frozen_universe: tuple[str, ...] = ("AAPL", "SPY"),
    knowledge_at: datetime = START,
    market_data_cutoff: datetime | None = None,
    author_kind: str = "agent",
    metric_value: float | None = None,
    metric_name: str | None = None,
    metric_unit: str | None = None,
    source_run_id: str | None = RUN_ID,
    source_artifact: str | None = "manifest.json",
    source_field: str | None = "outcomes.randomized_price_null",
    contradiction_ids: tuple[str, ...] = (),
    at: datetime = START,
) -> dict[str, object]:
    return store.create_evidence(
        claim="A cited test finding.",
        assets=assets,
        frozen_universe=frozen_universe,
        timeframe="1d",
        method="walk_forward_oos",
        knowledge_at=knowledge_at,
        market_data_cutoff=market_data_cutoff,
        author="codex",
        author_kind=cast(AuthorKind, author_kind),
        source_run_id=source_run_id,
        source_artifact=source_artifact,
        source_field=source_field,
        metric_value=metric_value,
        metric_name=metric_name,
        metric_unit=metric_unit,
        contradiction_ids=contradiction_ids,
        evidence_id=evidence_id,
        at=at,
    )


def test_content_addressed_versions_and_experiments_are_idempotent(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    first_version = _version(store)
    second_version = _version(store)
    assert first_version["version_id"] == second_version["version_id"]
    assert str(first_version["version_id"]).startswith("sv_")

    first_experiment = _experiment(store, str(first_version["version_id"]))
    second_experiment = _experiment(store, str(first_version["version_id"]))
    assert first_experiment["experiment_id"] == second_experiment["experiment_id"]
    assert first_experiment["universe"] == ["AAPL", "SPY"]
    assert str(first_experiment["experiment_id"]).startswith("ex_")

    detail = store.get_project(PROJECT_ID)
    assert detail["current_version_id"] == first_version["version_id"]
    assert detail["current_experiment_id"] == first_experiment["experiment_id"]
    assert len(cast(list[object], detail["versions"])) == 1
    assert len(cast(list[object], detail["experiments"])) == 1
    stages = cast(list[dict[str, object]], detail["stage_states"])
    assert len(stages) == 14
    assert next(row for row in stages if row["stage"] == "baseline")["state"] == "ready"
    assert {row["stage"] for row in stages if row["state"] == "pass"} == {
        "hypothesis",
        "data",
        "strategy",
    }
    assert (tmp_path / "control" / "workstation.sqlite3").is_file()
    assert all(
        not (tmp_path / run_dir / "workstation.sqlite3").exists() for run_dir in ("runs", "optim")
    )


def test_concurrent_content_addressed_version_link_is_atomic(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    with ThreadPoolExecutor(max_workers=8) as pool:
        rows = list(pool.map(lambda _: _version(store), range(16)))
    assert len({str(row["version_id"]) for row in rows}) == 1
    assert len(cast(list[object], store.get_project(PROJECT_ID)["versions"])) == 1


def test_holdout_reveal_is_one_shot_and_later_change_is_audited_contamination(
    tmp_path: Path,
) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    experiment = _experiment(store, str(version["version_id"]))

    sealed = store.seal_holdout(
        PROJECT_ID,
        str(experiment["experiment_id"]),
        actor="owner",
        reason="final period reserved before model selection",
        start_date="2026-04-01",
        end_date="2026-06-30",
        at=START + timedelta(minutes=30),
    )
    assert sealed["revealed_at"] is None

    _complete_pre_holdout(
        store,
        str(experiment["experiment_id"]),
        at=START + timedelta(minutes=45),
    )

    revealed = store.reveal_holdout(
        PROJECT_ID,
        str(experiment["experiment_id"]),
        actor="owner",
        reason="candidate frozen and approved",
        at=START + timedelta(hours=1),
    )
    assert revealed["contaminated_at"] is None
    pre_reveal = store.get_agent_brief_context(
        PROJECT_ID,
        as_of=START + timedelta(minutes=59),
    )
    assert [
        row["event"] for row in cast(list[dict[str, object]], pre_reveal["holdout_events"])
    ] == ["sealed"]
    brief_before_reveal = _agent_brief(
        store,
        PROJECT_ID,
        evidence_limit=10,
        as_of="2026-07-19T10:59:00Z",
    )
    warnings = cast(list[str], brief_before_reveal["warnings"])
    assert not any("holdout is visible" in warning for warning in warnings)
    post_reveal = store.get_agent_brief_context(
        PROJECT_ID,
        as_of=START + timedelta(hours=1, minutes=1),
    )
    assert [
        row["event"] for row in cast(list[dict[str, object]], post_reveal["holdout_events"])
    ] == ["sealed", "revealed"]
    with pytest.raises(DataError, match="already revealed"):
        store.reveal_holdout(
            PROJECT_ID,
            str(experiment["experiment_id"]),
            actor="owner",
            reason="second look",
        )

    changed = _version(
        store,
        source="git:2222222",
        window=30,
        at=START + timedelta(hours=2),
    )
    assert changed["version_id"] != version["version_id"]
    detail = store.get_project(PROJECT_ID)
    holdout = cast(list[dict[str, object]], detail["holdouts"])[0]
    assert holdout["contaminated_at"] is not None
    assert holdout["contamination_reason"] == "strategy version changed after holdout reveal"
    audit = cast(list[dict[str, object]], detail["holdout_audit"])
    assert [row["event"] for row in audit] == [
        "sealed",
        "revealed",
        "contaminated",
    ]
    historical = store.get_agent_brief_context(
        PROJECT_ID,
        as_of=START + timedelta(minutes=59),
    )
    assert historical["version_id"] == version["version_id"]
    assert "contaminated" not in {
        row["event"] for row in cast(list[dict[str, object]], historical["holdout_events"])
    }


def test_sealed_holdout_window_is_hashed_and_redacted_until_reveal(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    experiment = _experiment(store, str(version["version_id"]))
    experiment_id = str(experiment["experiment_id"])
    sealed = store.seal_holdout(
        PROJECT_ID,
        experiment_id,
        actor="owner",
        reason="reserve the final calendar window",
        start_date="2026-04-01",
        end_date="2026-06-30",
        at=START + timedelta(minutes=30),
    )
    assert sealed["holdout_spec_hash"] is not None
    assert sealed["start_date"] is None and sealed["end_date"] is None
    private = store.get_holdout_spec(PROJECT_ID, experiment_id)
    assert private == {
        "spec_hash": sealed["holdout_spec_hash"],
        "start_date": "2026-04-01",
        "end_date": "2026-06-30",
    }
    public = cast(list[dict[str, object]], store.get_project(PROJECT_ID)["holdouts"])[0]
    assert public["start_date"] is None and public["end_date"] is None

    _complete_pre_holdout(store, experiment_id, at=START + timedelta(minutes=45))
    revealed = store.reveal_holdout(
        PROJECT_ID,
        experiment_id,
        actor="owner",
        reason="candidate frozen",
        at=START + timedelta(hours=1),
    )
    assert revealed["start_date"] == "2026-04-01"
    assert revealed["end_date"] == "2026-06-30"


def test_holdout_window_requires_both_ordered_canonical_dates(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    experiment = _experiment(store, str(version["version_id"]))
    experiment_id = str(experiment["experiment_id"])
    with pytest.raises(DataError, match="expected a string"):
        store.seal_holdout(
            PROJECT_ID,
            experiment_id,
            actor="owner",
            reason="invalid",
            start_date="2026-04-01",
            end_date=cast(str, None),
        )
    with pytest.raises(DataError, match="must not follow"):
        store.seal_holdout(
            PROJECT_ID,
            experiment_id,
            actor="owner",
            reason="invalid",
            start_date="2026-07-01",
            end_date="2026-06-30",
        )


def test_holdout_seal_is_rejected_after_any_research_attempt(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    experiment = _experiment(store, str(version["version_id"]))
    experiment_id = str(experiment["experiment_id"])
    store.record_attempt(
        PROJECT_ID,
        experiment_id,
        stage="baseline",
        status="queued",
        config_fingerprint="suite:baseline:test",
        details={"action": "baseline"},
        at=START + timedelta(minutes=1),
    )

    with pytest.raises(DataError, match="before any research attempt or run"):
        store.seal_holdout(
            PROJECT_ID,
            experiment_id,
            actor="owner",
            reason="too late",
            start_date="2026-04-01",
            end_date="2026-06-30",
            at=START + timedelta(minutes=2),
        )


def test_project_lineage_cannot_reuse_any_revealed_holdout_dates(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    first = _experiment(store, str(version["version_id"]))
    first_id = str(first["experiment_id"])
    store.seal_holdout(
        PROJECT_ID,
        first_id,
        actor="owner",
        reason="reserve final window",
        start_date="2026-04-01",
        end_date="2026-06-30",
        at=START + timedelta(minutes=30),
    )
    _complete_pre_holdout(store, first_id, at=START + timedelta(minutes=45))
    store.reveal_holdout(
        PROJECT_ID,
        first_id,
        actor="owner",
        reason="candidate frozen",
        at=START + timedelta(hours=1),
    )

    next_version = _version(
        store,
        source="git:lineage-next",
        window=30,
        at=START + timedelta(hours=2),
    )
    descendant = _experiment(
        store,
        str(next_version["version_id"]),
        at=START + timedelta(hours=2),
    )
    descendant_id = str(descendant["experiment_id"])
    for start, end in (
        ("2026-04-01", "2026-06-30"),
        ("2026-03-01", "2026-04-15"),
        ("2026-06-15", "2026-07-31"),
    ):
        with pytest.raises(DataError, match="overlaps a previously revealed window"):
            store.seal_holdout(
                PROJECT_ID,
                descendant_id,
                actor="owner",
                reason="must not reuse disclosed data",
                start_date=start,
                end_date=end,
                at=START + timedelta(hours=3),
            )


@pytest.mark.parametrize(
    "method",
    [
        "correlation",
        "pearson_correlation",
        "spearman_correlation",
        "kendall_tau",
        "cross_asset_association",
    ],
)
def test_allowed_association_methods_require_governance_and_visible_label(
    tmp_path: Path, method: str
) -> None:
    row = _publish_correlation_run(tmp_path, metric_name=method)
    selector = _association_selector(row)
    store = _store(tmp_path)
    evidence = store.create_evidence(
        claim="AAPL and MSFT were positively associated in aligned OOS observations.",
        assets=["AAPL", "MSFT"],
        frozen_universe=["AAPL", "MSFT", "SPY"],
        timeframe="1d",
        method=method,
        knowledge_at=START,
        market_data_cutoff=START,
        author="research-agent",
        author_kind="agent",
        metric_name=method,
        metric_value=0.42,
        metric_unit="coefficient",
        source_run_id=RUN_ID,
        source_artifact="correlations.parquet",
        source_field="correlation",
        row_selector=selector,
        at=START,
    )
    assert evidence["status"] == "draft"
    assert evidence["interpretation_label"] == "association, not causation"

    for field, value, message in (
        ("aligned_oos", False, "aligned_oos"),
        ("sample_count", 0, "sample_count"),
        ("frequency", "1h", "frequency"),
        ("association_not_causation", False, "association, not causation"),
        ("snapshot_hash", "c" * 64, "snapshot_hash"),
    ):
        invalid = dict(selector)
        invalid[field] = value
        with pytest.raises(DataError, match=message):
            store.create_evidence(
                claim="Invalid correlation claim.",
                assets=["AAPL", "MSFT"],
                frozen_universe=["AAPL", "MSFT"],
                timeframe="1d",
                method=method,
                knowledge_at=START,
                author="owner",
                author_kind="human",
                metric_name=method,
                metric_value=0.42,
                metric_unit="coefficient",
                source_run_id=RUN_ID,
                source_artifact="correlations.parquet",
                source_field="correlation",
                row_selector=invalid,
                at=START,
            )


@pytest.mark.parametrize(
    "method",
    [
        "Pearson correlation on aligned OOS returns",
        "Spearman rank correlation",
        "kendall_correlation",
        "cross_asset_association_v2",
        "rolling_crosscorrelation",
    ],
)
def test_association_like_method_names_outside_allowlist_fail_closed(
    tmp_path: Path, method: str
) -> None:
    _publish_metric_run(tmp_path)
    store = _store(tmp_path)
    with pytest.raises(DataError, match="unsupported association method identifier"):
        store.create_evidence(
            claim="An unsupported association method must not bypass governance.",
            assets=["AAPL", "MSFT"],
            frozen_universe=["AAPL", "MSFT"],
            timeframe="1d",
            method=method,
            knowledge_at=START,
            author="research-agent",
            author_kind="agent",
            source_run_id=RUN_ID,
            source_artifact="manifest.json",
            source_field="metrics.sharpe",
            at=START,
        )


def test_evidence_metrics_bind_to_exact_parquet_and_manifest_scalars(tmp_path: Path) -> None:
    _publish_metric_run(tmp_path)
    store = _store(tmp_path)

    parquet = store.create_evidence(
        claim="The costed OOS Sharpe was exactly 1.25.",
        assets=["AAPL"],
        frozen_universe=["AAPL"],
        timeframe="1d",
        method="walk_forward_oos",
        knowledge_at=START,
        author="research-agent",
        author_kind="agent",
        metric_name="annualized_sharpe",
        metric_value=1.25,
        metric_unit="ratio",
        source_run_id=RUN_ID,
        source_artifact="metrics.parquet",
        source_field="value",
        row_selector={"symbol": "AAPL"},
        at=START,
    )
    manifest = store.create_evidence(
        claim="The manifest reports the same exact Sharpe.",
        assets=["AAPL"],
        frozen_universe=["AAPL"],
        timeframe="1d",
        method="walk_forward_oos",
        knowledge_at=START,
        author="research-agent",
        author_kind="agent",
        metric_name="annualized_sharpe",
        metric_value=1.25,
        metric_unit="ratio",
        source_run_id=RUN_ID,
        source_artifact="manifest.json",
        source_field="metrics.sharpe",
        at=START,
    )

    assert parquet["metric_value"] == manifest["metric_value"] == 1.25
    assert parquet["metric_unit"] == manifest["metric_unit"] == "ratio"


@pytest.mark.parametrize(
    ("metric_name", "metric_value", "message"),
    [
        ("annualized_sharpe", 1.24, "metric_value.*cited artifact scalar"),
        ("sharpe", 1.25, "metric_name.*cited artifact metric"),
    ],
)
def test_evidence_rejects_metric_value_or_name_not_bound_to_citation(
    tmp_path: Path, metric_name: str, metric_value: float, message: str
) -> None:
    _publish_metric_run(tmp_path)
    store = _store(tmp_path)
    with pytest.raises(DataError, match=message):
        store.create_evidence(
            claim="This self-asserted metric must be rejected.",
            assets=["AAPL"],
            frozen_universe=["AAPL"],
            timeframe="1d",
            method="walk_forward_oos",
            knowledge_at=START,
            author="research-agent",
            author_kind="agent",
            metric_name=metric_name,
            metric_value=metric_value,
            metric_unit="ratio",
            source_run_id=RUN_ID,
            source_artifact="metrics.parquet",
            source_field="value",
            row_selector={"symbol": "AAPL"},
            at=START,
        )


@pytest.mark.parametrize(
    ("artifact_unit", "message"),
    [
        (None, "does not carry an explicit metric unit"),
        ("percent", "metric_unit.*cited artifact unit"),
    ],
)
def test_evidence_rejects_missing_or_mismatched_artifact_unit(
    tmp_path: Path, artifact_unit: str | None, message: str
) -> None:
    _publish_metric_run(tmp_path, unit=artifact_unit)
    store = _store(tmp_path)
    with pytest.raises(DataError, match=message):
        store.create_evidence(
            claim="The artifact must carry the claimed unit.",
            assets=["AAPL"],
            frozen_universe=["AAPL"],
            timeframe="1d",
            method="walk_forward_oos",
            knowledge_at=START,
            author="research-agent",
            author_kind="agent",
            metric_name="annualized_sharpe",
            metric_value=1.25,
            metric_unit="ratio",
            source_run_id=RUN_ID,
            source_artifact="metrics.parquet",
            source_field="value",
            row_selector={"symbol": "AAPL"},
            at=START,
        )


def test_evidence_rejects_a_tampered_v3_parquet_before_reading_it(tmp_path: Path) -> None:
    run_id = "fedcba9876543210"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    artifact = run_dir / "metrics.parquet"
    pl.DataFrame({"metric": [0.42]}).write_parquet(artifact)
    _artifacts.write_manifest(
        run_dir,
        {
            "run_id": run_id,
            "command": "test_fixture",
            "run_identity_version": 3,
            "execution_fingerprint": "a" * 64,
            "strategy_fingerprint": "b" * 64,
            "source_fingerprint": "c" * 64,
            "snapshot_hash": None,
        },
    )
    artifact.write_bytes(artifact.read_bytes() + b"tampered")

    store = _store(tmp_path)
    with pytest.raises(DataError, match=r"artifact metrics\.parquet (size|hash) mismatch"):
        store.create_evidence(
            claim="This citation must never read modified bytes.",
            assets=["AAPL"],
            frozen_universe=["AAPL"],
            timeframe="1d",
            method="verified metric",
            knowledge_at=START,
            author="codex",
            author_kind="agent",
            source_run_id=run_id,
            source_artifact="metrics.parquet",
            source_field="metric",
            row_selector={"row_index": 0},
        )


@pytest.mark.parametrize("operation", ["create", "revise"])
@pytest.mark.parametrize("schema_version", [1, 2])
def test_evidence_admission_rejects_legacy_manifest_downgrades(
    tmp_path: Path,
    operation: str,
    schema_version: int,
) -> None:
    store, run_dir = _prepare_evidence_admission(tmp_path, operation=operation)
    _rewrite_run_manifest(run_dir, changes={"schema_version": schema_version})

    with pytest.raises(DataError, match="immutable v3 manifest"):
        _attempt_evidence_admission(store, operation=operation)

    if operation == "create":
        assert store.list_evidence() == []
    else:
        evidence = store.get_evidence(EVIDENCE_ID)
        assert evidence["status"] == "draft"
        assert evidence["revision"] == 1


@pytest.mark.parametrize("operation", ["create", "revise"])
@pytest.mark.parametrize(
    ("changes", "message"),
    [
        pytest.param(
            {"artifact_contract_version": 2},
            "artifact contract",
            id="artifact-contract-v2",
        ),
        pytest.param(
            {"run_identity_version": 2},
            "run_identity_version=3",
            id="run-identity-v2",
        ),
        pytest.param(
            {"run_id": "fedcba9876543210"},
            "identity does not match directory",
            id="selector-mismatch",
        ),
    ],
)
def test_evidence_admission_rejects_v3_authority_downgrades_and_selector_mismatch(
    tmp_path: Path,
    operation: str,
    changes: dict[str, object],
    message: str,
) -> None:
    store, run_dir = _prepare_evidence_admission(tmp_path, operation=operation)
    _rewrite_run_manifest(run_dir, changes=changes)

    with pytest.raises(DataError, match=message):
        _attempt_evidence_admission(store, operation=operation)

    if operation == "create":
        assert store.list_evidence() == []
    else:
        assert store.get_evidence(EVIDENCE_ID)["revision"] == 1


@pytest.mark.parametrize("operation", ["create", "revise"])
@pytest.mark.parametrize(
    ("changes", "remove"),
    [
        pytest.param({}, ("command",), id="missing-command"),
        pytest.param({"command": "validate_v3"}, (), id="aliased-command"),
    ],
)
def test_evidence_admission_requires_a_decision_grade_command(
    tmp_path: Path,
    operation: str,
    changes: dict[str, object],
    remove: tuple[str, ...],
) -> None:
    store, run_dir = _prepare_evidence_admission(tmp_path, operation=operation)
    _rewrite_run_manifest(run_dir, changes=changes, remove=remove)

    with pytest.raises(DataError, match="decision-grade command"):
        _attempt_evidence_admission(store, operation=operation)

    if operation == "create":
        assert store.list_evidence() == []
    else:
        assert store.get_evidence(EVIDENCE_ID)["revision"] == 1


@pytest.mark.parametrize("operation", ["create", "revise"])
@pytest.mark.parametrize(
    ("changes", "remove"),
    [
        pytest.param({"command": "research-pilot"}, ("kind",), id="missing-kind"),
        pytest.param({"kind": "research-v1"}, (), id="aliased-kind"),
        pytest.param(
            {"research_contract_id": "rc_" + "1" * 64},
            ("command", "kind"),
            id="contract-without-kind-or-command",
        ),
        pytest.param({"evidence_zone": "D0"}, (), id="d0-zone"),
        pytest.param({"evidence_zone": "D1"}, (), id="d1-zone"),
        pytest.param({"evidence_zone": "D2"}, (), id="d2-zone"),
        pytest.param({"evidence_zone": "D3"}, (), id="d3-zone"),
        pytest.param(
            {"eligible_for_holdout_or_execution": False},
            (),
            id="holdout-execution-ineligible",
        ),
        pytest.param({"real_market_evidence": False}, (), id="not-real-market-evidence"),
    ],
)
def test_evidence_admission_rejects_every_research_authority_marker(
    tmp_path: Path,
    operation: str,
    changes: dict[str, object],
    remove: tuple[str, ...],
) -> None:
    store, run_dir = _prepare_evidence_admission(tmp_path, operation=operation)
    _rewrite_run_manifest(run_dir, changes=changes, remove=remove)

    with pytest.raises(DataError, match="research runs cannot enter the generic evidence ledger"):
        _attempt_evidence_admission(store, operation=operation)

    if operation == "create":
        assert store.list_evidence() == []
    else:
        assert store.get_evidence(EVIDENCE_ID)["revision"] == 1


def test_evidence_version_and_experiment_must_share_the_same_lineage(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    _project(store)
    first_version = _version(store)
    experiment = _experiment(store, str(first_version["version_id"]))
    second_version = _version(store, source="git:2222222", window=40)

    def create(version_id: str) -> dict[str, object]:
        return store.create_evidence(
            claim="The cited null result belongs to this immutable experiment lineage.",
            assets=["AAPL"],
            frozen_universe=["AAPL", "SPY"],
            timeframe="1d",
            method="walk_forward_oos",
            knowledge_at=START,
            author="codex",
            author_kind="agent",
            project_id=PROJECT_ID,
            strategy_version_id=version_id,
            experiment_id=str(experiment["experiment_id"]),
            source_run_id=RUN_ID,
            source_artifact="manifest.json",
            source_field="outcomes.randomized_price_null",
            at=START,
        )

    valid = create(str(first_version["version_id"]))
    assert valid["strategy_version_id"] == first_version["version_id"]
    assert valid["experiment_id"] == experiment["experiment_id"]

    with pytest.raises(DataError, match="strategy version does not match the experiment lineage"):
        create(str(second_version["version_id"]))


def test_stage_links_attempts_and_run_ids_are_strict(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    experiment = _experiment(store, str(version["version_id"]))
    experiment_id = str(experiment["experiment_id"])

    link = store.link_stage_run(
        PROJECT_ID,
        experiment_id,
        stage="baseline",
        state="ready",
        run_id=RUN_ID,
        at=START,
    )
    attempt = store.record_attempt(
        PROJECT_ID,
        experiment_id,
        stage="robustness",
        status="failed",
        config_fingerprint="cfg:bootstrap:7",
        error="null threshold not cleared",
        details={"family": "bootstrap", "tier": 2},
        at=START,
    )
    assert link["run_id"] == RUN_ID
    assert attempt["status"] == "failed"
    attempts = cast(list[dict[str, object]], store.get_project(PROJECT_ID)["attempts"])
    details = cast(dict[str, object], attempts[0]["details"])
    assert details["tier"] == 2

    queued = store.link_stage_run(
        PROJECT_ID,
        experiment_id,
        stage="oos",
        state="queued",
        run_id=RUN_ID,
        at=START,
    )
    running = store.append_stage_state(
        str(queued["link_id"]),
        "running",
        reason="worker accepted job",
        at=START + timedelta(seconds=1),
    )
    assert running["state"] == "running"
    with pytest.raises(DataError, match="suite-owned"):
        store.append_stage_state(
            str(queued["link_id"]),
            "pass",
            reason="generic callers cannot award a gate",
            at=START + timedelta(seconds=2),
        )

    baseline_state = next(
        row
        for row in cast(list[dict[str, object]], store.get_project(PROJECT_ID)["stage_states"])
        if row["stage"] == "baseline"
    )
    assert baseline_state["state"] == "ready"

    _version(store, source="git:3333333", window=25, at=START + timedelta(seconds=3))
    links = cast(list[dict[str, object]], store.get_project(PROJECT_ID)["stage_run_links"])
    assert all(stage_link["state"] == "stale" for stage_link in links)
    baseline = next(stage_link for stage_link in links if stage_link["stage"] == "baseline")
    baseline_history = cast(list[dict[str, object]], baseline["state_history"])
    assert [event["state"] for event in baseline_history] == ["ready", "stale"]
    assert baseline_history[-1]["reason"] == "strategy version changed"
    assert all(
        row["state"] == "stale"
        for row in cast(list[dict[str, object]], store.get_project(PROJECT_ID)["stage_states"])
    )

    with pytest.raises(DataError, match="unknown completed run"):
        store.link_stage_run(
            PROJECT_ID,
            experiment_id,
            stage="oos",
            state="queued",
            run_id="fedcba9876543210",
        )
    with pytest.raises(DataError, match="unsupported development stage"):
        store.record_attempt(
            PROJECT_ID,
            experiment_id,
            stage="deploy_live",
            status="failed",
            config_fingerprint="cfg:x",
            error="not allowed",
        )


def test_job_status_and_event_journal_are_atomic_and_terminal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    job = store.create_job(
        kind="validation_suite",
        project_id=PROJECT_ID,
        request={"families": ["bootstrap", "student_t", "garch"]},
        job_id=JOB_ID,
        at=START,
    )
    assert job["status"] == "queued"
    assert job["last_sequence"] == 1

    running = store.set_job_status(JOB_ID, "running", at=START + timedelta(seconds=1))
    heartbeat = store.append_job_event(
        JOB_ID,
        event_type="heartbeat",
        payload={"progress": 0.5},
        at=START + timedelta(seconds=2),
    )
    done = store.set_job_status(
        JOB_ID,
        "succeeded",
        result_run_id=None,
        at=START + timedelta(seconds=3),
    )
    assert running["last_sequence"] == 2
    assert heartbeat["sequence"] == 3
    assert done["last_sequence"] == 4
    events = cast(list[dict[str, object]], store.get_job(JOB_ID)["events"])
    assert [row["event_type"] for row in events] == [
        "created",
        "status",
        "heartbeat",
        "status",
    ]
    with pytest.raises(DataError, match="terminal job"):
        store.append_job_event(JOB_ID, event_type="log", payload={"message": "late"})


def test_concurrent_direct_heavyweight_requests_admit_exactly_one(tmp_path: Path) -> None:
    assert ControlStore(tmp_path).heavyweight_job_capacity()["active_count"] == 0
    barrier = threading.Barrier(2)

    def reserve(kind: str, job_id: str) -> tuple[str, str]:
        barrier.wait()
        try:
            ControlStore(tmp_path).create_job(kind=kind, request={}, job_id=job_id)
        except DataError as exc:
            return "blocked", str(exc)
        return "admitted", job_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(reserve, "ml_train", "01010101-0101-4101-8101-010101010101"),
            pool.submit(reserve, "kronos_forecast", "02020202-0202-4202-8202-020202020202"),
        ]
    results = [future.result() for future in futures]
    assert sorted(status for status, _ in results) == ["admitted", "blocked"]
    assert "heavyweight job capacity is occupied" in next(
        detail for status, detail in results if status == "blocked"
    )
    capacity = ControlStore(tmp_path).heavyweight_job_capacity()
    assert capacity["limit"] == 1
    assert capacity["active_count"] == 1
    assert capacity["busy"] is True


def test_job_event_windows_remain_bounded_past_ten_thousand_rows(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_job(
        kind="validation_suite",
        request={"symbol": "AAPL"},
        job_id=JOB_ID,
        at=START,
    )
    total = 10_005
    occurred_at = START.isoformat(timespec="microseconds").replace("+00:00", "Z")
    database = tmp_path / "control" / DATABASE_NAME
    with sqlite3.connect(database) as connection:
        connection.executemany(
            "INSERT INTO job_events VALUES (?, ?, 'log', ?, ?)",
            (
                (JOB_ID, sequence, occurred_at, json.dumps({"index": sequence}))
                for sequence in range(2, total + 1)
            ),
        )
        connection.execute(
            "UPDATE jobs SET last_sequence = ? WHERE job_id = ?",
            (total, JOB_ID),
        )

    default_window = store.get_job(JOB_ID)
    default_events = cast(list[dict[str, object]], default_window["events"])
    assert [event["sequence"] for event in default_events[:2]] == [1, 2]
    assert default_events[-1]["sequence"] == 200
    assert default_window["event_total"] == total
    assert default_window["events_has_more"] is True
    assert default_window["events_truncated"] is True

    middle = store.get_job(JOB_ID, event_limit=3, event_offset=10_000)
    middle_events = cast(list[dict[str, object]], middle["events"])
    assert [event["sequence"] for event in middle_events] == [10_001, 10_002, 10_003]
    assert middle["events_has_more"] is True

    tail = store.get_job(JOB_ID, event_limit=3, event_tail=True)
    tail_events = cast(list[dict[str, object]], tail["events"])
    assert [event["sequence"] for event in tail_events] == [10_003, 10_004, 10_005]
    assert tail["event_tail"] is True
    assert tail["events_has_more"] is True

    prior_tail = store.get_job(JOB_ID, event_limit=3, event_offset=3, event_tail=True)
    prior_events = cast(list[dict[str, object]], prior_tail["events"])
    assert [event["sequence"] for event in prior_events] == [10_000, 10_001, 10_002]

    final = store.get_job(JOB_ID, event_limit=3, event_offset=10_003)
    final_events = cast(list[dict[str, object]], final["events"])
    assert [event["sequence"] for event in final_events] == [10_004, 10_005]
    assert final["events_has_more"] is False
    assert final["events_truncated"] is False

    with pytest.raises(DataError, match="limit must be in 1..500"):
        store.get_job(JOB_ID, event_limit=501)


def test_nonterminal_jobs_reconcile_after_restart(tmp_path: Path) -> None:
    store = _store(tmp_path)
    queued = store.create_job(
        kind="kronos_eval",
        request={"symbol": "AAPL"},
        job_id=JOB_ID,
        at=START,
    )
    assert queued["status"] == "queued"

    assert store.reconcile_interrupted_jobs(at=START + timedelta(seconds=59)) == []
    rows = store.reconcile_interrupted_jobs(at=START + timedelta(minutes=1))
    assert len(rows) == 1
    assert rows[0]["status"] == "failed"
    assert rows[0]["terminal_error"] == "process restarted before terminal job status"
    assert store.get_job(JOB_ID)["last_sequence"] == 2
    assert store.reconcile_interrupted_jobs(at=START + timedelta(minutes=2)) == []


def test_job_cancellation_request_is_durable_idempotent_and_not_terminal(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_job(
        kind="validation_suite",
        request={"symbol": "AAPL"},
        job_id=JOB_ID,
        at=START,
    )

    requested = store.request_job_cancellation(
        JOB_ID,
        actor="owner",
        reason="stop this workload",
        at=START + timedelta(seconds=1),
    )
    repeated = store.request_job_cancellation(
        JOB_ID,
        actor="owner",
        reason="repeat request",
        at=START + timedelta(seconds=2),
    )
    assert requested == repeated == {"job_id": JOB_ID, "status": "cancellation_requested"}
    assert store.job_cancellation_requested(JOB_ID) is True
    job = store.get_job(JOB_ID)
    assert job["status"] == "queued"
    events = cast(list[dict[str, object]], job["events"])
    assert [event["event_type"] for event in events] == ["created", "cancel_requested"]
    assert events[-1]["payload"] == {"actor": "owner", "reason": "stop this workload"}

    store.set_job_status(JOB_ID, "cancelled", at=START + timedelta(seconds=3))
    assert store.job_cancellation_requested(JOB_ID) is False
    assert store.request_job_cancellation(
        JOB_ID,
        actor="owner",
        reason="late request",
        at=START + timedelta(seconds=4),
    ) == {"job_id": JOB_ID, "status": "already_terminal"}


def test_resumed_job_accepts_a_new_cancellation_request(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_job(
        kind="validation_suite",
        request={"symbol": "AAPL"},
        job_id=JOB_ID,
        at=START,
    )
    store.request_job_cancellation(
        JOB_ID,
        actor="owner",
        reason="cancel first lease",
        at=START + timedelta(seconds=1),
    )
    store.set_job_status(JOB_ID, "cancelled", at=START + timedelta(seconds=2))

    # The holdout-resume path appends this audited transition atomically before reusing the same
    # job id.  Build the exact journal state directly so this unit test stays independent of the
    # much larger holdout-evidence fixture.
    resumed_at = (
        (START + timedelta(seconds=3)).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )
    database = tmp_path / "control" / DATABASE_NAME
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO job_events VALUES (?, 4, 'status', ?, ?)",
            (
                JOB_ID,
                resumed_at,
                json.dumps(
                    {"from": "cancelled", "resume": True, "to": "queued"},
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            ),
        )
        connection.execute(
            """UPDATE jobs SET status = 'queued', updated_at = ?, heartbeat_at = ?,
            last_sequence = 4 WHERE job_id = ?""",
            (resumed_at, resumed_at, JOB_ID),
        )

    assert store.job_cancellation_requested(JOB_ID) is False
    second = store.request_job_cancellation(
        JOB_ID,
        actor="owner",
        reason="cancel resumed lease",
        at=START + timedelta(seconds=4),
    )
    assert second == {"job_id": JOB_ID, "status": "cancellation_requested"}
    assert store.job_cancellation_requested(JOB_ID) is True
    events = cast(list[dict[str, object]], store.get_job(JOB_ID)["events"])
    assert [event["event_type"] for event in events].count("cancel_requested") == 2


def test_fresh_running_heartbeat_is_not_reconciled(tmp_path: Path) -> None:
    store = _store(tmp_path)
    store.create_job(kind="validation_suite", request={}, job_id=JOB_ID, at=START)
    store.set_job_status(JOB_ID, "running", at=START + timedelta(seconds=50))
    store.append_job_event(
        JOB_ID,
        event_type="heartbeat",
        payload={"step": 1},
        at=START + timedelta(seconds=100),
    )

    assert (
        store.reconcile_interrupted_jobs(
            stale_after_seconds=60,
            at=START + timedelta(seconds=150),
        )
        == []
    )
    reconciled = store.reconcile_interrupted_jobs(
        stale_after_seconds=60,
        at=START + timedelta(seconds=160),
    )
    assert [row["job_id"] for row in reconciled] == [JOB_ID]


def test_evidence_revisions_are_append_only_and_as_of_safe(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    _project(store)
    draft = store.create_evidence(
        claim="AAPL reversal is strongest after large negative z-scores.",
        assets=["AAPL"],
        frozen_universe=["SPY", "AAPL"],
        timeframe="1d",
        method="walk_forward_oos",
        knowledge_at=START,
        market_data_cutoff=START - timedelta(days=1),
        author="codex",
        author_kind="agent",
        project_id=PROJECT_ID,
        source_run_id=RUN_ID,
        source_artifact="manifest.json",
        source_field="outcomes.randomized_price_null",
        evidence_id=EVIDENCE_ID,
        at=START,
    )
    assert draft["status"] == "draft"
    assert draft["revision"] == 1
    assert draft["parent_revision"] is None
    assert draft["frozen_universe"] == ["AAPL", "SPY"]

    rejected = store.revise_evidence(
        EVIDENCE_ID,
        status="rejected",
        author="owner",
        author_kind="human",
        claim="The effect did not survive the locked costs.",
        counterevidence=["validation gate randomized_price_null failed"],
        at=START + timedelta(hours=1),
    )
    assert rejected["revision"] == 2
    assert rejected["parent_revision"] == 1
    assert store.get_evidence(EVIDENCE_ID)["status"] == "rejected"
    assert (
        store.list_evidence(asset="AAPL", as_of=START + timedelta(minutes=30))[0]["status"]
        == "draft"
    )
    assert store.list_evidence(asset="MSFT") == []

    contradiction = store.create_evidence(
        claim="The apparent AAPL reversal is explained by transaction costs.",
        assets=["AAPL"],
        frozen_universe=["AAPL", "SPY"],
        timeframe="1d",
        method="cost_sensitivity",
        knowledge_at=START + timedelta(hours=2),
        market_data_cutoff=START - timedelta(days=1),
        author="owner",
        author_kind="human",
        project_id=PROJECT_ID,
        source_run_id=RUN_ID,
        source_artifact="manifest.json",
        source_field="cost_sensitivity",
        contradiction_ids=[EVIDENCE_ID],
        evidence_id=EVIDENCE_ID_2,
        at=START + timedelta(hours=2),
    )
    assert contradiction["contradiction_ids"] == [EVIDENCE_ID]

    with pytest.raises(DataError, match="invalid evidence transition"):
        store.revise_evidence(
            EVIDENCE_ID,
            status="corroborated",
            author="owner",
            author_kind="human",
        )
    assert store.get_evidence(EVIDENCE_ID)["revision"] == 2

    with pytest.raises(DataError, match="unknown contradiction evidence"):
        store.revise_evidence(
            EVIDENCE_ID_2,
            status="rejected",
            author="owner",
            author_kind="human",
            contradiction_ids=["e519395b-cfd3-4973-bc81-aaad3595865e"],
        )


def test_evidence_citations_resolve_exact_artifact_fields(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)

    with pytest.raises(DataError, match="source artifact"):
        _draft(
            store,
            evidence_id=EVIDENCE_ID,
            source_artifact="missing.parquet",
        )
    with pytest.raises(DataError, match="source field"):
        _draft(
            store,
            evidence_id=EVIDENCE_ID,
            source_field="outcomes.not_a_real_metric",
        )


def test_control_store_rejects_symlink_root_and_nonfinite_json(tmp_path: Path) -> None:
    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / "control").symlink_to(external, target_is_directory=True)
    with pytest.raises(DataError, match="must not be a symlink"):
        _store(tmp_path).list_projects()

    clean = tmp_path / "clean"
    store = _store(clean)
    _project(store)
    with pytest.raises(DataError, match="finite JSON"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="mean_reversion",
            source_fingerprint="git:bad",
            definition={"entry_z": float("nan")},
            parameter_space={},
        )
    with pytest.raises(DataError, match="content-addressed id"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id="ex_" + "0" * 64,
            snapshot_id="snap",
            universe=["AAPL"],
            split_policy={},
            costs={},
            seeds={"master": 7},
        )


def test_experiment_freezes_and_validates_optional_market_state_contract(tmp_path: Path) -> None:
    store = _store(tmp_path)
    _project(store)
    version = _version(store)
    contract = MarketStateContractV1(
        universe=("AAPL", "SPY"),
        benchmark="SPY",
        calendar="equity",
        volatility_window=21,
        trend_window=63,
        correlation_window=63,
        annualization_sessions=252,
        volatility_thresholds=(0.10, 0.25),
        trend_threshold=0.02,
        breadth_thresholds=(0.35, 0.65),
        correlation_thresholds=(0.25, 0.75),
        minimum_state_samples=20,
    )
    experiment = store.create_experiment_spec(
        PROJECT_ID,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="snap-market-state",
        universe=["SPY", "AAPL"],
        split_policy={"train": 504, "test": 63, "embargo": 5},
        costs={"fee_bps": 1.0},
        seeds={"master": 7},
        stage_config={"market_state": contract.to_dict()},
    )
    assert experiment["stage_config"] == {"market_state": contract.to_dict()}

    mismatched = MarketStateContractV1(
        universe=("QQQ", "SPY"),
        benchmark="SPY",
        calendar="equity",
        volatility_window=21,
        trend_window=63,
        correlation_window=63,
        annualization_sessions=252,
        volatility_thresholds=(0.10, 0.25),
        trend_threshold=0.02,
        breadth_thresholds=(0.35, 0.65),
        correlation_thresholds=(0.25, 0.75),
        minimum_state_samples=20,
    ).to_dict()
    with pytest.raises(DataError, match="market-state universe"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id=str(version["version_id"]),
            snapshot_id="snap-market-state-mismatch",
            universe=["SPY", "AAPL"],
            split_policy={},
            costs={},
            seeds={"master": 7},
            stage_config={"market_state": mismatched},
        )

    malformed = contract.to_dict()
    malformed["trend_window"] = 0
    with pytest.raises(DataError, match="trend_window"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id=str(version["version_id"]),
            snapshot_id="snap-market-state-malformed",
            universe=["SPY", "AAPL"],
            split_policy={},
            costs={},
            seeds={"master": 7},
            stage_config={"market_state": malformed},
        )


def test_unknown_database_schema_version_fails_loud(tmp_path: Path) -> None:
    root = tmp_path / "control"
    root.mkdir()
    database = root / "workstation.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute("PRAGMA user_version = 99")
    connection.close()

    with pytest.raises(DataError, match="unsupported control store schema version 99"):
        _store(tmp_path).list_projects()


def test_public_validation_boundaries_fail_loud(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    with pytest.raises(DataError, match="project name: expected a string"):
        store.create_project(
            name=cast(str, 7),
            hypothesis="hypothesis",
            falsification_criterion="criterion",
        )
    with pytest.raises(DataError, match="canonical UUID"):
        store.create_project(
            name="name",
            hypothesis="hypothesis",
            falsification_criterion="criterion",
            project_id=PROJECT_ID.upper(),
        )
    with pytest.raises(DataError, match="project name"):
        store.create_project(
            name="",
            hypothesis="hypothesis",
            falsification_criterion="criterion",
        )
    with pytest.raises(DataError, match="project status"):
        store.create_project(
            name="name",
            hypothesis="hypothesis",
            falsification_criterion="criterion",
            status=cast(ProjectStatus, "unknown"),
        )
    with pytest.raises(DataError, match="timezone-aware"):
        store.create_project(
            name="name",
            hypothesis="hypothesis",
            falsification_criterion="criterion",
            at=datetime(2026, 1, 1),
        )
    _project(store)
    with pytest.raises(DataError, match="already exists"):
        _project(store)
    with pytest.raises(DataError, match="unknown strategy project"):
        store.get_project("3b91647c-ded3-4903-a1a6-c8e64e86d229")
    with pytest.raises(DataError, match="query limit"):
        store.list_projects(limit=0)
    with pytest.raises(DataError, match="query offset"):
        store.list_projects(offset=-1)

    with pytest.raises(DataError, match="finite JSON"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="mean_reversion",
            source_fingerprint="git:bad",
            definition={"bad": {1, 2}},
            parameter_space={},
        )
    with pytest.raises(DataError, match="JSON exceeds"):
        store.create_strategy_version(
            PROJECT_ID,
            strategy_name="mean_reversion",
            source_fingerprint="git:bad",
            definition={"huge": "x" * 70_000},
            parameter_space={},
        )
    version = _version(store)
    with pytest.raises(DataError, match="1..512 unique symbols"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id=str(version["version_id"]),
            snapshot_id="snap",
            universe=[],
            split_policy={},
            costs={},
            seeds={},
        )
    with pytest.raises(DataError, match="unsupported characters"):
        store.create_experiment_spec(
            PROJECT_ID,
            strategy_version_id=str(version["version_id"]),
            snapshot_id="snap",
            universe=["BAD SYMBOL"],
            split_policy={},
            costs={},
            seeds={},
        )
    experiment = _experiment(store, str(version["version_id"]))
    experiment_id = str(experiment["experiment_id"])
    with pytest.raises(DataError, match="sealed before reveal"):
        store.reveal_holdout(PROJECT_ID, experiment_id, actor="owner", reason="too early")
    store.seal_holdout(
        PROJECT_ID,
        experiment_id,
        actor="owner",
        reason="reserve",
        start_date="2026-04-01",
        end_date="2026-06-30",
        at=START,
    )
    with pytest.raises(DataError, match="unsupported stage state"):
        store.link_stage_run(
            PROJECT_ID,
            experiment_id,
            stage="baseline",
            state=cast(StageState, "done"),
            run_id=RUN_ID,
        )
    with pytest.raises(DataError, match="suite-owned"):
        store.link_stage_run(
            PROJECT_ID,
            experiment_id,
            stage="baseline",
            state="pass",
            run_id=RUN_ID,
        )
    link = store.link_stage_run(
        PROJECT_ID,
        experiment_id,
        stage="baseline",
        state="queued",
        run_id=RUN_ID,
        at=START,
    )
    with pytest.raises(DataError, match="suite-owned"):
        store.append_stage_state(
            str(link["link_id"]), "warning", reason="generic callers cannot award a gate"
        )
    with pytest.raises(DataError, match="unknown stage/run link"):
        store.append_stage_state(
            "cd3077f9-82ff-4c87-a7ff-8ee2c6c412ae", "running", reason="missing"
        )
    with pytest.raises(DataError, match="unsupported attempt status"):
        store.record_attempt(
            PROJECT_ID,
            experiment_id,
            stage="oos",
            status=cast(AttemptStatus, "unknown"),
            config_fingerprint="cfg",
        )
    with pytest.raises(DataError, match="requires an error"):
        store.record_attempt(
            PROJECT_ID,
            experiment_id,
            stage="oos",
            status="failed",
            config_fingerprint="cfg",
        )
    with pytest.raises(DataError, match="only valid for failed"):
        store.record_attempt(
            PROJECT_ID,
            experiment_id,
            stage="oos",
            status="passed",
            config_fingerprint="cfg",
            error="unexpected",
        )

    with pytest.raises(DataError, match="already sealed"):
        store.seal_holdout(
            PROJECT_ID,
            experiment_id,
            actor="owner",
            reason="again",
            start_date="2026-04-01",
            end_date="2026-06-30",
        )
    with pytest.raises(DataError, match="verified canonical suite evidence"):
        store.reveal_holdout(
            PROJECT_ID,
            experiment_id,
            actor="owner",
            reason="candidate not frozen",
            at=START + timedelta(seconds=1),
        )
    with pytest.raises(DataError, match="precedes seal"):
        store.reveal_holdout(
            PROJECT_ID,
            experiment_id,
            actor="owner",
            reason="time travel",
            at=START - timedelta(seconds=1),
        )

    with pytest.raises(DataError, match="requires project_id"):
        store.create_job(kind="test", request={}, experiment_id=experiment_id)
    store.create_job(kind="test", request={}, job_id=JOB_ID, at=START)
    with pytest.raises(DataError, match="already exists"):
        store.create_job(kind="test", request={}, job_id=JOB_ID)
    with pytest.raises(DataError, match="event type"):
        store.append_job_event(JOB_ID, event_type="created", payload={})
    with pytest.raises(DataError, match="unsupported job status"):
        store.set_job_status(JOB_ID, cast(JobStatus, "unknown"))
    with pytest.raises(DataError, match="requires terminal_error"):
        store.set_job_status(JOB_ID, "failed")
    with pytest.raises(DataError, match="only valid for failed"):
        store.set_job_status(JOB_ID, "running", terminal_error="bad")
    with pytest.raises(DataError, match="only valid for succeeded"):
        store.set_job_status(JOB_ID, "running", result_run_id=RUN_ID)
    with pytest.raises(DataError, match="invalid job transition"):
        store.set_job_status(JOB_ID, "succeeded", at=START)

    with pytest.raises(DataError, match="ISO-8601"):
        parse_timestamp("2026-07-19")
    with pytest.raises(DataError, match="ISO-8601"):
        parse_timestamp("not-a-timeZ")


def test_evidence_boundary_validation_is_strict(tmp_path: Path) -> None:
    _publish_run(tmp_path)
    store = _store(tmp_path)
    with pytest.raises(DataError, match="source requires"):
        _draft(store, evidence_id=EVIDENCE_ID, source_run_id=None)
    with pytest.raises(DataError, match="must not follow"):
        _draft(
            store,
            evidence_id=EVIDENCE_ID,
            market_data_cutoff=START + timedelta(seconds=1),
        )
    with pytest.raises(DataError, match="author kind"):
        _draft(store, evidence_id=EVIDENCE_ID, author_kind="robot")
    with pytest.raises(DataError, match="must be finite"):
        _draft(store, evidence_id=EVIDENCE_ID, metric_value=float("inf"))
    with pytest.raises(DataError, match="finite and numeric"):
        _draft(
            store,
            evidence_id=EVIDENCE_ID,
            metric_value=cast(float, True),
            metric_name="invalid_boolean",
            metric_unit="boolean",
        )
    with pytest.raises(DataError, match="must be supplied together"):
        _draft(store, evidence_id=EVIDENCE_ID, metric_value=1.0)
    with pytest.raises(DataError, match="contained in the frozen universe"):
        _draft(store, evidence_id=EVIDENCE_ID, assets=("MSFT",))
    with pytest.raises(DataError, match="precedes knowledge_at"):
        _draft(
            store,
            evidence_id=EVIDENCE_ID,
            knowledge_at=START + timedelta(seconds=1),
            at=START,
        )

    _draft(store, evidence_id=EVIDENCE_ID)
    with pytest.raises(DataError, match="already exists"):
        _draft(store, evidence_id=EVIDENCE_ID)
    with pytest.raises(DataError, match="cannot contradict itself"):
        store.revise_evidence(
            EVIDENCE_ID,
            status="rejected",
            author="owner",
            author_kind="human",
            contradiction_ids=[EVIDENCE_ID],
        )
    with pytest.raises(DataError, match="unknown evidence item"):
        store.get_evidence("847bf878-2e7b-4786-8057-7fa6bb87382e")
    with pytest.raises(DataError, match="unsupported evidence status"):
        store.list_evidence(status=cast(EvidenceStatus, "unknown"))
