from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_eval.investigation_cases import export_panel, synthetic_panel
from alpha_eval.investigation_demo import run_case


def test_export_excludes_future_and_preserves_parent_lineage(tmp_path: Path) -> None:
    panel = synthetic_panel("conditional")
    cutoff = panel["rows"][300]["ts"]
    first = export_panel(panel, tmp_path / "a", cutoff)
    panel["rows"][400]["equity"] *= 20
    second = export_panel(panel, tmp_path / "b", cutoff)
    assert (tmp_path / "a/panel.json").read_bytes() == (tmp_path / "b/panel.json").read_bytes()
    assert first["parent_sha256"] != second["parent_sha256"]
    assert first["panel_sha256"] == second["panel_sha256"]
    assert len(json.loads((tmp_path / "a/panel.json").read_text())["rows"]) == 301
    with pytest.raises(FileExistsError):
        export_panel(panel, tmp_path / "a", cutoff)


def test_export_has_no_truth_or_case_label(tmp_path: Path) -> None:
    export_panel(synthetic_panel("indicator_null"), tmp_path / "input", "2020-12-31")
    assert sorted(p.name for p in (tmp_path / "input").iterdir()) == ["manifest.json", "panel.json"]
    assert "indicator_null" not in (tmp_path / "input/panel.json").read_text()
    assert "parent_sha256" not in (tmp_path / "input/manifest.json").read_text()


def decision(action: str) -> dict:
    return dict(
        action=action,
        reason="Investigate the evidence.",
        conclusion="Descriptive only.",
        next_tests=["Use prospective observations."],
        evidence_ids=["attempt-1"] if action == "final" else [],
    )


def test_broker_debits_denials_and_reserves_final(tmp_path: Path) -> None:
    actions = iter(
        [
            "conditional_diagnostic",
            "inspect_run",
            "conditional_diagnostic",
            "conditional_diagnostic",
            "final",
        ]
    )
    measured = []

    def measure(action: str) -> dict:
        measured.append(action)
        return dict(integrity_ok=True)

    result = run_case(
        tmp_path / "trial",
        lambda prompt, path, seconds: {**decision(next(actions)), "evidence_ids": ["attempt-2"]},
        measure,
    )
    assert measured == ["inspect_run"]  # denied conditional request spent its one attempt
    assert len(result["attempts"]) == 4
    assert result["status"] == "completed"
    assert (tmp_path / "trial/attempt-1.json").exists()
    with pytest.raises(FileExistsError):
        run_case(tmp_path / "trial", lambda *args: decision("final"), measure)


def test_broker_stops_interpretation_after_integrity_failure(tmp_path: Path) -> None:
    actions = iter(["inspect_run", "loss_episodes", "final"])
    measured = []

    def measure(action: str) -> dict:
        measured.append(action)
        return dict(integrity_ok=False)

    result = run_case(tmp_path / "trial", lambda *args: decision(next(actions)), measure)
    assert measured == ["inspect_run"]
    assert result["attempts"][1]["status"] == "denied"
    assert result["integrity_ok"] is False


def test_model_failure_retains_reserved_attempt(tmp_path: Path) -> None:
    def fail(*args):
        raise RuntimeError("provider unavailable")

    result = run_case(tmp_path / "trial", fail, lambda _: {})
    assert result["status"] == "incomplete"
    assert (tmp_path / "trial/turn-1.json").exists()
    assert result["model_calls"] == 1


def test_fifth_action_never_executes_or_creates_fifth_attempt(tmp_path: Path) -> None:
    measured = []

    def measure(action: str) -> dict:
        measured.append(action)
        return dict(integrity_ok=True)

    actions = iter(
        [
            "inspect_run",
            "loss_episodes",
            "historical_context",
            "conditional_diagnostic",
            "loss_episodes",
        ]
    )
    result = run_case(tmp_path / "trial", lambda *args: decision(next(actions)), measure)
    assert len(measured) == 4
    assert len(result["attempts"]) == 4
    assert result["status"] == "incomplete"
    assert result["model_calls"] == 5
    assert not (tmp_path / "trial/attempt-5.json").exists()


def test_malformed_proposal_cannot_supply_paths_or_shell(tmp_path: Path) -> None:
    result = run_case(
        tmp_path / "trial",
        lambda *args: dict(**decision("inspect_run"), path="/private/owner", argv=["sh"]),
        lambda _: pytest.fail("must not execute"),
    )
    assert result["status"] == "incomplete"
    assert result["model_calls"] == 1
    assert result["attempts"] == []


def test_worker_environment_does_not_inherit_credentials(tmp_path: Path, monkeypatch) -> None:
    from alpha_eval.investigation_isolation import worker_env

    monkeypatch.setenv("UNRELATED_SECRET_TOKEN", "synthetic-secret")
    assert "UNRELATED_SECRET_TOKEN" not in worker_env(tmp_path)
    assert worker_env(tmp_path)["HOME"] == str(tmp_path)


def test_codex_has_no_general_tools_or_host_config(tmp_path: Path) -> None:
    from alpha_eval.investigation_codex import model_argv

    argv = model_argv(tmp_path, tmp_path / "schema", tmp_path / "result", "gpt-6-astra", "question")
    assert "--ignore-user-config" in argv and "--ignore-rules" in argv
    assert argv[argv.index("--disable") + 1] == "shell_tool"
    assert 'shell_environment_policy.inherit="none"' in argv
    assert "permissions.investigation.network.enabled=false" in argv
    assert not any("mcp_servers" in item for item in argv)
    assert "project_doc_max_bytes=0" in argv


@pytest.mark.parametrize(
    "conclusion,evidence", [("", ["attempt-1"]), ("Claim", []), ("Claim", ["invented"])]
)
def test_final_needs_substantive_bound_inspection(tmp_path: Path, conclusion, evidence) -> None:
    actions = iter(
        [
            decision("inspect_run"),
            {**decision("final"), "conclusion": conclusion, "evidence_ids": evidence},
        ]
    )
    result = run_case(
        tmp_path / "trial", lambda *args: next(actions), lambda _: dict(integrity_ok=True)
    )
    assert result["status"] == "incomplete"
    assert result["final"] is None


def test_worker_failure_is_reserved_before_execution_and_cannot_retry(tmp_path: Path) -> None:
    actions = iter(["inspect_run", "inspect_run", "final"])
    calls = []

    def measure(action):
        assert (tmp_path / "trial/attempt-1.json").is_file()
        calls.append(action)
        raise RuntimeError("measurement failed")

    result = run_case(tmp_path / "trial", lambda *args: decision(next(actions)), measure)
    assert calls == ["inspect_run"]
    assert [a["status"] for a in result["attempts"]] == ["failed", "denied"]
    assert result["status"] == "incomplete"


def test_unexpected_model_tool_event_invalidates_transport(tmp_path: Path, monkeypatch) -> None:
    from alpha_eval import investigation_codex as transport

    proposer = transport.CodexProposer.__new__(transport.CodexProposer)
    proposer.workspace = tmp_path
    proposer.model = "gpt-6-astra"
    proposer.version = "synthetic-client"

    def stream(argv, cwd, env, seconds, raw, consume):
        event = json.dumps(dict(type="item.started", item=dict(type="command_execution")))
        raw.write(event)
        assert consume(event) is False
        return dict(stop="tool_call_cap", returncode=-15, stderr_tail="")

    monkeypatch.setattr(transport, "stream_process", stream)
    with pytest.raises(RuntimeError, match="unexpected tool"):
        proposer("test", tmp_path / "call", 1)
    assert json.loads((tmp_path / "call.transport.json").read_text())["unexpected_or_failed_event"]


def test_report_keeps_all_table_rows_before_case_details() -> None:
    from alpha_eval.investigation_runner import render_report

    cases = [
        dict(
            case=name,
            calibration={"inspect_run": {"integrity_ok": True}},
            model_run=dict(status="completed", receipts=[], final=decision("final")),
        )
        for name in ("a", "b", "c")
    ]
    rendered = render_report(dict(cases=cases, inference="Synthetic only."))
    assert rendered.index("| c |") < rendered.index("## a")
