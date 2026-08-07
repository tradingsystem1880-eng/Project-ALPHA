"""CLI projections for the Workstation v3 control plane."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.control_store import ControlStore, parse_timestamp
from alpha_cli.main import app
from tests.fixtures.control_store_fixtures import (
    mark_project_as_migrated_legacy,
    publish_decision_grade_run,
)

runner = CliRunner()


def test_project_and_evidence_cli_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    publish_decision_grade_run(
        tmp_path,
        manifest_fields={"outcomes": {"randomized_price_null": {"passed": False}}},
    )

    created = runner.invoke(
        app,
        [
            "project",
            "create",
            "AAPL reversal",
            "--hypothesis",
            "Large deviations revert.",
            "--falsification",
            "Reject on non-positive locked OOS Sharpe.",
            "--json",
        ],
    )
    assert created.exit_code == 0, created.output
    project = json.loads(created.output)

    governed_version_out = runner.invoke(
        app,
        [
            "project",
            "version",
            project["project_id"],
            "--strategy",
            "mean_reversion",
            "--source-fingerprint",
            "git:abc1234",
            "--definition-json",
            '{"signal":"zscore","window":20}',
            "--parameter-space-json",
            '{"window":[10,20,40]}',
            "--json",
        ],
    )
    assert governed_version_out.exit_code != 0
    assert "research_contract_id" in governed_version_out.output
    research_case = ControlStore(tmp_path).research_case_summary(str(project["project_id"]))
    assert research_case["phase"] == "triage"

    legacy_store = ControlStore(tmp_path)
    project = legacy_store.create_project(
        name="Grandfathered AAPL reversal",
        hypothesis="Large deviations revert.",
        falsification_criterion="Reject on non-positive locked OOS Sharpe.",
        at=parse_timestamp("2026-07-19T09:00:00Z"),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(legacy_store, project_id)
    version_out = runner.invoke(
        app,
        [
            "project",
            "version",
            project_id,
            "--strategy",
            "mean_reversion",
            "--source-fingerprint",
            "git:abc1234",
            "--definition-json",
            '{"signal":"zscore","window":20}',
            "--parameter-space-json",
            '{"window":[10,20,40]}',
            "--json",
        ],
    )
    assert version_out.exit_code == 0, version_out.output
    version = json.loads(version_out.output)

    experiment_out = runner.invoke(
        app,
        [
            "project",
            "experiment",
            project_id,
            "--version-id",
            version["version_id"],
            "--snapshot",
            "aapl-2026q2",
            "--universe",
            "AAPL,SPY",
            "--split-policy-json",
            '{"train":504,"test":63,"embargo":5}',
            "--costs-json",
            '{"fee_bps":1.0,"slippage_bps":2.0}',
            "--seeds-json",
            '{"master":7}',
            "--json",
        ],
    )
    assert experiment_out.exit_code == 0, experiment_out.output
    experiment = json.loads(experiment_out.output)

    sealed = runner.invoke(
        app,
        [
            "project",
            "seal-holdout",
            project_id,
            experiment["experiment_id"],
            "--actor",
            "owner",
            "--reason",
            "final period reserved",
            "--start-date",
            "2026-04-01",
            "--end-date",
            "2026-06-30",
            "--json",
        ],
    )
    reveal = runner.invoke(
        app,
        [
            "project",
            "reveal-holdout",
            project_id,
            experiment["experiment_id"],
            "--actor",
            "owner",
            "--reason",
            "candidate frozen",
            "--json",
        ],
    )
    shown = runner.invoke(app, ["project", "show", project_id, "--json"])
    assert sealed.exit_code == 0, sealed.output
    assert reveal.exit_code != 0
    assert "verified canonical suite evidence" in reveal.output
    assert shown.exit_code == 0, shown.output
    assert json.loads(shown.output)["holdouts"][0]["revealed_by"] is None

    evidence_out = runner.invoke(
        app,
        [
            "evidence",
            "add",
            "AAPL reversal needs more OOS support.",
            "--assets",
            "AAPL",
            "--frozen-universe",
            "AAPL,SPY",
            "--method",
            "walk_forward_oos",
            "--knowledge-at",
            "2026-07-19T10:00:00Z",
            "--market-data-cutoff",
            "2026-07-18T10:00:00Z",
            "--author",
            "codex",
            "--author-kind",
            "agent",
            "--project-id",
            project_id,
            "--source-run-id",
            "0123456789abcdef",
            "--source-artifact",
            "manifest.json",
            "--source-field",
            "outcomes.randomized_price_null",
            "--json",
        ],
    )
    assert evidence_out.exit_code == 0, evidence_out.output
    evidence = json.loads(evidence_out.output)
    revised = runner.invoke(
        app,
        [
            "evidence",
            "revise",
            evidence["evidence_id"],
            "--status",
            "rejected",
            "--author",
            "owner",
            "--author-kind",
            "human",
            "--json",
        ],
    )
    listed = runner.invoke(app, ["evidence", "list", "--asset", "AAPL", "--json"])
    shown_evidence = runner.invoke(app, ["evidence", "show", evidence["evidence_id"]])
    plain_evidence = runner.invoke(app, ["evidence", "list", "--asset", "AAPL"])
    assert revised.exit_code == 0, revised.output
    assert listed.exit_code == 0, listed.output
    assert shown_evidence.exit_code == 0, shown_evidence.output
    assert plain_evidence.exit_code == 0, plain_evidence.output
    assert json.loads(listed.output)[0]["status"] == "rejected"


def test_agent_brief_is_bounded_point_in_time_and_omits_holdout_reveal_action(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    publish_decision_grade_run(
        tmp_path,
        manifest_fields={"outcomes": {"walk_forward_oos": {}, "locked_holdout": {}}},
    )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Agent brief",
        hypothesis="AAPL reversals persist after costs.",
        falsification_criterion="Reject on non-positive locked OOS Sharpe.",
        at=parse_timestamp("2026-07-19T07:00:00Z"),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="mean_reversion",
        source_fingerprint="git:abc1234",
        definition={"signal": "zscore"},
        parameter_space={"window": [10, 20]},
        at=parse_timestamp("2026-07-19T07:10:00Z"),
    )
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="snap-agent",
        universe=["AAPL", "SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1.0},
        seeds={"master": 7},
        at=parse_timestamp("2026-07-19T07:20:00Z"),
    )
    store.create_evidence(
        claim="Available before cutoff.",
        assets=["AAPL"],
        frozen_universe=["AAPL", "SPY"],
        timeframe="1d",
        method="walk_forward_oos",
        knowledge_at=parse_timestamp("2026-07-19T08:00:00Z"),
        author="codex",
        author_kind="agent",
        project_id=project_id,
        strategy_version_id=str(version["version_id"]),
        experiment_id=str(experiment["experiment_id"]),
        source_run_id="0123456789abcdef",
        source_artifact="manifest.json",
        source_field="outcomes.walk_forward_oos",
        at=parse_timestamp("2026-07-19T08:01:00Z"),
    )
    store.create_evidence(
        claim="Unavailable after cutoff.",
        assets=["AAPL"],
        frozen_universe=["AAPL", "SPY"],
        timeframe="1d",
        method="locked_holdout",
        knowledge_at=parse_timestamp("2026-07-19T10:00:00Z"),
        author="codex",
        author_kind="agent",
        project_id=project_id,
        strategy_version_id=str(version["version_id"]),
        experiment_id=str(experiment["experiment_id"]),
        source_run_id="0123456789abcdef",
        source_artifact="manifest.json",
        source_field="outcomes.locked_holdout",
        at=parse_timestamp("2026-07-19T10:01:00Z"),
    )

    result = runner.invoke(
        app,
        [
            "project",
            "agent-brief",
            project_id,
            "--evidence-limit",
            "1",
            "--as-of",
            "2026-07-19T09:00:00Z",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    brief = json.loads(result.output)
    assert brief["schema_version"] == 1
    assert brief["allowed_scope"] == {
        "experiment_id": experiment["experiment_id"],
        "snapshot_id": "snap-agent",
        "universe": ["AAPL", "SPY"],
        "version_id": version["version_id"],
    }
    assert [item["claim"] for item in brief["evidence"]] == ["Available before cutoff."]
    assert brief["evidence_truncated"] is False
    assert "reveal_holdout" not in json.dumps(brief)
    assert "filesystem" not in json.dumps(brief)


def test_owner_can_freeze_a_negative_decision_packet_through_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Rejected candidate",
        hypothesis="A test hypothesis.",
        falsification_criterion="Reject on baseline failure.",
        at=parse_timestamp("2026-07-19T07:00:00Z"),
    )
    mark_project_as_migrated_legacy(store, str(project["project_id"]))
    version = store.create_strategy_version(
        str(project["project_id"]),
        strategy_name="ts_momentum",
        source_fingerprint="git:abc123-clean",
        definition={},
        parameter_space={},
    )
    experiment = store.create_experiment_spec(
        str(project["project_id"]),
        strategy_version_id=str(version["version_id"]),
        snapshot_id="frozen",
        universe=["SPY"],
        split_policy={},
        costs={},
        seeds={"master": 7},
    )
    store.record_attempt(
        str(project["project_id"]),
        str(experiment["experiment_id"]),
        stage="baseline",
        status="rejected",
        config_fingerprint="baseline:rejected",
    )

    result = runner.invoke(
        app,
        [
            "project",
            "decide",
            str(project["project_id"]),
            str(experiment["experiment_id"]),
            "--verdict",
            "reject",
            "--actor",
            "owner",
            "--reason",
            "baseline falsified the hypothesis",
            "--acknowledge-negative-results",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    packet = json.loads(result.output)
    assert packet["verdict"] == "reject"
    assert packet["places_real_orders"] is False
    assert ControlStore(tmp_path).get_project(str(project["project_id"]))["status"] == "rejected"


def test_agent_brief_never_overlays_stage_links_from_an_old_experiment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = "0123456789abcdef"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Current experiment brief",
        hypothesis="A causal hypothesis.",
        falsification_criterion="Reject on failed OOS.",
        at=parse_timestamp("2026-07-19T07:00:00Z"),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="mean_reversion",
        source_fingerprint="git:abc1234",
        definition={"signal": "zscore"},
        parameter_space={"window": [20]},
    )
    first = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="snap-old",
        universe=["AAPL", "SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1.0},
        seeds={"master": 7},
    )
    store.link_stage_run(
        project_id,
        str(first["experiment_id"]),
        stage="baseline",
        state="queued",
        run_id=run_id,
    )
    current = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="snap-current",
        universe=["AAPL", "SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1.0},
        seeds={"master": 7},
    )

    result = runner.invoke(app, ["project", "agent-brief", project_id, "--json"])
    assert result.exit_code == 0, result.output
    brief = json.loads(result.output)
    assert brief["allowed_scope"]["experiment_id"] == current["experiment_id"]
    baseline = next(row for row in brief["stage_statuses"] if row["stage"] == "baseline")
    assert baseline == {"run_id": None, "stage": "baseline", "state": "ready"}


def test_cli_rejects_malformed_json_without_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    created = runner.invoke(
        app,
        [
            "project",
            "create",
            "Bad JSON test",
            "--hypothesis",
            "A hypothesis.",
            "--falsification",
            "A falsification rule.",
            "--json",
        ],
    )
    project_id = json.loads(created.output)["project_id"]
    result = runner.invoke(
        app,
        [
            "project",
            "version",
            project_id,
            "--strategy",
            "mean_reversion",
            "--source-fingerprint",
            "git:abc1234",
            "--definition-json",
            "not-json",
            "--json",
        ],
    )
    assert result.exit_code != 0
    assert "valid JSON object" in result.output
    assert "Traceback" not in result.output


def test_project_stage_attempt_and_job_cli_projections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = "0123456789abcdef"
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text("{}", encoding="utf-8")
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="CLI operations",
        hypothesis="A testable hypothesis.",
        falsification_criterion="Reject on failed OOS.",
        at=parse_timestamp("2026-07-19T07:00:00Z"),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="mean_reversion",
        source_fingerprint="git:abc1234",
        definition={"signal": "zscore"},
        parameter_space={"window": [20]},
    )
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="snap-cli",
        universe=["AAPL", "SPY"],
        split_policy={"train": 504, "test": 63},
        costs={"fee_bps": 1.0},
        seeds={"master": 7},
    )
    experiment_id = str(experiment["experiment_id"])

    linked = runner.invoke(
        app,
        [
            "project",
            "link-run",
            project_id,
            experiment_id,
            run_id,
            "--stage",
            "oos",
            "--state",
            "queued",
            "--json",
        ],
    )
    assert linked.exit_code == 0, linked.output
    link_id = json.loads(linked.output)["link_id"]
    transitioned = runner.invoke(
        app,
        [
            "project",
            "stage-state",
            link_id,
            "running",
            "--reason",
            "worker started",
            "--json",
        ],
    )
    attempted = runner.invoke(
        app,
        [
            "project",
            "attempt",
            project_id,
            experiment_id,
            "--stage",
            "robustness",
            "--status",
            "failed",
            "--config-fingerprint",
            "cfg:bootstrap:7",
            "--error",
            "gate failed",
            "--details-json",
            '{"family":"bootstrap"}',
            "--json",
        ],
    )
    assert transitioned.exit_code == 0, transitioned.output
    assert attempted.exit_code == 0, attempted.output

    created_job = runner.invoke(
        app,
        [
            "project",
            "job-create",
            "validation_suite",
            "--project-id",
            project_id,
            "--request-json",
            '{"family":"bootstrap"}',
            "--json",
        ],
    )
    assert created_job.exit_code == 0, created_job.output
    job_id = json.loads(created_job.output)["job_id"]
    running = runner.invoke(app, ["project", "job-status", job_id, "running", "--json"])
    event = runner.invoke(
        app,
        [
            "project",
            "job-event",
            job_id,
            "progress",
            "--payload-json",
            '{"completed":1,"total":3}',
            "--json",
        ],
    )
    failed = runner.invoke(
        app,
        [
            "project",
            "job-status",
            job_id,
            "failed",
            "--terminal-error",
            "worker stopped",
            "--json",
        ],
    )
    shown = runner.invoke(app, ["project", "job-show", job_id, "--json"])
    paged = runner.invoke(
        app,
        [
            "project",
            "job-show",
            job_id,
            "--event-limit",
            "2",
            "--event-offset",
            "1",
            "--json",
        ],
    )
    tailed = runner.invoke(
        app,
        ["project", "job-show", job_id, "--event-limit", "2", "--event-tail", "--json"],
    )
    listed = runner.invoke(app, ["project", "job-list", "--json"])
    assert all(
        result.exit_code == 0 for result in (running, event, failed, shown, paged, tailed, listed)
    )
    assert json.loads(shown.output)["last_sequence"] == 4
    assert [row["sequence"] for row in json.loads(paged.output)["events"]] == [2, 3]
    tail = json.loads(tailed.output)
    assert [row["sequence"] for row in tail["events"]] == [3, 4]
    assert tail["event_total"] == 4
    assert tail["events_has_more"] is True

    interrupted = runner.invoke(app, ["project", "job-create", "kronos_eval", "--json"])
    interrupted_id = json.loads(interrupted.output)["job_id"]
    cancellation = runner.invoke(
        app,
        [
            "project",
            "job-cancel",
            interrupted_id,
            "--actor",
            "owner",
            "--reason",
            "stop queued work",
            "--json",
        ],
    )
    reconciled = runner.invoke(app, ["project", "job-reconcile", "--json"])
    assert interrupted.exit_code == 0, interrupted.output
    assert cancellation.exit_code == 0, cancellation.output
    assert json.loads(cancellation.output)["status"] == "cancellation_requested"
    assert reconciled.exit_code == 0, reconciled.output
    assert json.loads(reconciled.output) == []  # fresh queued work is never auto-failed

    plain_projects = runner.invoke(app, ["project", "list"])
    plain_project = runner.invoke(app, ["project", "show", project_id])
    plain_jobs = runner.invoke(app, ["project", "job-list"])
    assert all(result.exit_code == 0 for result in (plain_projects, plain_project, plain_jobs))
    assert "CLI operations" in plain_projects.output


def test_empty_plain_control_lists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    projects = runner.invoke(app, ["project", "list"])
    jobs = runner.invoke(app, ["project", "job-list"])
    evidence = runner.invoke(app, ["evidence", "list"])
    assert projects.output.strip() == "no strategy projects"
    assert jobs.output.strip() == "no development jobs"
    assert evidence.output.strip() == "no evidence"


def test_control_cli_domain_errors_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    missing_project = "3b91647c-ded3-4903-a1a6-c8e64e86d229"
    missing_evidence = "847bf878-2e7b-4786-8057-7fa6bb87382e"
    missing_job = "cd3077f9-82ff-4c87-a7ff-8ee2c6c412ae"
    missing_experiment = "ex_" + "0" * 64
    commands = [
        [
            "project",
            "create",
            " ",
            "--hypothesis",
            "h",
            "--falsification",
            "f",
        ],
        ["project", "show", missing_project],
        [
            "project",
            "version",
            missing_project,
            "--strategy",
            "mean_reversion",
            "--source-fingerprint",
            "git:x",
        ],
        [
            "project",
            "experiment",
            missing_project,
            "--version-id",
            "sv_" + "0" * 64,
            "--snapshot",
            "snap",
            "--universe",
            "AAPL",
            "--split-policy-json",
            "{}",
            "--costs-json",
            "{}",
            "--seeds-json",
            "{}",
        ],
        [
            "project",
            "link-run",
            missing_project,
            missing_experiment,
            "0123456789abcdef",
            "--stage",
            "oos",
            "--state",
            "pass",
        ],
        [
            "project",
            "attempt",
            missing_project,
            missing_experiment,
            "--stage",
            "oos",
            "--status",
            "bad",
            "--config-fingerprint",
            "cfg",
        ],
        ["project", "stage-state", missing_job, "running", "--reason", "missing"],
        [
            "project",
            "seal-holdout",
            missing_project,
            missing_experiment,
            "--actor",
            "owner",
            "--reason",
            "missing",
        ],
        [
            "project",
            "reveal-holdout",
            missing_project,
            missing_experiment,
            "--actor",
            "owner",
            "--reason",
            "missing",
        ],
        [
            "project",
            "job-create",
            "test",
            "--experiment-id",
            missing_experiment,
        ],
        ["project", "job-status", missing_job, "running"],
        ["project", "job-event", missing_job, "progress"],
        ["project", "job-show", missing_job],
        ["project", "job-reconcile", "--reason", " "],
        [
            "evidence",
            "add",
            "claim",
            "--assets",
            "AAPL",
            "--frozen-universe",
            "AAPL",
            "--method",
            "oos",
            "--knowledge-at",
            "2026-07-19T10:00:00Z",
            "--author",
            "codex",
            "--author-kind",
            "robot",
            "--source-run-id",
            "0123456789abcdef",
            "--source-artifact",
            "manifest.json",
            "--source-field",
            "outcomes",
        ],
        [
            "evidence",
            "revise",
            missing_evidence,
            "--status",
            "rejected",
            "--author",
            "owner",
            "--author-kind",
            "human",
        ],
        ["evidence", "show", missing_evidence],
        ["evidence", "list", "--status", "unknown"],
    ]
    for command in commands:
        result = runner.invoke(app, command)
        assert result.exit_code != 0, command
        assert "Traceback" not in result.output

    malformed_object = runner.invoke(
        app,
        [
            "evidence",
            "add",
            "claim",
            "--assets",
            "AAPL",
            "--frozen-universe",
            "AAPL",
            "--method",
            "oos",
            "--knowledge-at",
            "2026-07-19T10:00:00Z",
            "--author",
            "codex",
            "--author-kind",
            "agent",
            "--source-run-id",
            "0123456789abcdef",
            "--source-artifact",
            "manifest.json",
            "--source-field",
            "outcomes",
            "--row-selector-json",
            "[]",
        ],
    )
    assert malformed_object.exit_code != 0
    assert "valid JSON object" in malformed_object.output


def test_version_command_passes_research_contract_id_to_the_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The governed-version CLI option must reach create_strategy_version verbatim.

    The governed-version SEMANTICS (approved confirmation contract, owner advance
    decision, denial without them) are exhaustively covered at the store layer in
    tests/unit/test_research_control_store.py; this guards the CLI plumbing that those
    tests cannot see.
    """
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    captured: dict[str, object] = {}

    def fake_create_strategy_version(
        self: ControlStore, project_id: str, **kwargs: object
    ) -> dict[str, object]:
        captured["project_id"] = project_id
        captured.update(kwargs)
        return {"version_id": "sv_fake", "research_contract_id": kwargs["research_contract_id"]}

    monkeypatch.setattr(ControlStore, "create_strategy_version", fake_create_strategy_version)
    result = runner.invoke(
        app,
        [
            "project",
            "version",
            "11111111-1111-4111-8111-111111111111",
            "--strategy",
            "double_bottom",
            "--source-fingerprint",
            "git:3333333",
            "--definition-json",
            '{"detector": "causal-double-bottom-v1"}',
            "--parameter-space-json",
            '{"tolerance": [0.005, 0.01]}',
            "--research-contract-id",
            "rc_" + "c" * 64,
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["project_id"] == "11111111-1111-4111-8111-111111111111"
    assert captured["strategy_name"] == "double_bottom"
    assert captured["source_fingerprint"] == "git:3333333"
    assert captured["definition"] == {"detector": "causal-double-bottom-v1"}
    assert captured["parameter_space"] == {"tolerance": [0.005, 0.01]}
    assert captured["research_contract_id"] == "rc_" + "c" * 64
    assert json.loads(result.output)["research_contract_id"] == "rc_" + "c" * 64
