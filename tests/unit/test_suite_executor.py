from __future__ import annotations

import contextlib
import hashlib
import json
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from alpha_cli import _artifacts, _optim, _suite
from alpha_cli._suite import (
    StepExecution,
    SuitePlan,
    SuiteProcessCleanupError,
    SuiteStep,
    _record_optimization_trial_attempts,
    build_suite_plan,
    execute_suite,
    reserve_suite_job,
)
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from tests.fixtures.control_store_fixtures import mark_project_as_migrated_legacy


def _setup(tmp_path: Path) -> tuple[ControlStore, str, str]:
    snapshot_dir = tmp_path / "snapshots" / "frozen"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "manifest.json").write_text(
        json.dumps({"snapshot_id": "frozen", "symbols": {}}, sort_keys=True),
        encoding="utf-8",
    )
    store = ControlStore(tmp_path)
    project = store.create_project(
        name="Suite",
        hypothesis="Momentum persists.",
        falsification_criterion="Reject on failed locked holdout.",
        at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    project_id = str(project["project_id"])
    mark_project_as_migrated_legacy(store, project_id)
    version = store.create_strategy_version(
        project_id,
        strategy_name="ts_momentum",
        source_fingerprint="git:abc",
        definition={"lookback": 5, "skip": 1, "vol_window": 3},
        parameter_space={"lookback": [5, 10]},
    )
    experiment = store.create_experiment_spec(
        project_id,
        strategy_version_id=str(version["version_id"]),
        snapshot_id="frozen",
        universe=["SPY"],
        split_policy={"train": 30, "test": 10, "embargo": 2},
        costs={"fee_bps": 0, "slippage_bps": 0},
        seeds={"master": 7},
    )
    experiment_id = str(experiment["experiment_id"])
    store.seal_holdout(
        project_id,
        experiment_id,
        actor="owner",
        reason="reserve final test window before research",
        start_date="2026-04-01",
        end_date="2026-06-30",
    )
    return store, project_id, experiment_id


def _publish(
    tmp_path: Path,
    run_id: str,
    *,
    passed: bool = True,
    research_cutoff: str = "2026-03-31",
) -> None:
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 3,
                "artifact_contract_version": 3,
                "run_identity_version": 3,
                "run_id": run_id,
                "command": "backtest_run",
                "snapshot_id": "frozen",
                "snapshot_hash": hashlib.sha256(
                    (tmp_path / "snapshots" / "frozen" / "manifest.json").read_bytes()
                ).hexdigest(),
                "execution_fingerprint": "a" * 64,
                "strategy_fingerprint": "b" * 64,
                "source_fingerprint": "c" * 64,
                "research_cutoff": research_cutoff,
                "artifacts": {},
                "passed": passed,
                "outcomes": [{"name": "randomized_price_null", "passed": passed, "detail": {}}],
            }
        ),
        encoding="utf-8",
    )


def test_execution_journals_attempt_result_and_stage_link(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    plan = build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    run_id = "0123456789abcdef"

    def fake(
        step: SuiteStep,
        job_id: str,
        control: ControlStore,
        cancelled: object,
    ) -> StepExecution:
        assert step.argv[:2] == ("backtest", "run")
        control.append_job_event(job_id, event_type="heartbeat", payload={"step": step.label})
        control.append_job_event(job_id, event_type="log", payload={"line": "fake run"})
        _publish(tmp_path, run_id)
        return StepExecution(returncode=0, run_ids=(run_id,))

    completed = execute_suite(store, plan, data_dir=tmp_path, step_runner=fake)
    assert completed["status"] == "succeeded"
    job = store.get_job(str(completed["job_id"]))
    events = cast(list[dict[str, object]], job["events"])
    assert [event["event_type"] for event in events] == [
        "created",
        "status",
        "progress",
        "heartbeat",
        "heartbeat",
        "log",
        "result",
        "status",
    ]
    project = store.get_project(project_id)
    attempts = cast(list[dict[str, object]], project["attempts"])
    assert [attempt["status"] for attempt in attempts] == ["queued", "passed"]
    links = cast(list[dict[str, object]], project["stage_run_links"])
    assert links[0]["run_id"] == run_id
    assert links[0]["state"] == "pass"


def test_suite_evidence_must_match_the_sealed_research_cutoff(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    run_id = "0123456789abcdee"
    _publish(tmp_path, run_id, research_cutoff="2026-04-01")

    with pytest.raises(DataError, match="sealed pre-holdout research cutoff"):
        store.link_suite_stage_run(
            project_id,
            experiment_id,
            suite_action="baseline",
            stage="baseline",
            state="pass",
            run_id=run_id,
        )


def test_grid_trial_ledger_projects_every_configuration_into_attempts(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    run_id = "0123456789abcdea"
    run_dir = tmp_path / "optim" / run_id
    outcomes = (
        _optim.TrialOutcome(
            trial_index=0,
            config=(("lookback", 5.0),),
            config_fingerprint=_optim._config_fingerprint((("lookback", 5.0),)),
            status="passed",
            error=None,
            oos_returns=(0.01, -0.005),
            annualized_sharpe=0.5,
        ),
        _optim.TrialOutcome(
            trial_index=1,
            config=(("lookback", 10.0),),
            config_fingerprint=_optim._config_fingerprint((("lookback", 10.0),)),
            status="failed",
            error="DataError: engine rejected the trial",
            oos_returns=(),
            annualized_sharpe=None,
        ),
        _optim.TrialOutcome(
            trial_index=2,
            config=(("lookback", 15.5),),
            config_fingerprint=_optim._config_fingerprint((("lookback", 15.5),)),
            status="rejected",
            error="DataError: lookback must be integer-valued",
            oos_returns=(),
            annualized_sharpe=None,
        ),
    )
    _optim.write_trial_ledger(run_dir, outcomes)
    _artifacts.write_trials(
        run_dir,
        matrix=np.asarray([[0.01], [-0.005]], dtype=np.float64),
        trial_indices=(0,),
    )
    snapshot_hash = hashlib.sha256(
        (tmp_path / "snapshots" / "frozen" / "manifest.json").read_bytes()
    ).hexdigest()
    _artifacts.write_manifest(
        run_dir,
        {
            "run_id": run_id,
            "run_identity_version": 3,
            "command": "optim_grid",
            "snapshot_id": "frozen",
            "snapshot_hash": snapshot_hash,
            "execution_fingerprint": "a" * 64,
            "strategy_fingerprint": "b" * 64,
            "source_fingerprint": "c" * 64,
            "research_cutoff": "2026-03-31",
            "passed": False,
        },
    )
    plan = SuitePlan(
        schema_version=1,
        project_id=project_id,
        experiment_id=experiment_id,
        action="optimize_grid",
        stage="optimization",
        ready=True,
        blockers=(),
        resolved_experiment={},
        resolved_strategy_version={},
        current_stage_state="ready",
        estimated_workload={},
        steps=(),
        governance={},
    )

    _record_optimization_trial_attempts(
        store,
        plan,
        data_dir=tmp_path,
        job_id="4d0d46e2-6625-47b8-a6e6-55bb04461364",
        run_ids=(run_id,),
    )

    attempts = cast(list[dict[str, object]], store.get_project(project_id)["attempts"])
    assert [attempt["status"] for attempt in attempts] == ["passed", "failed", "rejected"]
    assert [attempt["config_fingerprint"] for attempt in attempts] == [
        outcome.config_fingerprint for outcome in outcomes
    ]
    assert attempts[1]["error"] == "DataError: engine rejected the trial"
    assert cast(dict[str, object], attempts[2]["details"])["reason"] == (
        "DataError: lookback must be integer-valued"
    )


def test_failed_execution_is_terminal_and_audited(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    plan = build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)

    def failed(
        _step: SuiteStep,
        _job_id: str,
        _control: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        return StepExecution(returncode=9, run_ids=())

    with pytest.raises(DataError, match="exit 9"):
        execute_suite(store, plan, data_dir=tmp_path, step_runner=failed)
    jobs = store.list_jobs()
    assert jobs[0]["status"] == "failed"
    attempts = cast(list[dict[str, object]], store.get_project(project_id)["attempts"])
    assert [attempt["status"] for attempt in attempts] == ["queued", "failed"]
    stage = next(
        row
        for row in cast(list[dict[str, object]], store.get_project(project_id)["stage_states"])
        if row["stage"] == "baseline"
    )
    assert stage["state"] == "fail"


def test_unverified_suite_cleanup_keeps_heavyweight_capacity_reserved(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    baseline = build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    plan = replace(baseline, action="qlib", stage="ml", current_stage_state="not_started")

    def cleanup_failed(
        _step: SuiteStep,
        _job_id: str,
        _control: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        raise SuiteProcessCleanupError("suite process group still exists after SIGKILL")

    with pytest.raises(SuiteProcessCleanupError, match="still exists after SIGKILL"):
        execute_suite(store, plan, data_dir=tmp_path, step_runner=cleanup_failed)

    job = store.list_jobs()[0]
    assert job["status"] == "running"
    assert job["terminal_error"] is None
    assert store.heavyweight_job_capacity()["busy"] is True
    attempts = cast(list[dict[str, object]], store.get_project(project_id)["attempts"])
    assert [attempt["status"] for attempt in attempts] == ["queued", "failed"]
    assert cast(dict[str, object], attempts[-1]["details"])["cleanup_unverified"] is True
    stage = next(
        row
        for row in cast(list[dict[str, object]], store.get_project(project_id)["stage_states"])
        if row["stage"] == "ml"
    )
    assert stage["state"] == "running"
    events = cast(list[dict[str, object]], store.get_job(str(job["job_id"]))["events"])
    assert "heavyweight capacity remains reserved" in str(events[-1]["payload"])


def test_reserved_suite_observes_durable_cancellation_before_first_step(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    plan = build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    job_id = "5b139934-aaf0-49a1-83e5-82be78b62c87"
    reserved = reserve_suite_job(store, plan, job_id=job_id)
    assert reserved["status"] == "queued"
    store.request_job_cancellation(job_id, actor="codex", reason="scope changed")

    called = False

    def must_not_run(
        _step: SuiteStep,
        _job_id: str,
        _control: ControlStore,
        _cancelled: object,
    ) -> StepExecution:
        nonlocal called
        called = True
        return StepExecution(returncode=0, run_ids=())

    with pytest.raises(InterruptedError, match="cancelled"):
        execute_suite(store, plan, data_dir=tmp_path, job_id=job_id, step_runner=must_not_run)
    assert called is False
    assert store.get_job(job_id)["status"] == "cancelled"


def test_heavyweight_job_creation_is_atomic_and_serialized(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    with pytest.raises(DataError, match="reserved"):
        store.create_job(
            kind="suite:kronos",
            request={"action": "kronos"},
            project_id=project_id,
            experiment_id=experiment_id,
        )
    store.create_suite_job(
        kind="suite:kronos",
        request={"action": "kronos"},
        project_id=project_id,
        experiment_id=experiment_id,
    )
    with pytest.raises(DataError, match="capacity is occupied"):
        store.create_suite_job(
            kind="suite:qlib",
            request={"action": "qlib"},
            project_id=project_id,
            experiment_id=experiment_id,
        )


def test_direct_and_suite_heavyweight_requests_share_atomic_capacity(tmp_path: Path) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    barrier = threading.Barrier(2)

    def reserve_direct() -> tuple[str, str]:
        barrier.wait()
        try:
            ControlStore(tmp_path).create_job(
                kind="ml_train",
                request={"surface": "direct"},
                job_id="03030303-0303-4303-8303-030303030303",
            )
        except DataError as exc:
            return "blocked", str(exc)
        return "admitted", "direct"

    def reserve_suite() -> tuple[str, str]:
        barrier.wait()
        try:
            ControlStore(tmp_path).create_suite_job(
                kind="suite:kronos",
                request={"action": "kronos"},
                project_id=project_id,
                experiment_id=experiment_id,
                job_id="04040404-0404-4404-8404-040404040404",
            )
        except DataError as exc:
            return "blocked", str(exc)
        return "admitted", "suite"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [pool.submit(reserve_direct), pool.submit(reserve_suite)]
    resolved = [future.result() for future in results]
    assert sorted(status for status, _ in resolved) == ["admitted", "blocked"]

    admitted_job = next(
        row for row in store.list_jobs(limit=10) if row["status"] in {"queued", "running"}
    )
    store.set_job_status(str(admitted_job["job_id"]), "failed", terminal_error="test complete")
    released = store.create_suite_job(
        kind="suite:qlib",
        request={"action": "qlib"},
        project_id=project_id,
        experiment_id=experiment_id,
        job_id="05050505-0505-4505-8505-050505050505",
    )
    assert released["status"] == "queued"
    assert store.heavyweight_job_capacity()["active_count"] == 1


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="requires POSIX process groups")
def test_suite_selector_initialization_failure_reaps_spawned_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _project_id, _experiment_id = _setup(tmp_path)
    original_popen = subprocess.Popen
    captured: dict[str, subprocess.Popen[str]] = {}

    def launch(_command: list[str], **kwargs: object) -> subprocess.Popen[str]:
        assert kwargs["start_new_session"] is True
        process = original_popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        captured["process"] = process
        return process

    def selector_failure() -> object:
        raise OSError("selector allocation exhausted")

    monkeypatch.setattr("alpha_cli._suite.subprocess.Popen", launch)
    monkeypatch.setattr(selectors, "DefaultSelector", selector_failure)
    step = SuiteStep(
        label="selector guard",
        argv=("ignored",),
        preview=("alpha", "ignored"),
        evidence_role="cleanup regression",
    )

    with pytest.raises(OSError, match="selector allocation exhausted"):
        _suite._default_step_runner(
            step,
            "06060606-0606-4606-8606-060606060606",
            store,
            lambda: False,
        )

    process = captured["process"]
    assert process.poll() is not None
    assert _suite._process_group_exists(process.pid) is False


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="requires POSIX process groups")
def test_suite_heartbeats_and_cancels_after_leader_exits_with_live_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, _project_id, _experiment_id = _setup(tmp_path)
    job_id = "08080808-0808-4808-8808-080808080808"
    store.create_job(kind="ml_train", request={"test": "suite descendant"}, job_id=job_id)
    store.set_job_status(job_id, "running")
    ready_path = tmp_path / "suite-descendant.pid"
    nested_code = (
        "import os, signal, sys, time\n"
        "from pathlib import Path\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "Path(sys.argv[1]).write_text(str(os.getpid()), encoding='utf-8')\n"
        "time.sleep(30)\n"
    )
    leader_code = (
        "import subprocess, sys\n"
        f"subprocess.Popen([sys.executable, '-c', {nested_code!r}, sys.argv[1]])\n"
    )
    original_popen = subprocess.Popen
    captured: dict[str, subprocess.Popen[str]] = {}

    def launch(_command: list[str], **kwargs: object) -> subprocess.Popen[str]:
        assert kwargs["start_new_session"] is True
        process = original_popen(
            [sys.executable, "-c", leader_code, str(ready_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        captured["process"] = process
        return process

    def heartbeat_seen() -> bool:
        events = cast(list[dict[str, object]], store.get_job(job_id)["events"])
        return any(event["event_type"] == "heartbeat" for event in events)

    monkeypatch.setattr("alpha_cli._suite.subprocess.Popen", launch)
    monkeypatch.setattr(_suite, "_SUITE_HEARTBEAT_INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(_suite, "_PROCESS_TERM_GRACE_SECONDS", 0.1)
    monkeypatch.setattr(_suite, "_PROCESS_REAP_TIMEOUT_SECONDS", 1.0)
    step = SuiteStep(
        label="descendant lease",
        argv=("ignored",),
        preview=("alpha", "ignored"),
        evidence_role="heartbeat regression",
    )

    nested_pid: int | None = None
    try:
        execution = _suite._default_step_runner(step, job_id, store, heartbeat_seen)
        nested_pid = int(ready_path.read_text(encoding="utf-8"))
        assert captured["process"].poll() == 0
        assert execution.returncode == 0
        assert heartbeat_seen()
        deadline = time.monotonic() + 1
        while process_exists := _suite._process_group_exists(captured["process"].pid):
            if time.monotonic() >= deadline:
                break
            time.sleep(0.01)
        assert process_exists is False
    finally:
        process = captured.get("process")
        if process is not None and _suite._process_group_exists(process.pid):
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=1)
        if nested_pid is not None:
            with contextlib.suppress(ProcessLookupError):
                os.kill(nested_pid, signal.SIGKILL)


def test_suite_cleanup_normalizes_unexpected_verification_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        pid = 12345

        @staticmethod
        def poll() -> None:
            return None

    def cleanup_failure(_process: subprocess.Popen[str]) -> None:
        raise PermissionError("process group state unavailable")

    monkeypatch.setattr(_suite, "_process_group_exists", lambda _process_group_id: True)
    monkeypatch.setattr(_suite, "_terminate_process_group", cleanup_failure)

    with pytest.raises(SuiteProcessCleanupError, match="cleanup could not be verified"):
        _suite._cleanup_process_group(cast(subprocess.Popen[str], FakeProcess()))


def test_suite_cleanup_failure_has_priority_over_resource_close_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingStdout:
        @staticmethod
        def close() -> None:
            raise OSError("stdout close failed")

    class FakeProcess:
        pid = 12345
        stdout = FailingStdout()

    class FailingSelector:
        @staticmethod
        def register(_stream: object, _events: object) -> None:
            raise RuntimeError("selector registration failed")

        @staticmethod
        def close() -> None:
            raise OSError("selector close failed")

    fake_process = cast(subprocess.Popen[str], FakeProcess())

    def launch(_command: list[str], **_kwargs: object) -> subprocess.Popen[str]:
        return fake_process

    def cleanup_failed(_process: subprocess.Popen[str]) -> None:
        raise SuiteProcessCleanupError("suite process group still exists after SIGKILL")

    monkeypatch.setattr("alpha_cli._suite.subprocess.Popen", launch)
    monkeypatch.setattr(
        selectors,
        "DefaultSelector",
        lambda: cast(selectors.BaseSelector, FailingSelector()),
    )
    monkeypatch.setattr(_suite, "_cleanup_process_group", cleanup_failed)
    step = SuiteStep(
        label="cleanup priority",
        argv=("ignored",),
        preview=("alpha", "ignored"),
        evidence_role="cleanup regression",
    )

    with pytest.raises(SuiteProcessCleanupError, match="still exists after SIGKILL") as caught:
        _suite._default_step_runner(
            step,
            "07070707-0707-4707-8707-070707070707",
            cast(ControlStore, object()),
            lambda: False,
        )
    assert "selector close failed" in " ".join(caught.value.__notes__)


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="requires POSIX process groups")
def test_suite_cancellation_kills_and_reaps_nested_worker_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store, project_id, experiment_id = _setup(tmp_path)
    plan = build_suite_plan(store, project_id, experiment_id, "baseline", data_dir=tmp_path)
    nested_pid_path = tmp_path / "nested-worker.pid"
    original_popen = subprocess.Popen
    captured: dict[str, int] = {}
    script = "\n".join(
        [
            "import signal",
            "import subprocess",
            "import sys",
            "import time",
            "from pathlib import Path",
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)",
            (
                "child_code = 'import signal,time; "
                "signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)'"
            ),
            "child = subprocess.Popen([sys.executable, '-c', child_code])",
            "Path(sys.argv[1]).write_text(str(child.pid), encoding='utf-8')",
            "print('nested worker ready', flush=True)",
            "time.sleep(60)",
        ]
    )

    def launch(_command: list[str], **kwargs: object) -> subprocess.Popen[str]:
        assert kwargs["start_new_session"] is True
        process = original_popen(
            [sys.executable, "-c", script, str(nested_pid_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,
        )
        captured["process_group_id"] = process.pid
        return process

    def nested_ready() -> bool:
        try:
            return bool(nested_pid_path.read_text(encoding="utf-8").strip())
        except OSError:
            return False

    def process_exists(process_id: int) -> bool:
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return False
        return True

    def process_group_exists(process_group_id: int) -> bool:
        try:
            os.killpg(process_group_id, 0)
        except ProcessLookupError:
            return False
        return True

    monkeypatch.setattr("alpha_cli._suite.subprocess.Popen", launch)
    monkeypatch.setattr(_suite, "_PROCESS_TERM_GRACE_SECONDS", 0.1)
    monkeypatch.setattr(_suite, "_PROCESS_REAP_TIMEOUT_SECONDS", 1.0)

    with pytest.raises(InterruptedError, match="cancelled"):
        execute_suite(store, plan, data_dir=tmp_path, cancelled=nested_ready)

    process_group_id = captured["process_group_id"]
    nested_pid = int(nested_pid_path.read_text(encoding="utf-8"))
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline and (
        process_group_exists(process_group_id) or process_exists(nested_pid)
    ):
        time.sleep(0.02)
    group_orphaned = process_group_exists(process_group_id)
    child_orphaned = process_exists(nested_pid)
    try:
        assert group_orphaned is False
        assert child_orphaned is False
        assert store.list_jobs()[0]["status"] == "cancelled"
    finally:
        if group_orphaned:
            os.killpg(process_group_id, signal.SIGKILL)
        elif child_orphaned:
            os.kill(nested_pid, signal.SIGKILL)
