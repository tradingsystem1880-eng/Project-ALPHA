"""Assistant failure boundaries without model calls, network access, or owner-state writes."""

from __future__ import annotations

import io
import json
import signal
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli import assistant_cmds, assistant_runtime, assistant_worker
from alpha_cli.assistant_contracts import AssistantContext, AssistantTurnRequest
from alpha_cli.assistant_service import validate_answer
from alpha_core import DataError


@pytest.mark.parametrize("command", ["create", "show", "check", "turn"])
def test_cli_errors_are_plain_bounded_failures(
    command: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        if command == "show":
            raise ValueError("Verified context unavailable")
        raise DataError("Verified context unavailable")

    target = {"create": "create_session", "show": "get_session", "turn": "run_turn"}
    if command == "check":
        monkeypatch.setattr("alpha_cli.assistant_service.check_session", denied)
    else:
        monkeypatch.setattr(assistant_cmds, target[command], denied)
    args = [command]
    if command == "create":
        args += ["--context", json.dumps({"symbol": "SPY", "as_of": "2020-01-01T00:00:00Z"})]
    else:
        args += ["test-session"]
    if command == "turn":
        args += ["--request", json.dumps({"action": "explain_chart"})]
    result = CliRunner().invoke(assistant_cmds.assistant_app, [*args, "--json"])
    assert result.exit_code != 0
    assert "Verified context unavailable" in result.output
    assert "Traceback" not in result.output


def test_cli_roundtrip_and_turn_failure_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    session: dict[str, Any] = {"session_id": "session", "turns": [{"status": "completed"}]}
    monkeypatch.setattr(assistant_cmds, "create_session", lambda *args: session)
    monkeypatch.setattr(assistant_cmds, "get_session", lambda *args: session)
    monkeypatch.setattr(assistant_cmds, "run_turn", lambda *args: session)
    monkeypatch.setattr("alpha_cli.assistant_service.check_session", lambda *args: {"valid": True})
    monkeypatch.setattr(assistant_cmds, "check_readiness", lambda: {"available": False})
    calls = [
        ["create", "--context", '{"symbol":"SPY","as_of":"2020-01-01T00:00:00Z"}'],
        ["show", "session"],
        ["check", "session"],
        ["readiness"],
        ["turn", "session", "--request", '{"action":"explain_chart"}'],
    ]
    for args in calls:
        result = runner.invoke(assistant_cmds.assistant_app, [*args, "--json"])
        assert result.exit_code == 0, result.output
        assert isinstance(json.loads(result.stdout), dict)
    session["turns"][0]["status"] = "failed"
    result = runner.invoke(assistant_cmds.assistant_app, calls[-1])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["turns"][0]["status"] == "failed"
    invalid = runner.invoke(assistant_cmds.assistant_app, ["create", "--context", "{}"])
    assert invalid.exit_code != 0 and "symbol" in invalid.output


@pytest.mark.parametrize("failure", ["isolation", "auth", "timeout", "missing", None])
def test_readiness_fails_closed_without_inference(
    failure: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def probe(work: Path) -> None:
        if failure == "isolation":
            raise RuntimeError("Boundary unavailable")

    def run(*args: object, **kwargs: object) -> SimpleNamespace:
        calls.append(args[0])
        if failure == "timeout":
            raise subprocess.TimeoutExpired("codex", 15)
        if failure == "missing":
            raise FileNotFoundError("codex missing")
        return SimpleNamespace(returncode=1 if failure == "auth" else 0)

    monkeypatch.setattr(assistant_runtime, "preflight", probe)
    monkeypatch.setattr("alpha_cli.assistant_runtime.subprocess.run", run)
    result = assistant_runtime.readiness()
    assert result["available"] == (failure is None)
    assert result["isolation_verified"] == (failure is None)
    assert result["reason"] is None if failure is None else isinstance(result["reason"], str)
    assert all(command == ["codex", "login", "status"] for command in calls)


@pytest.mark.parametrize("available,enforced", [(False, False), (True, False), (True, True)])
def test_preflight_requires_actual_enforcement_result(
    available: bool, enforced: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    commands: list[list[str]] = []
    monkeypatch.setattr(
        "alpha_cli.assistant_runtime.shutil.which", lambda _: "/bin/codex" if available else None
    )

    def run(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append(command)
        assert "sandbox" in command and "alpha_assistant" in command
        assert "permissions.alpha_assistant.network.enabled=false" in command
        return SimpleNamespace(
            returncode=0 if enforced else 1, stdout="isolation verified" if enforced else ""
        )

    monkeypatch.setattr("alpha_cli.assistant_runtime.subprocess.run", run)
    if available and enforced:
        assistant_runtime.preflight(work)
    else:
        with pytest.raises(RuntimeError, match="unavailable"):
            assistant_runtime.preflight(work)
    assert bool(commands) is available


@pytest.mark.parametrize(
    "outcome", ["success", "cancel", "missing", "nonzero", "oversize", "malformed"]
)
def test_runtime_output_and_cancellation_boundary(
    outcome: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assistant_runtime, "preflight", lambda _: None)
    killed: list[int] = []
    waited: list[bool] = []
    monkeypatch.setattr(
        "alpha_cli.assistant_runtime.os.killpg", lambda pid, sig: killed.append(pid)
    )
    old_signal = signal.getsignal(signal.SIGTERM)

    class Process:
        pid = 12345
        returncode = 1 if outcome == "nonzero" else 0

        def __init__(self, work: Path) -> None:
            self.work = work

        def communicate(self, prompt: str, **kwargs: object) -> tuple[str, str]:
            assert "no tools or execution authority" in prompt
            if outcome == "cancel":
                callback = signal.getsignal(signal.SIGTERM)
                assert callable(callback)
                callback(signal.SIGTERM, None)
            output = self.work / "answer.json"
            if outcome == "oversize":
                output.write_text("x" * 100001)
            elif outcome == "malformed":
                output.write_text("not json")
            elif outcome != "missing":
                output.write_text(
                    json.dumps(
                        {"text": "proposal", "citations": ["chart"], "rule_draft": '{"version":1}'}
                    )
                )
            return "", "do not expose this stderr"

        def poll(self) -> int | None:
            return None if outcome == "cancel" else self.returncode

        def wait(self) -> int:
            waited.append(True)
            return self.returncode

    def start(command: list[str], **kwargs: Any) -> Process:
        assert "alpha_cli.assistant_worker" in command
        assert kwargs["pass_fds"] == (77,)
        assert kwargs["start_new_session"] is True
        assert set(kwargs["env"]) <= {"HOME", "PATH", "CODEX_HOME", "TMPDIR", "LANG", "LC_ALL"}
        return Process(kwargs["cwd"])

    monkeypatch.setattr("alpha_cli.assistant_runtime.subprocess.Popen", start)
    request = AssistantTurnRequest(action="draft_rules")
    if outcome == "success":
        result = assistant_runtime.infer(request, [], [], lock_fd=77)
        assert result["rule_draft"] == {"version": 1}
    elif outcome == "cancel":
        with pytest.raises(KeyboardInterrupt):
            assistant_runtime.infer(request, [], [], lock_fd=77)
        assert killed == [12345, 12345]
    else:
        with pytest.raises((RuntimeError, ValueError)) as error:
            assistant_runtime.infer(request, [], [], lock_fd=77)
        assert "do not expose this stderr" not in str(error.value)
    assert waited == [True]
    assert signal.getsignal(signal.SIGTERM) == old_signal


@pytest.mark.parametrize("outcome", ["normal", "parent_missing", "parent_died", "deadline"])
def test_watchdog_trusted_process_lifecycle(
    outcome: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        "alpha_cli.assistant_worker.sys.argv", ["worker", "123", "5", "trusted-codex"]
    )
    monkeypatch.setattr("alpha_cli.assistant_worker.sys.stdin", io.StringIO("bounded prompt"))
    pids = iter(
        [0] if outcome == "parent_missing" else [123, 0 if outcome == "parent_died" else 123]
    )
    monkeypatch.setattr("alpha_cli.assistant_worker.os.getppid", lambda: next(pids))
    clocks = iter([0.0, 6.0])
    monkeypatch.setattr("alpha_cli.assistant_worker.time.monotonic", lambda: next(clocks))
    monkeypatch.setattr("alpha_cli.assistant_worker.os.getpgrp", lambda: 999)
    killed: list[int] = []

    def kill(group: int, sig: int) -> None:
        killed.append(group)
        assert sig == signal.SIGKILL
        raise SystemExit(137)

    monkeypatch.setattr("alpha_cli.assistant_worker.os.killpg", kill)

    class Process:
        returncode = 0

        def communicate(self, prompt: str, timeout: float) -> tuple[str, str]:
            assert prompt == "bounded prompt"
            if outcome == "normal":
                return "answer", "diagnostic"
            raise subprocess.TimeoutExpired("codex", timeout)

    monkeypatch.setattr(
        "alpha_cli.assistant_worker.subprocess.Popen", lambda *args, **kwargs: Process()
    )
    with pytest.raises(SystemExit) as exited:
        assistant_worker.main()
    assert exited.value.code == (
        0 if outcome == "normal" else 125 if outcome == "parent_missing" else 137
    )
    if outcome == "normal":
        captured = capsys.readouterr()
        assert captured.out == "answer" and captured.err == "diagnostic"
    assert bool(killed) == (outcome in {"parent_died", "deadline"})


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"text": "", "citations": [], "rule_draft": None},
        {"text": "a", "citations": ["fiction"], "rule_draft": None},
    ],
)
def test_invalid_answer_contracts_rejected(raw: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        validate_answer(raw, {"chart"})


def test_context_daily_cutoff_and_incompatible_sources() -> None:
    context = AssistantContext(symbol="SPY", as_of="2020-01-01T23:59:59Z", rules_name="example")
    assert context.as_of.microsecond == 999999
    for payload in [
        {"as_of": "2020-01-01"},
        {"as_of": "2020-01-01T12:00:00Z", "rules_name": "example"},
        {"snapshot_id": "snapshot", "manifest_id": "archive"},
        {"run_id": "run", "manifest_id": "archive"},
        {"manifest_id": "archive", "rules_name": "example"},
    ]:
        with pytest.raises(ValueError):
            AssistantContext.model_validate(
                {"symbol": "SPY", "as_of": "2020-01-01T23:59:59Z", **payload}
            )


def test_oversized_prompt_is_rejected_before_starting_codex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(_: Path) -> None:
        raise AssertionError("oversized prompt must fail before probing or launching Codex")

    monkeypatch.setattr(assistant_runtime, "preflight", forbidden)
    with pytest.raises(ValueError, match="150 KB"):
        assistant_runtime.infer(
            AssistantTurnRequest(action="explain_chart"), [{"data": "x" * 160000}], []
        )


def test_assistant_turn_api_is_closed_cli_job_and_reports_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from alpha_web.api.assistant import router

    monkeypatch.setenv("ALPHA_WEB_PORT", "8801")
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, base_url="http://localhost:8801")
    headers = {"origin": "http://localhost:8801", "sec-fetch-site": "same-origin"}
    monkeypatch.setattr(
        "alpha_web.api.assistant._assistant.show", lambda *args, **kwargs: {"session_id": "s"}
    )
    jobs: dict[str, object] = {}
    monkeypatch.setattr("alpha_web.api.assistant._invoke.JOBS", jobs)
    launched: list[list[str]] = []

    def launch(args: list[str], **kwargs: object) -> SimpleNamespace:
        launched.append(args)
        assert kwargs["run_type"] is None
        return SimpleNamespace(job_id="job", status="running", session_id=None)

    monkeypatch.setattr("alpha_web.api.assistant._invoke.launch", launch)
    body = {"action": "explain_chart", "message": "literal text; not shell $(command)"}
    response = client.post("/api/assistant/sessions/s/turns", headers=headers, json=body)
    assert response.status_code == 200, response.text
    assert response.json()["job_id"] == "job"
    assert launched[0][:4] == ["assistant", "turn", "s", "--request"]
    assert json.loads(launched[0][4]) == body
    jobs["other"] = SimpleNamespace(
        args=["assistant", "turn", "other"], status="running", job_id="other"
    )
    response = client.post("/api/assistant/sessions/s/turns", headers=headers, json=body)
    assert response.status_code == 409 and len(launched) == 1

    def missing(*args: object, **kwargs: object) -> None:
        raise RuntimeError("Unknown assistant session")

    monkeypatch.setattr("alpha_web.api.assistant._assistant.show", missing)
    assert client.get("/api/assistant/sessions/missing").status_code == 404
    monkeypatch.setattr("alpha_web.api.assistant._assistant.create", missing)
    response = client.post(
        "/api/assistant/sessions",
        headers=headers,
        json={"context": {"symbol": "SPY", "as_of": "2020-01-01T00:00:00Z"}},
    )
    assert response.status_code == 422


def test_verified_run_unknown_cutoff_and_snapshot_drift_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import UTC, datetime

    import polars as pl

    from alpha_cli.artifact_contract import artifact_contract
    from alpha_cli.assistant_context import assemble_context

    run_id = "c" * 16
    directory = tmp_path / "runs" / run_id
    directory.mkdir(parents=True)
    manifest = {
        "schema_version": 3,
        "run_identity_version": 3,
        "artifact_contract_version": 3,
        "run_id": run_id,
        "symbol": "SPY",
        "snapshot_id": "frozen",
        "snapshot_hash": "a" * 64,
        "execution_fingerprint": "a" * 64,
        "source_fingerprint": "a" * 64,
        "strategy_fingerprint": None,
        "artifacts": {},
    }
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest))
    context = AssistantContext(symbol="SPY", run_id=run_id, as_of="2020-02-01T00:00:00Z")
    with pytest.raises(ValueError, match="cutoff is unavailable"):
        assemble_context(context, tmp_path)
    pl.DataFrame({"ts": [datetime(2020, 1, 1, tzinfo=UTC)], "equity": [100.0]}).write_parquet(
        directory / "equity_curve.parquet"
    )
    manifest["artifacts"] = artifact_contract(directory)
    path.write_text(json.dumps(manifest))
    monkeypatch.setattr("alpha_cli._runner.verified_snapshot_hash", lambda *args: "b" * 64)
    with pytest.raises(ValueError, match="snapshot identity changed"):
        assemble_context(context, tmp_path)
    with pytest.raises(ValueError, match="snapshot does not match"):
        assemble_context(context.model_copy(update={"snapshot_id": "different"}), tmp_path)
    with pytest.raises(ValueError, match="symbol does not match"):
        assemble_context(context.model_copy(update={"symbol": "QQQ"}), tmp_path)
