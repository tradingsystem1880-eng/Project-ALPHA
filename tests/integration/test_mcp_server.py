"""The MCP server's tools drive the real `alpha` CLI end-to-end (offline, no network).

These call the tool functions directly (FastMCP leaves them ordinary callables) against a temp
ALPHA_DATA_DIR seeded with the shared fixture, so a real `alpha` subprocess runs each time —
exercising subprocess invocation, run-id parsing, manifest reads, run-type routing, the
filesystem read tools, and the FastMCP registration.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore
from alpha_mcp import _invoke, server
from tests.fixtures.cli_fixtures import seed_store
from tests.fixtures.control_store_fixtures import (
    mark_project_as_migrated_legacy,
    publish_decision_grade_run,
)

# small-parameter knobs so the fixture's 60 bars warm up, trade, and cost nothing
_OPTS = {
    "lookback": "5",
    "skip": "1",
    "vol-window": "3",
    "rebalance-every": "2",
    "fee-bps": "0",
    "slippage-bps": "0",
    "starting-cash": "100000",
}


def test_backtest_run_tool_returns_a_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    manifest = server.backtest_run("SPY", options=_OPTS)
    assert manifest["command"] == "backtest_run"
    run_id = manifest["run_id"]

    # the read tools see the same run from disk, no engine
    assert server.get_run(run_id)["run_id"] == run_id
    assert any(r["run_id"] == run_id for r in server.list_runs())


def test_propfirm_from_run_tool(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)

    bt = server.backtest_run("SPY", options=_OPTS)
    pf = server.propfirm_run(
        from_run=bt["run_id"], firm="topstep", options={"n-paths": "200", "seed": "7"}
    )
    assert pf["command"] == "propfirm"
    assert pf["firm"] == "topstep"


def test_forecast_run_tool_returns_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=30)

    manifest = server.forecast_run(
        "SPY", options={"model": "fake", "context": "8", "horizon": "4", "samples": "6"}
    )
    assert manifest["command"] == "forecast_run"
    assert manifest["model"]["model_id"] == "fake"
    assert server.get_run(manifest["run_id"])["run_id"] == manifest["run_id"]
    assert any(r["run_id"] == manifest["run_id"] for r in server.list_runs())
    jobs = ControlStore(tmp_path).list_jobs()
    assert len(jobs) == 1
    assert jobs[0]["kind"] == "kronos_forecast"
    assert jobs[0]["status"] == "succeeded"
    assert jobs[0]["result_run_id"] == manifest["run_id"]


def test_failed_run_surfaces_the_cli_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=60)
    # no such symbol stored -> the CLI fails loud -> the tool raises with the CLI's message
    with pytest.raises(RuntimeError):
        server.backtest_run("NOPE", options=_OPTS)


def test_list_strategies_includes_the_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "ts_momentum" in server.list_strategies()


def test_all_expected_tools_are_registered() -> None:
    names = {t.name for t in anyio.run(server.mcp.list_tools)}
    assert {
        "data_pull",
        "backtest_run",
        "backtest_portfolio",
        "backtest_cross_sectional",
        "validate",
        "optim_grid",
        "propfirm_run",
        "forecast_run",
        "forecast_eval",
        "get_run",
        "list_runs",
        "list_strategies",
    } <= names
    assert {
        "create_strategy_project",
        "create_strategy_version",
        "create_experiment_spec",
        "link_project_run",
        "advance_stage_state",
        "advance_experiment_stage",
        "record_project_attempt",
        "seal_project_holdout",
        "list_projects",
        "get_project",
        "get_strategy_version",
        "get_experiment_spec",
        "get_agent_brief",
        "create_development_job",
        "list_development_jobs",
        "get_development_job",
        "search_evidence",
        "get_evidence",
        "draft_evidence",
        "review_evidence",
        "plan_development_suite",
        "launch_development_suite",
        "cancel_development_suite",
        "reconcile_development_jobs",
        "plan_ml_experiment",
        "launch_ml_experiment",
        "search_asset_evidence",
        "get_chart_bundle",
        "get_portfolio_analytics",
        "compare_runs",
    } <= names
    assert (
        not {
            "reveal_holdout",
            "place_order",
            "run_command",
            "run_python",
            "raw_sql",
            "read_file",
            "review_monte_carlo",
        }
        & names
    )


def test_control_plane_tools_round_trip_through_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    run_id = "0123456789abcdef"
    publish_decision_grade_run(
        tmp_path,
        run_id=run_id,
        manifest_fields={"outcomes": {"randomized_price_null": {"passed": False}}},
    )

    project = server.create_strategy_project(
        "AAPL reversal",
        "Large deviations revert after costs.",
        "Reject on non-positive locked OOS Sharpe.",
    )
    governed_project_id = project["project_id"]
    with pytest.raises(RuntimeError, match="research_contract_id"):
        server.create_strategy_version(
            governed_project_id,
            "mean_reversion",
            "git:must-not-bypass",
            {"signal": "zscore", "window": 20},
            {"window": [10, 20, 40]},
        )
    assert ControlStore(tmp_path).research_case_summary(governed_project_id)["phase"] == "triage"

    project = ControlStore(tmp_path).create_project(
        name="Grandfathered AAPL reversal",
        hypothesis="Large deviations revert after costs.",
        falsification_criterion="Reject on non-positive locked OOS Sharpe.",
        at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(ControlStore(tmp_path), project_id)
    version = server.create_strategy_version(
        project_id,
        "mean_reversion",
        "git:abc1234",
        {"signal": "zscore", "window": 20},
        {"window": [10, 20, 40]},
    )
    experiment = server.create_experiment_spec(
        project_id,
        version["version_id"],
        "snap-aapl",
        ["AAPL", "SPY"],
        {"train": 504, "test": 63, "embargo": 5},
        {"fee_bps": 1.0, "slippage_bps": 2.0},
        {"master": 7},
        {"null_families": ["bootstrap", "student_t", "garch"]},
    )
    sealed = server.seal_project_holdout(
        project_id,
        experiment["experiment_id"],
        "owner",
        "final period reserved before selection",
        "2026-04-01",
        "2026-06-30",
    )
    assert sealed["revealed_at"] is None
    assert sealed["holdout_spec_hash"] is not None
    assert sealed["start_date"] is None and sealed["end_date"] is None
    baseline = server.advance_experiment_stage(
        project_id,
        experiment["experiment_id"],
        "baseline",
        "queued",
        "owner approved resolved baseline spec",
    )
    assert baseline["state"] == "queued"
    assert baseline["state_history_truncated"] is False
    linked = server.link_project_run(
        project_id, experiment["experiment_id"], "oos", "queued", run_id
    )
    running = server.advance_stage_state(linked["link_id"], "running", "worker accepted")
    assert running["state"] == "running"
    attempt = server.record_project_attempt(
        project_id,
        experiment["experiment_id"],
        "robustness",
        "failed",
        "cfg:bootstrap:7",
        error="Tier-2 null threshold not cleared",
        details={"family": "bootstrap", "tier": 2},
    )
    assert attempt["status"] == "failed"
    assert server.list_projects(limit=1)["items"][0]["project_id"] == project_id
    shown_project = server.get_project(project_id)
    assert shown_project["current_version_id"] == version["version_id"]
    assert len(shown_project["stage_states"]) == 15
    assert (
        next(row for row in shown_project["stage_states"] if row["stage"] == "baseline")["state"]
        == "queued"
    )
    assert (
        server.get_strategy_version(project_id, version["version_id"])["source_fingerprint"]
        == "git:abc1234"
    )
    assert (
        server.get_experiment_spec(project_id, experiment["experiment_id"])["snapshot_id"]
        == "snap-aapl"
    )

    drafted = server.draft_evidence(
        claim="AAPL reversal needs more OOS support.",
        assets=["AAPL"],
        frozen_universe=["AAPL", "SPY"],
        method="walk_forward_oos",
        knowledge_at="2026-07-19T08:00:00Z",
        author="codex",
        source_run_id=run_id,
        source_artifact="manifest.json",
        source_field="outcomes.randomized_price_null",
        project_id=project_id,
        strategy_version_id=version["version_id"],
        experiment_id=experiment["experiment_id"],
    )
    assert drafted["status"] == "draft"
    assert drafted["author_kind"] == "agent"
    evidence = server.search_evidence(asset="AAPL", project_id=project_id)
    assert evidence["items"][0]["evidence_id"] == drafted["evidence_id"]
    reviewed = server.review_evidence(drafted["evidence_id"], "rejected", "codex")
    assert reviewed["revision"] == 2
    assert reviewed["author_kind"] == "agent"
    assert server.get_evidence(drafted["evidence_id"])["revisions_truncated"] is False

    brief = server.get_agent_brief(project_id, evidence_limit=10)
    assert brief["allowed_scope"]["snapshot_id"] == "snap-aapl"
    assert len(brief["stage_statuses"]) == 15
    assert (
        next(row for row in brief["stage_statuses"] if row["stage"] == "baseline")["run_id"] is None
    )
    assert "reveal_holdout" not in str(brief)

    job = server.create_development_job(
        "validation_suite",
        {"families": ["bootstrap", "student_t", "garch"]},
        project_id=project_id,
        experiment_id=experiment["experiment_id"],
    )
    assert job["status"] == "queued"
    assert server.list_development_jobs(limit=1)["items"][0]["job_id"] == job["job_id"]
    ControlStore(tmp_path).append_job_event(
        job["job_id"], event_type="log", payload={"message": "latest"}
    )
    journal = server.get_development_job(job["job_id"], event_limit=1)
    assert journal["events"][0]["payload"] == {"message": "latest"}
    assert journal["event_total"] == 2
    assert journal["event_tail"] is True
    assert journal["events_has_more"] is True
    prior = server.get_development_job(job["job_id"], event_limit=1, event_offset=1)
    assert prior["events"][0]["event_type"] == "created"
    assert prior["events_has_more"] is False
    baseline_plan = server.plan_development_suite(
        project_id, experiment["experiment_id"], "baseline"
    )
    assert baseline_plan["action"] == "baseline"
    assert baseline_plan["ready"] is False  # baseline was already queued above
    ml_plan = server.plan_ml_experiment(project_id, experiment["experiment_id"])
    assert ml_plan["action"] == "qlib"
    assert (
        server.search_asset_evidence("AAPL", project_id=project_id)["items"][0]["evidence_id"]
        == drafted["evidence_id"]
    )


def test_control_plane_tool_bounds_fail_before_cli() -> None:
    with pytest.raises(ValueError, match="limit"):
        server.list_runs(limit=501)
    with pytest.raises(ValueError, match="limit"):
        server.list_projects(limit=101)
    with pytest.raises(ValueError, match="lineage_limit"):
        server.get_project("8458c871-8c13-412d-8332-40e90b2041fd", lineage_limit=0)
    with pytest.raises(ValueError, match="counterevidence"):
        server.review_evidence(
            "74312554-5131-4b2e-8434-c80151573166",
            "rejected",
            "codex",
            counterevidence=[],
        )
    with pytest.raises(ValueError, match="owner-only"):
        server.launch_development_suite(
            "8458c871-8c13-412d-8332-40e90b2041fd",
            "ex_" + "a" * 64,
            "holdout_reveal",
        )
    with pytest.raises(ValueError, match="cannot grant corroborated"):
        server.review_evidence(
            "74312554-5131-4b2e-8434-c80151573166",
            "corroborated",
            "codex",
        )


def test_legacy_action_options_are_closed_per_tool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_subprocess(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("invalid MCP input reached the CLI subprocess")

    monkeypatch.setattr(_invoke, "run_alpha", unexpected_subprocess)
    calls: tuple[Callable[[], object], ...] = (
        lambda: server.backtest_run("SPY", options={"stride": "2"}),
        lambda: server.backtest_portfolio(["SPY", "QQQ"], options={"top-quantile": "0.2"}),
        lambda: server.backtest_cross_sectional(["SPY", "QQQ"], options={"account-type": "MARGIN"}),
        lambda: server.validate("SPY", options={"size-on-equity": ""}),
        lambda: server.optim_grid("SPY", {"lookback": [5.0]}, options={"tier1-paths": "10"}),
        lambda: server.forecast_run("SPY", options={"stride": "2"}),
        lambda: server.forecast_eval("SPY", options={"halt-drawdown": "0.1"}),
        lambda: server.propfirm_run(from_run="0" * 16, options={"as-of": "2026-01-01"}),
    )
    for call in calls:
        with pytest.raises(ValueError, match="unsupported"):
            call()


def test_legacy_action_inputs_are_counted_and_length_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_subprocess(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("invalid MCP input reached the CLI subprocess")

    monkeypatch.setattr(_invoke, "run_alpha", unexpected_subprocess)
    with pytest.raises(ValueError, match="32-option limit"):
        server.backtest_run("SPY", options={f"unknown-{index}": "1" for index in range(33)})
    with pytest.raises(ValueError, match="256 characters"):
        server.backtest_run("SPY", options={"as-of": "x" * 257})
    with pytest.raises(ValueError, match="duplicate normalized"):
        server.backtest_run("SPY", options={"fee-bps": "1", "fee_bps": "2"})
    with pytest.raises(ValueError, match="filesystem-like"):
        server.backtest_run("../SPY")
    with pytest.raises(ValueError, match="2..100"):
        server.backtest_portfolio([f"S{index}" for index in range(101)])
    with pytest.raises(ValueError, match="16-parameter limit"):
        server.backtest_run("SPY", params={f"param_{index}": "1" for index in range(17)})
    with pytest.raises(ValueError, match="4096-configuration"):
        server.optim_grid(
            "SPY",
            {
                "lookback": [float(value) for value in range(65)],
                "skip": [float(value) for value in range(65)],
            },
        )


def test_data_pull_dates_are_canonical_valid_and_ordered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_subprocess(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("invalid MCP input reached the CLI subprocess")

    monkeypatch.setattr(_invoke, "run_alpha", unexpected_subprocess)
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        server.data_pull("SPY", start="20260719")
    with pytest.raises(ValueError, match="valid YYYY-MM-DD"):
        server.data_pull("SPY", start="2026-02-30")
    with pytest.raises(ValueError, match="on or before"):
        server.data_pull("SPY", start="2026-07-20", end="2026-07-19")


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("model", "/tmp/Kronos", "managed repository id"),
        ("model", "../Kronos", "managed repository id"),
        ("model", "org/repo/weights", "managed repository id"),
        ("tokenizer", r"C:\\models\\tokenizer", "managed repository id"),
        ("model-revision", "refs/heads/main", "immutable revision"),
    ],
)
def test_forecast_actions_reject_path_like_model_inputs(
    key: str,
    value: str,
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_subprocess(*args: object, **kwargs: object) -> dict[str, object]:
        raise AssertionError("invalid MCP input reached the CLI subprocess")

    monkeypatch.setattr(_invoke, "run_alpha", unexpected_subprocess)
    for call in (server.forecast_run, server.forecast_eval):
        with pytest.raises(ValueError, match=message):
            call("SPY", options={key: value})


def test_forecast_action_preserves_safe_managed_identifier_compatibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(args: list[str], *, data_dir: Path, run_type: str | None) -> dict[str, object]:
        captured.update(args=args, data_dir=data_dir, run_type=run_type)
        return {"run_id": "0" * 16}

    monkeypatch.setattr(_invoke, "run_alpha", fake_run)
    result = server.forecast_run(
        "SPY",
        options={
            "model": "NeoQuasar/Kronos-small",
            "model_revision": "0123456789abcdef",
            "tokenizer": "NeoQuasar/Kronos-Tokenizer-base",
            "tokenizer_revision": "fedcba9876543210",
        },
    )
    assert result["run_id"] == "0" * 16
    assert captured["run_type"] == "forecast"
    assert captured["args"] == [
        "forecast",
        "run",
        "SPY",
        "--model",
        "NeoQuasar/Kronos-small",
        "--model-revision",
        "0123456789abcdef",
        "--tokenizer",
        "NeoQuasar/Kronos-Tokenizer-base",
        "--tokenizer-revision",
        "fedcba9876543210",
    ]


def test_v3_control_tools_publish_named_output_schemas() -> None:
    tools = {tool.name: tool for tool in anyio.run(server.mcp.list_tools)}
    typed_names = {
        "create_strategy_project",
        "create_strategy_version",
        "create_experiment_spec",
        "link_project_run",
        "advance_stage_state",
        "advance_experiment_stage",
        "record_project_attempt",
        "seal_project_holdout",
        "list_projects",
        "get_project",
        "get_strategy_version",
        "get_experiment_spec",
        "get_agent_brief",
        "create_development_job",
        "list_development_jobs",
        "get_development_job",
        "search_evidence",
        "get_evidence",
        "draft_evidence",
        "review_evidence",
        "plan_development_suite",
        "launch_development_suite",
        "cancel_development_suite",
        "reconcile_development_jobs",
        "plan_ml_experiment",
        "launch_ml_experiment",
        "search_asset_evidence",
        "get_chart_bundle",
        "get_portfolio_analytics",
        "compare_runs",
        "get_run",
        "list_runs",
    }
    for name in typed_names:
        schema = tools[name].outputSchema
        assert schema is not None
        assert schema.get("type") == "object"
        assert schema.get("properties"), name
        assert schema.get("additionalProperties") is not True
    holdout_required = tools["seal_project_holdout"].inputSchema.get("required")
    assert isinstance(holdout_required, list)
    assert {"start_date", "end_date"} <= set(holdout_required)


def test_chart_bundle_and_run_comparison_are_snapshot_locked_and_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=70)
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
    first = server.backtest_run("SPY", options={**_OPTS, "snapshot": "frozen"})
    second = server.backtest_run(
        "SPY", options={**_OPTS, "snapshot": "frozen", "rebalance-every": "3"}
    )

    bundle = server.get_chart_bundle(first["run_id"], limit=25, bar_limit=30)
    assert bundle["bars_status"] == "available"
    assert len(bundle["bars"]) == 30
    assert bundle["trace_status"] == "available"
    assert bundle["provenance"]["snapshot_id"] == "frozen"
    assert bundle["provenance"]["snapshot_hash"] == first["snapshot_hash"]
    assert bundle["truncated"]["bars"] is True

    comparison = server.compare_runs([first["run_id"], second["run_id"]])
    assert comparison["same_snapshot_hash"] is True
    assert [row["run_id"] for row in comparison["rows"]] == [
        first["run_id"],
        second["run_id"],
    ]
    assert all(
        metric["source_artifact"] == "manifest.json"
        for row in comparison["rows"]
        for metric in row["metrics"]
    )


def test_portfolio_analytics_tool_is_typed_bounded_and_cited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    seed_store(tmp_path, symbol="SPY", n=80, seed=0)
    seed_store(tmp_path, symbol="QQQ", n=80, seed=1)
    create_snapshot(
        ParquetStore(tmp_path / "store"),
        tmp_path / "snapshots",
        "portfolio-frozen",
        ["SPY", "QQQ"],
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    options = {
        **_OPTS,
        "train-size": "15",
        "test-size": "5",
        "embargo": "1",
        "snapshot": "portfolio-frozen",
    }
    manifest = server.backtest_portfolio(["SPY", "QQQ"], options=options)

    projection = server.get_portfolio_analytics(
        manifest["run_id"], timestamp_limit=7, symbol_limit=2
    )

    assert projection["symbols"] == ["QQQ", "SPY"]
    assert len(projection["correlations"]) == 4
    assert projection["bounds"]["allocation_timestamps"]["returned"] == 7
    assert projection["bounds"]["allocation_timestamps"]["truncated"] is True
    assert projection["provenance"]["snapshot_hash"] == manifest["snapshot_hash"]
    assert projection["provenance"]["association_label"] == "association, not causation"
    assert projection["provenance"]["artifact_sha256"]["correlations.parquet"]
    with pytest.raises(DataError, match="symbol_limit"):
        server.get_portfolio_analytics(manifest["run_id"], symbol_limit=101)
