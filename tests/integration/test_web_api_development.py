"""Bounded Workstation v3 project, job, evidence, and AgentBrief projections."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_web.app import create_app
from tests.fixtures.control_store_fixtures import (
    mark_project_as_migrated_legacy,
    publish_decision_grade_run,
)

runner = CliRunner()


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    return TestClient(create_app())


def _project(client: TestClient, name: str = "AAPL reversal") -> dict[str, object]:
    response = client.post(
        "/api/projects",
        json={
            "name": name,
            "hypothesis": "Large deviations revert after declared costs.",
            "falsification_criterion": "Reject on non-positive locked OOS Sharpe.",
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def _legacy_project(tmp_path: Path, name: str = "AAPL reversal") -> dict[str, object]:
    store = ControlStore(tmp_path)
    project = store.create_project(
        name=name,
        hypothesis="Large deviations revert after declared costs.",
        falsification_criterion="Reject on non-positive locked OOS Sharpe.",
        at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    mark_project_as_migrated_legacy(store, str(project["project_id"]))
    return project


def _version(client: TestClient, project_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/projects/{project_id}/versions",
        json={
            "strategy_name": "mean_reversion",
            "source_fingerprint": "git:abc1234",
            "definition": {"signal": "zscore", "window": 20},
            "parameter_space": {"window": [10, 20, 40]},
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def _experiment(client: TestClient, project_id: str, version_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/projects/{project_id}/experiments",
        json={
            "version_id": version_id,
            "snapshot_id": "snap-aapl-2026q2",
            "universe": ["AAPL", "SPY"],
            "split_policy": {"train": 504, "test": 63, "embargo": 5},
            "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
            "seeds": {"master": 7},
            "stage_config": {"null_families": ["bootstrap", "student_t", "garch"]},
        },
    )
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


def test_monte_carlo_owner_review_has_no_rest_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    response = client.post(
        "/api/projects/project/experiments/experiment/monte-carlo-review",
        json={"decision": "continue", "actor": "owner", "reason": "reviewed"},
    )
    assert response.status_code == 404


def test_project_version_experiment_stage_and_agent_brief_round_trip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "0123456789abcdef"
    publish_decision_grade_run(
        tmp_path,
        run_id=run_id,
        manifest_fields={"outcomes": {"randomized_price_null": {"passed": False}}},
    )
    client = _client(tmp_path, monkeypatch)
    governed_project = _project(client)
    blocked = client.post(
        f"/api/projects/{governed_project['project_id']}/versions",
        json={
            "strategy_name": "mean_reversion",
            "source_fingerprint": "git:must-not-bypass",
            "definition": {"signal": "zscore", "window": 20},
            "parameter_space": {"window": [10, 20, 40]},
        },
    )
    assert blocked.status_code == 422
    assert "research_contract_id" in blocked.text
    assert (
        ControlStore(tmp_path).research_case_summary(str(governed_project["project_id"]))["phase"]
        == "triage"
    )

    project = _legacy_project(tmp_path)
    project_id = str(project["project_id"])
    version = _version(client, project_id)
    experiment = _experiment(client, project_id, str(version["version_id"]))
    sealed = client.post(
        f"/api/projects/{project_id}/holdouts/seal",
        json={
            "experiment_id": experiment["experiment_id"],
            "actor": "owner",
            "reason": "final period reserved before selection",
            "start_date": "2026-01-01",
            "end_date": "2026-06-30",
        },
    )
    assert sealed.status_code == 403, sealed.text
    assert "explicit local alpha CLI owner ceremony" in sealed.text
    cli_sealed = runner.invoke(
        app,
        [
            "project",
            "seal-holdout",
            project_id,
            str(experiment["experiment_id"]),
            "--actor",
            "owner",
            "--reason",
            "final period reserved before selection",
            "--start-date",
            "2026-01-01",
            "--end-date",
            "2026-06-30",
            "--json",
        ],
    )
    assert cli_sealed.exit_code == 0, cli_sealed.output
    shown_version = client.get(f"/api/projects/{project_id}/versions/{version['version_id']}")
    shown_experiment = client.get(
        f"/api/projects/{project_id}/experiments/{experiment['experiment_id']}"
    )
    assert shown_version.status_code == 200, shown_version.text
    assert shown_version.json()["source_fingerprint"] == "git:abc1234"
    assert shown_experiment.status_code == 200, shown_experiment.text
    assert shown_experiment.json()["snapshot_id"] == "snap-aapl-2026q2"

    initialized = client.get(f"/api/projects/{project_id}?lineage_limit=25")
    assert initialized.status_code == 200, initialized.text
    initial_stages = initialized.json()["stage_states"]
    assert len(initial_stages) == 15
    assert next(row for row in initial_stages if row["stage"] == "baseline")["state"] == "ready"
    queued_baseline = client.post(
        f"/api/projects/{project_id}/experiments/{experiment['experiment_id']}"
        "/stages/baseline/state",
        json={"state": "queued", "reason": "owner approved resolved baseline spec"},
    )
    assert queued_baseline.status_code == 200, queued_baseline.text
    assert queued_baseline.json()["state"] == "queued"
    assert queued_baseline.json()["state_history_truncated"] is False
    cannot_reset = client.post(
        f"/api/projects/{project_id}/experiments/{experiment['experiment_id']}"
        "/stages/baseline/state",
        json={"state": "not_started", "reason": "attempted lifecycle reset"},
    )
    assert cannot_reset.status_code == 422

    linked = client.post(
        f"/api/projects/{project_id}/stage-links",
        json={
            "experiment_id": experiment["experiment_id"],
            "stage": "oos",
            "state": "queued",
            "run_id": run_id,
        },
    )
    assert linked.status_code == 200, linked.text
    transitioned = client.post(
        f"/api/stage-links/{linked.json()['link_id']}/state",
        json={"state": "running", "reason": "worker accepted bounded job"},
    )
    assert transitioned.status_code == 200, transitioned.text
    assert transitioned.json()["state"] == "running"
    attempt = client.post(
        f"/api/projects/{project_id}/attempts",
        json={
            "experiment_id": experiment["experiment_id"],
            "stage": "robustness",
            "status": "failed",
            "config_fingerprint": "cfg:bootstrap:7",
            "error": "Tier-2 null threshold not cleared",
            "details": {"family": "bootstrap", "tier": 2},
        },
    )
    assert attempt.status_code == 200, attempt.text
    assert attempt.json()["status"] == "failed"
    detail = client.get(f"/api/projects/{project_id}?lineage_limit=25")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["current_version_id"] == version["version_id"]
    assert body["current_experiment_id"] == experiment["experiment_id"]
    assert len(body["stage_states"]) == 15
    assert next(row for row in body["stage_states"] if row["stage"] == "baseline")["state"] == (
        "queued"
    )
    assert body["stage_run_links"][0]["state_history_truncated"] is False
    assert body["attempts"][0]["details"] == {"family": "bootstrap", "tier": 2}
    assert body["holdouts"][0]["sealed_by"] == "owner"
    assert body["truncated"] == {
        "versions": False,
        "experiments": False,
        "stage_states": False,
        "stage_run_links": False,
        "attempts": False,
        "holdouts": False,
        "holdout_audit": False,
        "decision_packets": False,
        "monte_carlo_reviews": False,
        "research_gate_overrides": False,
    }
    assert body["decision_packets"] == []

    brief = client.get(f"/api/projects/{project_id}/agent-brief?evidence_limit=10")
    assert brief.status_code == 200, brief.text
    brief_body = brief.json()
    assert brief_body["allowed_scope"]["snapshot_id"] == "snap-aapl-2026q2"
    assert len(brief_body["stage_statuses"]) == 15
    assert next(row for row in brief_body["stage_statuses"] if row["stage"] == "baseline") == {
        "run_id": None,
        "stage": "baseline",
        "state": "queued",
    }
    assert next(row for row in brief_body["stage_statuses"] if row["stage"] == "oos") == {
        "run_id": run_id,
        "stage": "oos",
        "state": "running",
    }
    assert "reveal_holdout" not in brief.text


def test_owner_decision_endpoint_denies_mutation_and_cli_freezes_negative_packet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    project = _legacy_project(tmp_path, "Decision")
    project_id = str(project["project_id"])
    version = _version(client, project_id)
    experiment = _experiment(client, project_id, str(version["version_id"]))
    attempt = client.post(
        f"/api/projects/{project_id}/attempts",
        json={
            "experiment_id": experiment["experiment_id"],
            "stage": "baseline",
            "status": "rejected",
            "config_fingerprint": "baseline:rejected",
            "details": {"reason": "falsified"},
        },
    )
    assert attempt.status_code == 200, attempt.text

    missing_ack = client.post(
        f"/api/projects/{project_id}/experiments/{experiment['experiment_id']}/decision",
        json={"verdict": "reject", "actor": "owner", "reason": "falsified"},
    )
    assert missing_ack.status_code == 422
    frozen = client.post(
        f"/api/projects/{project_id}/experiments/{experiment['experiment_id']}/decision",
        json={
            "verdict": "reject",
            "actor": "owner",
            "reason": "baseline falsified the hypothesis",
            "negative_results_acknowledged": True,
        },
    )
    assert frozen.status_code == 403, frozen.text
    assert "explicit local alpha CLI owner ceremony" in frozen.text
    cli_frozen = runner.invoke(
        app,
        [
            "project",
            "decide",
            project_id,
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
    assert cli_frozen.exit_code == 0, cli_frozen.output
    cli_packet = cast(dict[str, object], json.loads(cli_frozen.output))
    assert cli_packet["deployment_scope"] == "sandbox_only"
    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "rejected"
    assert detail.json()["decision_packets"][0]["packet_id"] == cli_packet["packet_id"]


def test_evidence_draft_rejects_mismatched_version_experiment_lineage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "0123456789abcdef"
    publish_decision_grade_run(
        tmp_path,
        run_id=run_id,
        manifest_fields={"outcomes": {"randomized_price_null": {"passed": False}}},
    )
    client = _client(tmp_path, monkeypatch)
    project = _legacy_project(tmp_path, "Evidence lineage")
    project_id = str(project["project_id"])
    first_version = _version(client, project_id)
    experiment = _experiment(client, project_id, str(first_version["version_id"]))
    second_version_response = client.post(
        f"/api/projects/{project_id}/versions",
        json={
            "strategy_name": "mean_reversion",
            "source_fingerprint": "git:def5678",
            "definition": {"signal": "zscore", "window": 40},
            "parameter_space": {"window": [20, 40, 60]},
        },
    )
    assert second_version_response.status_code == 200, second_version_response.text
    second_version = second_version_response.json()
    request = {
        "claim": "The null result is exactly cited to its immutable experiment lineage.",
        "assets": ["AAPL"],
        "frozen_universe": ["AAPL", "SPY"],
        "timeframe": "1d",
        "method": "walk_forward_oos",
        "knowledge_at": "2026-07-19T10:00:00Z",
        "author": "codex",
        "author_kind": "agent",
        "project_id": project_id,
        "experiment_id": experiment["experiment_id"],
        "source_run_id": run_id,
        "source_artifact": "manifest.json",
        "source_field": "outcomes.randomized_price_null",
    }

    valid = client.post(
        "/api/evidence/draft",
        json={**request, "strategy_version_id": first_version["version_id"]},
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["experiment_id"] == experiment["experiment_id"]
    assert valid.json()["strategy_version_id"] == first_version["version_id"]

    mismatched = client.post(
        "/api/evidence/draft",
        json={**request, "strategy_version_id": second_version["version_id"]},
    )
    assert mismatched.status_code == 422
    detail = " ".join(str(mismatched.json()["message"]).split())
    assert "evidence strategy version" in detail
    assert "does not match the experiment" in detail
    assert "lineage" in detail


def test_project_and_job_pages_are_bounded_and_report_continuation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    first = _project(client, "First")
    _project(client, "Second")
    page = client.get("/api/projects?limit=1&offset=0")
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["has_more"] is True
    assert client.get("/api/projects?limit=101").status_code == 422

    created = client.post(
        "/api/development/jobs",
        json={
            "kind": "validation_suite",
            "request": {"families": ["bootstrap", "student_t", "garch"]},
            "project_id": first["project_id"],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "queued"
    jobs = client.get("/api/development/jobs?limit=1")
    assert jobs.status_code == 200, jobs.text
    assert jobs.json()["items"][0]["job_id"] == created.json()["job_id"]
    ControlStore(tmp_path).append_job_event(
        created.json()["job_id"], event_type="log", payload={"message": "latest"}
    )
    shown = client.get(f"/api/development/jobs/{created.json()['job_id']}?event_limit=1")
    assert shown.status_code == 200, shown.text
    assert shown.json()["events"][0]["event_type"] == "created"
    assert shown.json()["event_total"] == 2
    assert shown.json()["events_has_more"] is True
    assert shown.json()["events_truncated"] is True
    assert shown.json()["event_tail"] is False

    latest = client.get(
        f"/api/development/jobs/{created.json()['job_id']}?event_limit=1&event_tail=true"
    )
    assert latest.status_code == 200, latest.text
    assert latest.json()["events"][0]["payload"] == {"message": "latest"}
    assert latest.json()["event_tail"] is True


def test_evidence_draft_search_review_and_as_of_are_exactly_cited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "0123456789abcdef"
    publish_decision_grade_run(
        tmp_path,
        run_id=run_id,
        manifest_fields={"outcomes": {"randomized_price_null": {"passed": False}}},
    )
    client = _client(tmp_path, monkeypatch)
    project = _legacy_project(tmp_path)
    project_id = str(project["project_id"])
    version = _version(client, project_id)
    experiment = _experiment(client, project_id, str(version["version_id"]))
    draft = client.post(
        "/api/evidence/draft",
        json={
            "claim": "AAPL reversal needs more OOS support.",
            "assets": ["AAPL"],
            "frozen_universe": ["AAPL", "SPY"],
            "timeframe": "1d",
            "method": "walk_forward_oos",
            "knowledge_at": "2026-07-19T08:00:00Z",
            "market_data_cutoff": "2026-07-18T08:00:00Z",
            "author": "codex",
            "author_kind": "agent",
            "project_id": project_id,
            "strategy_version_id": version["version_id"],
            "experiment_id": experiment["experiment_id"],
            "source_run_id": run_id,
            "source_artifact": "manifest.json",
            "source_field": "outcomes.randomized_price_null",
            "row_selector": {},
            "counterevidence": [],
            "contradiction_ids": [],
        },
    )
    assert draft.status_code == 200, draft.text
    assert draft.json()["status"] == "draft"

    page = client.get(
        "/api/evidence",
        params={
            "asset": "AAPL",
            "project_id": project_id,
            "as_of": draft.json()["created_at"],
        },
    )
    assert page.status_code == 200, page.text
    assert page.json()["items"][0]["source_artifact"] == "manifest.json"
    reviewed = client.post(
        f"/api/evidence/{draft.json()['evidence_id']}/review",
        json={"status": "rejected", "author": "owner", "author_kind": "human"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["revision"] == 2
    shown = client.get(f"/api/evidence/{draft.json()['evidence_id']}?revision_limit=1")
    assert shown.status_code == 200, shown.text
    assert shown.json()["revisions_truncated"] is True


def test_control_api_rejects_unbounded_and_arbitrary_payloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    assert client.get("/api/evidence?limit=101").status_code == 422
    response = client.post(
        "/api/projects",
        json={
            "name": "Unsafe",
            "hypothesis": "Hypothesis.",
            "falsification_criterion": "Criterion.",
            "command": "python -c arbitrary",
        },
    )
    assert response.status_code == 422
    paths = create_app().openapi()["paths"]
    assert not any("reveal" in path or "command" in path for path in paths if "projects" in path)


def test_research_gate_state_and_active_overrides_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _client(tmp_path, monkeypatch)
    project = _project(client, name="Gate state probe")
    project_id = str(project["project_id"])
    assert project["research_gate_state"] == "open"

    listed = client.get("/api/projects")
    assert listed.status_code == 200, listed.text
    items = cast(list[dict[str, object]], listed.json()["items"])
    assert (
        next(item["research_gate_state"] for item in items if item["project_id"] == project_id)
        == "open"
    )

    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["research_gate_state"] == "open"
    assert body["research_gate_overrides"] == []
    assert body["truncated"]["research_gate_overrides"] is False

    # The override itself is owner-only trusted-local CLI authority; REST only reads it.
    ControlStore(tmp_path).record_research_gate_override(
        project_id,
        actor="owner",
        reason="Owner accepts exploratory-only engine work before research completes.",
    )

    after = client.get(f"/api/projects/{project_id}").json()
    assert after["research_gate_state"] == "overridden"
    overrides = cast(list[dict[str, object]], after["research_gate_overrides"])
    assert [(row["sequence"], row["actor"]) for row in overrides] == [(1, "owner")]

    active = client.get("/api/research-gate-overrides")
    assert active.status_code == 200, active.text
    rows = cast(list[dict[str, object]], active.json())
    assert [(row["project_id"], row["sequence"]) for row in rows] == [(project_id, 1)]
    assert rows[0]["project_name"] == "Gate state probe"

    # No mutation verb exists for the override surface.
    assert client.post("/api/research-gate-overrides", json={}).status_code == 405

    legacy = _legacy_project(tmp_path, name="Grandfathered momentum")
    legacy_detail = client.get(f"/api/projects/{legacy['project_id']}").json()
    assert legacy_detail["research_gate_state"] == "not_required"
