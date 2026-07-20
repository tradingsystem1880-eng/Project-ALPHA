"""The web IDE's job runner: launch `alpha`, capture streaming output, parse the run id.

Uses a fast fake command (a tiny `python -c`) in place of the real CLI so the lifecycle —
capture, run-id parse, terminal status — is exercised without the engine.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from alpha_cli.durable_lease import DurableLeaseError, terminate_and_reap
from alpha_web import _invoke


def _fake(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    cmd: Callable[[list[str]], list[str]] = lambda args: ["python", "-c", script]  # noqa: E731
    monkeypatch.setattr(_invoke, "_command", cmd)


def _wait(job: _invoke.Job, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while not job.finished and time.time() < end:
        time.sleep(0.02)
    assert job.finished, "job did not finish in time"


def _process_is_executing(pid: int) -> bool:
    probe = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)],
        capture_output=True,
        text=True,
        check=False,
    )
    state = probe.stdout.strip()
    return probe.returncode == 0 and bool(state) and not state.startswith("Z")


def test_launch_captures_output_and_parses_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake(monkeypatch, "print('starting'); print('validate SPY -> run 0123456789abcdef: PASS')")
    job = _invoke.launch(["validate", "SPY"], data_dir=tmp_path, run_type="runs")
    _wait(job)
    assert job.status == "done"
    assert any("starting" in ln for ln in job.lines)
    assert job.run_id == "0123456789abcdef"


def test_launch_marks_failure_on_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake(monkeypatch, "import sys; print('boom'); sys.exit(3)")
    job = _invoke.launch(["validate", "X"], data_dir=tmp_path, run_type="runs")
    _wait(job)
    assert job.status == "failed" and job.returncode == 3
    assert any("boom" in ln for ln in job.lines)


def test_no_run_id_parsed_when_run_type_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fake(monkeypatch, "print('pulled 252 bars')")
    job = _invoke.launch(["data", "pull", "X"], data_dir=tmp_path, run_type=None)
    _wait(job)
    assert job.status == "done" and job.run_id is None


def test_job_is_registered_for_streaming(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake(monkeypatch, "print('hi')")
    job = _invoke.launch(["validate", "Y"], data_dir=tmp_path, run_type="runs")
    assert _invoke.JOBS[job.job_id] is job


def test_paper_session_id_is_parsed_without_a_research_run_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id = "7e19841c-8bb3-4ab8-aeed-388f56ecfcf8"
    _fake(monkeypatch, f"print('paper BTC/USDT -> session {session_id}: SANDBOX')")
    job = _invoke.launch(["paper", "run", "BTC/USDT"], data_dir=tmp_path, run_type=None)
    _wait(job)
    assert job.session_id == session_id
    assert job.run_id is None
    assert job.summary()["session_id"] == session_id


def test_silent_heavyweight_job_heartbeats_independently_of_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    job_id = "33333333-3333-4333-8333-333333333333"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        return {"status": "ok"}

    monkeypatch.setattr(_invoke, "_run_json", project)
    monkeypatch.setattr(_invoke, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.02)
    _fake(monkeypatch, "import time; time.sleep(0.15)")

    job = _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)
    _wait(job)

    heartbeats = [args for args in calls if args[1:4] == ["job-event", job_id, "heartbeat"]]
    assert len(heartbeats) >= 2
    assert all("--json" in args for args in heartbeats)
    assert calls[-1][1:4] == ["job-status", job_id, "succeeded"]


def test_heavyweight_heartbeat_failure_kills_child_and_fails_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    job_id = "44444444-4444-4444-8444-444444444444"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            raise RuntimeError("heartbeat CLI unavailable")
        return {"status": "ok"}

    monkeypatch.setattr(_invoke, "_run_json", project)
    monkeypatch.setattr(_invoke, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.02)
    _fake(monkeypatch, "import time; time.sleep(30)")

    job = _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)
    _wait(job)

    assert job.status == "failed"
    assert job.returncode is not None
    failed = [args for args in calls if args[1:4] == ["job-status", job_id, "failed"]]
    assert len(failed) == 1
    assert any("heartbeat CLI unavailable" in line for line in job.lines)


def test_successful_process_with_terminal_projection_failure_is_not_reported_done(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    job_id = "45454545-4545-4545-8545-454545454545"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        if args[1:4] == ["job-status", job_id, "succeeded"]:
            raise ValueError("terminal journal returned malformed JSON")
        return {"status": "ok"}

    monkeypatch.setattr(_invoke, "_run_json", project)
    _fake(monkeypatch, "print('completed')")

    job = _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)
    _wait(job)

    assert job.returncode == 0
    assert job.status == "failed"
    assert job.terminal_error is not None
    assert "malformed JSON" in job.terminal_error
    assert any(args[1:4] == ["job-status", job_id, "failed"] for args in calls)


def test_pump_thread_start_failure_reaps_child_before_releasing_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    job_id = "46464646-4646-4646-8646-464646464646"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        return {"status": "ok"}

    original_start = threading.Thread.start
    starts = 0

    def start(thread: threading.Thread) -> None:
        nonlocal starts
        starts += 1
        if starts == 2:
            raise RuntimeError("pump thread resources exhausted")
        original_start(thread)

    cleaned: list[subprocess.Popen[str]] = []

    def cleanup(process: subprocess.Popen[str], **kwargs: object) -> None:
        cleaned.append(process)
        terminate_and_reap(process, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(_invoke, "_run_json", project)
    monkeypatch.setattr(threading.Thread, "start", start)
    monkeypatch.setattr(_invoke, "terminate_and_reap", cleanup)
    _fake(monkeypatch, "import time; time.sleep(30)")

    with pytest.raises(RuntimeError, match="background job monitor"):
        _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)

    assert starts == 2
    assert cleaned and cleaned[0].poll() is not None
    assert job_id not in _invoke.JOBS
    assert any(args[1:4] == ["job-status", job_id, "failed"] for args in calls)


def test_spawn_failure_drops_memory_handle_when_failure_projection_is_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "47474747-4747-4747-8747-474747474747"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        raise ValueError("failure projection returned malformed JSON")

    def spawn_failure(*_args: object, **_kwargs: object) -> subprocess.Popen[str]:
        raise OSError("process table exhausted")

    monkeypatch.setattr(_invoke, "_run_json", project)
    monkeypatch.setattr(subprocess, "Popen", spawn_failure)

    with pytest.raises(OSError, match="process table exhausted"):
        _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)
    assert job_id not in _invoke.JOBS


def test_live_heavyweight_cancel_reaps_a_sigterm_ignoring_nested_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    job_id = "55555555-5555-4555-8555-555555555555"
    ready_path = tmp_path / "workstation-nested-child"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        return {"status": "ok"}

    nested_code = (
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    leader_code = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {nested_code!r}, sys.argv[1]], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "time.sleep(30)\n"
    )
    monkeypatch.setattr(_invoke, "_run_json", project)
    _fake(monkeypatch, leader_code.replace("sys.argv[1]", repr(str(ready_path))))

    job = _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)
    nested_pid: int | None = None
    try:
        deadline = time.monotonic() + 2
        while not ready_path.exists() and not job.finished and time.monotonic() < deadline:
            time.sleep(0.01)
        assert ready_path.exists()
        nested_pid = int(ready_path.read_text(encoding="utf-8"))
        assert _process_is_executing(nested_pid)

        assert _invoke.cancel_job(job.job_id, data_dir=tmp_path) is job
        _wait(job)

        assert job.status == "cancelled"
        deadline = time.monotonic() + 2
        while _process_is_executing(nested_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not _process_is_executing(nested_pid)
        assert any(args[1:4] == ["job-status", job_id, "cancelled"] for args in calls)
    finally:
        process = job._proc
        if process is not None and process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
        if nested_pid is not None and _process_is_executing(nested_pid):
            with contextlib.suppress(ProcessLookupError):
                os.kill(nested_pid, signal.SIGKILL)


def test_durable_startup_status_failure_reaps_the_entire_process_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    job_id = "66666666-6666-4666-8666-666666666666"
    ready_path = tmp_path / "startup-failure-nested-child"

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-status", job_id, "running"]:
            deadline = time.monotonic() + 2
            while not ready_path.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            assert ready_path.exists()
            raise ValueError("durable running status unavailable")
        return {"status": "ok"}

    nested_code = (
        "import os, signal, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        f"Path({str(ready_path)!r}).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    leader_code = (
        "import subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, '-c', {nested_code!r}], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
        "time.sleep(30)\n"
    )
    monkeypatch.setattr(_invoke, "_run_json", project)
    _fake(monkeypatch, leader_code)

    nested_pid: int | None = None
    try:
        with pytest.raises(ValueError, match="durable running status unavailable"):
            _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)

        nested_pid = int(ready_path.read_text(encoding="utf-8"))
        deadline = time.monotonic() + 2
        while _process_is_executing(nested_pid) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert not _process_is_executing(nested_pid)
        assert job_id not in _invoke.JOBS
        assert any(args[1:4] == ["job-status", job_id, "failed"] for args in calls)
    finally:
        retained = _invoke.JOBS.pop(job_id, None)
        process = None if retained is None else retained._proc
        if process is not None and process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
        if nested_pid is not None and _process_is_executing(nested_pid):
            with contextlib.suppress(ProcessLookupError):
                os.kill(nested_pid, signal.SIGKILL)


def test_durable_startup_cleanup_failure_retains_capacity_and_live_handle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "77777777-7777-4777-8777-777777777777"
    calls: list[list[str]] = []

    def project(args: list[str], *, data_dir: Path, **kwargs: object) -> object:
        del kwargs
        assert data_dir == tmp_path
        calls.append(args)
        if args[:2] == ["project", "job-create"]:
            return {"job_id": job_id}
        if args[1:4] == ["job-status", job_id, "running"]:
            raise RuntimeError("durable running status unavailable")
        return {"status": "ok"}

    def failed_cleanup(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise DurableLeaseError("process group still exists after SIGKILL")

    monkeypatch.setattr(_invoke, "_run_json", project)
    monkeypatch.setattr(_invoke, "terminate_and_reap", failed_cleanup)
    _fake(monkeypatch, "import time; time.sleep(30)")

    try:
        with pytest.raises(RuntimeError, match="heavyweight capacity remains reserved"):
            _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)

        retained = _invoke.JOBS[job_id]
        assert retained.finished is False
        assert retained.status == "running"
        assert any("cleanup failed" in line for line in retained.lines)
        assert not any(args[1:4] == ["job-status", job_id, "failed"] for args in calls)
    finally:
        cleanup_job = _invoke.JOBS.pop(job_id) if job_id in _invoke.JOBS else None
        process = None if cleanup_job is None else cleanup_job._proc
        if process is not None and process.poll() is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=1)
        if process is not None and process.stdout is not None:
            process.stdout.close()
