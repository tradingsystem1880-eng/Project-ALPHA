"""The gate's separate owner must really reap descendants, not classify zombies away."""

import importlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import gate
import pytest

RUNNER = Path(__file__).resolve().parents[2] / "scripts/run_owned_test.py"


def run_owned(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(RUNNER), "--", sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=15,
    )


@pytest.mark.skipif(sys.platform != "linux", reason="Linux subreaper ownership contract")
def test_reaps_orphan_before_command_finishes() -> None:
    grandchild = "import time; time.sleep(0.1)"
    leader = (
        "import subprocess,sys; "
        f"p=subprocess.Popen([sys.executable,'-c',{grandchild!r}], "
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid)"
    )
    command = f"""
import os,subprocess,sys,time
pid=int(subprocess.check_output([sys.executable,'-c',{leader!r}],text=True))
deadline=time.monotonic()+4
while time.monotonic()<deadline:
    try: os.kill(pid,0)
    except ProcessLookupError: break
    time.sleep(0.01)
else: raise AssertionError('descendant still exists, including zombie')
print('actually reaped')
"""
    result = run_owned(command)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "actually reaped"


@pytest.mark.parametrize("status", [0, 37])
def test_preserves_command_status_and_both_streams(status: int) -> None:
    result = run_owned(
        "import sys; print('owned output'); print('owned error',file=sys.stderr); "
        f"sys.exit({status})"
    )
    assert result.returncode == status
    assert result.stdout.strip() == "owned output"
    assert result.stderr.strip() == "owned error"


def test_unrelated_sibling_status_remains_owned_by_its_parent() -> None:
    with subprocess.Popen([sys.executable, "-c", "import sys; sys.exit(41)"]) as sibling:
        assert run_owned("pass").returncode == 0
        assert sibling.wait(timeout=5) == 41


@pytest.mark.skipif(sys.platform != "linux", reason="Linux orphan cleanup contract")
def test_live_orphan_is_reaped_and_cannot_turn_command_into_a_pass(tmp_path: Path) -> None:
    pid_file = tmp_path / "orphan.pid"
    command = (
        "import subprocess,sys; from pathlib import Path; "
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],"
        "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True); "
        f"Path({str(pid_file)!r}).write_text(str(p.pid))"
    )
    result = run_owned(command)
    assert result.returncode != 0
    assert "command left live descendants" in result.stderr
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux bounded descendant cleanup")
def test_timeout_kills_and_reaps_detached_sigterm_ignoring_child(tmp_path: Path) -> None:
    pid_file = tmp_path / "timeout-child.pid"
    nested = (
        "import os,signal,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        f"Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
    )
    command = (
        "import subprocess,sys,time; "
        f"subprocess.Popen([sys.executable,'-c',{nested!r}],start_new_session=True); "
        "time.sleep(30)"
    )
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "0.5", "--", sys.executable, "-c", command],
        capture_output=True,
        text=True,
        timeout=12,
    )
    assert result.returncode == 124, result.stderr
    assert "TimeoutExpired" in result.stderr
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux gate timeout ownership")
def test_gate_timeout_lets_owner_reap_instead_of_killing_supervisor(tmp_path: Path) -> None:
    pid_file = tmp_path / "bounded.pid"
    code = (
        "import os,time; from pathlib import Path; "
        f"Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)"
    )
    binary = tmp_path / "uv"
    binary.write_text(
        f"#!{sys.executable}\nimport os,sys\nos.execv(sys.executable,"
        f"[sys.executable,'-c',{code!r}])\n"
    )
    binary.chmod(0o755)
    ok, _, output = gate._env_runner(
        ["uv", "run", "pytest"],
        timeout=0.5,
        env={**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"},
    )
    assert not ok
    assert "TimeoutExpired" in output
    with pytest.raises(ProcessLookupError):
        os.kill(int(pid_file.read_text()), 0)


@pytest.mark.skipif(sys.platform != "linux", reason="Linux signal forwarding contract")
def test_forwards_signal_and_preserves_child_handler_status(tmp_path: Path) -> None:
    ready = tmp_path / "ready"
    received = tmp_path / "received"
    command = f"""
import signal,sys,time
from pathlib import Path
def stop(sig,frame):
    Path({str(received)!r}).write_text(str(sig))
    sys.exit(23)
signal.signal(signal.SIGTERM,stop)
Path({str(ready)!r}).touch()
while True: time.sleep(0.01)
"""
    with subprocess.Popen(
        [sys.executable, str(RUNNER), "--", sys.executable, "-c", command]
    ) as owner:
        try:
            deadline = time.monotonic() + 5
            while not ready.exists() and owner.poll() is None and time.monotonic() < deadline:
                time.sleep(0.01)
            assert ready.exists()
            owner.send_signal(signal.SIGTERM)
            assert owner.wait(timeout=8) == 23
            assert received.read_text() == str(signal.SIGTERM)
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.wait(timeout=5)


def test_non_linux_executes_original_command(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = importlib.import_module("run_owned_test")
    monkeypatch.setattr(runner.sys, "platform", "darwin")
    seen: list[object] = []

    def execute(executable: str, command: list[str]) -> None:
        seen.extend([executable, command])
        raise RuntimeError("exec replaced process")

    monkeypatch.setattr(runner.os, "execvp", execute)
    with pytest.raises(RuntimeError, match="exec replaced process"):
        runner.main(["--", "python", "-m", "pytest", "original"])
    assert seen == ["python", ["python", "-m", "pytest", "original"]]


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_gate_wraps_only_pytest_without_changing_other_commands(
    monkeypatch: pytest.MonkeyPatch, platform: str
) -> None:
    monkeypatch.setattr("gate.sys.platform", platform)
    calls: list[list[str]] = []

    def execute(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("gate.subprocess.run", execute)
    original = ["uv", "run", "pytest", "-q", "--cov"]
    assert gate._env_runner(original)[0]
    assert calls[-1] == (
        [sys.executable, str(RUNNER), "--", *original] if platform == "linux" else original
    )
    assert gate._env_runner(["uv", "sync", "--locked"])[0]
    assert calls[-1] == ["uv", "sync", "--locked"]
