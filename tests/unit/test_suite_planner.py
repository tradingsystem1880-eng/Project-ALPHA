from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest

from alpha_cli._suite import (
    SUITE_ACTIONS,
    StepExecution,
    SuiteAction,
    SuiteStep,
    build_suite_plan,
    execute_suite,
    reserve_suite_job,
)
from alpha_cli.control_store import ControlStore, StageState
from alpha_core import DataError
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy

type TestRun = tuple[str, str, StageState, bool | None, str | None]


def _experiment(tmp_path: Path, *, seal: bool = True) -> tuple[ControlStore, str, str]:
    snapshot_dir = tmp_path / "snapshots" / "frozen-2026q2"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps({"snapshot_id": "frozen-2026q2", "symbols": {}}, sort_keys=True),
        encoding="utf-8",
    )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="AAPL mean reversion",
        hypothesis="Large close deviations revert.",
        falsification_criterion="Reject when locked OOS Sharpe is non-positive.",
        at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="mean_reversion",
        source_fingerprint="git:abc123",
        definition={"window": 20, "entry_z": 2.0, "account_type": "CASH"},
        parameter_space={"window": [10, 20, 40], "entry_z": [1.5, 2.0]},
    )
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="frozen-2026q2",
        universe=["SPY", "AAPL"],
        split_policy={"train": 504, "test": 63, "embargo": 5},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
        stage_config={
            "tier1_paths": 100,
            "tier2_paths": 8,
            "n_resamples": 200,
            "kronos_model": "fake",
        },
    )
    experiment_id = str(experiment["experiment_id"])
    if seal:
        store.seal_holdout(
            project_id,
            experiment_id,
            actor="owner",
            reason="reserve final test window before research",
            start_date="2026-04-01",
            end_date="2026-06-30",
        )
    return store, project_id, experiment_id


def _complete_action(
    store: ControlStore,
    tmp_path: Path,
    project_id: str,
    experiment_id: str,
    action: str,
) -> None:
    actions: dict[str, tuple[str, list[TestRun]]] = {
        "baseline": ("baseline", [("2000000000000001", "backtest_run", "pass", None, None)]),
        "inner_oos": ("oos", [("2000000000000002", "backtest_oos", "pass", None, None)]),
        "three_null_families": (
            "robustness",
            [
                ("2000000000000003", "validate", "pass", True, "bootstrap"),
                ("2000000000000004", "validate", "warning", None, "student_t"),
                ("2000000000000005", "validate", "warning", None, "garch"),
            ],
        ),
        "optimize_grid": (
            "optimization",
            [("2000000000000006", "optim_grid", "pass", True, None)],
        ),
        "portfolio_cross_asset": (
            "portfolio",
            [
                ("2000000000000007", "backtest_portfolio", "pass", None, None),
                ("2000000000000008", "cross_sectional", "pass", None, None),
            ],
        ),
    }
    stage, rows = actions[action]
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
    snapshot_hash = hashlib.sha256(
        (tmp_path / "snapshots" / "frozen-2026q2" / "manifest.json").read_bytes()
    ).hexdigest()
    for run_id, command, state, passed, null_model in rows:
        run_dir = tmp_path / "runs" / run_id
        run_dir.mkdir(parents=True)
        manifest: dict[str, object] = {
            "schema_version": 3,
            "artifact_contract_version": 3,
            "run_identity_version": 3,
            "run_id": run_id,
            "command": command,
            "snapshot_id": "frozen-2026q2",
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


def test_research_actions_are_blocked_until_a_dated_holdout_is_sealed(
    tmp_path: Path,
) -> None:
    store, project_id, experiment_id = _experiment(tmp_path, seal=False)

    for action in ("baseline", "qlib", "kronos"):
        plan = build_suite_plan(
            store,
            project_id,
            experiment_id,
            action,
            data_dir=tmp_path,
        )
        assert plan.ready is False
        assert "dated final holdout must be sealed before research begins" in plan.blockers


def test_suite_plan_is_bounded_and_resolves_only_immutable_spec(tmp_path: Path) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)

    plan = build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    public = plan.as_dict()
    resolved_experiment = cast(dict[str, object], public["resolved_experiment"])
    resolved_version = cast(dict[str, object], public["resolved_strategy_version"])
    public_steps = cast(list[dict[str, object]], public["steps"])

    assert plan.ready is True
    assert public["action"] == "baseline"
    assert resolved_experiment["experiment_id"] == experiment_id
    assert resolved_version["strategy_name"] == "mean_reversion"
    assert public["estimated_workload"] == {
        "class": "standard",
        "commands": 1,
        "estimated_canonical_runs": 1,
        "description": "one fixed-parameter discovery backtest",
    }
    holdout = cast(list[dict[str, object]], store.get_project(project_id)["holdouts"])[0]
    assert public_steps[0]["command"] == [
        "backtest",
        "run",
        "AAPL",
        "--strategy",
        "mean_reversion",
        "--snapshot",
        "frozen-2026q2",
        "--fee-bps",
        "1",
        "--slippage-bps",
        "2",
        "--account-type",
        "CASH",
        "--param",
        "entry_z=2",
        "--param",
        "window=20",
        "--as-of",
        f"<sealed-pre-holdout:{holdout['holdout_spec_hash']}>",
    ]
    assert "2026-03-31" in plan.steps[0].argv
    assert "2026-03-31" not in json.dumps(public, sort_keys=True)
    assert "argv" not in public_steps[0]


def test_action_readiness_uses_stage_dependencies_and_nulls_are_not_a_vote(
    tmp_path: Path,
) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)
    blocked = build_suite_plan(store, project_id, experiment_id, "inner_oos", data_dir=tmp_path)
    assert blocked.ready is False
    assert blocked.blockers == ("baseline stage must be pass or warning",)

    _complete_action(store, tmp_path, project_id, experiment_id, "baseline")
    store.append_experiment_stage_state(
        project_id, experiment_id, "oos", "ready", reason="baseline passed"
    )
    oos = build_suite_plan(store, project_id, experiment_id, "inner_oos", data_dir=tmp_path)
    assert oos.ready is True
    assert oos.steps[0].argv[:3] == ("backtest", "oos", "AAPL")

    _complete_action(store, tmp_path, project_id, experiment_id, "inner_oos")
    nulls = build_suite_plan(
        store, project_id, experiment_id, "three_null_families", data_dir=tmp_path
    )
    assert nulls.ready is True
    assert [step.evidence_role for step in nulls.steps] == [
        "headline_tier1_plus_tier2",
        "tier1_sensitivity_tier2_repeated_non_governing",
        "tier1_sensitivity_tier2_repeated_non_governing",
    ]
    assert [step.argv[step.argv.index("--null-model") + 1] for step in nulls.steps] == [
        "bootstrap",
        "student_t",
        "garch",
    ]
    governance = cast(dict[str, object], nulls.as_dict()["governance"])
    assert governance["aggregation"] == "no_majority_vote"
    assert "non-governing" in str(governance["sensitivity_tier2_execution"])


def test_qlib_plan_derives_opaque_control_resources_and_all_four_steps(
    tmp_path: Path,
) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)

    plan = build_suite_plan(store, project_id, experiment_id, "qlib", data_dir=tmp_path)
    public = plan.as_dict()
    steps = cast(list[dict[str, object]], public["steps"])
    rendered = json.dumps(public, sort_keys=True)

    assert len(steps) == 4
    assert [step["label"] for step in steps] == [
        "Generate immutable Qlib input",
        "Prepare isolated Qlib exchange",
        "Qlib fold training",
        "Canonical ALPHA ML replay",
    ]
    assert [cast(list[str], step["command"])[1] for step in steps] == [
        "export-input",
        "prepare",
        "train",
        "replay",
    ]
    assert "<managed-input:" in rendered
    assert "<managed-exchange:" in rendered
    assert "<isolated-worker-lock>" in rendered
    assert str(tmp_path) not in rendered
    assert plan.steps[0].argv[4].startswith(str(tmp_path / "control" / "ml" / "inputs"))
    assert plan.steps[1].argv[4].startswith(str(tmp_path / "control" / "ml" / "exchanges"))
    assert public["estimated_workload"] == {
        "class": "heavyweight",
        "commands": 4,
        "estimated_canonical_runs": 1,
        "description": "isolated fold-by-fold Qlib training plus canonical ALPHA replay",
    }
    assert "at least 20 frozen symbols" in " ".join(plan.blockers)


def test_optimizer_grid_is_declared_and_bounded(tmp_path: Path) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)
    _complete_action(store, tmp_path, project_id, experiment_id, "baseline")
    _complete_action(store, tmp_path, project_id, experiment_id, "inner_oos")

    plan = build_suite_plan(store, project_id, experiment_id, "optimize_grid", data_dir=tmp_path)
    plan_public = plan.as_dict()
    steps = cast(list[dict[str, object]], plan_public["steps"])
    command = cast(list[str], steps[0]["command"])
    assert command.count("--grid") == 2
    assert "entry_z=1.5,2" in command
    assert "window=10,20,40" in command
    estimated = cast(dict[str, object], plan_public["estimated_workload"])
    assert estimated["grid_configurations"] == 6


def test_suite_rejects_unmanaged_paths_and_unknown_actions(tmp_path: Path) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)
    with pytest.raises(DataError, match="unsupported suite action"):
        build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, "shell"),
            data_dir=tmp_path,
        )
    assert (
        frozenset(
            {
                "baseline",
                "inner_oos",
                "three_null_families",
                "optimize_grid",
                "fixed_stress",
                "portfolio_cross_asset",
                "qlib",
                "kronos",
                "holdout_reveal",
                "paper_preflight",
            }
        )
        == SUITE_ACTIONS
    )


def test_every_public_action_plan_omits_managed_filesystem_paths(tmp_path: Path) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)
    for action in sorted(SUITE_ACTIONS):
        plan = build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, action),
            data_dir=tmp_path,
        )
        rendered = json.dumps(plan.as_dict(), sort_keys=True)
        assert str(tmp_path) not in rendered
        assert '"argv"' not in rendered
        assert plan.action == action


def test_holdout_plan_redacts_sealed_window_and_runs_canonical_evaluation(tmp_path: Path) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)
    for action in (
        "baseline",
        "inner_oos",
        "three_null_families",
        "optimize_grid",
        "portfolio_cross_asset",
    ):
        _complete_action(store, tmp_path, project_id, experiment_id, action)
    for state in ("ready", "queued", "running", "pass"):
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            "candidate",
            state,
            reason="candidate frozen",
        )
    sealed = cast(list[dict[str, object]], store.get_project(project_id)["holdouts"])[0]

    plan = build_suite_plan(store, project_id, experiment_id, "holdout_reveal", data_dir=tmp_path)
    public = plan.as_dict()
    rendered = json.dumps(public, sort_keys=True)
    assert plan.ready is True
    assert len(plan.steps) == 2
    assert plan.steps[0].argv == ("__holdout__",)
    assert plan.steps[1].argv[:2] == ("backtest", "holdout")
    assert "2026-04-01" in plan.steps[1].argv and "2026-06-30" in plan.steps[1].argv
    assert "2026-04-01" not in rendered and "2026-06-30" not in rendered
    assert f"<sealed:{sealed['holdout_spec_hash']}>" in rendered
    assert public["estimated_workload"] == {
        "class": "standard",
        "commands": 2,
        "estimated_canonical_runs": 1,
        "description": "one audited owner reveal followed by one locked candidate evaluation",
    }


def test_interrupted_holdout_evaluation_resumes_only_the_same_reserved_job(
    tmp_path: Path,
) -> None:
    store, project_id, experiment_id = _experiment(tmp_path)
    for action in (
        "baseline",
        "inner_oos",
        "three_null_families",
        "optimize_grid",
        "portfolio_cross_asset",
    ):
        _complete_action(store, tmp_path, project_id, experiment_id, action)
    for state in ("ready", "queued", "running", "pass"):
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            "candidate",
            state,
            reason="candidate frozen",
        )

    first = build_suite_plan(store, project_id, experiment_id, "holdout_reveal", data_dir=tmp_path)
    job_id = "b5e8389a-ef2e-48dc-aea3-93c205eec791"
    reserve_suite_job(store, first, job_id=job_id)
    for state in ("ready", "queued", "running"):
        store.append_experiment_stage_state(
            project_id,
            experiment_id,
            "holdout",
            cast(StageState, state),
            reason="interrupted holdout suite",
        )
    store.set_job_status(job_id, "running")
    store.record_attempt(
        project_id,
        experiment_id,
        stage="holdout",
        status="queued",
        config_fingerprint="suite:holdout-reveal-step-1",
        details={"action": "holdout_reveal", "job_id": job_id, "step": 1},
    )
    store.reveal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="candidate frozen and approved",
    )
    store.set_job_status(job_id, "failed", terminal_error="worker crashed before evaluation")

    unrelated = build_suite_plan(
        store,
        project_id,
        experiment_id,
        "holdout_reveal",
        data_dir=tmp_path,
        resume_job_id="ce02421f-7d8b-4f64-aea8-f1d6ef48a631",
    )
    assert unrelated.ready is False
    resumed = build_suite_plan(
        store,
        project_id,
        experiment_id,
        "holdout_reveal",
        data_dir=tmp_path,
        resume_job_id=job_id,
    )
    assert resumed.ready is True
    assert resumed.governance["resume_same_job_after_interruption"] is True
    run_id = "2000000000000099"

    def finish_evaluation(
        step: SuiteStep,
        _job_id: str,
        _control: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        assert step.argv[:2] == ("backtest", "holdout")
        holdout = store.get_holdout_spec(project_id, experiment_id)
        assert holdout is not None
        snapshot_hash = hashlib.sha256(
            (tmp_path / "snapshots" / "frozen-2026q2" / "manifest.json").read_bytes()
        ).hexdigest()
        run_dir = tmp_path / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 3,
                    "artifact_contract_version": 3,
                    "run_identity_version": 3,
                    "run_id": run_id,
                    "command": "backtest_holdout",
                    "snapshot_id": "frozen-2026q2",
                    "snapshot_hash": snapshot_hash,
                    "holdout_spec_hash": holdout["spec_hash"],
                    "passed": True,
                    "execution_fingerprint": "a" * 64,
                    "strategy_fingerprint": "b" * 64,
                    "source_fingerprint": "c" * 64,
                    "artifacts": {},
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return StepExecution(returncode=0, run_ids=(run_id,))

    result = execute_suite(
        store,
        resumed,
        data_dir=tmp_path,
        job_id=job_id,
        step_runner=finish_evaluation,
    )

    assert result["status"] == "succeeded"
    audit = cast(list[dict[str, object]], store.get_project(project_id)["holdout_audit"])
    assert [row["event"] for row in audit] == ["sealed", "revealed"]


def _governed_overridden_experiment(tmp_path: Path) -> tuple[ControlStore, str, str]:
    """A research-governed project whose gate the owner overrode (spec §15, ADR-0026)."""
    snapshot_dir = tmp_path / "snapshots" / "frozen-2026q2"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps({"snapshot_id": "frozen-2026q2", "symbols": {}}, sort_keys=True),
        encoding="utf-8",
    )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="SPY exploratory probe",
        hypothesis="Large close deviations revert.",
        falsification_criterion="Reject when locked OOS Sharpe is non-positive.",
        at=datetime(2026, 8, 6, 9, 0, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    store.record_research_gate_override(
        project_id,
        actor="owner",
        reason="Owner accepts exploratory-only engine work before research completes.",
    )
    version = store.create_strategy_version(
        project_id,
        strategy_name="mean_reversion",
        source_fingerprint="git:abc123",
        definition={"window": 20, "entry_z": 2.0, "account_type": "CASH"},
        parameter_space={"window": [10, 20, 40], "entry_z": [1.5, 2.0]},
    )
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="frozen-2026q2",
        universe=["SPY", "AAPL"],
        split_policy={"train": 504, "test": 63, "embargo": 5},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
        stage_config={"tier1_paths": 100, "tier2_paths": 8, "n_resamples": 200},
    )
    experiment_id = str(experiment["experiment_id"])
    store.seal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="reserve final test window before research",
        start_date="2026-04-01",
        end_date="2026-06-30",
    )
    return store, project_id, experiment_id


def test_overridden_gate_injects_the_watermark_flag_into_run_producing_steps(
    tmp_path: Path,
) -> None:
    store, project_id, experiment_id = _governed_overridden_experiment(tmp_path)
    run_actions = (
        "baseline",
        "inner_oos",
        "three_null_families",
        "optimize_grid",
        "portfolio_cross_asset",
        "holdout_reveal",
    )
    for action in run_actions:
        plan = build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, action),
            data_dir=tmp_path,
        )
        assert plan.governance["research_gate"] == {
            "state": "overridden",
            "watermark": "EXPLORATORY / RESEARCH GATE NOT COMPLETED",
        }, action
        run_steps = [
            step for step in plan.steps if step.argv[0] in {"backtest", "validate", "optim"}
        ]
        assert run_steps, action
        for step in run_steps:
            assert "--research-gate-override" in step.argv, (action, step.label)
            assert "--research-gate-override" in step.preview, (action, step.label)


def test_unoverridden_gates_never_inject_the_watermark_flag(tmp_path: Path) -> None:
    # Grandfathered (not_required) projects and every non-overridden state stay unmarked.
    store, project_id, experiment_id = _experiment(tmp_path)
    for action in ("baseline", "three_null_families", "holdout_reveal"):
        plan = build_suite_plan(
            store,
            project_id,
            experiment_id,
            cast(SuiteAction, action),
            data_dir=tmp_path,
        )
        assert "research_gate" not in plan.governance, action
        for step in plan.steps:
            assert "--research-gate-override" not in step.argv, (action, step.label)
            assert "--research-gate-override" not in step.preview, (action, step.label)
