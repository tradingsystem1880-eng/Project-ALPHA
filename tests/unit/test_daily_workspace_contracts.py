"""Shared-root workspace contracts with artificial data and an external transport port.

Two owner-confirmed projects share immutable inputs and separate D0 history. Only one D1
study exposure is permitted. These tests do not accept a worker, process or native result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import daily_native_cmds
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_loop_admission import NativeLaunch
from alpha_cli._native_rule_authority import RuleAuthority
from alpha_cli.native_supervisor import prepare_daily_workspace, start_daily_owner
from alpha_core import DataError
from tests.unit.test_daily_native_dispatch_contracts import PortableCase
from tests.unit.test_daily_native_dispatch_contracts import portable_case as portable_case
from tests.unit.test_native_daily_rule_lifecycle import _case, _reservations
from tests.unit.test_research_control_store import PROJECT_ID

SECOND = "cc55f253-3ffc-4b03-bd81-5343f29357df"
JOB = "e855f253-3ffc-4b03-bd81-5343f29357df"


def _second(case: PortableCase, monkeypatch: pytest.MonkeyPatch) -> tuple[str, NativeLaunch]:
    assert isinstance(case.launch.study, DailyRuleStudyV1)
    _, contract_id, launch = _case(
        case.root,
        monkeypatch,
        case.launch.source,
        project_id=SECOND,
        study=case.launch.study,
        prepare_workspace=False,
    )
    return contract_id, launch


def _project_reservations(case: PortableCase, project_id: str) -> list[dict[str, object]]:
    return [row for row in _reservations(case.store) if row["project_id"] == project_id]


def _immutable_inputs(case: PortableCase) -> dict[str, bytes]:
    return {
        str(path.relative_to(case.root)): path.read_bytes()
        for name in ("bulk", "crypto", "control/crypto")
        for path in (case.root / name).rglob("*")
        if path.is_file()
    }


def test_two_approved_projects_share_root_without_transferring_or_resetting_study_exposure(
    portable_case: PortableCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = portable_case
    first_contract = case.store.get_research_contract(case.contract_id)
    first_summary = case.store.research_case_summary(PROJECT_ID)
    first_reservations = _project_reservations(case, PROJECT_ID)
    inputs = _immutable_inputs(case)
    cid, second = _second(case, monkeypatch)
    assert second.study == case.launch.study
    assert cid != case.contract_id
    assert _immutable_inputs(case) == inputs
    assert len(_project_reservations(case, SECOND)) == 1  # Independent genuine D0 only.
    assert case.launch.authority is not None and second.authority is not None
    prepare_daily_workspace(case.launch.authority)
    prepare_daily_workspace(second.authority)
    marker = case.root / "daily-rule-workspace.json"
    marker_before = marker.read_bytes()
    assert json.loads(marker_before) == {"schema": "DailyRuleWorkspaceV2", "root": str(case.root)}
    starts: list[tuple[str, str]] = []

    class NoResultTransport:
        def wait(self, *, timeout: float) -> int:
            assert timeout == pytest.approx(79)
            return 0

    def dispatch(root: Path, job_id: str, *, native: NativeLaunch, seconds: float) -> Any:
        assert root == case.root and native.authority is not None
        # Keep the actual workspace boundary in the transport port. No process is started.
        prepare_daily_workspace(native.authority)
        assert seconds == pytest.approx(59)
        starts.append((native.authority.project_id, job_id))
        return NoResultTransport()

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", dispatch)
    result = daily_native_cmds.run_daily_deep(SECOND, data_dir=case.root)
    assert starts == [(SECOND, result["job_id"])]
    assert result["native"] == {"claim": None, "state": "unclaimed"}
    charged = _reservations(case.store)
    assert len(charged) == 3  # First D0, second D0 and the sole study-wide native allowance.
    assert case.store.get_research_contract(case.contract_id) == first_contract
    assert case.store.research_case_summary(PROJECT_ID) == first_summary
    assert _project_reservations(case, PROJECT_ID) == first_reservations
    assert marker.read_bytes() == marker_before
    for _ in range(2):
        reopened = daily_native_cmds.run_daily_deep(SECOND, data_dir=case.root)
        assert reopened["job_id"] == result["job_id"] and reopened["reconnected"] is True
    assert starts == [(SECOND, result["job_id"])]
    assert _reservations(case.store) == charged
    # A second project never establishes a new numerical allowance for identical frozen inputs.
    with pytest.raises(DataError, match="could not confirm its reservation") as denied:
        daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=case.root)
    assert isinstance(denied.value.__cause__, DataError)
    assert "capacity" in str(denied.value.__cause__)
    interrupted = daily_native_cmds.run_daily_deep(PROJECT_ID, data_dir=case.root)
    assert interrupted["state"] == "pre_dispatch_interrupted"
    assert interrupted["reconnected"] is True and interrupted["reservation_recorded"] is False
    assert starts == [(SECOND, result["job_id"])]
    assert _reservations(case.store) == charged


def test_legacy_project_marker_remains_unchanged_but_is_not_cross_project_authority(
    portable_case: PortableCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = portable_case
    cid, second = _second(case, monkeypatch)
    assert second.authority is not None
    marker = case.root / "daily-rule-workspace.json"
    legacy = json.dumps(
        {"schema": "DailyRuleWorkspaceV1", "root": str(case.root), "project_id": PROJECT_ID},
        indent=2,
    ).encode()
    marker.write_bytes(legacy)
    before = _reservations(case.store)
    assert prepare_daily_workspace(second.authority) == case.root
    assert marker.read_bytes() == legacy
    assert case.store.get_research_contract(cid)["project_id"] == SECOND
    with pytest.raises(DataError):
        prepare_daily_workspace(RuleAuthority(case.root, SECOND, case.contract_id))
    assert marker.read_bytes() == legacy
    assert _reservations(case.store) == before


@pytest.mark.parametrize("defect", ["malformed", "wrong_root", "unknown_schema"])
def test_invalid_workspace_fails_before_second_project_job_or_native_charge(
    portable_case: PortableCase,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    case = portable_case
    _second(case, monkeypatch)
    marker = case.root / "daily-rule-workspace.json"
    if defect == "malformed":
        marker.write_bytes(b"not json")
    elif defect == "wrong_root":
        marker.write_text(
            json.dumps({"schema": "DailyRuleWorkspaceV2", "root": str(case.root / "elsewhere")})
        )
    else:
        marker.write_text(json.dumps({"schema": "DailyRuleWorkspaceV99", "root": str(case.root)}))
    before = _reservations(case.store)
    with case.store._transaction(write=False) as connection:
        jobs_before = [
            tuple(row) for row in connection.execute("SELECT * FROM jobs ORDER BY job_id")
        ]

    def forbidden_dispatch(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("invalid workspace reached an external transport")

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden_dispatch)
    with pytest.raises(DataError):
        daily_native_cmds.run_daily_deep(SECOND, data_dir=case.root)
    assert _reservations(case.store) == before
    with case.store._transaction(write=False) as connection:
        assert [
            tuple(row) for row in connection.execute("SELECT * FROM jobs ORDER BY job_id")
        ] == jobs_before


def test_wrong_store_or_project_authority_cannot_prepare_or_charge_shared_root(
    portable_case: PortableCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = portable_case
    _, second = _second(case, monkeypatch)
    before = _reservations(case.store)
    with pytest.raises(DataError):
        prepare_daily_workspace(RuleAuthority(case.root, SECOND, case.contract_id))
    other = case.root / "another-root"
    with pytest.raises(DataError, match="typed approved study"):
        start_daily_owner(other, JOB, native=second, seconds=59)
    assert not other.exists()
    assert _reservations(case.store) == before


@pytest.mark.skipif(
    sys.platform != "linux", reason="requires the real retained Linux owner identity"
)
def test_shared_workspace_does_not_transfer_reserved_job_authority_or_reset_consumed_exposure(
    portable_case: PortableCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_cli.native_supervisor import _open_lock, _Owner
    from tests.unit.test_daily_claim_contracts import JOB as CLAIM_JOB
    from tests.unit.test_daily_claim_contracts import _reserve

    case = portable_case
    _, second = _second(case, monkeypatch)
    _reserve(case, monkeypatch)
    charged = _reservations(case.store)
    with _open_lock(case.root, CLAIM_JOB) as lock:
        wrong_project = _Owner(case.root, CLAIM_JOB, "native_loop", 59, lock, native=second)
        with pytest.raises(DataError, match="authority differs from the reserved store/contract"):
            case.store.claim_native_fixture(CLAIM_JOB, wrong_project)
        assert wrong_project.container is None and wrong_project.process is None
    assert case.store.native_fixture_status(CLAIM_JOB) == {"claim": None, "state": "unclaimed"}
    assert _reservations(case.store) == charged
    foreign = case.root / "foreign-root"
    foreign.mkdir()
    (foreign / "daily-rule-workspace.json").write_text(
        json.dumps({"schema": "DailyRuleWorkspaceV2", "root": str(foreign)})
    )
    with (
        _open_lock(foreign, CLAIM_JOB) as lock,
        pytest.raises(DataError, match="root differs from approved authority"),
    ):
        _Owner(foreign, CLAIM_JOB, "native_loop", 59, lock, native=second)
    assert _reservations(case.store) == charged
    # The rightful retained owner genuinely records that it never attempted payload creation.
    # This releases capacity through the ordinary failure transition, retaining its full charge.
    with _open_lock(case.root, CLAIM_JOB) as lock:
        owner = _Owner(case.root, CLAIM_JOB, "native_loop", 59, lock, native=case.launch)
        case.store.claim_native_fixture(CLAIM_JOB, owner)
        assert owner.container is not None and owner.container.create_attempted is False
        assert owner.process is None and owner.spawn_attempted is False
        case.store.record_native_fixture_observation(CLAIM_JOB, owner.without_child("owner_error"))
    assert case.store.get_job(CLAIM_JOB)["status"] == "failed"
    assert case.store.heavyweight_job_capacity()["active_count"] == 0
    assert _reservations(case.store) == charged

    def forbidden_dispatch(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("a consumed study must not reach another transport")

    monkeypatch.setattr(daily_native_cmds, "start_daily_owner", forbidden_dispatch)
    with pytest.raises(DataError, match="could not confirm its reservation") as denied:
        daily_native_cmds.run_daily_deep(SECOND, data_dir=case.root)
    assert isinstance(denied.value.__cause__, DataError)
    assert "consumed its one trial exposure" in str(denied.value.__cause__)
    assert _reservations(case.store) == charged
