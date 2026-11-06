"""Synthetic assistant cleanup, with no model or network calls."""

from __future__ import annotations

import io
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import assistant_worker


def test_watchdog_waits_for_child_before_releasing_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.setattr("alpha_cli.assistant_worker.sys.argv", ["worker", "123", "0", "synthetic"])
    monkeypatch.setattr("alpha_cli.assistant_worker.sys.stdin", io.StringIO("prompt"))
    monkeypatch.setattr("alpha_cli.assistant_worker.os.getppid", lambda: 123)
    monkeypatch.setattr("alpha_cli.assistant_worker.os.getpgrp", lambda: 999)

    class Child:
        pid = 456
        returncode: int | None = None

        def communicate(self, *args: object, **kwargs: object) -> tuple[str, str]:
            raise subprocess.TimeoutExpired("synthetic", 0.2)

        def wait(self) -> int:
            events.append("reaped")
            self.returncode = -9
            return -9

    def start(*args: object, **kwargs: Any) -> Child:
        assert kwargs.get("start_new_session") is True
        return Child()

    def kill(group: int, sig: int) -> None:
        assert group == 456, "the lock holder must survive its model-group signal"
        if sig == signal.SIGKILL:
            events.append("signalled")
        else:
            assert sig == 0
            assert events == ["signalled", "reaped"]
            raise ProcessLookupError

    monkeypatch.setattr("alpha_cli.assistant_worker.subprocess.Popen", start)
    monkeypatch.setattr("alpha_cli.assistant_worker.os.killpg", kill)
    with pytest.raises(SystemExit):
        assistant_worker.main()
    assert events == ["signalled", "reaped"]


@pytest.mark.usefixtures("owned_test_process")
@pytest.mark.parametrize(
    "reason", ["parent_death", "owner_cancel", "deadline", "leader_exit", "closed_pipes"]
)
def test_assistant_cleanup_reaps_model_group_before_unlock(tmp_path: Path, reason: str) -> None:
    import fcntl

    lockpath = tmp_path / "active.lock"
    pidpath = tmp_path / "model.pids"
    script = """import fcntl,sys
from alpha_cli import assistant_runtime as runtime
from alpha_cli.assistant_contracts import AssistantTurnRequest
runtime.preflight=lambda work: None
runtime.TIMEOUT_SECONDS=2 if sys.argv[3] in {'deadline','leader_exit'} else 20
child='''import os,pathlib,signal,subprocess,sys,time
signal.signal(signal.SIGTERM,signal.SIG_IGN)
grandcode='import signal,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); time.sleep(60)'
kwargs={}
if sys.argv[2]=='closed_pipes':
    grandcode=('import pathlib,sys,time; p=pathlib.Path(sys.argv[1]+".exit"); '
               'exec("while not p.exists(): time.sleep(0.02)")')
    kwargs=dict(stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
grandchild=subprocess.Popen([sys.executable,'-c',grandcode,sys.argv[1]],**kwargs)
pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()} {grandchild.pid}')
if sys.argv[2] in {'leader_exit','closed_pipes'}: raise SystemExit(0)
time.sleep(60)
'''
runtime.codex_command=lambda work: [sys.executable,'-c',child,sys.argv[2],sys.argv[3]]
with open(sys.argv[1],'a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX)
    try: runtime.infer(AssistantTurnRequest(action='explain_chart'),[],[],lock_fd=lock.fileno())
    except (KeyboardInterrupt,RuntimeError): pass
"""
    parent = subprocess.Popen(
        [sys.executable, "-c", script, str(lockpath), str(pidpath), reason],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 10
        while not pidpath.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert pidpath.exists(), "synthetic model and descendant must start"
        if reason == "closed_pipes":
            leader = pidpath.read_text().split()[0]
            deadline = time.monotonic() + 5
            while subprocess.run(
                ["ps", "-o", "stat=", "-p", leader],
                capture_output=True,
                text=True,
                check=False,
            ).stdout.strip():
                assert time.monotonic() < deadline, "communicate must reap the exited leader"
                time.sleep(0.02)
        with lockpath.open("a") as lock:
            with pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if reason == "parent_death":
                parent.kill()
            elif reason == "owner_cancel":
                parent.terminate()
            elif reason == "closed_pipes":
                Path(str(pidpath) + ".exit").touch()
            parent.communicate(timeout=10)
            deadline = time.monotonic() + 10
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    assert time.monotonic() < deadline, "cleanup must complete before unlock"
                    time.sleep(0.02)
            for raw in pidpath.read_text().split():
                state = subprocess.run(
                    ["ps", "-o", "stat=", "-p", raw],
                    capture_output=True,
                    text=True,
                    check=False,
                ).stdout.strip()
                assert not state or state.startswith("Z"), state
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait(timeout=5)


def test_cancellation_during_launch_still_reaps_child(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("alpha_cli.assistant_worker.sys.argv", ["worker", "123", "10", "synthetic"])
    monkeypatch.setattr("alpha_cli.assistant_worker.sys.stdin", io.StringIO("prompt"))
    monkeypatch.setattr("alpha_cli.assistant_worker.os.getppid", lambda: 123)
    waited: list[bool] = []

    class Child:
        pid = 456
        returncode: int | None = None

        def wait(self) -> int:
            # Repeated cancellation cannot interrupt cleanup.
            callback = signal.getsignal(signal.SIGTERM)
            assert callable(callback)
            callback(signal.SIGTERM, None)
            waited.append(True)
            self.returncode = -9
            return -9

    def start(*args: object, **kwargs: object) -> Child:
        callback = signal.getsignal(signal.SIGTERM)
        assert callable(callback)
        callback(signal.SIGTERM, None)
        return Child()

    def kill(group: int, sig: int) -> None:
        assert group == 456
        if sig == 0:
            raise ProcessLookupError

    monkeypatch.setattr("alpha_cli.assistant_worker.subprocess.Popen", start)
    monkeypatch.setattr("alpha_cli.assistant_worker.os.killpg", kill)
    with pytest.raises(SystemExit, match="137"):
        assistant_worker.main()
    assert waited == [True]


@pytest.mark.parametrize("missing", [False, True])
def test_cleanup_waits_for_group_and_never_resignals_after_reap(
    monkeypatch: pytest.MonkeyPatch,
    missing: bool,
) -> None:
    events: list[str] = []
    probes = 0

    class Child:
        pid = 456
        returncode: int | None = None

        def wait(self) -> int:
            events.append("reaped")
            self.returncode = -9
            return -9

    def kill(group: int, sig: int) -> None:
        nonlocal probes
        assert group == 456
        if sig == signal.SIGKILL:
            assert not events
            events.append("signalled")
            if missing:
                raise ProcessLookupError
        else:
            assert sig == 0 and "reaped" in events
            probes += 1
            if probes == 2:
                raise ProcessLookupError

    monkeypatch.setattr("alpha_cli.assistant_worker.os.killpg", kill)
    monkeypatch.setattr("alpha_cli.assistant_worker.time.sleep", lambda _: events.append("waited"))
    child: Any = Child()
    assistant_worker._reap_group(child)
    assert events == ["signalled", "reaped", "waited"]


def test_cancel_during_prompt_read_never_launches_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("alpha_cli.assistant_worker.sys.argv", ["worker", "123", "10", "synthetic"])

    class Input:
        def read(self) -> str:
            callback = signal.getsignal(signal.SIGTERM)
            assert callable(callback)
            callback(signal.SIGTERM, None)
            raise AssertionError("cancellation must interrupt the pre-launch input read")

    monkeypatch.setattr("alpha_cli.assistant_worker.sys.stdin", Input())
    with pytest.raises(SystemExit, match="125"):
        assistant_worker.main()
