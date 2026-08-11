"""Focused release coverage for Workstation v3 control and suite contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import _suite, run_projection
from alpha_cli import control_store as control
from alpha_cli._suite import StepExecution, SuiteAction, SuitePlan, SuiteStep
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_core import DataError
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

NOW = datetime(2026, 1, 1, 1, 0, tzinfo=UTC)
type TestRun = tuple[str, str, control.StageState, bool | None, str | None]


def _experiment(
    tmp_path: Path,
    *,
    universe: list[str] | None = None,
    definition: dict[str, object] | None = None,
    parameter_space: dict[str, object] | None = None,
    stage_config: dict[str, object] | None = None,
    source: str = "git:abc123",
) -> tuple[ControlStore, str, str, str]:
    snapshot_dir = tmp_path / "snapshots" / "frozen"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    snapshot_manifest = snapshot_dir / "manifest.json"
    if not snapshot_manifest.exists():
        snapshot_manifest.write_text(
            json.dumps({"snapshot_id": "frozen", "symbols": {}}, sort_keys=True),
            encoding="utf-8",
        )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Release coverage",
        hypothesis="A causal daily signal persists after costs.",
        falsification_criterion="Reject on failed OOS evidence.",
        at=NOW,
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="ts_momentum",
        source_fingerprint=source,
        definition=definition or {"lookback": 5, "skip": 1, "vol_window": 3},
        parameter_space=parameter_space or {"lookback": [5, 10]},
        at=NOW,
    )
    version_id = str(version["version_id"])
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=version_id,
        snapshot_id="frozen",
        universe=universe or ["SPY", "AAPL"],
        split_policy={"train": 30, "test": 10, "embargo": 2},
        costs={"fee_bps": 0, "slippage_bps": 0},
        seeds={"master": 7},
        stage_config=stage_config or {},
        at=NOW,
    )
    experiment_id = str(experiment["experiment_id"])
    store.seal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="reserve final release-coverage window before research",
        start_date="2025-10-01",
        end_date="2025-12-31",
        at=NOW,
    )
    return store, project_id, version_id, experiment_id


def _stage_state(store: ControlStore, project_id: str, experiment_id: str, stage: str) -> str:
    rows = cast(list[dict[str, object]], store.get_project(project_id)["stage_states"])
    return str(
        next(
            row for row in rows if row["experiment_id"] == experiment_id and row["stage"] == stage
        )["state"]
    )


def _publish_suite(
    tmp_path: Path,
    run_id: str,
    command: str,
    *,
    passed: bool | None = None,
    null_model: str | None = None,
    holdout_spec_hash: str | None = None,
    null_outcome: bool | None = None,
) -> None:
    rdir = tmp_path / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema_version": 3,
        "artifact_contract_version": 3,
        "run_identity_version": 3,
        "run_id": run_id,
        "command": command,
        "snapshot_id": "frozen",
        "snapshot_hash": hashlib.sha256(
            (tmp_path / "snapshots" / "frozen" / "manifest.json").read_bytes()
        ).hexdigest(),
        "execution_fingerprint": "a" * 64,
        "strategy_fingerprint": "b" * 64,
        "source_fingerprint": "c" * 64,
        "research_cutoff": "2025-09-30",
        "artifacts": {},
    }
    if passed is not None:
        manifest["passed"] = passed
    if null_model is not None:
        manifest["metadata"] = {"null_model": null_model}
    if command.startswith("monte_carlo_"):
        manifest["status"] = "clear"
    if holdout_spec_hash is not None:
        manifest["holdout_spec_hash"] = holdout_spec_hash
    if null_outcome is not None:
        manifest["outcomes"] = [
            {"name": "randomized_price_null", "passed": null_outcome, "detail": {}}
        ]
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _pass_stage(
    store: ControlStore,
    tmp_path: Path,
    project_id: str,
    experiment_id: str,
    stage: str,
) -> None:
    if stage == "candidate":
        transitions = {
            "not_started": ("ready", "queued", "running", "pass"),
            "ready": ("queued", "running", "pass"),
            "queued": ("running", "pass"),
            "running": ("pass",),
            "pass": (),
        }
        for state in transitions[_stage_state(store, project_id, experiment_id, stage)]:
            store.append_experiment_stage_state(
                project_id,
                experiment_id,
                stage,
                cast(control.StageState, state),
                reason="release coverage",
                at=NOW + timedelta(minutes=1),
            )
        return
    actions: dict[str, tuple[str, list[TestRun]]] = {
        "baseline": (
            "baseline",
            [("3000000000000001", "backtest_run", "pass", None, None)],
        ),
        "oos": (
            "inner_oos",
            [("3000000000000002", "backtest_oos", "pass", None, None)],
        ),
        "robustness": (
            "three_null_families",
            [
                ("3000000000000003", "validate", "pass", True, "bootstrap"),
                ("3000000000000004", "validate", "warning", None, "student_t"),
                ("3000000000000005", "validate", "warning", None, "garch"),
            ],
        ),
        "monte_carlo": (
            "monte_carlo",
            [
                ("3000000000000009", "monte_carlo_classical", "pass", None, None),
                ("300000000000000a", "monte_carlo_kronos", "pass", None, None),
            ],
        ),
        "optimization": (
            "optimize_grid",
            [("3000000000000006", "optim_grid", "pass", True, None)],
        ),
        "portfolio": (
            "portfolio_cross_asset",
            [
                ("3000000000000007", "backtest_portfolio", "pass", None, None),
                ("3000000000000008", "cross_sectional", "pass", None, None),
            ],
        ),
    }
    action, runs = actions[stage]
    transitions = {
        "not_started": ("ready", "queued", "running"),
        "ready": ("queued", "running"),
        "queued": ("running",),
        "running": (),
        "pass": (),
    }
    for state in transitions[_stage_state(store, project_id, experiment_id, stage)]:
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            stage,
            cast(control.StageState, state),
            reason="release coverage",
            at=NOW + timedelta(minutes=1),
        )
    for run_id, command, state, passed, null_model in runs:
        _publish_suite(
            tmp_path,
            run_id,
            command,
            passed=passed,
            null_model=null_model,
        )
        store.link_suite_stage_run(
            project_id,
            experiment_id,
            suite_action=action,
            stage=stage,
            state=state,
            run_id=run_id,
            at=NOW + timedelta(minutes=1),
        )
    store.complete_suite_stage(
        project_id,
        experiment_id,
        suite_action=action,
        stage=stage,
        state="pass",
        reason="verified release evidence",
        at=NOW + timedelta(minutes=1),
    )


def _publish(
    tmp_path: Path,
    run_id: str,
    *,
    passed: bool = True,
    null_outcome: bool | None = None,
) -> None:
    rdir = tmp_path / "runs" / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "run_id": run_id,
        "command": "backtest_run",
        "snapshot_id": "frozen",
        "snapshot_hash": "a" * 64,
        "passed": passed,
    }
    if null_outcome is not None:
        manifest["outcomes"] = [
            {"name": "randomized_price_null", "passed": null_outcome, "detail": {}}
        ]
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def _minimal_plan(action: SuiteAction, *, ready: bool = True) -> SuitePlan:
    return SuitePlan(
        schema_version=1,
        project_id="00000000-0000-0000-0000-000000000001",
        experiment_id="ex_" + "a" * 64,
        action=action,
        stage="baseline",
        ready=ready,
        blockers=() if ready else ("blocked by test",),
        resolved_experiment={},
        resolved_strategy_version={},
        current_stage_state="ready",
        estimated_workload={},
        steps=(),
        governance={},
    )


def test_suite_immutable_projection_and_scalar_guards() -> None:
    with pytest.raises(DataError, match="expected an object"):
        _suite._object([], "spec")
    with pytest.raises(DataError, match="finite number"):
        _suite._number(True, "value")
    with pytest.raises(DataError, match="finite value"):
        _suite._number(float("nan"), "value", minimum=0)
    with pytest.raises(DataError, match="expected an integer"):
        _suite._integer(1.5, "count")
    with pytest.raises(DataError, match="managed identifier"):
        _suite._safe_id("../snapshot", "snapshot")
    with pytest.raises(DataError, match="collection"):
        _suite._selected({}, id_field="id", item_id="x", label="row")
    with pytest.raises(DataError, match="unknown immutable"):
        _suite._selected([], id_field="id", item_id="x", label="row")
    with pytest.raises(DataError, match="stage states"):
        _suite._stage_states({"stage_states": {}}, "ex")
    with pytest.raises(DataError, match="account_type"):
        _suite._definition_options({"account_type": "BROKER"})
    with pytest.raises(DataError, match="allow_short"):
        _suite._definition_options({"allow_short": 1})
    assert _suite._definition_options({"allow_short": False}) == ["--no-allow-short"]
    assert _suite._strategy_options("ts_momentum", {}) == []
    with pytest.raises(DataError, match="anchored"):
        _suite._split_options({"anchored": "yes"})
    assert "--no-anchored" in _suite._split_options({"anchored": False})
    with pytest.raises(DataError, match="value <="):
        _suite._stage_float({"x": 2}, "x", 0, minimum=0, maximum=1)
    assert _suite._latest_run({"stage_run_links": None}, "ex", ("oos",)) is None
    project = {
        "stage_run_links": [
            {
                "experiment_id": "ex",
                "stage": "oos",
                "state": "warning",
                "run_id": "0123456789abcdef",
            }
        ]
    }
    assert _suite._latest_run(project, "ex", ("oos",)) == "0123456789abcdef"


def test_grid_contract_rejects_unbounded_or_undeclared_axes() -> None:
    base: dict[str, Any] = {
        "primary": "SPY",
        "strategy": "ts_momentum",
        "snapshot": "frozen",
        "costs": {},
        "definition": {"lookback": 5, "skip": 1, "vol_window": 3},
        "split": {},
        "seeds": {},
        "config": {},
        "research_cutoff": "2025-09-30",
        "cutoff_marker": "<sealed-research-cutoff>",
    }
    with pytest.raises(DataError, match="unsupported immutable optimization axis"):
        _suite._grid_steps(**base, parameter_space={"shell": [1]})
    with pytest.raises(DataError, match="must contain 1..256"):
        _suite._grid_steps(**base, parameter_space={"lookback": []})
    with pytest.raises(DataError, match="4096-configuration"):
        _suite._grid_steps(
            **base,
            parameter_space={
                "periods_per_year": list(range(65)),
                "starting_cash": list(range(65)),
            },
        )
    with pytest.raises(DataError, match="declared parameter_space"):
        _suite._grid_steps(**base, parameter_space={})
    step, combinations = _suite._grid_steps(
        **{**base, "config": {"max_workers": 2}},
        parameter_space={"lookback": [5, 10]},
    )
    assert combinations == 2
    assert step.argv[-2:] == ("--max-workers", "2")


def test_plan_blockers_and_optional_command_controls(tmp_path: Path) -> None:
    store, project_id, _version_id, experiment_id = _experiment(
        tmp_path,
        definition={
            "lookback": 5,
            "skip": 1,
            "vol_window": 3,
            "starting_cash": 50_000,
        },
        stage_config={"max_workers": 2, "portfolio_weighting": "equal"},
    )
    store.append_experiment_stage_state(
        project_id, experiment_id, "baseline", "queued", reason="queued", at=NOW
    )
    queued = _suite.build_suite_plan(
        store, project_id, experiment_id, "baseline", data_dir=tmp_path
    )
    assert "baseline stage is queued" in queued.blockers
    _pass_stage(store, tmp_path, project_id, experiment_id, "baseline")
    _pass_stage(store, tmp_path, project_id, experiment_id, "oos")
    nulls = _suite.build_suite_plan(
        store, project_id, experiment_id, "three_null_families", data_dir=tmp_path
    )
    assert "--max-workers" in nulls.steps[0].argv
    paper = _suite.build_suite_plan(
        store, project_id, experiment_id, "paper_preflight", data_dir=tmp_path
    )
    assert "--starting-cash" in paper.steps[0].argv

    stress = _suite.build_suite_plan(
        store, project_id, experiment_id, "fixed_stress", data_dir=tmp_path
    )
    assert "3000000000000002" in stress.steps[0].argv


def test_plan_detects_noncurrent_single_asset_and_managed_qlib_resources(tmp_path: Path) -> None:
    store, project_id, version_id, experiment_id = _experiment(tmp_path, universe=["SPY"])
    second = store.create_experiment_spec(
        project_id,
        strategy_version_id=version_id,
        snapshot_id="newer",
        universe=["SPY", "AAPL"],
        split_policy={"train": 30, "test": 10},
        costs={},
        seeds={},
        at=NOW + timedelta(minutes=1),
    )
    store.seal_holdout(
        project_id,
        str(second["experiment_id"]),
        actor="owner",
        reason="reserve final window before planning this experiment",
        start_date="2025-10-01",
        end_date="2025-12-31",
        at=NOW + timedelta(minutes=1),
    )
    old = _suite.build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    assert "not the project's current" in " ".join(old.blockers)
    portfolio = _suite.build_suite_plan(
        store, project_id, str(second["experiment_id"]), "portfolio_cross_asset", data_dir=tmp_path
    )
    assert len(portfolio.steps) == 2

    symbols = [f"S{index:02d}" for index in range(20)]
    qstore, qproject, _qversion, qexperiment = _experiment(tmp_path / "qlib", universe=symbols)
    first = _suite.build_suite_plan(
        qstore, qproject, qexperiment, "qlib", data_dir=tmp_path / "qlib"
    )
    managed_input = Path(first.steps[0].argv[4])
    managed_input.mkdir(parents=True)
    duplicate = _suite.build_suite_plan(
        qstore, qproject, qexperiment, "qlib", data_dir=tmp_path / "qlib"
    )
    assert "already exist" in " ".join(duplicate.blockers)


@pytest.mark.parametrize(
    ("config", "message", "is_blocker"),
    [
        ({}, "pinned model id", True),
        ({"kronos_model": "repo/model/extra"}, "kronos_model", False),
        ({"kronos_model": "repo/model"}, "pinned model revision", True),
        (
            {"kronos_model": "repo/model", "kronos_model_revision": "bad revision"},
            "safe immutable revision",
            False,
        ),
        (
            {"kronos_model": "fake", "kronos_tokenizer": "bad tokenizer"},
            "kronos_tokenizer",
            False,
        ),
        ({"kronos_model": "fake", "kronos_device": "tpu"}, "kronos_device", False),
    ],
)
def test_kronos_plan_fails_closed_on_unpinned_or_unsafe_models(
    tmp_path: Path,
    config: dict[str, object],
    message: str,
    is_blocker: bool,
) -> None:
    store, project_id, _version_id, experiment_id = _experiment(tmp_path, stage_config=config)
    if is_blocker:
        plan = _suite.build_suite_plan(
            store, project_id, experiment_id, "kronos", data_dir=tmp_path
        )
        assert message in " ".join(plan.blockers)
    else:
        with pytest.raises(DataError, match=message):
            _suite.build_suite_plan(store, project_id, experiment_id, "kronos", data_dir=tmp_path)


def test_kronos_plan_accepts_explicit_model_and_tokenizer_revisions(tmp_path: Path) -> None:
    config: dict[str, object] = {
        "kronos_model": "repo/model",
        "kronos_model_revision": "refs/rev-1",
        "kronos_tokenizer": "repo/tokenizer",
        "kronos_tokenizer_revision": "refs/token-1",
        "kronos_device": "mps",
    }
    store, project_id, _version_id, experiment_id = _experiment(tmp_path, stage_config=config)
    plan = _suite.build_suite_plan(store, project_id, experiment_id, "kronos", data_dir=tmp_path)
    command = plan.steps[0].argv
    assert command[command.index("--model-revision") + 1] == "refs/rev-1"
    assert command[command.index("--tokenizer") + 1] == "repo/tokenizer"
    assert command[command.index("--device") + 1] == "mps"


def test_execute_suite_rejects_blocked_and_ownerless_holdout(tmp_path: Path) -> None:
    store = ControlStore(tmp_path)
    with pytest.raises(DataError, match="not ready"):
        _suite.execute_suite(store, _minimal_plan("baseline", ready=False), data_dir=tmp_path)
    with pytest.raises(DataError, match="explicit owner"):
        _suite.execute_suite(store, _minimal_plan("holdout_reveal"), data_dir=tmp_path)


def test_execute_suite_cancellation_audits_stage_attempt_and_job(tmp_path: Path) -> None:
    symbols = [f"S{index:02d}" for index in range(20)]
    store, project_id, _version_id, experiment_id = _experiment(tmp_path, universe=symbols)
    plan = _suite.build_suite_plan(store, project_id, experiment_id, "qlib", data_dir=tmp_path)
    assert plan.ready is True
    with pytest.raises(InterruptedError, match="cancelled"):
        _suite.execute_suite(store, plan, data_dir=tmp_path, cancelled=lambda: True)
    assert _stage_state(store, project_id, experiment_id, "ml") == "fail"
    assert store.list_jobs()[0]["status"] == "cancelled"
    attempts = cast(list[dict[str, object]], store.get_project(project_id)["attempts"])
    assert [row["status"] for row in attempts] == ["queued", "cancelled"]


def test_execute_suite_honors_cancellation_after_a_step_returns(tmp_path: Path) -> None:
    store, project_id, _version_id, experiment_id = _experiment(tmp_path)
    plan = _suite.build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    checks = iter((False, True))

    def cancel_after_runner() -> bool:
        return next(checks)

    def success(
        _step: SuiteStep,
        _job_id: str,
        _store: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        return StepExecution(returncode=0, run_ids=())

    with pytest.raises(InterruptedError, match="cancelled"):
        _suite.execute_suite(
            store,
            plan,
            data_dir=tmp_path,
            cancelled=cancel_after_runner,
            step_runner=success,
        )
    assert store.list_jobs()[0]["status"] == "cancelled"


def test_three_null_execution_links_sensitivities_as_warnings(tmp_path: Path) -> None:
    store, project_id, _version_id, experiment_id = _experiment(tmp_path)
    _pass_stage(store, tmp_path, project_id, experiment_id, "baseline")
    _pass_stage(store, tmp_path, project_id, experiment_id, "oos")
    plan = _suite.build_suite_plan(
        store, project_id, experiment_id, "three_null_families", data_dir=tmp_path
    )
    run_ids = ("0000000000000001", "0000000000000002", "0000000000000003")
    index = 0

    def complete(
        step: SuiteStep,
        _job_id: str,
        _store: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        nonlocal index
        run_id = run_ids[index]
        index += 1
        null_model = step.argv[step.argv.index("--null-model") + 1]
        _publish_suite(
            tmp_path,
            run_id,
            "validate",
            passed=True if null_model == "bootstrap" else None,
            null_model=null_model,
            null_outcome=True,
        )
        return StepExecution(returncode=0, run_ids=(run_id,))

    result = _suite.execute_suite(store, plan, data_dir=tmp_path, step_runner=complete)
    assert cast(dict[str, object], result["result"])["stage_state"] == "pass"
    links = cast(list[dict[str, object]], store.get_project(project_id)["stage_run_links"])
    states = {str(row["run_id"]): row["state"] for row in links if row["stage"] == "robustness"}
    assert states == {run_ids[0]: "pass", run_ids[1]: "warning", run_ids[2]: "warning"}


def test_holdout_execution_performs_the_audited_reveal_before_evaluation(tmp_path: Path) -> None:
    store, project_id, _version_id, experiment_id = _experiment(tmp_path)
    for stage in (
        "baseline",
        "oos",
        "robustness",
        "monte_carlo",
        "optimization",
        "portfolio",
        "candidate",
    ):
        _pass_stage(store, tmp_path, project_id, experiment_id, stage)
    plan = _suite.build_suite_plan(
        store, project_id, experiment_id, "holdout_reveal", data_dir=tmp_path
    )
    run_id = "0000000000000099"

    def evaluate(
        _step: SuiteStep,
        _job_id: str,
        _store: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        sealed = store.get_holdout_spec(project_id, experiment_id)
        assert sealed is not None
        _publish_suite(
            tmp_path,
            run_id,
            "backtest_holdout",
            passed=True,
            holdout_spec_hash=str(sealed["spec_hash"]),
        )
        return StepExecution(returncode=0, run_ids=(run_id,))

    result = _suite.execute_suite(
        store,
        plan,
        data_dir=tmp_path,
        owner_actor="owner",
        owner_reason="candidate frozen",
        step_runner=evaluate,
    )
    assert cast(dict[str, object], result["result"])["stage_state"] == "pass"
    revealed = _suite.build_suite_plan(
        store, project_id, experiment_id, "holdout_reveal", data_dir=tmp_path
    )
    assert "final holdout was already revealed" in revealed.blockers


def test_headline_verdict_reads_only_published_canonical_evidence(tmp_path: Path) -> None:
    assert _suite._headline_state(tmp_path, _minimal_plan("baseline"), ()) == "pass"
    assert (
        _suite._headline_state(tmp_path, _minimal_plan("baseline"), ("missing000000000",)) == "pass"
    )
    with pytest.raises(DataError, match="was not published"):
        _suite._headline_state(tmp_path, _minimal_plan("optimize_grid"), ("0000000000000001",))
    _publish(tmp_path, "0000000000000001", passed=False)
    assert (
        _suite._headline_state(tmp_path, _minimal_plan("optimize_grid"), ("0000000000000001",))
        == "fail"
    )
    _publish(tmp_path, "0000000000000002", null_outcome=True)
    _publish(tmp_path, "0000000000000003", null_outcome=False)
    assert (
        _suite._headline_state(
            tmp_path, _minimal_plan("three_null_families"), ("0000000000000002",)
        )
        == "pass"
    )
    assert (
        _suite._headline_state(
            tmp_path, _minimal_plan("three_null_families"), ("0000000000000003",)
        )
        == "fail"
    )
    assert _suite._redact("secret value", SuiteStep("x", (), (), "x", (("secret", "<x>"),))) == (
        "<x> value"
    )


def test_control_value_store_and_transaction_guards(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="YYYY-MM-DD"):
        control._iso_date("2026-02-30", "date")
    with pytest.raises(DataError, match="canonical"):
        control._iso_date("2026-W14-3", "date")
    nested: object = None
    for _ in range(18):
        nested = [nested]
    with pytest.raises(DataError, match="nesting"):
        control._clean_json(nested, label="nested")
    with pytest.raises(DataError, match="keys"):
        control._clean_json({1: "bad"}, label="mapping")
    with pytest.raises(DataError, match="finite JSON"):
        control._canonical_json({"bad": object()}, "payload")
    with pytest.raises(DataError, match="is not text"):
        control._decode_json(1, "payload")
    with pytest.raises(DataError, match="invalid payload"):
        control._decode_json("{", "payload")
    with pytest.raises(DataError, match="too many values"):
        control._strings(["x"] * 257, "values")
    with pytest.raises(DataError, match="too many values"):
        control._evidence_ids(["00000000-0000-0000-0000-000000000001"] * 257)

    store = ControlStore(tmp_path / "transaction")
    with (
        pytest.raises(DataError, match="transaction failed"),
        store._transaction(write=True) as connection,
    ):
        connection.execute("definitely not SQL")

    target = tmp_path / "target"
    target.mkdir()
    symlink_root = tmp_path / "symlinked" / "control"
    symlink_root.parent.mkdir()
    symlink_root.symlink_to(target, target_is_directory=True)
    with pytest.raises(DataError, match="root must not be a symlink"):
        ControlStore(tmp_path / "symlinked").list_projects()

    database = tmp_path / "directory-db" / "control" / control.DATABASE_NAME
    database.mkdir(parents=True)
    with pytest.raises(DataError, match="database is not a file"):
        ControlStore(tmp_path / "directory-db").list_projects()


def test_control_stage_attempt_job_and_corruption_guards(tmp_path: Path) -> None:
    store, project_id, _version_id, experiment_id = _experiment(tmp_path)
    _publish(tmp_path, "0123456789abcdef")
    with pytest.raises(DataError, match="unsupported development stage"):
        store.link_stage_run(
            project_id,
            experiment_id,
            stage="deployment",
            state="pass",
            run_id="0123456789abcdef",
        )
    with pytest.raises(DataError, match="unsupported development stage"):
        store.append_experiment_stage_state(
            project_id, experiment_id, "deployment", "ready", reason="bad"
        )
    with pytest.raises(DataError, match="unsupported stage state"):
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            "baseline",
            cast(control.StageState, "green"),
            reason="bad",
        )
    with pytest.raises(DataError, match="candidate freeze"):
        store.append_experiment_stage_state(
            project_id, experiment_id, "candidate", "ready", reason="too early"
        )

    link = store.link_stage_run(
        project_id,
        experiment_id,
        stage="baseline",
        state="queued",
        run_id="0123456789abcdef",
        at=NOW + timedelta(minutes=2),
    )
    with pytest.raises(DataError, match="suite-owned"):
        store.link_stage_run(
            project_id,
            experiment_id,
            stage="baseline",
            state="pass",
            run_id="0123456789abcdef",
        )
    with pytest.raises(DataError, match="unsupported stage state"):
        store.append_stage_state(
            str(link["link_id"]), cast(control.StageState, "green"), reason="bad"
        )
    with pytest.raises(DataError, match="precedes prior event"):
        store.append_stage_state(
            str(link["link_id"]),
            "running",
            reason="backdated",
            at=NOW,
        )

    attempt_id = "00000000-0000-0000-0000-000000000099"
    store.record_attempt(
        project_id,
        experiment_id,
        stage="baseline",
        status="passed",
        config_fingerprint="cfg",
        attempt_id=attempt_id,
    )
    with pytest.raises(DataError, match="already exists"):
        store.record_attempt(
            project_id,
            experiment_id,
            stage="baseline",
            status="passed",
            config_fingerprint="cfg",
            attempt_id=attempt_id,
        )

    job = store.create_job(kind="coverage", request={}, at=NOW + timedelta(minutes=3))
    job_id = str(job["job_id"])
    with pytest.raises(DataError, match="precedes prior job update"):
        store.append_job_event(job_id, event_type="log", payload={}, at=NOW)
    store.set_job_status(
        job_id,
        "failed",
        terminal_error="expected failure",
        at=NOW + timedelta(minutes=4),
    )
    with pytest.raises(DataError, match="terminal job"):
        store.append_job_result(job_id, {}, at=NOW + timedelta(minutes=5))
    with pytest.raises(DataError, match="transition terminal job"):
        store.set_job_status(job_id, "cancelled", at=NOW + timedelta(minutes=5))

    with store._transaction(write=True) as connection:
        connection.execute(
            "DELETE FROM stage_state_events WHERE link_id = ?", (str(link["link_id"]),)
        )
    with pytest.raises(DataError, match="has no events"):
        store.get_project(project_id)


def test_evidence_citation_and_correlation_guards(tmp_path: Path) -> None:
    store, _project_id, _version_id, _experiment_id = _experiment(tmp_path)
    run_id = "0123456789abcdef"
    _publish(tmp_path, run_id)
    rdir = tmp_path / "runs" / run_id
    pl.DataFrame({"symbol": ["AAPL", "MSFT"], "score": [1.0, 2.0]}).write_parquet(
        rdir / "scores.parquet"
    )
    (rdir / "notes.txt").write_text("audit", encoding="utf-8")

    with pytest.raises(DataError, match="do not accept a row selector"):
        store._validate_evidence_citation(
            run_id=run_id,
            artifact="manifest.json",
            field="passed",
            row_selector={"row_index": 0},
        )
    with pytest.raises(DataError, match="manifest.json or Parquet"):
        store._validate_evidence_citation(
            run_id=run_id, artifact="notes.txt", field="x", row_selector={}
        )
    with pytest.raises(DataError, match="does not exist"):
        store._validate_evidence_citation(
            run_id=run_id,
            artifact="scores.parquet",
            field="missing",
            row_selector={"row_index": 0},
        )
    with pytest.raises(DataError, match="outside the artifact"):
        store._validate_evidence_citation(
            run_id=run_id,
            artifact="scores.parquet",
            field="score",
            row_selector={"row_index": 10},
        )
    with pytest.raises(DataError, match="selector field"):
        store._validate_evidence_citation(
            run_id=run_id,
            artifact="scores.parquet",
            field="score",
            row_selector={"missing": "AAPL"},
        )
    with pytest.raises(DataError, match="must be scalar"):
        store._validate_evidence_citation(
            run_id=run_id,
            artifact="scores.parquet",
            field="score",
            row_selector={"symbol": ["AAPL"]},
        )
    with pytest.raises(DataError, match="exactly one row"):
        store._validate_evidence_citation(
            run_id=run_id, artifact="scores.parquet", field="score", row_selector={}
        )

    correlation: dict[str, object] = {
        "assets": ["AAPL", "MSFT"],
        "timeframe": "1d",
        "metric_name": "correlation",
        "metric_value": 0.4,
        "metric_unit": "coefficient",
        "run_id": run_id,
        "artifact": "scores.parquet",
        "row_selector": {
            "sample_count": 2,
            "aligned_oos": True,
            "frequency": "1d",
            "association_not_causation": True,
            "oos_start": "2026-01-01",
            "oos_end": "2026-06-30",
            "snapshot_hash": "a" * 64,
        },
    }
    for update, message in (
        ({"assets": ["AAPL"]}, "at least two assets"),
        ({"artifact": "manifest.json"}, "Parquet report"),
        ({"metric_name": None}, "explicit metric"),
        (
            {
                "row_selector": {
                    **cast(dict[str, object], correlation["row_selector"]),
                    "oos_end": "2025-01-01",
                }
            },
            "ordered aligned OOS",
        ),
        (
            {
                "row_selector": {
                    **cast(dict[str, object], correlation["row_selector"]),
                    "snapshot_hash": "bad",
                }
            },
            "64-hex",
        ),
    ):
        with pytest.raises(DataError, match=message):
            store._validate_correlation_evidence(**{**correlation, **update})  # type: ignore[arg-type]


def test_project_and_suite_cli_plain_and_error_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    actions = runner.invoke(app, ["suite", "actions"])
    assert actions.exit_code == 0 and "baseline" in actions.output
    actions_json = runner.invoke(app, ["suite", "actions", "--json"])
    assert json.loads(actions_json.output)[0]["action"] == "baseline"

    empty_projects = runner.invoke(app, ["project", "list"])
    empty_projects_json = runner.invoke(app, ["project", "list", "--json"])
    empty_jobs = runner.invoke(app, ["project", "job-list"])
    empty_jobs_json = runner.invoke(app, ["project", "job-list", "--json"])
    assert "no strategy projects" in empty_projects.output
    assert json.loads(empty_projects_json.output) == []
    assert "no development jobs" in empty_jobs.output
    assert json.loads(empty_jobs_json.output) == []

    created = runner.invoke(
        app,
        [
            "project",
            "create",
            "CLI coverage",
            "--hypothesis",
            "Signal persists.",
            "--falsification",
            "Reject on failed OOS.",
            "--json",
        ],
    )
    project_id = str(json.loads(created.output)["project_id"])
    malformed = runner.invoke(
        app,
        [
            "project",
            "version",
            project_id,
            "--strategy",
            "ts_momentum",
            "--source-fingerprint",
            "git:abc",
            "--definition-json",
            "[]",
        ],
    )
    assert malformed.exit_code != 0 and "valid JSON object" in malformed.output
    missing_items = (
        ("version-show", "sv_" + "a" * 64),
        ("experiment-show", "ex_" + "a" * 64),
    )
    for command, item in missing_items:
        missing = runner.invoke(app, ["project", command, project_id, item])
        assert missing.exit_code != 0 and "unknown" in missing.output

    brief = runner.invoke(app, ["project", "agent-brief", project_id, "--json"])
    warnings = json.loads(brief.output)["warnings"]
    assert "no immutable strategy version is selected" in warnings
    assert "no immutable experiment specification is selected" in warnings
    bad_plan = runner.invoke(
        app,
        ["suite", "plan", project_id, "ex_" + "a" * 64, "shell"],
    )
    bad_status = runner.invoke(app, ["suite", "status", "00000000-0000-0000-0000-000000000002"])
    bad_decision = runner.invoke(
        app,
        [
            "project",
            "decide",
            project_id,
            "ex_" + "a" * 64,
            "--verdict",
            "accept",
            "--actor",
            "owner",
            "--reason",
            "test",
        ],
    )
    assert bad_plan.exit_code != 0 and "unsupported suite action" in bad_plan.output
    assert bad_status.exit_code != 0 and "unknown control job" in bad_status.output
    assert bad_decision.exit_code != 0


def test_legacy_rule_fold_projection_is_typed_and_skips_malformed_entries(
    tmp_path: Path,
) -> None:
    manifest: dict[str, object] = {
        "folds": [
            {
                "index": 3,
                "train_start": datetime(2025, 1, 1, tzinfo=UTC).timestamp(),
                "train_end": datetime(2025, 3, 31, tzinfo=UTC).timestamp(),
                "test_start": datetime(2025, 4, 1, tzinfo=UTC).timestamp(),
                "test_end": datetime(2025, 4, 30, tzinfo=UTC).timestamp(),
            },
            "not-an-object",
            {"index": "invalid", "train_start": "missing required boundaries"},
        ]
    }

    assert run_projection._folds(tmp_path, manifest, 10) == [
        {
            "fold": 3,
            "semantics": "fixed_rule_evaluation_no_refit",
            "train_start": datetime(2025, 1, 1, tzinfo=UTC).timestamp(),
            "train_end": datetime(2025, 3, 31, tzinfo=UTC).timestamp(),
            "validation_start": None,
            "validation_end": None,
            "test_start": datetime(2025, 4, 1, tzinfo=UTC).timestamp(),
            "test_end": datetime(2025, 4, 30, tzinfo=UTC).timestamp(),
        }
    ]
