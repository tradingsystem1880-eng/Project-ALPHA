"""Portable pre-effect ledger/policy contracts; no native process or container is run.

The imported fixture ports only external runtime observations. A non-executable
temporary mount supplies the constructor's filesystem input. The real owner,
reservation, authority, code fingerprints and event validators remain in use.
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pytest

from alpha_cli import _native_loop_admission as admission
from alpha_cli import _native_rule_environment as environment
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_fixture_store import _append, _events
from alpha_cli.native_supervisor import _open_lock, _Owner
from alpha_core import DataError
from tests.unit.test_daily_native_dispatch_contracts import PortableCase
from tests.unit.test_daily_native_dispatch_contracts import portable_case as portable_case
from tests.unit.test_native_daily_rule_lifecycle import _reservations
from tests.unit.test_research_control_store import START, _native_d1_job

JOB = "a655f253-3ffc-4b03-bd81-5343f29357df"
pytestmark = pytest.mark.skipif(
    sys.platform != "linux", reason="requires the real retained Linux owner identity"
)


def _reserve(case: PortableCase, monkeypatch: pytest.MonkeyPatch) -> None:
    worker = case.root / "non-executable-worker-mount"
    (worker / ".venv-economics-qualified/bin").mkdir(parents=True)
    (worker / ".venv-economics-qualified/bin/python").write_text("not executable")
    # Only the mount input changes; actual implementation_fingerprints continues
    # reading the real source/locks through _native_rule_environment.WORKER.
    monkeypatch.setattr(admission, "WORKER", worker)
    _native_d1_job(
        case.store,
        case.contract_id,
        job_id=JOB,
        manifest_sha256=case.launch.fingerprint,
        started_at=START + timedelta(minutes=12),
    )


def test_daily_claim_binds_existing_allowance_and_policy_without_creating_resource(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    case = portable_case
    _reserve(case, monkeypatch)
    charged = _reservations(case.store)
    with _open_lock(case.root, JOB) as lock:
        owner = _Owner(case.root, JOB, "native_loop", 59, lock, native=case.launch)
        claim = case.store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is not None
        assert isinstance(case.launch.study, DailyRuleStudyV1)
        assert owner.native_admission["query_sha256"] == case.launch.study.query_sha256
        selected = next(row for row in charged if row["phase"] == "deep_research")
        assert owner.native_admission["reservation_id"] == selected["reservation_id"]
        container = owner.container
        assert container is not None
        assert container.policy["memory_bytes"] == 1024**3
        assert container.policy["network"] == "none"
        assert container.policy["readonly_root"] is True
        assert container.policy["cpu_seconds"] == 60
        assert container.policy["deadline_monotonic_ns"] == int(owner.deadline * 1_000_000_000)
        assert all(claim[key] == value for key, value in container.binding().items())
        assert container.cid is None and container.create_attempted is False
        assert not container.work.exists()
        assert _reservations(case.store) == charged
        with pytest.raises(DataError, match="already has a launch claim; reconnect only"):
            case.store.claim_native_fixture(JOB, owner)
        assert _reservations(case.store) == charged


@pytest.mark.parametrize("cause", ["over_remaining_wall", "cancelled", "changed_guard"])
def test_daily_claim_refuses_effects_without_mutating_reserved_exposure(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch, cause: str
) -> None:
    case = portable_case
    _reserve(case, monkeypatch)
    charged = _reservations(case.store)
    if cause == "cancelled":
        case.store.cancel_native_fixture(JOB, reason="artificial pre-effect contract")
    if cause == "changed_guard":
        target = Path(environment.__file__).with_name("_native_daily_rule_restore.py")
        original = Path.read_bytes
        monkeypatch.setattr(
            Path,
            "read_bytes",
            lambda path: (
                original(path) + b"\nchanged approval guard" if path == target else original(path)
            ),
        )
    with _open_lock(case.root, JOB) as lock:
        owner = _Owner(
            case.root,
            JOB,
            "native_loop",
            60 if cause == "over_remaining_wall" else 59,
            lock,
            native=case.launch,
        )
        with pytest.raises(DataError):
            case.store.claim_native_fixture(JOB, owner)
        assert owner.native_admission is None
        assert owner.container is None
        assert not (case.root / ("payload-" + JOB)).exists()
    assert _reservations(case.store) == charged


@pytest.mark.parametrize("change", ["foreign_image", "invalid_id", "start_without_created"])
def test_daily_event_reader_rejects_resource_substitution_before_any_outcome(
    portable_case: PortableCase, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    case = portable_case
    _reserve(case, monkeypatch)
    charged = _reservations(case.store)
    with _open_lock(case.root, JOB) as lock:
        owner = _Owner(case.root, JOB, "native_loop", 59, lock, native=case.launch)
        claim = case.store.claim_native_fixture(JOB, owner)
        assert owner.container is not None
        common = {
            key: claim[key]
            for key in ("schema", "job_id", "reservation_id", "spec_sha256", "owner_id")
        }
        created = {**common, **owner.container.binding(), "container_id": "c" * 64}
        with case.store._transaction(write=True) as connection:
            if change == "start_without_created":
                _append(
                    connection,
                    JOB,
                    "native_started",
                    {
                        **common,
                        "leader_pid": 42,
                        "container_id": "c" * 64,
                    },
                )
            else:
                created["image_id" if change == "foreign_image" else "container_id"] = (
                    "sha256:" + "d" * 64 if change == "foreign_image" else "not-an-id"
                )
                _append(connection, JOB, "native_container_created", created)
        with (
            case.store._transaction(write=False) as connection,
            pytest.raises(DataError, match="container"),
        ):
            _events(connection, JOB)
        assert owner.container.create_attempted is False
    assert _reservations(case.store) == charged
