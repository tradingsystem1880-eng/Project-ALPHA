"""Comparison cases bind optional evidence without rewriting historical v2 cases."""

import hashlib
import json
from pathlib import Path

import pytest

from alpha_cli.investigation_case import Case
from alpha_cli.research_suggestions import suggest_investigations
from alpha_core import DataError
from tests.unit.test_research_execution import run_fixture


def test_no_comparison_retains_exact_v2_identity(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    packet = suggest_investigations(run, cutoff="2020-01-02")
    case = Case.create(tmp_path / "case", run, "2020-01-02", "Why?", "gpt-6-astra")
    expected = {
        "schema_version": 2,
        "question": "Why?",
        "model": "gpt-6-astra",
        "run": str(run.resolve()),
        "cutoff": "2020-01-02",
        "basis_sha256": packet["basis_sha256"],
        "max_calls": 6,
        "request_limit": 12,
    }
    encoded = json.dumps(expected, sort_keys=True, separators=(",", ":"), allow_nan=False)
    assert case.context()["case_id"] == hashlib.sha256(encoded.encode()).hexdigest()
    assert case.verify() == packet
    assert "comparison_series" not in case.context()


def test_comparison_case_binds_and_reverifies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import investigation_case as module
    from alpha_cli.investigation_comparisons import ComparisonPlan

    plan = ComparisonPlan.model_validate_json(
        json.dumps(
            {
                "schema_version": 1,
                "series": [
                    {
                        "snapshot_id": "frozen",
                        "snapshot_sha256": "a" * 64,
                        "symbol": "SPY",
                        "role": "market",
                    }
                ],
            }
        )
    )
    evidence = {"policy_sha256": "b" * 64, "comparisons": [{"status": "blocked"}]}
    calls = []

    def compare(packet: object, supplied: object, data_dir: Path) -> dict[str, object]:
        calls.append((supplied, data_dir))
        result: dict[str, object] = json.loads(json.dumps(evidence))
        return result

    monkeypatch.setattr(module, "comparison_evidence", compare)
    run = run_fixture(tmp_path)
    case = Case.create(
        tmp_path / "case",
        run,
        "2020-01-02",
        "Why?",
        "gpt-6-astra",
        comparisons=plan,
        data_dir=tmp_path,
    )
    assert case.context()["comparison_series"] == [
        {"symbol": "SPY", "role": "market", "snapshot_id": "frozen"}
    ]
    case.call("inspect_execution")
    receipt = case.call("inspect_losses")
    assert receipt["result"]["comparisons"] == evidence
    count = len(calls)
    assert Case.open(case.path).call("inspect_losses") == receipt
    assert len(calls) > count
    assert calls[-1] == (plan, tmp_path.resolve())
    with pytest.raises(DataError, match="identity"):
        Case.create(case.path, run, "2020-01-02", "Why?", "gpt-6-astra")
    evidence["comparisons"] = [{"status": "available"}]
    with pytest.raises(DataError, match="evidence|policy"):
        Case.open(case.path).call("inspect_losses")


def test_data_root_without_plan_rejected(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    with pytest.raises(DataError, match="together"):
        Case.create(tmp_path / "case", run, "2020-01-02", "Why?", "gpt-6-astra", data_dir=tmp_path)


def test_cli_freezes_comparison_plan_before_model_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from alpha_cli import codex_investigation, investigation_case, research_diagnostic_cmds

    (tmp_path / "runs").mkdir()
    run_fixture(tmp_path / "runs")
    monkeypatch.setattr(
        research_diagnostic_cmds, "AlphaSettings", lambda: SimpleNamespace(data_dir=tmp_path)
    )
    monkeypatch.setattr(investigation_case, "comparison_evidence", lambda *_: {"status": "blocked"})
    launched = []

    async def launch(case: Case) -> dict[str, object]:
        launched.append(case)
        return {"status": "not_model_test"}

    monkeypatch.setattr(codex_investigation, "run_investigation", launch)
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "series": [
                    {
                        "snapshot_id": "frozen",
                        "snapshot_sha256": "a" * 64,
                        "symbol": "SPY",
                        "role": "market",
                    }
                ],
            }
        )
    )
    research_diagnostic_cmds.investigate(
        tmp_path / "case",
        run_id="1234567890abcdef",
        as_of="2020-01-02",
        question="Why?",
        comparisons=plan_path,
    )
    assert len(launched) == 1
    plan_path.unlink()
    assert launched[0].verify()["observations"]["comparisons"] == {"status": "blocked"}


def test_cli_rejects_resume_revision_and_malformed_plan_before_launch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import typer

    from alpha_cli import codex_investigation, research_diagnostic_cmds

    async def forbidden_launch(case: Case) -> dict[str, object]:
        pytest.fail("invalid inputs must fail before model dispatch")

    monkeypatch.setattr(codex_investigation, "run_investigation", forbidden_launch)
    plan = tmp_path / "plan.json"
    plan.write_text('{"schema_version":1,"series":[],"extra":true}')
    with pytest.raises(typer.BadParameter, match="Resume uses frozen"):
        research_diagnostic_cmds.investigate(tmp_path / "case", resume=True, comparisons=plan)
    with pytest.raises(typer.BadParameter):
        research_diagnostic_cmds.investigate(
            tmp_path / "case",
            run_id="1234567890abcdef",
            as_of="2020-01-02",
            question="Why?",
            comparisons=plan,
        )
    assert not (tmp_path / "case" / "case.sqlite3").exists()


def test_real_snapshot_comparison_through_mcp_cli_and_cached_tamper(tmp_path: Path) -> None:
    import asyncio

    import polars as pl

    from alpha_cli.artifact_contract import artifact_contract
    from alpha_mcp.investigation_server import build_server
    from tests.unit.test_investigation_comparisons import plan, snapshot

    snap = snapshot(tmp_path)
    run = run_fixture(tmp_path)
    equity_path = run / "equity_curve.parquet"
    pl.read_parquet(equity_path).with_columns(pl.Series("equity", [100.0, 80.0])).write_parquet(
        equity_path
    )
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["artifacts"] = artifact_contract(run)
    manifest_path.write_text(json.dumps(manifest))
    case = Case.create(
        tmp_path / "case",
        run,
        "2020-01-02",
        "Compare the loss",
        "gpt-6-astra",
        comparisons=plan(snap),
        data_dir=tmp_path,
    )
    server = build_server(case.path)

    async def exercise() -> None:
        await server.call_tool("inspect_execution", {})
        await server.call_tool("inspect_losses", {})

    asyncio.run(exercise())
    receipts = case.receipts()
    assert [receipt["status"] for receipt in receipts] == ["succeeded", "succeeded"]
    comparison = receipts[1]["result"]["comparisons"]
    series = comparison["series"][0]
    assert series["dataset"]["symbol"] == "SPY"
    assert series["dataset"]["currency"] == "USD"
    assert series["windows"][0]["price_change"] == pytest.approx(-0.2)
    assert series["windows"][0]["observed_rows"] == 2
    assert comparison["causal_attribution"] == "not_tested"
    assert Case.open(case.path).call("inspect_losses") == receipts[1]
    (snap / "bars" / "SPY.parquet").write_bytes(b"tampered")
    with pytest.raises(DataError, match="integrity"):
        Case.open(case.path).call("inspect_losses")


def test_cli_rejects_oversized_comparison_plan(tmp_path: Path) -> None:
    import typer

    from alpha_cli.research_diagnostic_cmds import investigate

    plan = tmp_path / "oversized.json"
    plan.write_bytes(b" " * (65536 + 1))
    with pytest.raises(typer.BadParameter, match="64 KiB"):
        investigate(
            tmp_path / "case",
            run_id="1234567890abcdef",
            as_of="2020-01-02",
            question="Why?",
            comparisons=plan,
        )
    assert not (tmp_path / "case").exists()
