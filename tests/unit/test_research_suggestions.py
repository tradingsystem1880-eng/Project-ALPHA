"""A teammate proposes falsifiable investigations without inventing measurements or execution."""

import json
from pathlib import Path

import polars as pl
import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from alpha_cli.artifact_contract import artifact_contract
from alpha_cli.main import app
from alpha_cli.research_suggestions import suggest_investigations
from alpha_cli.research_workflow_contract import InvestigationProposal
from alpha_core import DataError
from tests.unit.test_research_execution import run_fixture


def test_proposals_remain_advisory_and_do_not_write(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    before = {p.name: p.read_bytes() for p in run.iterdir()}
    result = suggest_investigations(run, cutoff="2020-01-02")
    assert result["advisory_only"] and not result["admitted"]
    assert result["execution_status"] == "proposed"
    assert [s["id"] for s in result["suggestions"]][:2] == ["coverage", "rejected_requests"]
    assert result["executed_experiments"] == []
    assert {p.name: p.read_bytes() for p in run.iterdir()} == before
    assert result == suggest_investigations(run, cutoff="2020-01-02")


def test_loss_episode_invites_diagnosis_not_automatic_rejection(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    equity = pl.read_parquet(run / "equity_curve.parquet").with_columns(
        pl.Series("equity", [100.0, 40.0])
    )
    equity.write_parquet(run / "equity_curve.parquet")
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["artifacts"] = artifact_contract(run)
    (run / "manifest.json").write_text(json.dumps(manifest))
    result = suggest_investigations(run, cutoff="2020-01-02")
    episode = result["observations"]["drawdown_episodes"][0]
    assert episode["depth"] == pytest.approx(-0.6)
    assert episode["peak_to_trough_intervals"] == 1
    proposal = next(s for s in result["suggestions"] if s["id"] == "loss_episode")
    assert "benchmark" in proposal["test"]
    assert "causal" in proposal["stop_condition"]
    assert result["strategy_disposition"] == "not_assessed"
    assert result["observations"]["regime_effect"] == "not_tested"


def test_corrupt_or_wrong_cutoff_evidence_is_not_advice(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    with pytest.raises(DataError, match="cutoff"):
        suggest_investigations(run, cutoff="2020-01-01")
    (run / "fills.parquet").write_bytes(b"corrupt")
    with pytest.raises((DataError, ValueError)):
        suggest_investigations(run, cutoff="2020-01-02")


def test_novel_proposal_is_bound_to_current_brief(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    initial = suggest_investigations(run, cutoff="2020-01-02")
    proposal = InvestigationProposal(
        question="Could funding payments explain the difference?",
        rationale="The recorded cost configuration may not capture venue funding.",
        competing_explanation="Price exposure or missing position accounting.",
        test="Reconcile funding cash flows against the same holding intervals.",
        data_needed=("Timestamped funding and positions",),
        decision_value="Would distinguish carry costs from price losses.",
        stop_condition="Stop if funding data or instrument eligibility cannot be verified.",
        evidence_pointers=("/observations/execution/configuration",),
    )
    result = suggest_investigations(
        run, cutoff="2020-01-02", proposals=(proposal,), basis_sha256=initial["basis_sha256"]
    )
    assert result["suggestions"][-1]["origin"] == "external_proposal"
    assert result["suggestions"][-1]["claim_verification"] == "binding_only"
    with pytest.raises(DataError, match="basis"):
        suggest_investigations(
            run, cutoff="2020-01-02", proposals=(proposal,), basis_sha256="0" * 64
        )
    bad = proposal.model_copy(update={"evidence_pointers": ("/observations/invented",)})
    with pytest.raises(DataError, match="pointer"):
        suggest_investigations(
            run, cutoff="2020-01-02", proposals=(bad,), basis_sha256=initial["basis_sha256"]
        )


def test_proposals_cannot_claim_execution_or_supply_commands() -> None:
    with pytest.raises(ValidationError):
        InvestigationProposal.model_validate({"execution_status": "executed", "argv": ["alpha"]})


def test_cli_suggest_is_read_only_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    run_fixture(runs)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(
        app, ["research", "diagnostic", "suggest", "1234567890abcdef", "--as-of", "2020-01-02"]
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["advisory_only"]


@pytest.mark.parametrize(
    "pointer",
    [
        "/observations/drawdown_episodes/-1",
        "/observations/~2",
        "/observations/drawdown_episodes/01",
    ],
)
def test_invalid_external_pointers_fail(tmp_path: Path, pointer: str) -> None:
    from alpha_cli.research_suggestions import _resolve

    with pytest.raises(DataError, match="pointer"):
        _resolve({"drawdown_episodes": [1]}, pointer)


def test_normal_activity_proposes_transfer_without_claiming_edge(tmp_path: Path) -> None:
    run = run_fixture(tmp_path)
    trades = pl.read_parquet(run / "trades.parquet")
    dates = pl.read_parquet(run / "equity_curve.parquet")["ts"].to_list()
    pl.DataFrame(
        {"instrument_id": ["TEST.SIM"], "entry_ts": [dates[0]], "exit_ts": [dates[-1]]},
        schema=trades.schema,
    ).write_parquet(run / "trades.parquet")
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["n_trades"] = 1
    manifest["artifacts"] = artifact_contract(run)
    (run / "manifest.json").write_text(json.dumps(manifest))
    result = suggest_investigations(run, cutoff="2020-01-02")
    assert "robustness" in [s["id"] for s in result["suggestions"]]
    assert "activity" not in [s["id"] for s in result["suggestions"]]
    assert result["observations"]["drawdown_episodes"] == []
    assert result["observations"]["macro_cause"] == "not_tested"


def test_cli_rejects_invalid_id_and_oversized_proposals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    assert (
        runner.invoke(
            app, ["research", "diagnostic", "suggest", "../elsewhere", "--as-of", "2020-01-02"]
        ).exit_code
        != 0
    )
    large = tmp_path / "large.json"
    large.write_text(" " * 65_537)
    result = runner.invoke(
        app,
        [
            "research",
            "diagnostic",
            "suggest",
            "1234567890abcdef",
            "--as-of",
            "2020-01-02",
            "--proposals",
            str(large),
        ],
    )
    assert result.exit_code != 0
    assert "64 KiB" in result.output
