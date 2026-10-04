"""Conversation additions preserve case scope and spent budgets."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from alpha_cli.codex_session import Session


def test_read_only_snapshot_and_prompt_binding(tmp_path: Path) -> None:
    assert Session.snapshot(tmp_path, "a" * 64, "model") is None
    assert list(tmp_path.iterdir()) == []
    with Session(tmp_path, "a" * 64, "model") as session:
        session.bind_thread("thread")
        session.reserve_turn(prompt={"followup": "Check costs"})
        session.start_turn("turn")
        state = Session.snapshot(tmp_path, "a" * 64, "model")
        assert state is not None and state["turns"][0]["status"] == "running"
        session.finish_turn("failed")
    marker = tmp_path / "codex-turn-1.json"
    record = json.loads(marker.read_text())
    record["input"]["followup"] = "Changed"
    marker.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="input"):
        Session.snapshot(tmp_path, "a" * 64, "model")


def test_historical_markers_remain_readable(tmp_path: Path) -> None:
    with Session(tmp_path, "a" * 64, "model") as session:
        session.reserve_turn()
        session.finish_turn("failed")
    state = Session.snapshot(tmp_path, "a" * 64, "model")
    assert state is not None and len(state["turns"]) == 1


def test_followup_reuses_thread_retries_retained_question_and_keeps_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio
    from typing import Any

    from alpha_cli import codex_environment, codex_investigation
    from alpha_cli.investigation_case import ACTIONS, Case
    from tests.unit.test_research_execution import run_fixture

    case = Case.create(
        tmp_path / "case", run_fixture(tmp_path), "2020-01-02", "Why?", "gpt-6-astra"
    )
    prompts: list[dict[str, Any]] = []
    threads: list[str] = []
    fail = False

    class Peer:
        def __init__(self, *_: Any, **__: Any) -> None:
            self.events: list[dict[str, Any]] = []

        async def __aenter__(self) -> Peer:
            return self

        async def __aexit__(self, *_: Any) -> None:
            pass

        async def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
            if method.startswith("thread/"):
                threads.append(method)
                return dict(
                    model="gpt-6-astra",
                    approvalPolicy="never",
                    thread={"id": "t"},
                    activePermissionProfile={"id": "investigation", "extends": None},
                    sandbox={"type": "readOnly", "networkAccess": False},
                )
            if method == "mcpServerStatus/list":
                return {"data": [{"name": "alpha_investigation", "tools": dict.fromkeys(ACTIONS)}]}
            prompts.append(json.loads(params["input"][0]["text"]))
            receipt = case.call("inspect_execution")
            if fail:
                case.call("inspect_losses")
            report = dict(
                findings=[{"observation": "Measured", "receipt_ids": [receipt["id"]]}],
                hypotheses=[],
                next_tests=[],
                limitations=["Small sample"],
            )
            self.events = [
                {
                    "method": "item/completed",
                    "params": {
                        "threadId": "t",
                        "turnId": "u",
                        "item": {"type": "agentMessage", "text": json.dumps(report)},
                    },
                },
                {
                    "method": "turn/completed",
                    "params": {"threadId": "t", "turn": {"id": "u", "status": "completed"}},
                },
            ]
            return {"turn": {"id": "u"}}

        async def next_event(self, **_: Any) -> dict[str, Any]:
            if fail:
                raise TimeoutError("test failure")
            return self.events.pop(0)

    async def preflight(*_: Any) -> dict[str, Any]:
        return {"test_double": True}

    monkeypatch.setattr(codex_investigation, "CodexRpc", Peer)
    monkeypatch.setattr(codex_environment, "prepare", lambda _: (["peer"], tmp_path, {}))
    monkeypatch.setattr(codex_environment, "preflight", preflight)
    with pytest.raises(ValueError, match="prior completed"):
        asyncio.run(codex_investigation.run_investigation(case, followup="Check costs"))
    first = asyncio.run(codex_investigation.run_investigation(case))
    fail = True
    with pytest.raises(TimeoutError):
        asyncio.run(codex_investigation.run_investigation(case, followup="Check costs"))
    state = Session.snapshot(case.path, case.context()["case_id"], "gpt-6-astra")
    assert state is not None and state["latest_report"]["report"] == first["report"]
    assert state["turns"][-1]["status"] == "failed"
    fail = False
    asyncio.run(codex_investigation.run_investigation(case))
    assert prompts[-1]["followup"] == prompts[-2]["followup"] == "Check costs"
    asyncio.run(codex_investigation.run_investigation(case, followup="Challenge this"))
    assert threads == ["thread/start", "thread/resume", "thread/resume", "thread/resume"]
    with pytest.raises(ValueError, match="budget"):
        asyncio.run(codex_investigation.run_investigation(case, followup="Again"))
    cached = asyncio.run(codex_investigation.run_investigation(case))
    assert cached["latest_completed_turn"] == 4
    assert len(prompts) == 4
    assert case.context()["requests_remaining"] == 7


def test_read_snapshot_marks_inflight_reservation_busy_without_replenishing(tmp_path: Path) -> None:
    with Session(tmp_path, "a" * 64, "model") as session:
        session._write("codex-turn-1.json", session._reservation(1), immutable=True)
        with pytest.raises(ValueError, match="busy"):
            Session.snapshot(tmp_path, "a" * 64, "model")
    with pytest.raises(ValueError, match="ledger mismatch"):
        Session.snapshot(tmp_path, "a" * 64, "model")
