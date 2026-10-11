"""A browser identity resolves only CLI-owned, source-verified investigation state."""

from pathlib import Path
from typing import Any

import pytest

from alpha_cli.investigation_workspace import create, eligibility, show
from alpha_cli.investigation_workspace_contracts import InvestigationCreate
from alpha_core import DataError
from tests.unit.test_comparison_acquisition import parent_case


def root_with_run(tmp_path: Path) -> Path:
    import shutil

    parent_case(tmp_path)
    root = tmp_path / "data"
    (root / "runs").mkdir(parents=True)
    shutil.copytree(tmp_path / "1234567890abcdef", root / "runs/1234567890abcdef")
    return root


def test_create_and_show_verify_source_and_derive_cutoff(tmp_path: Path) -> None:
    root = root_with_run(tmp_path)
    assert eligibility(root, "1234567890abcdef").eligible
    result = create(root, InvestigationCreate(run_id="1234567890abcdef", question="Why this loss?"))
    assert result.status == "ready"
    assert result.cutoff == "2020-01-03"
    assert result.turns_remaining == 4
    assert result.requests_remaining == 12
    assert result.authority == "none" and result.admitted is False
    assert show(root, result.id) == result
    (root / "runs/1234567890abcdef/equity_curve.parquet").write_bytes(b"changed")
    with pytest.raises(DataError):
        show(root, result.id)


@pytest.mark.parametrize("identifier", ["../outside", "/etc/passwd", "a" * 33, "A" * 32])
def test_opaque_identity_rejects_paths(tmp_path: Path, identifier: str) -> None:
    with pytest.raises(ValueError):
        show(tmp_path, identifier)


def test_run_retains_report_and_budget_in_durable_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from alpha_cli import investigation_workspace as workspace
    from alpha_cli.codex_session import Session
    from alpha_cli.investigation_case import Case
    from alpha_cli.investigation_report import verify_report
    from alpha_cli.investigation_workspace_contracts import InvestigationTurnRequest

    root = root_with_run(tmp_path)
    view = create(root, InvestigationCreate(run_id="1234567890abcdef", question="Why loss?"))

    def execute(case: Case, request: InvestigationTurnRequest, callback: object) -> dict[str, Any]:
        case.call("inspect_execution")
        case.call("inspect_losses")
        report = verify_report(
            case,
            json.dumps(
                {
                    "findings": [
                        {
                            "observation": "The fixture loses 40%.",
                            "receipt_ids": [case.receipts()[0]["id"]],
                        }
                    ],
                    "hypotheses": ["Market exposure may explain losses."],
                    "next_tests": ["Compare the market over the same period."],
                    "limitations": ["Synthetic fixture; no causal inference."],
                }
            ),
        )
        context = case.context()
        with Session(case.path, context["case_id"], context["model"]) as session:
            session.bind_thread("fixture")
            session.reserve_turn()
            session.start_turn("fixture-turn")
            session.finish_turn("completed", report=report)
        return report

    monkeypatch.setattr(workspace, "_execute", execute)
    result = workspace.run(root, view.id, InvestigationTurnRequest())
    assert result.status == "completed"
    assert result.report and result.report.hypotheses
    assert result.turns_remaining == 3
    assert result.requests_remaining == 10
    assert result.can_followup
    assert show(root, view.id) == result


def test_ambiguous_failed_turn_is_blocked_and_read_does_not_recreate_lock(tmp_path: Path) -> None:
    from alpha_cli import investigation_workspace as workspace
    from alpha_cli.codex_session import Session

    root = root_with_run(tmp_path)
    view = create(root, InvestigationCreate(run_id="1234567890abcdef", question="Why?"))
    directory = workspace._directory(root, view.id)
    with Session(directory, view.case_id, "gpt-6-astra") as session:
        session.reserve_turn(prompt={"followup": None})
    workspace._write(
        directory / "workspace-state.json", {"status": "failed", "error": "timeout", "progress": []}
    )
    result = show(root, view.id)
    assert result.status == "blocked" and not result.can_resume
    assert result.turns_remaining == 3
    (directory / "workspace.lock").unlink()
    with pytest.raises(OSError):
        show(root, view.id)
    assert not (directory / "workspace.lock").exists()


def test_interrupted_publication_does_not_break_saved_case_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli import investigation_workspace as workspace

    root = root_with_run(tmp_path)
    first = create(root, InvestigationCreate(run_id="1234567890abcdef", question="First"))

    def crash(*args: Any, **kwargs: Any) -> None:
        raise OSError("fixture crash")

    monkeypatch.setattr(workspace, "_register", crash)
    with pytest.raises(OSError, match="fixture crash"):
        create(root, InvestigationCreate(run_id="1234567890abcdef", question="Second"))
    assert [view.id for view in workspace.list_cases(root, first.run_id)] == [first.id]


def test_cli_show_returns_failed_state_successfully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from typer.testing import CliRunner

    from alpha_cli import investigation_workspace as workspace
    from alpha_cli.investigation_workspace_cmds import app

    root = root_with_run(tmp_path)
    view = create(root, InvestigationCreate(run_id="1234567890abcdef", question="Why?"))
    workspace._write(
        workspace._directory(root, view.id) / "workspace-state.json",
        {"status": "failed", "error": "A retained failure", "progress": []},
    )
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    response = CliRunner().invoke(app, ["show", view.id])
    assert response.exit_code == 0, response.output
    assert json.loads(response.stdout)["error"] == "A retained failure"


@pytest.mark.parametrize("cancelled", [True, False])
def test_worker_cancellation_distinguished_from_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cancelled: bool
) -> None:
    from alpha_cli import investigation_workspace as workspace
    from alpha_cli.investigation_lifecycle import InvestigationInterrupted
    from alpha_cli.investigation_workspace_contracts import InvestigationTurnRequest

    root = root_with_run(tmp_path)
    view = create(root, InvestigationCreate(run_id="1234567890abcdef", question="Why?"))

    def fail(*args: Any, **kwargs: Any) -> None:
        if cancelled:
            raise InvestigationInterrupted("Known interruption")
        raise RuntimeError("Known failure")

    monkeypatch.setattr(workspace, "_execute", fail)
    result = workspace.run(root, view.id, InvestigationTurnRequest())
    assert result.status == ("interrupted" if cancelled else "failed")
    assert result.turns_remaining == 4
