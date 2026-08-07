from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from fastapi.testclient import TestClient

from alpha_cli.control_store import ControlStore
from alpha_web import _invoke
from alpha_web.app import create_app
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy


def _graph(tmp_path: Path, client: TestClient) -> tuple[str, str]:
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Suite project",
        hypothesis="AAPL deviations revert.",
        falsification_criterion="Reject on failed OOS evidence.",
        at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = client.post(
        f"/api/projects/{project_id}/versions",
        json={
            "strategy_name": "mean_reversion",
            "source_fingerprint": "git:abc",
            "definition": {"window": 20, "entry_z": 2.0},
            "parameter_space": {"window": [10, 20, 40]},
        },
    ).json()
    experiment = client.post(
        f"/api/projects/{project_id}/experiments",
        json={
            "version_id": version["version_id"],
            "snapshot_id": "frozen-2026q2",
            "universe": ["AAPL", "SPY"],
            "split_policy": {"train": 504, "test": 63, "embargo": 5},
            "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
            "seeds": {"master": 7},
            "stage_config": {},
        },
    ).json()
    sealed = client.post(
        f"/api/projects/{project_id}/holdouts/seal",
        json={
            "experiment_id": experiment["experiment_id"],
            "actor": "owner",
            "reason": "reserve the final period before suite research",
            "start_date": "2026-04-01",
            "end_date": "2026-06-30",
        },
    )
    assert sealed.status_code == 200, sealed.text
    return project_id, str(experiment["experiment_id"])


def test_suite_plan_and_launch_are_typed_and_allowlisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    _invoke.JOBS.clear()
    client = TestClient(create_app())
    project_id, experiment_id = _graph(tmp_path, client)

    preview = client.get(
        f"/api/projects/{project_id}/experiments/{experiment_id}/suite/baseline/plan"
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["ready"] is True
    assert preview.json()["resolved_experiment"]["experiment_id"] == experiment_id
    assert preview.json()["steps"][0]["command"][:3] == ["backtest", "run", "AAPL"]
    assert preview.json()["estimated_workload"]["commands"] == 1

    launched_args: list[list[str]] = []

    def fake_launch(args: list[str], *, data_dir: Path, run_type: str | None) -> _invoke.Job:
        assert data_dir == tmp_path
        assert run_type is None
        launched_args.append(args)
        job = _invoke.Job(args, run_type)
        _invoke.JOBS[job.job_id] = job
        return job

    monkeypatch.setattr(_invoke, "launch", fake_launch)
    launched = client.post(
        f"/api/projects/{project_id}/experiments/{experiment_id}/suite/baseline/run",
        json={},
    )
    assert launched.status_code == 200, launched.text
    body = cast(dict[str, object], launched.json())
    assert body["status"] == "starting"
    assert launched_args[0][:5] == [
        "suite",
        "run",
        project_id,
        experiment_id,
        "baseline",
    ]
    assert "--job-id" in launched_args[0]
    assert "python" not in launched.text and "filesystem" not in launched.text

    cancelled = client.delete(f"/api/development/suite-jobs/{body['job_id']}")
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancellation_requested"


def test_suite_rest_rejects_free_form_and_requires_owner_holdout_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    client = TestClient(create_app())
    project_id, experiment_id = _graph(tmp_path, client)
    path = f"/api/projects/{project_id}/experiments/{experiment_id}/suite"
    assert client.get(f"{path}/shell/plan").status_code == 422
    unsafe = client.post(
        f"{path}/baseline/run",
        json={"command": "python -c arbitrary"},
    )
    assert unsafe.status_code == 422
    holdout = client.post(f"{path}/holdout_reveal/run", json={})
    assert holdout.status_code == 422
    assert "owner_actor" in holdout.text
