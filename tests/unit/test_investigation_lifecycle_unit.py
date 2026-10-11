"""In-process host contracts supplement real process-tree lifecycle acceptance."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from alpha_cli import codex_investigation
from alpha_cli import investigation_lifecycle as lifecycle
from alpha_cli.investigation_case import Case


@pytest.mark.parametrize("outcome", ["success", "error", "cancel"])
def test_host_forwards_context_and_restores_signal_handlers_after_unwind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    handlers: dict[int, Callable[[], None]] = {}
    removed: list[int] = []
    emitted: list[dict[str, Any]] = []
    unwound: list[bool] = []
    previous = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGINT)}
    case = Case(tmp_path)
    failure = ValueError("fixture evidence failure")

    def install(self: Any, sig: int, callback: Callable[[], None], *args: Any) -> None:
        handlers[sig] = callback

    def remove(self: Any, sig: int) -> bool:
        removed.append(sig)
        return True

    async def investigate(
        actual: Case, *, followup: str | None, on_event: Callable[[dict[str, Any]], None] | None
    ) -> dict[str, Any]:
        assert actual is case and followup == "Check costs"
        assert set(handlers) == {signal.SIGTERM, signal.SIGINT}
        assert on_event is not None
        try:
            on_event({"method": "fixture_progress"})
            if outcome == "error":
                raise failure
            if outcome == "cancel":
                handlers[signal.SIGTERM]()
                handlers[signal.SIGINT]()
                task = asyncio.current_task()
                assert task is not None and task.cancelling() == 1
                await asyncio.sleep(0)
                pytest.fail("cancellation was not delivered")
            return {"authority": "none", "report": "fixture"}
        finally:
            unwound.append(True)

    monkeypatch.setattr(asyncio.unix_events._UnixSelectorEventLoop, "add_signal_handler", install)
    monkeypatch.setattr(asyncio.unix_events._UnixSelectorEventLoop, "remove_signal_handler", remove)
    monkeypatch.setattr(codex_investigation, "run_investigation", investigate)
    if outcome == "success":
        assert lifecycle.run(case, followup="Check costs", on_event=emitted.append) == {
            "authority": "none",
            "report": "fixture",
        }
    elif outcome == "error":
        with pytest.raises(ValueError) as error:
            lifecycle.run(case, followup="Check costs", on_event=emitted.append)
        assert error.value is failure
    else:
        with pytest.raises(lifecycle.InvestigationInterrupted, match="spent budgets retained"):
            lifecycle.run(case, followup="Check costs", on_event=emitted.append)
    assert unwound == [True]
    assert emitted == [{"method": "fixture_progress"}]
    assert removed == [signal.SIGTERM, signal.SIGINT]
    assert {sig: signal.getsignal(sig) for sig in previous} == previous


class GroupKilled(BaseException):
    """A fake killpg never signals the pytest process."""


@pytest.mark.parametrize("reason", ["parent_death", "deadline", "leader_exit"])
def test_watchdog_reaps_only_owned_group_for_each_terminal_condition(
    monkeypatch: pytest.MonkeyPatch, reason: str
) -> None:
    monkeypatch.setattr(os, "getpid", lambda: 101)
    monkeypatch.setattr(os, "getpgrp", lambda: 101)
    parents = iter([100, 100, 1] if reason == "parent_death" else [100, 100])
    monkeypatch.setattr(os, "getppid", lambda: next(parents))
    clock = iter([0.0, 1.0] if reason == "deadline" else [0.0, 0.0])
    monkeypatch.setattr(time, "monotonic", lambda: next(clock))
    child = Mock(returncode=0)
    if reason == "parent_death":
        child.wait.side_effect = subprocess.TimeoutExpired("fixture", 0.1)
    popen = Mock(return_value=child)
    killed = Mock(side_effect=GroupKilled)
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(os, "killpg", killed)
    with pytest.raises(GroupKilled):
        lifecycle._watch(100, 0.5, ["trusted-peer"])
    popen.assert_called_once_with(["trusted-peer"])
    killed.assert_called_once_with(101, signal.SIGKILL)
    if reason == "deadline":
        child.wait.assert_not_called()
    else:
        child.wait.assert_called_once_with(timeout=0.1)


def test_watchdog_refuses_foreign_group_or_already_dead_parent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(os, "getpid", lambda: 101)
    monkeypatch.setattr(os, "getpgrp", lambda: 99)
    popen = Mock()
    kill = Mock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(os, "killpg", kill)
    with pytest.raises(ValueError, match="own isolated process group"):
        lifecycle._watch(100, 10, ["peer"])
    monkeypatch.setattr(os, "getpgrp", lambda: 101)
    monkeypatch.setattr(os, "getppid", lambda: 1)
    assert lifecycle._watch(100, 10, ["peer"]) == 125
    popen.assert_not_called()
    kill.assert_not_called()
