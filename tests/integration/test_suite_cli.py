from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from tests.fixtures.cli_fixtures import seed_store


def test_suite_cli_previews_then_runs_the_exact_resolved_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=80)
    create_snapshot(
        ParquetStore(tmp_path / "store"),
        tmp_path / "snapshots",
        "frozen",
        ["SPY"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Suite CLI",
        hypothesis="Momentum persists.",
        falsification_criterion="Reject on failed locked OOS evidence.",
    )
    project_id = str(project["project_id"])
    version = store.create_strategy_version(
        project_id,
        strategy_name="ts_momentum",
        source_fingerprint="git:abc",
        definition={
            "lookback": 5,
            "skip": 1,
            "vol_window": 3,
            "rebalance_every": 2,
            "starting_cash": 100_000,
        },
        parameter_space={"lookback": [5, 10]},
    )
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="frozen",
        universe=["SPY"],
        split_policy={"train": 30, "test": 10, "embargo": 2},
        costs={"fee_bps": 0, "slippage_bps": 0},
        seeds={"master": 7},
    )
    experiment_id = str(experiment["experiment_id"])
    store.seal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="reserve final test window before research",
        start_date="2026-01-01",
        end_date="2026-03-31",
    )
    runner = CliRunner()

    preview = runner.invoke(app, ["suite", "plan", project_id, experiment_id, "baseline", "--json"])
    assert preview.exit_code == 0, preview.output
    plan = json.loads(preview.output)
    assert plan["ready"] is True
    assert plan["resolved_experiment"] == experiment

    launched = runner.invoke(app, ["suite", "run", project_id, experiment_id, "baseline", "--json"])
    assert launched.exit_code == 0, launched.output
    job = json.loads(launched.output)
    assert job["status"] == "succeeded"
    assert job["plan"] == plan
    assert len(job["result"]["run_ids"]) == 1
    detail = store.get_project(project_id)
    links = cast(list[dict[str, object]], detail["stage_run_links"])
    assert links[0]["run_id"] == job["result"]["run_ids"][0]
    assert links[0]["state"] == "pass"
    journal = store.get_job(job["job_id"])
    events = cast(list[dict[str, object]], journal["events"])
    assert any(event["event_type"] == "heartbeat" for event in events)
    assert any(event["event_type"] == "result" for event in events)
