"""Portable observed-input recovery contracts, not process/resource/native acceptance.

Only external runtime/host-storage qualification measurements are fixture ports. Owner confirmation,
ControlStore reservations/events, code fingerprints, numerical accounting, receipt validation,
immutable publication and recovery are real. No supervisor, Docker or upstream native loop runs.
"""

from __future__ import annotations

import copy
import hashlib
import json
import runpy
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._native_daily_rule_protocol import (
    canonical,
    daily_position_payload,
    daily_worker_request,
    sha,
)
from alpha_cli._native_daily_rule_restore import restore_daily_rule_evidence
from alpha_cli._native_daily_rule_study import DailyRuleStudyV1
from alpha_cli._native_fixture_store import _append, _events
from alpha_cli._native_loop_admission import SOURCE_SHA256, WORKER, WORKER_FILES, NativeLaunch
from alpha_cli._native_rule_completion import complete_rule_trial
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from tests.unit.test_native_daily_rule_lifecycle import _case, _reservations
from tests.unit.test_research_control_store import PROJECT_ID, START, _native_d1_job

JOB = "ee55f253-3ffc-4b03-bd81-5343f29357df"
OWNER = "d86a01ae-2dc3-4607-84f0-2715f9d62daf"
PROFILE = hashlib.sha256(b"portable observed-input external profile, not qualified").hexdigest()
IMAGE = "sha256:" + hashlib.sha256(b"portable observed-input image, not installed").hexdigest()


@dataclass(frozen=True)
class ObservedDailyCase:
    """Reusable exact observed-input contract, deliberately without a process handle."""

    root: Path
    store: ControlStore
    contract_id: str
    launch: NativeLaunch
    receipt: dict[str, Any]
    admission: dict[str, Any]
    events: dict[str, dict[str, object]]
    reservation: dict[str, Any]
    job_id: str = JOB


def observed_daily_case(root: Path, monkeypatch: pytest.MonkeyPatch) -> ObservedDailyCase:
    """Prepare actual authority/ledger/receipt fixtures for portable completion consumers.

    Returns root/store/contract_id/launch plus prepared receipt/admission/validated events and
    reservation. External qualification measurements are explicit inputs, never acceptance.
    The native receipt wraps a canonical-engine artificial replay and hand-bound observations.
    """
    import alpha_cli._native_daily_rule_container as container
    import alpha_cli._native_daily_rule_restore as restore
    import alpha_cli._native_loop_admission as native
    import alpha_cli._native_rule_completion as completion
    import alpha_cli._native_rule_environment as environment
    import tests.unit.test_native_daily_rule_lifecycle as lifecycle

    root.mkdir(parents=True, exist_ok=True)
    source = root / "observed-input-source"
    source.mkdir()
    monkeypatch.setattr(environment, "measure_rule_environment", lambda costed=False: PROFILE)
    monkeypatch.setattr(lifecycle, "measure_rule_environment", lambda costed=False: PROFILE)
    monkeypatch.setattr(completion, "measure_rule_environment", lambda costed=False: PROFILE)
    monkeypatch.setattr(restore, "measure_rule_environment", lambda costed=False: PROFILE)
    monkeypatch.setattr(
        container,
        "daily_container_profile",
        lambda: {
            "image_id": IMAGE,
            "config_sha256": sha("fixture config"),
            "docker_sha256": sha("fixture client"),
        },
    )

    def measured_proposal(selected: Path, mode: str, study: object = None) -> str:
        if selected != source or mode != "INCONCLUSIVE" or not isinstance(study, DailyRuleStudyV1):
            raise DataError("unqualified external fixture measurement")
        return sha(
            {
                "fixture_port": "no native runtime qualification",
                "source": str(selected),
                "mode": mode,
                "study": study.content_sha256,
                "implementation": environment.rule_implementation_fingerprints(
                    True, daily_study=study
                ),
            }
        )

    monkeypatch.setattr(native, "measure_native_proposal", measured_proposal)
    store, contract_id, launch = _case(root, monkeypatch, source)
    assert isinstance(launch.study, DailyRuleStudyV1)
    study = launch.study
    _, reservation = _native_d1_job(
        store, contract_id, job_id=JOB, manifest_sha256=launch.fingerprint, started_at=START
    )
    with store._transaction(write=False) as connection:
        review = store._latest_research_review(connection, contract_id)
        assert review is not None
        from alpha_cli._native_rule_protocol import require_rule_confirmation

        owner_receipt = require_rule_confirmation(
            connection, PROJECT_ID, contract_id, str(review["actor"])
        )
    binding = {
        "container_name": "alpha-daily-" + sha([JOB, reservation["reservation_id"], OWNER])[:40],
        "image_id": IMAGE,
        "resource_fingerprint": sha("hand-bound observed-input resource evidence"),
        "deadline_monotonic_ns": 123_000_000_000,
    }
    budget = reservation["budget_reserved"]
    assert isinstance(budget, dict)
    admission = {
        "schema": "DailyNativeAdmissionV1",
        "job_id": JOB,
        "reservation_id": reservation["reservation_id"],
        "spec_sha256": reservation["config_fingerprint"],
        "manifest_sha256": launch.fingerprint,
        "owner_id": OWNER,
        "mode": "INCONCLUSIVE",
        "loop_steps": budget["rdagent_native_v1_loop_steps"],
        "rule_request": daily_worker_request(study),
        "rule_profile": PROFILE,
        "study_id": study.content_sha256,
        "trial_id": reservation["reservation_id"],
        "owner_receipt_id": owner_receipt,
        "query_sha256": study.query_sha256,
        "cpu_milliseconds": budget["rdagent_native_v1_cpu_milliseconds"],
        **binding,
        "container_id": sha("hand-bound observed-input container"),
    }
    worker = runpy.run_path(str(WORKER / "costed_probe.py"))
    replay = worker["execute"]({**study.to_dict(), "bars": admission["rule_request"]["bars"]})
    receipt = {
        "admission": admission,
        "binding_sha256": sha(admission),
        "rule_positions": daily_position_payload(study),
        "economics": replay,
        "authority": "none",
        "synthetic": True,
        "routes_enabled": False,
        "scientific_acceptance": "not_admitted",
        "source_tree_sha256": SOURCE_SHA256,
        "checkpoint_binding_verified": True,
        "checks": {"events": ["direct_exp_gen", "coding", "running", "feedback", "record"]},
        "imported_worker_sha256": {
            name.removesuffix(".py"): hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
            for name in (*WORKER_FILES, "rule_probe.py", "costed_probe.py")
            if name.endswith(".py") and name != "fixture_entry.py"
        },
    }
    work = root / ("payload-" + JOB)
    work.mkdir()
    for role in ("baseline", "control"):
        (work / (role + ".json")).write_text(
            canonical(
                {
                    "schema": "RulePositionArtifactV1",
                    "unit": "position",
                    "positions": receipt["rule_positions"][role],
                }
            )
        )
    (work / "receipt.json").write_text(canonical(receipt))
    (work / "daily-admission.json").write_text(canonical(admission))
    common = {
        "schema": "SyntheticNativeLifecycleV1",
        "job_id": JOB,
        "reservation_id": reservation["reservation_id"],
        "spec_sha256": reservation["config_fingerprint"],
        "owner_id": OWNER,
    }
    claim = {
        **common,
        **binding,
        "owner_pid": 123,
        "owner_birth": "456",
        "host": {"profile": "observed-input-only", "boot": "fixture", "pid_namespace": "fixture"},
        "lock_device": 1,
        "lock_inode": 2,
        "runtime_sha256": sha("observed input, no process"),
        "fixture": "native_loop",
        "seconds": budget["wall_seconds"],
        "cleanup_scope": "docker_container_and_posix_process_group",
    }
    with store._transaction(write=True) as connection:
        _append(connection, JOB, "native_claim", claim)
        _append(
            connection,
            JOB,
            "native_container_created",
            {**common, **binding, "container_id": admission["container_id"]},
        )
        _append(
            connection,
            JOB,
            "native_started",
            {**common, "leader_pid": 789, "container_id": admission["container_id"]},
        )
        _append(
            connection,
            JOB,
            "native_outcome",
            {
                **common,
                "reason": "exit",
                "returncode": 0,
                "elapsed_seconds": 1.0,
                "cleanup_scope": "docker_container_and_posix_process_group",
                "scientific_acceptance": "not_admitted",
                "rule_result": {
                    "schema": "DailyNativeRuleObservationV1",
                    "receipt_sha256": hashlib.sha256(
                        (work / "receipt.json").read_bytes()
                    ).hexdigest(),
                },
            },
        )
        events = _events(connection, JOB)
    return ObservedDailyCase(
        root, store, contract_id, launch, receipt, admission, events, reservation
    )


@pytest.fixture
def observed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ObservedDailyCase:
    return observed_daily_case(tmp_path, monkeypatch)


def _ledger(case: ObservedDailyCase) -> tuple[list[dict[str, object]], list[tuple[object, ...]]]:
    with case.store._transaction(write=False) as connection:
        attempts = [
            tuple(row)
            for row in connection.execute(
                "SELECT * FROM research_attempt_records ORDER BY attempt_id"
            )
        ]
    return _reservations(case.store), attempts


def test_portable_completion_publishes_once_and_reopens_without_new_charge(
    observed: ObservedDailyCase,
) -> None:
    before = _reservations(observed.store)
    result = complete_rule_trial(observed.store, JOB, observed.launch)
    assert result["status"] == "completed"
    details = result["details"]
    assert isinstance(details, dict)
    assert details["data_origin"] == "artificial_fixture"
    reference = details["native_receipt_ref"]
    assert isinstance(reference, dict)
    assert (
        reference["content_sha256"]
        == hashlib.sha256(
            (observed.root / ("payload-" + JOB) / "receipt.json").read_bytes()
        ).hexdigest()
    )
    assert _reservations(observed.store) == before
    ledger = _ledger(observed)
    assert complete_rule_trial(ControlStore(observed.root), JOB, observed.launch) == result
    assert _ledger(observed) == ledger


def test_portable_restore_missing_only_preserves_later_authoritative_reservations(
    observed: ObservedDailyCase,
) -> None:
    from tests.unit.test_native_rule_authority import _pilot

    result = complete_rule_trial(observed.store, JOB, observed.launch)
    reference = observed.root / "independent-reference"
    reference.mkdir()
    for name in ("runs", "snapshots"):
        shutil.copytree(observed.root / name, reference / name)
    _pilot(observed.root, project_id="3a55f253-3ffc-4b03-bd81-5343f29357df")
    ledger = _ledger(observed)
    run = observed.root / "runs" / str(result["run_id"])
    selectors = json.loads((run / "projections.json").read_text())
    chart = observed.root / "snapshots" / selectors["chart_snapshot_id"]
    chart_manifest = json.loads((chart / "manifest.json").read_text())
    symbol = chart_manifest["symbols"]["BTC/USDT"]
    missing = [
        run / "query.json",
        chart / symbol["bars_file"],
        observed.root
        / "runs"
        / selectors["roles"]["baseline"]["run_id"]
        / "decision_trace.parquet",
    ]
    original = {path: path.read_bytes() for path in missing}
    for path in missing:
        path.unlink()
    restored = restore_daily_rule_evidence(observed.root, reference, JOB)
    restored_files = restored["restored_files"]
    assert isinstance(restored_files, list)
    assert set(restored_files) == {str(path.relative_to(observed.root)) for path in missing}
    assert all(path.read_bytes() == raw for path, raw in original.items())
    assert restored["control_database_replaced"] is False
    assert _ledger(observed) == ledger
    assert restore_daily_rule_evidence(observed.root, reference, JOB)["restored_files"] == []


def _reference(case: ObservedDailyCase) -> tuple[dict[str, Any], Path]:
    result = complete_rule_trial(case.store, JOB, case.launch)
    reference = case.root / "independent-reference"
    reference.mkdir()
    for name in ("runs", "snapshots"):
        shutil.copytree(case.root / name, reference / name)
    return result, reference


def _replace_event(case: ObservedDailyCase, kind: str, payload: dict[str, object]) -> None:
    """Inject storage corruption into a disposable observed-input fixture, not an API action."""
    with case.store._transaction(write=True) as connection:
        connection.execute(
            "UPDATE job_events SET payload_json=? WHERE job_id=? AND event_type=?",
            (canonical(payload), JOB, kind),
        )


def test_completion_recovers_published_bytes_without_a_catalog_attempt(
    observed: ObservedDailyCase,
) -> None:
    from alpha_cli._native_rule_artifacts import publish_rule_run
    from alpha_cli._native_rule_authority import RuleAuthority

    contract = RuleAuthority(observed.root, PROJECT_ID, observed.contract_id).verify()
    before = _ledger(observed)
    manifest = publish_rule_run(
        observed.root,
        project_id=PROJECT_ID,
        contract_id=observed.contract_id,
        contract=contract,
        execution_fingerprint=str(observed.reservation["config_fingerprint"]),
        native_receipt=observed.receipt,
        native_receipt_bytes=(observed.root / ("payload-" + JOB) / "receipt.json").read_bytes(),
    )
    # This is the actual interrupted state: immutable publication exists, but the controller
    # has not linked a completed attempt. No numerical worker or publisher routine is mocked.
    assert _ledger(observed) == before
    hashes = {
        str(p.relative_to(observed.root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for directory in ("runs", "snapshots")
        for p in (observed.root / directory).rglob("*")
        if p.is_file()
    }
    result = complete_rule_trial(observed.store, JOB, observed.launch)
    assert result["run_id"] == manifest["run_id"]
    assert _reservations(observed.store) == before[0]
    assert hashes == {
        str(p.relative_to(observed.root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for directory in ("runs", "snapshots")
        for p in (observed.root / directory).rglob("*")
        if p.is_file()
    }


@pytest.mark.parametrize(
    "defect",
    [
        "cancel",
        "uncertain",
        "observed_receipt",
        "started_container",
        "claim_owner",
        "receipt_owner",
        "receipt_bytes",
        "code",
    ],
)
def test_completion_rejects_untrusted_or_changed_inputs_without_charging_again(
    observed: ObservedDailyCase,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    before = _ledger(observed)
    if defect in {"cancel", "uncertain"}:
        common = {
            key: observed.events["native_claim"][key]
            for key in ("schema", "job_id", "reservation_id", "spec_sha256", "owner_id")
        }
        with observed.store._transaction(write=True) as connection:
            if defect == "cancel":
                _append(
                    connection,
                    JOB,
                    "cancel_requested",
                    {"actor": "fixture-owner", "reason": "fixture durable stop intent"},
                )
            else:
                _append(
                    connection,
                    JOB,
                    "native_uncertain",
                    {**common, "reason": "fixture unresolved cleanup"},
                )
    elif defect in {"observed_receipt", "started_container", "claim_owner"}:
        kind = {
            "observed_receipt": "native_outcome",
            "started_container": "native_started",
            "claim_owner": "native_claim",
        }[defect]
        changed = copy.deepcopy(observed.events[kind])
        if defect == "observed_receipt":
            changed["rule_result"] = {
                "schema": "DailyNativeRuleObservationV1",
                "receipt_sha256": sha("different observed bytes"),
            }
        elif defect == "started_container":
            changed["container_id"] = sha("different container")
        else:
            changed["owner_id"] = "c86a01ae-2dc3-4607-84f0-2715f9d62daf"
        _replace_event(observed, kind, changed)
    elif defect in {"receipt_owner", "receipt_bytes"}:
        path = observed.root / ("payload-" + JOB) / "receipt.json"
        if defect == "receipt_bytes":
            path.write_text(path.read_text() + " ")
        else:
            changed_receipt = copy.deepcopy(observed.receipt)
            changed_receipt["admission"]["owner_id"] = "another-owner"
            changed_receipt["binding_sha256"] = sha(changed_receipt["admission"])
            path.write_text(canonical(changed_receipt))
    else:
        target = WORKER / "daily_container_entry.py"
        read_bytes = Path.read_bytes

        def changed_bytes(path: Path) -> bytes:
            original = read_bytes(path)
            return original + b"\n# changed approved guard" if path == target else original

        monkeypatch.setattr(Path, "read_bytes", changed_bytes)
    with pytest.raises(DataError):
        complete_rule_trial(observed.store, JOB, observed.launch)
    assert _ledger(observed) == before


@pytest.mark.parametrize(
    "defect",
    [
        "same_root",
        "reference_receipt",
        "reference_projection",
        "existing_conflict",
        "profile",
        "no_attempt",
        "oversized_receipt",
        "symlink_reference",
    ],
)
def test_restore_preflights_authority_reference_and_all_conflicts_before_any_repair(
    observed: ObservedDailyCase,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    if defect == "no_attempt":
        before = _ledger(observed)
        with pytest.raises(DataError, match="authoritative completed attempt"):
            restore_daily_rule_evidence(observed.root, observed.root / "absent-reference", JOB)
        assert _ledger(observed) == before
        return
    result, reference = _reference(observed)
    run_id = str(result["run_id"])
    run = observed.root / "runs" / run_id
    (run / "query.json").unlink()
    before = _ledger(observed)
    if defect == "same_root":
        reference = observed.root
    elif defect == "reference_receipt":
        receipt = reference / "runs" / run_id / "native_receipt.json"
        receipt.write_bytes(receipt.read_bytes() + b" ")
    elif defect == "oversized_receipt":
        assert isinstance(observed.launch.study, DailyRuleStudyV1)
        with (reference / "runs" / run_id / "native_receipt.json").open("wb") as stream:
            stream.truncate(observed.launch.study.resources.max_artifact_bytes + 1)
    elif defect == "symlink_reference":
        target = reference / "runs" / run_id / "native_receipt.json"
        raw = target.read_bytes()
        outside = observed.root / "outside-reference.json"
        outside.write_bytes(raw)
        target.unlink()
        target.symlink_to(outside)
    elif defect == "reference_projection":
        projections = json.loads((reference / "runs" / run_id / "projections.json").read_text())
        baseline = (
            reference / "runs" / projections["roles"]["baseline"]["run_id"] / "raw_result.json"
        )
        baseline.write_text("{}")
    elif defect == "existing_conflict":
        (run / "economics.json").write_text("conflicting retained bytes")
    elif defect == "profile":
        import alpha_cli._native_daily_rule_restore as restoration

        monkeypatch.setattr(
            restoration,
            "measure_rule_environment",
            lambda costed=False: sha("different external profile"),
        )
    with pytest.raises(DataError):
        restore_daily_rule_evidence(observed.root, reference, JOB)
    assert not (run / "query.json").exists(), (
        "restore changed a file before preflighting all conflicts"
    )
    assert _ledger(observed) == before


def test_atomic_missing_file_restore_handles_concurrent_identical_and_conflicting_destinations(
    tmp_path: Path,
) -> None:
    from alpha_cli._native_daily_rule_restore import _restore_missing_file

    target = tmp_path / "observed-evidence.json"
    _restore_missing_file(target, b"exact admitted bytes")
    _restore_missing_file(target, b"exact admitted bytes")
    assert target.read_bytes() == b"exact admitted bytes"
    with pytest.raises(DataError, match="conflicting concurrent bytes"):
        _restore_missing_file(target, b"different bytes")
    assert target.read_bytes() == b"exact admitted bytes"
    assert list(tmp_path.glob(".daily-restore-*")) == []


@pytest.mark.parametrize("relative", ["../outside.json", "/outside.json"])
def test_restore_path_guard_rejects_escape_before_io(tmp_path: Path, relative: str) -> None:
    from alpha_cli._native_daily_rule_restore import _safe_file

    with pytest.raises(DataError, match="path is unsafe"):
        _safe_file(tmp_path, relative)


def test_completion_rejects_other_store_before_publishing(observed: ObservedDailyCase) -> None:
    before = _ledger(observed)
    other = observed.root / "other-control-root"
    with pytest.raises(DataError, match="another store"):
        complete_rule_trial(ControlStore(other), JOB, observed.launch)
    assert not other.exists()
    assert _ledger(observed) == before
