"""CLI recovery, bounded progress, and explicit comparison handoff contracts."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli import comparison_acquisition, comparison_acquisition_worker
from alpha_cli import investigation_workspace as workspace
from alpha_cli.investigation_case import Case
from alpha_cli.investigation_workspace_cmds import app
from alpha_cli.investigation_workspace_contracts import InvestigationTurnRequest
from tests.unit.test_comparison_acquisition import fixture_dispatch, provider_result
from tests.unit.test_investigation_workspace import root_with_run


def test_cli_failure_progress_and_explicit_child_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = root_with_run(tmp_path)
    monkeypatch.setenv("ALPHA_DATA_DIR", str(root))
    runner = CliRunner()

    def invoke(args: list[str], code: int = 0) -> Any:
        result = runner.invoke(app, args)
        assert result.exit_code == code, result.output
        return json.loads(result.stdout)

    assert invoke(["eligibility", "1234567890abcdef"])["eligible"]
    assert invoke(["list", "--run-id", "1234567890abcdef"]) == []
    created = invoke(
        ["create", "--request", json.dumps({"run_id": "1234567890abcdef", "question": "Why?"})]
    )
    identifier = created["id"]

    def execute(
        case: Case,
        request: InvestigationTurnRequest,
        progress: Callable[[dict[str, Any]], None],
    ) -> dict[str, Any]:
        progress({"method": "raw/model/text", "params": {"item": {"text": "PRIVATE MODEL TEXT"}}})
        case.call("inspect_execution")
        case.call("inspect_losses")
        for _ in range(20):
            for method in ("item/started", "item/completed"):
                progress(
                    {
                        "method": method,
                        "params": {"item": {"type": "mcpToolCall", "tool": "inspect_losses"}},
                    }
                )
        raise RuntimeError("Model transport disconnected")

    monkeypatch.setattr(workspace, "_execute", execute)
    failed = invoke(["run", identifier], code=1)
    assert failed["status"] == "failed" and failed["can_resume"]
    assert failed["error"] == "Model transport disconnected"
    assert len(failed["progress"]) == 32
    assert {entry["stage"] for entry in failed["progress"]} == {"tool_started", "tool_completed"}
    assert "PRIVATE MODEL TEXT" not in json.dumps(failed)
    assert invoke(["show", identifier]) == failed
    assert invoke(["list", "--run-id", "1234567890abcdef"])[0]["id"] == identifier

    preview = invoke(
        [
            "draft",
            identifier,
            "--request",
            json.dumps({"series": [{"symbol": "SPY", "asset_class": "etf", "role": "market"}]}),
        ]
    )
    monkeypatch.setenv("ALPHA_TIINGO_API_KEY", "fixture")
    monkeypatch.setattr(comparison_acquisition_worker, "_fetch", provider_result)
    monkeypatch.setattr(comparison_acquisition, "_dispatch", fixture_dispatch)
    # An older retained model failure does not disappear on successful comparison acquisition.
    acquired = invoke(
        ["acquire", identifier, "--request", json.dumps({"plan_sha256": preview["plan_sha256"]})]
    )
    assert acquired["acquisition_status"] == "succeeded"
    child = invoke(["show", acquired["comparison_child_id"]])
    assert child["parent_id"] == identifier and child["authority"] == "none"
    assert child["turns_remaining"] == 4
    assert acquired["requests_remaining"] == failed["requests_remaining"]


@pytest.mark.parametrize("payload", ["{" + "x" * 65536, '{"unexpected":true}', "[]"])
def test_cli_rejects_invalid_requests_without_creating_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: str
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    result = CliRunner().invoke(app, ["create", "--request", payload])
    assert result.exit_code == 1 and "Error:" in result.output
    assert not (tmp_path / "investigations").exists()
