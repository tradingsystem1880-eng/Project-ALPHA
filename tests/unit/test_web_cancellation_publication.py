"""Cancellation reports physical cleanup and authoritative publication separately."""

from __future__ import annotations

import contextlib
import sys
import time
from pathlib import Path
from typing import Any, Literal, cast

import pytest

from alpha_cli import durable_lease
from alpha_cli.control_store import ControlStore
from alpha_web import _catalog, _invoke


@pytest.mark.parametrize(
    "outcome",
    ["normal", "before_commit", "after_commit", "read_unavailable", "conflict", "cleanup_failure"],
)
def test_cancel_publication_is_truthful_and_never_repeats_a_terminal_transition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    store = ControlStore(tmp_path)
    job_id = "77777777-7777-4777-8777-777777777777"
    writes: list[str] = []
    reads: list[str] = []

    def project(args: list[str], **kwargs: Any) -> object:
        assert kwargs["data_dir"] == tmp_path
        if args[1] == "job-create":
            return store.create_job(kind="ml_train", request={"fixture": True}, job_id=job_id)
        if args[1] == "job-event":
            store.request_job_cancellation(job_id, actor="owner", reason="fixture stop")
            store.append_job_event(job_id, event_type="heartbeat", payload={"fixture": True})
            return {"cancel_requested": True}
        if args[1] == "job-show":
            reads.append(args[1])
            if outcome == "read_unavailable":
                raise RuntimeError("read unavailable")
            return store.get_job(job_id, event_limit=1, event_tail=True)
        assert args[1] == "job-status"
        status = cast(Literal["running", "cancelled", "succeeded"], args[3])
        if status == "running":
            return store.set_job_status(job_id, status)
        writes.append(status)
        assert writes == ["cancelled"]
        if outcome in {"before_commit", "read_unavailable"}:
            raise RuntimeError("publication unavailable before commit")
        if outcome == "conflict":
            store.set_job_status(job_id, "succeeded")
            raise RuntimeError("another terminal outcome committed")
        row = store.set_job_status(job_id, status)
        if outcome == "after_commit":
            raise RuntimeError("publication response lost")
        return row

    monkeypatch.setattr(_invoke, "_run_json", project)
    monkeypatch.setattr(_invoke, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.01)
    monkeypatch.setattr(
        _invoke, "_command", lambda args: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    if outcome == "cleanup_failure":
        original_cleanup = durable_lease.terminate_and_reap

        def uncertain_cleanup(*args: Any, **kwargs: Any) -> None:
            original_cleanup(*args, **kwargs)
            raise durable_lease.DurableLeaseError("cleanup verification unavailable")

        monkeypatch.setattr(durable_lease, "terminate_and_reap", uncertain_cleanup)
    job = _invoke.launch(["forecast", "run", "SPY"], data_dir=tmp_path, run_type=None)
    try:
        deadline = time.monotonic() + 4
        while not job.finished and time.monotonic() < deadline:
            time.sleep(0.01)
        assert job.finished
        assert job._proc is not None and job._proc.poll() is not None
        verified = outcome in {"normal", "after_commit"}
        assert job.status == ("cancelled" if verified else "failed")
        assert (job.terminal_error is None) == verified
        row = store.get_job(job_id)
        expected = (
            "cancelled" if verified else ("succeeded" if outcome == "conflict" else "running")
        )
        assert row["status"] == expected
        assert store.heavyweight_job_capacity()["active_count"] == (expected == "running")
        events = cast(list[dict[str, Any]], row["events"])
        terminal_events = [
            e for e in events if e["event_type"] == "status" and e["payload"]["to"] != "running"
        ]
        assert len(terminal_events) == (expected != "running")
        assert writes == ([] if outcome == "cleanup_failure" else ["cancelled"])
        assert len(reads) == (outcome not in {"normal", "cleanup_failure"})
    finally:
        if job._proc is not None:
            with contextlib.suppress(ProcessLookupError):
                job._proc.kill()
            job._proc.wait(timeout=2)
        _invoke.JOBS.pop(job.job_id, None)


def test_cancel_publication_cli_timeout_keeps_capacity_within_existing_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = ControlStore(tmp_path)
    job_id = "88888888-8888-4888-8888-888888888888"
    store.create_job(kind="ml_train", request={"fixture": True}, job_id=job_id)
    store.set_job_status(job_id, "running")
    job = _invoke.Job([], None, job_id=job_id, durable=True)
    job.cancelled = True  # Owner request must not mask publication failure.
    calls: list[str] = []

    def stalled_cli(args: list[str], **kwargs: Any) -> object:
        calls.append(args[1])
        return _catalog._run_json(args, **kwargs)

    monkeypatch.setattr(_invoke, "_run_json", stalled_cli)
    monkeypatch.setattr(_invoke, "_DURABLE_HEARTBEAT_TIMEOUT_S", 0.1)
    monkeypatch.setattr(
        _catalog, "_command", lambda args: [sys.executable, "-c", "import time; time.sleep(30)"]
    )
    started = time.monotonic()
    with pytest.raises(RuntimeError, match="terminal state remains unverified.*timed out") as error:
        _invoke._mark_durable_cancelled(job, data_dir=tmp_path)
    assert time.monotonic() - started < 1
    assert calls == ["job-status"]  # No extra subprocess after the budget expires.
    job.terminal_error = str(error.value)
    job.finished = True
    assert job.status == "failed"
    assert store.get_job(job_id)["status"] == "running"
    assert store.heavyweight_job_capacity()["active_count"] == 1
