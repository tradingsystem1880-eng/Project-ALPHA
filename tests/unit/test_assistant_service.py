"""Advisory assistant boundaries and persisted sessions."""

from pathlib import Path
from typing import TextIO

import pytest
from pydantic import ValidationError

from alpha_cli.assistant_contracts import AssistantContext, AssistantTurnRequest
from alpha_cli.assistant_service import create_session, get_session, validate_answer


def test_context_rejects_browser_facts_and_missing_cutoff() -> None:
    with pytest.raises(ValidationError):
        AssistantContext.model_validate({"symbol": "BTC/USD", "bars": []})
    with pytest.raises(ValidationError):
        AssistantTurnRequest(action="execute_order", message="buy")


def test_session_and_citations_are_bound_to_resolved_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Verified chart", "data": {"bars": []}}],
    )
    context = AssistantContext(symbol="BTC/USD", as_of="2026-09-29T00:00:00Z")
    session = create_session(tmp_path, context)
    assert session["authority"] == "none"
    assert get_session(tmp_path, session["session_id"])["context_hash"] == session["context_hash"]
    with pytest.raises(ValueError, match="citation"):
        validate_answer({"text": "claim", "citations": ["invented"], "rule_draft": None}, {"chart"})
    assert (
        validate_answer(
            {"text": "insufficient evidence", "citations": ["chart"], "rule_draft": None}, {"chart"}
        )["rule_draft"]
        is None
    )


def test_changed_context_prevents_inference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.assistant_service import run_turn

    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {"close": 1}}],
    )
    session = create_session(tmp_path, AssistantContext(symbol="SPY", as_of="2026-09-29T00:00:00Z"))
    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {"close": 2}}],
    )
    with pytest.raises(ValueError, match="context changed"):
        run_turn(tmp_path, session["session_id"], AssistantTurnRequest(action="explain_chart"))


def test_inference_command_disables_tools_and_rejects_unverified_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.assistant_runtime import codex_command, infer

    command = codex_command(tmp_path)
    assert "--ignore-user-config" in command
    assert "--ephemeral" in command
    assert "shell_tool" in command
    assert "plugins" in command
    assert "skip_host_skill_discovery" in command
    assert "skill_search" in command
    assert any("permissions.alpha_assistant.filesystem=" in arg for arg in command)
    monkeypatch.setattr(
        "alpha_cli.assistant_runtime.preflight",
        lambda _: (_ for _ in ()).throw(RuntimeError("Isolation unavailable")),
    )
    with pytest.raises(RuntimeError, match="Isolation unavailable"):
        infer(AssistantTurnRequest(action="explain_chart"), [], [])


def test_interrupted_session_recovers_and_invalid_draft_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.assistant_service import _save, run_turn

    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {}}],
    )
    session = create_session(tmp_path, AssistantContext(symbol="SPY", as_of="2026-09-29T00:00:00Z"))
    session["turns"] = [{"turn_id": "previous", "status": "running"}]
    _save(tmp_path, session)
    assert get_session(tmp_path, session["session_id"])["turns"][0]["status"] == "interrupted"
    monkeypatch.setattr(
        "alpha_cli.assistant_runtime.infer",
        lambda *args, **kwargs: {
            "text": "proposal",
            "citations": ["chart"],
            "rule_draft": {"shell": "bad"},
        },
    )
    result = run_turn(tmp_path, session["session_id"], AssistantTurnRequest(action="draft_rules"))
    assert result["turns"][-1]["status"] == "failed"
    assert result["turns"][-1]["answer"] is None
    assert len(result["turns"]) == 2


def test_single_active_turn_and_owner_cancellation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl

    from alpha_cli.assistant_service import run_turn

    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {}}],
    )
    session = create_session(tmp_path, AssistantContext(symbol="SPY", as_of="2026-09-29T00:00:00Z"))
    with (tmp_path / "assistant_advisory" / "active.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with pytest.raises(ValueError, match="already active"):
            run_turn(tmp_path, session["session_id"], AssistantTurnRequest(action="explain_chart"))

    def cancelled(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("alpha_cli.assistant_runtime.infer", cancelled)
    result = run_turn(tmp_path, session["session_id"], AssistantTurnRequest(action="explain_chart"))
    assert result["turns"][-1]["status"] == "cancelled"


def test_assistant_api_requires_exact_origin_and_recovers_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from alpha_web.api.assistant import router

    monkeypatch.setenv("ALPHA_WEB_PORT", "8801")
    app = FastAPI()
    app.include_router(router)
    monkeypatch.setattr(
        "alpha_web.api.assistant._assistant.create", lambda *args, **kwargs: {"bad": True}
    )
    client = TestClient(app, base_url="http://localhost:8801")
    response = client.post(
        "/api/assistant/sessions",
        json={"context": {"symbol": "SPY", "as_of": "2026-09-29T00:00:00Z"}},
        headers={"origin": "https://evil.example"},
    )
    assert response.status_code == 403
    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {}}],
    )
    session = create_session(tmp_path, AssistantContext(symbol="SPY", as_of="2026-09-29T00:00:00Z"))
    monkeypatch.setattr("alpha_web.api.assistant._assistant.show", lambda *args, **kwargs: session)
    monkeypatch.setattr(
        "alpha_web.api.assistant._invoke.JOBS",
        {
            "job": SimpleNamespace(
                args=["assistant", "turn", session["session_id"]], status="running", job_id="job"
            )
        },
    )
    response = client.get("/api/assistant/sessions/" + session["session_id"])
    assert response.status_code == 200
    assert response.json()["active_job_id"] == "job"


@pytest.mark.bias_guard
def test_assistant_context_is_exact_cutoff_bounded_and_future_poison_invariant(
    tmp_path: Path,
) -> None:
    from datetime import date

    import polars as pl

    from alpha_cli.assistant_context import assemble_context
    from alpha_data.store import ParquetStore
    from tests.fixtures.pit_fixtures import linear_bars

    store = ParquetStore(tmp_path / "store")
    history = linear_bars("ZZ", date(2020, 1, 1), 150)
    store.write_bars("ZZ", history)
    context = AssistantContext(symbol="ZZ", as_of="2020-05-29T00:00:00Z")
    before = assemble_context(context, tmp_path)
    assert before[0]["label"] == "Stored chart · last 120 bars maximum"
    assert before[0]["data"]["attached_bars"] == 120
    assert before[0]["data"]["total_bars"] == 150
    future = linear_bars("ZZ", date(2020, 5, 30), 30, first_close=10000.0)
    store.write_bars("ZZ", pl.concat([history, future]))
    assert assemble_context(context, tmp_path) == before
    # The leaky twin intentionally takes a later cutoff and must observe the poisoned bars.
    leaky = assemble_context(AssistantContext(symbol="ZZ", as_of="2020-06-29T00:00:00Z"), tmp_path)
    assert leaky[0]["data"]["bars"] != before[0]["data"]["bars"]


def test_runtime_timeout_kills_descendants(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    from alpha_cli.assistant_runtime import infer

    monkeypatch.setattr("alpha_cli.assistant_runtime.preflight", lambda _: None)
    killed: list[tuple[int, int]] = []
    monkeypatch.setattr(
        "alpha_cli.assistant_runtime.os.killpg", lambda pid, sig: killed.append((pid, sig))
    )

    class TimedOut:
        pid = 123
        returncode = -9
        calls = 0

        def communicate(self, *args: object, **kwargs: object) -> tuple[str, str]:
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("codex", 300)
            return "", ""

        def poll(self) -> int:
            return -9

        def wait(self) -> int:
            return -9

    monkeypatch.setattr(
        "alpha_cli.assistant_runtime.subprocess.Popen", lambda *args, **kwargs: TimedOut()
    )
    with pytest.raises(RuntimeError, match="five-minute timeout"):
        infer(AssistantTurnRequest(action="explain_chart"), [], [])
    assert killed and killed[0][0] == 123


def test_stale_proposal_check_and_citation_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_cli.assistant_service import check_session

    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {"close": 1}}],
    )
    session = create_session(tmp_path, AssistantContext(symbol="SPY", as_of="2026-09-29T00:00:00Z"))
    assert check_session(tmp_path, session["session_id"])["valid"]
    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {"close": 2}}],
    )
    with pytest.raises(ValueError, match="context changed"):
        check_session(tmp_path, session["session_id"])
    with pytest.raises(ValueError, match="citation"):
        validate_answer(
            {"text": "claim", "citations": [{"arbitrary": "object"}], "rule_draft": None}, {"chart"}
        )


def test_api_to_real_cli_session_roundtrip_and_stale_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import date

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from alpha_data.store import ParquetStore
    from alpha_web.api.assistant import router
    from tests.fixtures.pit_fixtures import linear_bars

    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ALPHA_WEB_PORT", "8801")
    store = ParquetStore(tmp_path / "store")
    store.write_bars("ZZ", linear_bars("ZZ", date(2020, 1, 1), 40))
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, base_url="http://localhost:8801")
    headers = {"origin": "http://localhost:8801", "sec-fetch-site": "same-origin"}
    response = client.post(
        "/api/assistant/sessions",
        headers=headers,
        json={"context": {"symbol": "ZZ", "as_of": "2020-02-09T23:59:59Z"}},
    )
    assert response.status_code == 200, response.text
    session_id = response.json()["session_id"]
    assert (
        client.get("/api/assistant/sessions/" + session_id).json()["context_hash"]
        == response.json()["context_hash"]
    )
    assert (
        client.post(
            "/api/assistant/sessions/" + session_id + "/check", headers=headers, json={}
        ).status_code
        == 200
    )
    store.write_bars("ZZ", linear_bars("ZZ", date(2020, 1, 1), 40, first_close=10000.0))
    response = client.post(
        "/api/assistant/sessions/" + session_id + "/check", headers=headers, json={}
    )
    assert response.status_code == 409
    assert "context changed" in response.text


def test_run_context_does_not_read_mutable_store_or_later_bars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json
    from datetime import UTC, datetime

    import polars as pl

    from alpha_cli.assistant_context import assemble_context
    from alpha_core import Bar

    run_id = "a" * 16
    directory = tmp_path / "runs" / run_id
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "symbol": "ZZ",
                "snapshot_id": "frozen",
                "command": "backtest_run",
            }
        )
    )
    cutoff = datetime(2020, 1, 5, tzinfo=UTC)
    pl.DataFrame({"ts": [cutoff], "equity": [100.0]}).write_parquet(
        directory / "equity_curve.parquet"
    )
    seen: list[object] = []

    def load(
        symbol: str, *, data_dir: Path, snapshot_id: str, as_of: datetime
    ) -> tuple[list[Bar], str]:
        seen.extend([symbol, snapshot_id, as_of])
        return [Bar(symbol="ZZ", ts=cutoff, open=1, high=2, low=1, close=2, volume=1)], snapshot_id

    monkeypatch.setattr("alpha_cli._runner.load_bars", load)
    monkeypatch.setattr("alpha_cli._runner.verified_snapshot_hash", lambda *args: "a" * 64)
    from alpha_cli.artifact_contract import artifact_contract

    manifest = {
        "schema_version": 3,
        "run_identity_version": 3,
        "artifact_contract_version": 3,
        "run_id": run_id,
        "symbol": "ZZ",
        "snapshot_id": "frozen",
        "snapshot_hash": "a" * 64,
        "execution_fingerprint": "a" * 64,
        "source_fingerprint": "a" * 64,
        "strategy_fingerprint": None,
        "artifacts": artifact_contract(directory),
    }
    (directory / "manifest.json").write_text(json.dumps(manifest))
    result = assemble_context(
        AssistantContext(symbol="ZZ", run_id=run_id, as_of="2020-05-01T00:00:00Z"), tmp_path
    )
    assert seen == ["ZZ", "frozen", cutoff]
    assert result[0]["data"]["as_of"] == cutoff.isoformat()
    with pytest.raises(ValueError, match="beyond the requested cutoff"):
        assemble_context(
            AssistantContext(symbol="ZZ", run_id=run_id, as_of="2020-01-01T00:00:00Z"), tmp_path
        )


def test_completed_turn_cannot_be_overwritten_by_recovery_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl

    from alpha_cli.assistant_service import _save

    monkeypatch.setattr(
        "alpha_cli.assistant_service.assemble_context",
        lambda context, root: [{"ref": "chart", "label": "Chart", "data": {}}],
    )
    session = create_session(tmp_path, AssistantContext(symbol="SPY", as_of="2026-09-29T00:00:00Z"))
    session["turns"] = [{"turn_id": "turn", "status": "running", "answer": None}]
    _save(tmp_path, session)
    real_flock = fcntl.flock

    def complete_then_lock(fd: int | TextIO, operation: int) -> None:
        session["turns"][0].update(status="completed", answer={"text": "preserved"})
        _save(tmp_path, session)
        real_flock(fd, operation)

    monkeypatch.setattr("alpha_cli.assistant_service.fcntl.flock", complete_then_lock)
    recovered = get_session(tmp_path, session["session_id"])
    assert recovered["turns"][0]["status"] == "completed"
    assert recovered["turns"][0]["answer"]["text"] == "preserved"


def test_legacy_run_cannot_masquerade_as_verified_evidence(tmp_path: Path) -> None:
    import json

    from alpha_cli.assistant_context import assemble_context

    run_id = "b" * 16
    directory = tmp_path / "runs" / run_id
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(
        json.dumps({"schema_version": 1, "symbol": "ZZ", "metrics": {"profit": 100}})
    )
    with pytest.raises(ValueError, match="Legacy run"):
        assemble_context(
            AssistantContext(symbol="ZZ", run_id=run_id, as_of="2020-01-01T00:00:00Z"), tmp_path
        )


def test_watchdog_kills_child_and_retains_lock_after_parent_death(tmp_path: Path) -> None:
    import fcntl
    import subprocess
    import sys
    import time

    lockpath = tmp_path / "active.lock"
    childpath = tmp_path / "child.pid"
    parent_script = """import fcntl,os,subprocess,sys,time
lock=open(sys.argv[1],'a'); fcntl.flock(lock,fcntl.LOCK_EX)
child=("import os,pathlib,sys,time; "
       "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(60)")
p=subprocess.Popen([sys.executable,'-m','alpha_cli.assistant_worker',str(os.getpid()),'10',sys.executable,'-c',child,sys.argv[2]],stdin=subprocess.PIPE,pass_fds=(lock.fileno(),),start_new_session=True)
p.stdin.close()
time.sleep(60)
"""
    parent = subprocess.Popen([sys.executable, "-c", parent_script, str(lockpath), str(childpath)])
    try:
        deadline = time.monotonic() + 10
        while not childpath.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert childpath.exists(), "supervised child must start"
        with lockpath.open("a") as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            parent.kill()
            parent.wait(timeout=5)
            # Once watchdog releases the inherited lock, its model process group has been killed.
            deadline = time.monotonic() + 10
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    assert time.monotonic() < deadline, "watchdog must release after killing child"
                    time.sleep(0.02)
        child_pid = int(childpath.read_text())
        # A killed orphan may remain briefly as a zombie; it must not remain running.
        state = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(child_pid)], capture_output=True, text=True, check=False
        ).stdout.strip()
        assert not state or state.startswith("Z"), state
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=5)


def test_assistant_rule_context_rejects_changed_scan_identity_before_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import date

    from alpha_data.store import ParquetStore
    from tests.fixtures.pit_fixtures import linear_bars

    store = ParquetStore(tmp_path / "store")
    store.write_bars("ZZ", linear_bars("ZZ", date(2020, 1, 1), 40))
    current = {"rules_sha256": "a" * 64, "signal": 1, "conditions": []}
    monkeypatch.setattr("alpha_cli.assistant_context.projection", lambda *args: dict(current))

    def no_inference(*args: object, **kwargs: object) -> None:
        raise AssertionError("Creating or rejecting a context must never launch inference")

    monkeypatch.setattr("alpha_cli.assistant_runtime.infer", no_inference)
    context = AssistantContext.model_validate(
        {
            "symbol": "ZZ",
            "as_of": "2020-02-09T23:59:59Z",
            "rules_name": "scan-rules",
            "rules_sha256": "a" * 64,
        }
    )
    session = create_session(tmp_path, context)
    assert session["context"]["rules_sha256"] == "a" * 64
    assert session["attachments"][-1]["ref"] == "rules:scan-rules"
    current["rules_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="Saved rules changed since the selected scan"):
        create_session(tmp_path, context)
    # Deliberately current-rule context remains supported when no scan identity is requested.
    current_context = context.model_copy(update={"rules_sha256": None})
    assert create_session(tmp_path, current_context)["context"]["rules_sha256"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {"rules_sha256": "a" * 64},
        {"rules_name": "scan-rules", "rules_sha256": "bad"},
        {"rules_name": "scan-rules", "rules_sha256": "g" * 64},
    ],
)
def test_expected_rule_hash_requires_name_and_strict_digest(payload: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        AssistantContext.model_validate(
            {"symbol": "ZZ", "as_of": "2020-02-09T23:59:59Z", **payload}
        )


@pytest.mark.parametrize("symbol", ["^VIX", "^TNX", "EURUSD=X", "ES=F"])
def test_assistant_accepts_stored_provider_symbols_without_rewriting(
    symbol: str, tmp_path: Path
) -> None:
    from datetime import date

    from alpha_cli.assistant_context import assemble_context
    from alpha_data.store import ParquetStore
    from tests.fixtures.pit_fixtures import linear_bars

    store = ParquetStore(tmp_path / "store")
    store.write_bars(symbol, linear_bars(symbol, date(2020, 1, 1), 40))
    context = AssistantContext(symbol=symbol, as_of="2020-01-20T23:59:59Z")
    source = assemble_context(context, tmp_path)[0]["data"]
    assert source["symbol"] == symbol
    assert source["total_bars"] == 20
    assert source["bars"][-1]["t"] <= context.as_of.timestamp()
    session = create_session(tmp_path, context)
    assert session["context"]["symbol"] == symbol


@pytest.mark.parametrize("symbol", ["/etc/passwd", "../owner", "A\\B", "A\nB"])
def test_assistant_symbol_compatibility_keeps_unsafe_inputs_rejected(symbol: str) -> None:
    with pytest.raises(ValidationError):
        AssistantContext(symbol=symbol, as_of="2020-01-20T23:59:59Z")


def test_assistant_storage_guard_still_rejects_embedded_traversal(tmp_path: Path) -> None:
    from alpha_core import DataError

    context = AssistantContext(symbol="A/../owner", as_of="2020-01-20T23:59:59Z")
    with pytest.raises(DataError, match="invalid symbol for storage"):
        create_session(tmp_path, context)
