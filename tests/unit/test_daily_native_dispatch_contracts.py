"""Portable artificial dispatch contracts; these do not accept a native process or market study.

The profile/source/image measurements are deterministic external-runtime test ports. The frozen
study, normalized query, immutable snapshots, consumed owner confirmation, D0 receipt, typed
NativeLaunch, ControlStore transactions and reconnect/cancellation reads are the real code.
The worker transport returns no result and never claims that scientific execution completed.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from alpha_cli import daily_native_cmds
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli.control_store import ControlStore
from alpha_cli.main import app
from alpha_core import DataError
from tests.unit import test_native_daily_rule_lifecycle as lifecycle
from tests.unit.test_research_control_store import PROJECT_ID


@dataclass(frozen=True)
class PortableCase:
    root: Path
    store: ControlStore
    contract_id: str
    runtime_profile: Path
    launch: NativeLaunch


@pytest.fixture
def portable_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> PortableCase:
    import alpha_cli._native_daily_rule_container as container
    import alpha_cli._native_loop_admission as admission
    import alpha_cli._native_rule_environment as runtime

    source = tmp_path / "artificial-runtime-port"
    source.mkdir()
    profile = source / "profile.json"
    profile.write_text('{"schema":"ArtificialRuntimeMeasurementPortV1","revision":1}')

    def measure(costed: bool = False) -> str:
        assert costed is True
        return hashlib.sha256(profile.read_bytes()).hexdigest()

    def proposal(selected: Path, mode: str, study: object = None) -> str:
        assert selected == source and mode == "INCONCLUSIVE"
        assert isinstance(study, DailyRuleStudyV1)
        return hashlib.sha256(
            json.dumps(
                {
                    "profile": measure(True),
                    "study": study.content_sha256,
                    "implementation": runtime.rule_implementation_fingerprints(
                        True, daily_study=study
                    ),
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

    for module in (runtime, lifecycle):
        monkeypatch.setattr(module, "measure_rule_environment", measure)
    monkeypatch.setattr(
        container,
        "daily_container_profile",
        lambda: {
            "image_id": "sha256:" + hashlib.sha256(b"artificial image identity port").hexdigest(),
        },
    )
    monkeypatch.setattr(admission, "measure_native_proposal", proposal)
    monkeypatch.setenv("ALPHA_RDAGENT_SOURCE", str(source))
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    store, contract_id, launch = lifecycle._case(tmp_path, monkeypatch, source)
    return PortableCase(tmp_path, store, contract_id, profile, launch)


def _deep() -> dict[str, Any]:
    result = CliRunner().invoke(app, ["research", "run", "deep", PROJECT_ID, "--json"])
    assert result.exit_code == 0, result.output
    value = json.loads(result.output)
    assert isinstance(value, dict)
    return value


def _jobs(store: ControlStore) -> list[dict[str, object]]:
    with store._transaction(write=False) as connection:
        return [
            dict(row)
            for row in connection.execute(
                "SELECT job_id,status,request_json FROM jobs WHERE project_id=? ORDER BY job_id",
                (PROJECT_ID,),
            ).fetchall()
        ]


def test_public_daily_launch_reserves_once_and_cancel_reconnect_never_replaces_owner(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = portable_case
    starts: list[str] = []

    class WaitingTransport:
        def wait(self, *, timeout: float) -> int:
            assert timeout == pytest.approx(79)
            return 0

    def dispatch(root: Path, job_id: str, *, native: NativeLaunch, seconds: float) -> Any:
        assert root == case.root
        assert native.study == case.launch.study
        assert native.authority == case.launch.authority
        assert seconds == pytest.approx(59)
        starts.append(job_id)
        return WaitingTransport()

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", dispatch)
    first = _deep()
    job_id = first["job_id"]
    assert starts == [job_id]
    assert first["native"] == {"claim": None, "state": "unclaimed"}
    reserved = lifecycle._reservations(case.store)
    assert len(reserved) == 2  # The genuine D0 and the one pre-effect native envelope.
    jobs = _jobs(case.store)
    status = case.store.cancel_native_fixture(job_id, reason="Artificial cancellation contract")
    assert status == {"claim": None, "state": "unclaimed"}
    for _ in range(2):
        reopened = _deep()
        assert reopened["job_id"] == job_id and reopened["reconnected"] is True
        assert "attempt" not in reopened
    assert starts == [job_id]
    assert _jobs(case.store) == jobs
    assert lifecycle._reservations(case.store) == reserved
    with case.store._transaction(write=False) as connection:
        assert case.store._active_job_cancellation(connection, job_id)


def test_public_timeout_keeps_the_same_charged_unclaimed_job(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[str] = []

    class SlowTransport:
        def wait(self, *, timeout: float) -> int:
            raise subprocess.TimeoutExpired("artificial worker transport", timeout)

    def dispatch(root: Path, job_id: str, **kwargs: Any) -> Any:
        starts.append(job_id)
        return SlowTransport()

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", dispatch)
    first = _deep()
    assert first["reconnected"] is False
    reserved = lifecycle._reservations(portable_case.store)
    second = _deep()
    assert second["reconnected"] is True
    assert first["job_id"] == second["job_id"]
    assert starts == [first["job_id"]]
    assert lifecycle._reservations(portable_case.store) == reserved


def test_uncertain_worker_start_reports_existing_job_and_reconnects_without_retry(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[str] = []

    def unavailable(root: Path, job_id: str, **kwargs: Any) -> Any:
        starts.append(job_id)
        raise OSError("artificial worker transport lost its start response")

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", unavailable)
    failed = CliRunner().invoke(app, ["research", "run", "deep", PROJECT_ID, "--json"])
    assert failed.exit_code != 0
    assert len(starts) == 1
    assert starts[0] in failed.output and "uncertain" in failed.output
    reserved = lifecycle._reservations(portable_case.store)
    assert len(reserved) == 2
    reopened = _deep()
    assert reopened["reconnected"] is True and reopened["job_id"] == starts[0]
    assert starts == [reopened["job_id"]]
    assert lifecycle._reservations(portable_case.store) == reserved


@pytest.mark.parametrize("boundary", ["queue_commit", "create_commit", "reserve_commit"])
def test_public_pre_dispatch_response_loss_preserves_original_identity_and_accounting(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch, boundary: str
) -> None:
    case = portable_case
    transition = ControlStore.transition_research_execution
    create = ControlStore.create_research_job
    reserve = ControlStore.reserve_d1_native_research_launch
    known: list[str] = []

    def lose_queue(*args: Any, **kwargs: Any) -> Any:
        result = transition(*args, **kwargs)
        if kwargs.get("to_state") == "queued":
            known.append(str(kwargs["checkpoint"]).removeprefix("daily-native:queued:"))
            raise OSError("artificial lost queue acknowledgement")
        return result

    def lose_create(*args: Any, **kwargs: Any) -> Any:
        create(*args, **kwargs)
        known.append(str(kwargs["job_id"]))
        raise OSError("artificial lost job acknowledgement")

    def lose_reserve(*args: Any, **kwargs: Any) -> Any:
        reserve(*args, **kwargs)
        known.append(str(args[3]))
        raise OSError("artificial lost reservation acknowledgement")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("uncertain pre-dispatch preparation reached worker transport")

    if boundary == "queue_commit":
        monkeypatch.setattr(ControlStore, "transition_research_execution", lose_queue)
    elif boundary == "create_commit":
        monkeypatch.setattr(ControlStore, "create_research_job", lose_create)
    else:
        monkeypatch.setattr(ControlStore, "reserve_d1_native_research_launch", lose_reserve)
    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden)
    failed = CliRunner().invoke(app, ["research", "run", "deep", PROJECT_ID, "--json"])
    assert failed.exit_code != 0
    assert len(known) == 1
    assert known[0] in failed.output
    assert "do not launch a replacement" in failed.output
    reserved = lifecycle._reservations(case.store)
    jobs = _jobs(case.store)
    budgets = case.store.research_case_summary(PROJECT_ID)
    for _ in range(2):
        reopened = _deep()
        assert reopened["job_id"] == known[0]
        assert reopened["reconnected"] is True
        if boundary != "reserve_commit":
            assert reopened["state"] == "pre_dispatch_interrupted"
            assert reopened["job_recorded"] is (boundary == "create_commit")
            assert reopened["reservation_recorded"] is False
        assert lifecycle._reservations(case.store) == reserved
        assert _jobs(case.store) == jobs
        current = case.store.research_case_summary(PROJECT_ID)
        assert current["elapsed_budget"] == budgets["elapsed_budget"]
        assert current["remaining_budget"] == budgets["remaining_budget"]
    assert len(known) == 1


@pytest.mark.parametrize("drift", ["runtime_profile", "storage_config", "source_unconfigured"])
def test_changed_frozen_inputs_or_missing_runtime_deny_public_dispatch_without_effects(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch, drift: str
) -> None:
    case = portable_case
    reserved = lifecycle._reservations(case.store)
    if drift == "runtime_profile":
        case.runtime_profile.write_text(
            '{"schema":"ArtificialRuntimeMeasurementPortV1","revision":2}'
        )
    elif drift == "storage_config":
        (case.root / "crypto/storage-config.json").write_text('{"changed":true}')
    else:
        monkeypatch.delenv("ALPHA_RDAGENT_SOURCE")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("changed frozen inputs reached worker transport")

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden)
    failed = CliRunner().invoke(app, ["research", "run", "deep", PROJECT_ID, "--json"])
    assert failed.exit_code != 0
    expected = {
        "runtime_profile": "code/runtime differs",
        "storage_config": "storage profile changed",
        "source_unconfigured": "ALPHA_RDAGENT_SOURCE",
    }
    assert expected[drift] in failed.output
    assert _jobs(case.store) == []
    assert lifecycle._reservations(case.store) == reserved


def test_changed_workspace_binding_denies_reconnect_without_new_dispatch_or_refund(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    starts: list[str] = []

    class WaitingTransport:
        def wait(self, *, timeout: float) -> int:
            return 0

    def dispatch(root: Path, job_id: str, **kwargs: Any) -> Any:
        starts.append(job_id)
        return WaitingTransport()

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", dispatch)
    first = _deep()
    reserved = lifecycle._reservations(portable_case.store)
    marker = portable_case.root / "daily-rule-workspace.json"
    original = marker.read_bytes()
    binding = json.loads(original)
    binding["root"] = str(portable_case.root / "foreign")
    marker.write_text(json.dumps(binding))
    failed = CliRunner().invoke(app, ["research", "run", "deep", PROJECT_ID, "--json"])
    assert failed.exit_code != 0
    assert "workspace binding differs" in failed.output
    assert starts == [first["job_id"]]
    assert lifecycle._reservations(portable_case.store) == reserved
    marker.write_bytes(original)
    assert _deep()["job_id"] == first["job_id"]
    assert starts == [first["job_id"]]


def test_nonidle_daily_case_does_not_infer_another_launch(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = portable_case
    case.store.transition_research_execution(
        PROJECT_ID,
        to_state="blocked",
        contract_id=case.contract_id,
        actor="test-agent",
        reason="Artificial block",
        next_action="Inspect the explicit block",
        responsibility="owner",
        blocker="Artificial preparation block",
        recovery="Owner inspects without dispatch",
    )

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("blocked case reached worker transport")

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden)
    with pytest.raises(DataError, match="idle approved D1"):
        daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=case.root)
    assert _jobs(case.store) == []
    assert len(lifecycle._reservations(case.store)) == 1
