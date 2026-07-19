"""The web IDE's job runner: launch `alpha`, capture streaming output, parse the run id.

Uses a fast fake command (a tiny `python -c`) in place of the real CLI so the lifecycle —
capture, run-id parse, terminal status — is exercised without the engine.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from alpha_web import _invoke


def _fake(monkeypatch: pytest.MonkeyPatch, script: str) -> None:
    cmd: Callable[[list[str]], list[str]] = lambda args: ["python", "-c", script]  # noqa: E731
    monkeypatch.setattr(_invoke, "_command", cmd)


def _wait(job: _invoke.Job, timeout: float = 5.0) -> None:
    end = time.time() + timeout
    while not job.finished and time.time() < end:
        time.sleep(0.02)
    assert job.finished, "job did not finish in time"


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
