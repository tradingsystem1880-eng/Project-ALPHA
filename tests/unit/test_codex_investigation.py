"""Codex research policy must hold independently of model obedience."""

import json
from pathlib import Path
from typing import Any

import pytest

from alpha_cli.codex_policy import launch_config, permission_settings


def test_launch_has_only_case_mcp_and_no_workspace_tools(tmp_path: Path) -> None:
    case = tmp_path / "case"
    case.mkdir()
    workspace = case / "workspace"
    workspace.mkdir()
    config = launch_config(case, workspace, python=Path("/usr/bin/python3"))
    assert set(config["mcp_servers"]) == {"alpha_investigation"}
    assert config["mcp_servers"]["alpha_investigation"]["required"] is True
    assert config["features"]["shell_tool"] is False
    assert config["features"]["apps"] is False
    assert config["features"]["image_generation"] is False
    assert config["features"]["code_mode_host"] is True
    scoped = config["mcp_servers"]["alpha_investigation"]
    assert set(scoped["tools"]) == set(scoped["enabled_tools"])
    assert all(value == {"approval_mode": "approve"} for value in scoped["tools"].values())
    assert config["web_search"] == "disabled"
    assert config["project_doc_max_bytes"] == 0
    assert config["permissions"]["investigation"]["filesystem"][str(workspace)] == "read"
    assert config["permissions"]["investigation"]["filesystem"]["/"] == "deny"


def test_profile_uses_resolved_roots_and_no_write_grant(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(real)
    settings = permission_settings(alias)
    assert settings["permissions"]["investigation"]["filesystem"][str(real)] == "read"
    assert "write" not in json.dumps(settings)


def test_profile_rejects_root_as_workspace() -> None:
    with pytest.raises(ValueError, match="dedicated"):
        permission_settings(Path("/"))


def test_report_cannot_invent_receipts_or_skip_execution(tmp_path: Path) -> None:
    from alpha_cli.investigation_case import Case
    from alpha_cli.investigation_report import verify_report
    from tests.unit.test_research_execution import run_fixture

    case = Case.create(
        tmp_path / "case", run_fixture(tmp_path), "2020-01-02", "Why?", "gpt-6-astra"
    )
    report: dict[str, Any] = {
        "findings": [{"observation": "One fill", "receipt_ids": ["invented"]}],
        "hypotheses": [],
        "next_tests": [],
        "limitations": ["Small sample"],
    }
    with pytest.raises(ValueError, match="execution inspection"):
        verify_report(case, json.dumps(report))
    receipt = case.call("inspect_execution")
    with pytest.raises(ValueError, match="nonexistent"):
        verify_report(case, json.dumps(report))
    report["findings"][0]["receipt_ids"] = [receipt["id"]]
    result = verify_report(case, json.dumps(report))
    assert result["claim_verification"] == "binding_only"
    assert result["authority"] == "none"


def test_config_is_valid_toml(tmp_path: Path) -> None:
    import tomllib

    from alpha_cli.codex_policy import config_text

    config = launch_config(tmp_path, tmp_path, python=Path("/usr/bin/python3"))
    assert tomllib.loads(config_text(config)) == config


def test_stream_ignores_stale_turn_and_rejects_foreign_tool() -> None:
    import asyncio
    from typing import Any

    from alpha_cli.codex_investigation import InvestigationTurn

    class Peer:
        def __init__(self, events: list[dict[str, Any]]) -> None:
            self.events = iter(events)

        async def next_event(self, **_: Any) -> dict[str, Any]:
            return next(self.events)

    def event(method: str, turn_id: str, **extra: Any) -> dict[str, Any]:
        return {"method": method, "params": {"threadId": "thread", "turnId": turn_id, **extra}}

    peer = Peer(
        [
            event("item/completed", "stale", item={"type": "agentMessage", "text": "wrong"}),
            event("item/completed", "turn", item={"type": "agentMessage", "text": "right"}),
            event("turn/completed", "turn", turn={"status": "completed"}),
        ]
    )
    assert asyncio.run(InvestigationTurn(peer, "thread", "turn").collect()) == "right"  # type: ignore[arg-type]
    peer = Peer(
        [
            event(
                "item/started",
                "turn",
                item={
                    "type": "mcpToolCall",
                    "server": "alpha",
                    "tool": "backtest_run",
                },
            )
        ]
    )
    with pytest.raises(RuntimeError, match="Unexpected MCP"):
        asyncio.run(InvestigationTurn(peer, "thread", "turn").collect())  # type: ignore[arg-type]


def test_steer_and_interrupt_are_bound_to_active_turn() -> None:
    import asyncio
    from typing import Any

    from alpha_cli.codex_investigation import InvestigationTurn

    calls = []

    class Peer:
        async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            calls.append((method, params))
            return {}

    async def check() -> None:
        turn = InvestigationTurn(Peer(), "thread", "turn")  # type: ignore[arg-type]
        await turn.steer("Investigate costs first")
        await turn.interrupt()

    asyncio.run(check())
    assert calls[0][1]["expectedTurnId"] == "turn"
    assert calls[1] == ("turn/interrupt", {"threadId": "thread", "turnId": "turn"})


def test_scoped_mcp_has_only_parameterless_diagnostic_tools(tmp_path: Path) -> None:
    import asyncio

    from alpha_mcp.investigation_server import build_server

    server = build_server(tmp_path)
    tools = asyncio.run(server.list_tools())
    assert {tool.name for tool in tools} == {
        "inspect_execution",
        "inspect_losses",
        "suggest_followups",
    }
    assert all(tool.inputSchema["properties"] == {} for tool in tools)
    assert all(tool.inputSchema["additionalProperties"] is False for tool in tools)
    with pytest.raises(ValueError, match="no arguments"):
        asyncio.run(server.call_tool("inspect_execution", {"run_id": "another"}))


@pytest.mark.parametrize("failure", [None, "malformed", "timeout", "cancel"])
def test_runtime_journals_real_case_and_resumes_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    import asyncio

    from alpha_cli import codex_environment, codex_investigation
    from alpha_cli.investigation_case import ACTIONS, Case
    from tests.unit.test_research_execution import run_fixture

    case = Case.create(
        tmp_path / "case", run_fixture(tmp_path), "2020-01-02", "Why?", "gpt-6-astra"
    )
    methods: list[str] = []
    closed: list[bool] = []

    class Peer:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.events: list[dict[str, Any]] = []

        async def __aenter__(self) -> "Peer":
            return self

        async def __aexit__(self, *_: Any) -> None:
            closed.append(True)

        async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            methods.append(method)
            if method in ("thread/start", "thread/resume"):
                return {
                    "model": "gpt-6-astra",
                    "approvalPolicy": "never",
                    "thread": {"id": "t"},
                    "activePermissionProfile": {"id": "investigation", "extends": None},
                    "sandbox": {"type": "readOnly", "networkAccess": False},
                }
            if method == "mcpServerStatus/list":
                return {"data": [{"name": "alpha_investigation", "tools": dict.fromkeys(ACTIONS)}]}
            assert method == "turn/start"
            receipt = case.call("inspect_execution")
            text = json.dumps(
                {
                    "findings": [{"observation": "One fill", "receipt_ids": [receipt["id"]]}],
                    "hypotheses": [],
                    "next_tests": [],
                    "limitations": ["Small sample"],
                }
            )
            if failure == "malformed":
                text = "{invalid"
            self.events = [
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "t",
                        "turnId": "u",
                        "item": {"type": "agentMessage", "text": text},
                    },
                },
                {
                    "method": "turn/completed",
                    "params": {"threadId": "t", "turn": {"id": "u", "status": "completed"}},
                },
            ]
            return {"turn": {"id": "u"}}

        async def next_event(self, **_: Any) -> dict[str, Any]:
            if failure == "timeout":
                raise TimeoutError("injected stream timeout")
            if failure == "cancel":
                raise asyncio.CancelledError()
            return self.events.pop(0)

    async def probe(*_: Any) -> dict[str, Any]:
        return {"verified": True, "test_double": True}

    monkeypatch.setattr(codex_investigation, "CodexRpc", Peer)
    monkeypatch.setattr(codex_environment, "prepare", lambda _: (["peer"], tmp_path, {}))
    monkeypatch.setattr(codex_environment, "preflight", probe)
    if failure:
        error = {"malformed": ValueError, "timeout": TimeoutError, "cancel": asyncio.CancelledError}
        with pytest.raises(error[failure]):
            asyncio.run(codex_investigation.run_investigation(case))
    else:
        result = asyncio.run(codex_investigation.run_investigation(case))
        assert result["authority"] == "none"
        # No new transport or model call is required to return a verified completed checkpoint.
        cached = asyncio.run(codex_investigation.run_investigation(Case.open(case.path)))
        assert cached["report"] == result["report"]
        assert cached["resumed_from_checkpoint"] is True
    state = json.loads((case.path / "codex-session.json").read_text())
    expected = "interrupted" if failure == "cancel" else "failed" if failure else "completed"
    assert state["turns"][0]["status"] == expected
    assert len(state["turns"]) == 1
    assert methods.count("turn/start") == 1
    assert closed == [True]


def test_mcp_calls_supported_cli_against_real_artifacts(tmp_path: Path) -> None:
    import asyncio

    from alpha_cli.investigation_case import Case
    from alpha_mcp.investigation_server import build_server
    from tests.unit.test_research_execution import run_fixture

    case = Case.create(
        tmp_path / "case", run_fixture(tmp_path), "2020-01-02", "Why?", "gpt-6-astra"
    )
    server = build_server(case.path)

    async def call_all() -> None:
        for action in ("inspect_execution", "inspect_losses", "suggest_followups"):
            await server.call_tool(action, {})

    asyncio.run(call_all())
    assert [r["status"] for r in case.receipts()] == ["succeeded"] * 3
    assert case.context()["requests_remaining"] == 9


def test_stream_stops_repeated_tool_calls_and_failed_turn() -> None:
    import asyncio

    from alpha_cli.codex_investigation import InvestigationTurn

    class Peer:
        async def next_event(self, **_: Any) -> dict[str, Any]:
            return {
                "method": "item/started",
                "params": {
                    "threadId": "t",
                    "turnId": "u",
                    "item": {
                        "type": "mcpToolCall",
                        "server": "alpha_investigation",
                        "tool": "inspect_execution",
                    },
                },
            }

    with pytest.raises(RuntimeError, match="tool-call budget"):
        asyncio.run(InvestigationTurn(Peer(), "t", "u").collect())  # type: ignore[arg-type]


def test_inventory_rejects_additional_server_and_capability() -> None:
    import asyncio

    from alpha_cli.codex_investigation import _check_tools

    class Peer:
        async def request(self, *_: Any) -> dict[str, Any]:
            return {"data": inventory}

    inventory = [{"name": "alpha", "tools": {"backtest_run": {}}}]
    with pytest.raises(RuntimeError, match="capability inventory"):
        asyncio.run(_check_tools(Peer(), "t"))  # type: ignore[arg-type]
    inventory = []
    with pytest.raises(RuntimeError, match="exactly one"):
        asyncio.run(_check_tools(Peer(), "t"))  # type: ignore[arg-type]
