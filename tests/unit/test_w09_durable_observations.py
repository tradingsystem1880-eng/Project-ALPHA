"""Disposable storage fixtures; no native admission or research execution."""

from __future__ import annotations

import copy
import dataclasses
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._ml_observation_store import validate_prefix
from alpha_cli.ml_contract import MLContractError
from alpha_cli.ml_native_plan import _hash, build_manifest, fingerprint_worker

from .test_ml_native_plan import _observations, _protocol, _worker


@pytest.fixture
def storage(tmp_path: Path) -> Any:
    """Populate actual SQLite schema with artificial rows, not admitted Qlib work.

    This tests the association/transaction boundary only. Synthetic storage rows
    deliberately do not purport to qualify the separate research admission path.
    """
    import hashlib
    import json
    import uuid

    from alpha_cli.control_store import _D1_NATIVE_RESOURCE_KEYS, ControlStore, _at, _d1_native_spec
    from alpha_cli.ml_contract import canonical_json_bytes

    store = ControlStore(tmp_path / "store")
    project = store.create_project(
        name="storage fixture", hypothesis="synthetic", falsification_criterion="synthetic"
    )
    pid = str(project["project_id"])
    version_id = "sv_" + hashlib.sha256(b"storage strategy").hexdigest()
    experiment_id = "ex_" + hashlib.sha256(b"storage experiment").hexdigest()
    now = _at(None)
    with store._transaction(write=True) as connection:
        connection.execute(
            "INSERT INTO strategy_versions VALUES (?, 'fixture', 'synthetic', '{}', '{}', ?)",
            (version_id, now),
        )
        connection.execute(
            "INSERT INTO experiment_specs VALUES (?, ?, 'synthetic', '[]', '{}', "
            "'{}', '{}', '{}', ?)",
            (experiment_id, version_id, now),
        )
        connection.execute(
            "INSERT INTO project_experiments VALUES (?, ?, ?)", (pid, experiment_id, now)
        )
    worker = _worker(tmp_path / "worker")
    cid = "rc_" + hashlib.sha256(b"synthetic storage contract").hexdigest()
    protocol = dataclasses.replace(
        _protocol(worker),
        project_id=pid,
        experiment_id=experiment_id,
        contract_id=cid,
    )
    manifest = build_manifest(protocol)
    payload = {
        "budget": {
            "wall_seconds": 100,
            "source_requests": 0,
            "variants": 1,
            **{key: 100 for key in _D1_NATIVE_RESOURCE_KEYS},
        },
        "analysis_plan": {"fixture": "storage only, not native Qlib adoption"},
        "hashes": {
            key: hashlib.sha256(key.encode()).hexdigest()
            for key in ("code", "dependency_lock", "environment", "evaluator", "data")
        },
    }
    now = _at(None)
    with store._transaction(write=True) as connection:
        connection.execute(
            "INSERT INTO research_contracts VALUES (?, ?, 'exploration', NULL, ?, "
            "'fixture', 'agent', ?)",
            (cid, pid, json.dumps(payload), now),
        )

    def job(number: int = 1) -> tuple[str, str, dict[str, str]]:
        jid, invocation = str(uuid.uuid4()), str(uuid.uuid4())
        rid = "rl_" + hashlib.sha256(jid.encode()).hexdigest()
        spec = _d1_native_spec(
            project_id=pid,
            contract_id=cid,
            job_id=jid,
            attempt_number=number,
            payload=payload,
            native_manifest_sha256=manifest.manifest_id,
        )
        request = {
            "stage": "rdagent_native",
            "contract_id": cid,
            "job_id": jid,
            "attempt_number": number,
            "native_invocation_spec": spec,
            "w09_diagnostic": {
                "manifest_id": manifest.manifest_id,
                "experiment_id": protocol.experiment_id,
                "request_sha256": protocol.request_sha256,
            },
        }
        with store._transaction(write=True) as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?, 'research:event-study', 'running', ?, "
                "NULL, ?, ?, ?, ?, NULL, NULL, 1)",
                (jid, pid, json.dumps(request), now, now, now),
            )
            connection.execute(
                "INSERT INTO job_events VALUES (?, 1, 'created', ?, '{}')", (jid, now)
            )
            connection.execute(
                "INSERT INTO research_execution_events VALUES (?, ?, ?, 'running', "
                "?, 'fixture', 'synthetic', 'synthetic', 'codex', ?, NULL, NULL, NULL)",
                (pid, number, cid, now, jid),
            )
            connection.execute(
                "INSERT INTO research_launch_reservations VALUES (?, ?, ?, "
                "'deep_research', 'd1-deep-research', ?, ?, ?, ?, ?)",
                (
                    rid,
                    pid,
                    cid,
                    number,
                    spec["spec_sha256"],
                    json.dumps(payload["budget"]),
                    number,
                    now,
                ),
            )
        return (
            jid,
            rid,
            {
                "job_id": jid,
                "reservation_id": rid,
                "manifest_id": manifest.manifest_id,
                "invocation_id": invocation,
            },
        )

    jid, rid, scope = job()
    full = _observations(protocol, worker)
    initial = {**copy.deepcopy(full), "status": "entered", "folds": {}}

    def checkpoints() -> list[dict[str, Any]]:
        result = [copy.deepcopy(initial)]
        current = copy.deepcopy(initial)
        for fold, sealed in full["folds"].items():
            current["folds"][fold] = {"events": []}
            for event in sealed["events"]:
                events = current["folds"][fold]["events"]
                events.append(
                    {
                        **copy.deepcopy(event),
                        "status": "entered",
                        "output_hashes": {},
                        "state_sha256": None,
                    }
                )
                current["folds"][fold]["trace_sha256"] = _hash(events)
                result.append(copy.deepcopy(current))
                events[-1] = copy.deepcopy(event)
                current["folds"][fold]["trace_sha256"] = _hash(events)
                result.append(copy.deepcopy(current))
        result.append(copy.deepcopy(full))
        return result

    def write(
        snapshot: dict[str, Any], selected: dict[str, str] | None = None
    ) -> dict[str, object]:
        selected = scope if selected is None else selected
        return store.record_w09_diagnostic(
            selected["job_id"],
            selected["reservation_id"],
            manifest,
            canonical_json_bytes({"scope": selected, "snapshot": snapshot}),
            worker_project=worker,
        )

    def read() -> dict[str, object]:
        return store.read_w09_diagnostic(jid, rid, manifest, scope["invocation_id"])

    def accounting() -> list[list[tuple[Any, ...]]]:
        with store._transaction(write=False) as connection:
            return [
                [tuple(row) for row in connection.execute(f"SELECT * FROM {table}")]
                for table in (
                    "research_launch_reservations",
                    "research_attempt_records",
                    "research_launch_attempt_links",
                    "research_execution_events",
                )
            ]

    return dict(
        store=store,
        manifest=manifest,
        worker=worker,
        job=job,
        jid=jid,
        rid=rid,
        scope=scope,
        initial=initial,
        full=full,
        checkpoints=checkpoints,
        write=write,
        read=read,
        accounting=accounting,
    )


def test_complete_replay_and_lost_ack_do_not_change_accounting(storage: Any) -> None:
    before = storage["accounting"]()
    points = storage["checkpoints"]()
    for point in points:
        storage["write"](point)
    report = storage["read"]()
    assert report["status"] == "completed"
    assert report["fitted_state_verified"] is False
    assert report["durable_accounting_verified"] is False
    assert storage["write"](points[0]) == report  # delayed duplicate acknowledgement
    assert storage["write"](points[-1]) == report
    assert storage["accounting"]() == before
    with storage["store"]._transaction(write=False) as connection:
        assert connection.execute(
            "SELECT count(*) FROM job_events WHERE event_type='w09_observation'"
        ).fetchone()[0] == len(points)


def test_interruption_and_failed_prediction_keep_completed_fit(storage: Any) -> None:
    points = storage["checkpoints"]()
    for point in points[:10]:  # binding + four completed calls + prediction entry
        storage["write"](point)
    interrupted = storage["read"]()
    assert interrupted["status"] == "unknown"
    snapshot = copy.deepcopy(interrupted["snapshot"])
    events = snapshot["folds"]["0"]["events"]
    assert events[3]["status"] == "completed"
    assert events[4]["status"] == "entered"
    events[4].update(status="failed", error_type="LookupError")
    snapshot["folds"]["0"]["trace_sha256"] = _hash(events)
    storage["write"](snapshot)
    snapshot.update(status="failed", error_type="LookupError")
    assert storage["write"](snapshot)["status"] == "failed"
    assert storage["read"]()["snapshot"]["folds"]["0"]["events"][3]["status"] == "completed"


def test_concurrent_duplicate_delivery_is_one_event(storage: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(storage["write"], [storage["initial"], storage["initial"]]))
    assert reports[0] == reports[1]
    with storage["store"]._transaction(write=False) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM job_events WHERE event_type='w09_observation'"
            ).fetchone()[0]
            == 1
        )


def test_cross_job_invocation_copy_rejected(storage: Any) -> None:
    from alpha_core import DataError

    storage["write"](storage["initial"])
    _, _, second = storage["job"](2)
    second["invocation_id"] = storage["scope"]["invocation_id"]
    with pytest.raises(DataError, match="another job"):
        storage["write"](storage["initial"], second)


def test_unentered_completion_and_terminal_rewrite_rejected(storage: Any) -> None:
    from alpha_core import DataError

    with pytest.raises(DataError, match="pre-call"):
        storage["write"](storage["full"])
    storage["write"](storage["initial"])
    failed = {**storage["initial"], "status": "failed", "error_type": "OSError"}
    storage["write"](failed)
    with pytest.raises(DataError, match="terminal"):
        storage["write"]({**failed, "error_type": "ValueError"})


def test_transaction_failure_rolls_back_event_and_cursor(storage: Any) -> None:
    from alpha_core import DataError

    store = storage["store"]
    with store._transaction(write=True) as connection:
        connection.execute(
            "CREATE TRIGGER fixture_fail BEFORE UPDATE OF last_sequence ON jobs "
            "BEGIN SELECT RAISE(ABORT, 'synthetic cursor failure'); END"
        )
    with pytest.raises(DataError, match="transaction failed"):
        storage["write"](storage["initial"])
    with store._transaction(write=True) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM job_events WHERE event_type='w09_observation'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT last_sequence FROM jobs WHERE job_id=?", (storage["jid"],)
            ).fetchone()[0]
            == 1
        )
        connection.execute("DROP TRIGGER fixture_fail")
    assert storage["write"](storage["initial"])["status"] == "unknown"


def test_concurrent_conflicting_terminal_delivery_retains_one(storage: Any) -> None:
    from concurrent.futures import ThreadPoolExecutor

    from alpha_core import DataError

    storage["write"](storage["initial"])

    def finish(error: str) -> str:
        try:
            storage["write"]({**storage["initial"], "status": "failed", "error_type": error})
        except DataError:
            return "rejected"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(finish, ["ValueError", "OSError"]))
    assert sorted(results) == ["rejected", "saved"]
    assert storage["read"]()["status"] == "failed"


@pytest.mark.parametrize(
    "mutation", ["manifest", "experiment", "contract", "reservation", "native_claim", "rule"]
)
def test_scope_changes_rejected_without_mutation(storage: Any, mutation: str) -> None:
    import json

    from alpha_cli.control_store import _at
    from alpha_core import DataError

    store = storage["store"]
    with store._transaction(write=True) as connection:
        if mutation in {"manifest", "experiment", "contract"}:
            row = connection.execute(
                "SELECT request_json FROM jobs WHERE job_id=?", (storage["jid"],)
            ).fetchone()
            request = json.loads(row[0])
            if mutation == "manifest":
                request["native_invocation_spec"]["native_manifest_sha256"] = "f" * 64
            elif mutation == "experiment":
                request["w09_diagnostic"]["experiment_id"] = "ex_" + "f" * 64
            else:
                request["contract_id"] = "rc_" + "f" * 64
            connection.execute(
                "UPDATE jobs SET request_json=? WHERE job_id=?",
                (json.dumps(request), storage["jid"]),
            )
        elif mutation == "reservation":
            connection.execute(
                "UPDATE research_launch_reservations SET config_fingerprint='changed'"
            )
        elif mutation == "native_claim":
            connection.execute(
                "INSERT INTO job_events VALUES (?, 2, 'native_claim', ?, '{}')",
                (storage["jid"], _at(None)),
            )
        else:
            cid = storage["manifest"].protocol.contract_id
            row = connection.execute(
                "SELECT payload_json FROM research_contracts WHERE contract_id=?", (cid,)
            ).fetchone()
            payload = json.loads(row[0])
            payload["protocol"] = {"d0_operator": {"name": "synthetic_frozen_rule_positions"}}
            connection.execute(
                "UPDATE research_contracts SET payload_json=? WHERE contract_id=?",
                (json.dumps(payload), cid),
            )
    before = storage["accounting"]()
    with pytest.raises(DataError):
        storage["write"](storage["initial"])
    assert before == storage["accounting"]()
    with store._transaction(write=False) as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM job_events WHERE event_type='w09_observation'"
            ).fetchone()[0]
            == 0
        )


def test_existing_attempt_run_association_is_not_completion_authority(storage: Any) -> None:
    from alpha_cli.control_store import _at
    from alpha_core import DataError

    store = storage["store"]
    storage["write"](storage["initial"])
    with store._transaction(write=True) as connection:
        reservation = connection.execute(
            "SELECT * FROM research_launch_reservations WHERE reservation_id=?", (storage["rid"],)
        ).fetchone()
        connection.execute(
            "INSERT INTO research_attempt_records VALUES (?, ?, ?, ?, ?, "
            "'completed', ?, '{}', 'synthetic-run-reference', NULL, '{}', ?)",
            (
                "ra_" + "a" * 64,
                reservation["project_id"],
                reservation["contract_id"],
                reservation["phase"],
                reservation["kind"],
                reservation["config_fingerprint"],
                _at(None),
            ),
        )
        connection.execute(
            "INSERT INTO research_launch_attempt_links VALUES (?, ?, ?)",
            (storage["rid"], "ra_" + "a" * 64, _at(None)),
        )
    before = storage["accounting"]()
    report = storage["read"]()
    assert report["attempt_id"] == "ra_" + "a" * 64
    assert report["run_id"] == "synthetic-run-reference"
    assert report["run_link_verified"] is False
    assert report["status"] == "unknown"
    assert storage["accounting"]() == before
    with store._transaction(write=True) as connection:
        connection.execute("UPDATE research_attempt_records SET config_fingerprint='cross-scope'")
    with pytest.raises(DataError, match="attempt scope"):
        storage["read"]()


def test_journal_corruption_and_scope_rebinding_rejected(storage: Any) -> None:
    import json
    import uuid

    from alpha_core import DataError

    storage["write"](storage["initial"])
    with pytest.raises(DataError, match="identity or chain"):
        storage["store"].read_w09_diagnostic(
            storage["jid"], storage["rid"], storage["manifest"], str(uuid.uuid4())
        )
    with storage["store"]._transaction(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM job_events WHERE event_type='w09_observation'"
        ).fetchone()
        body = json.loads(row[0])
        body["snapshot_sha256"] = "f" * 64
        connection.execute(
            "UPDATE job_events SET payload_json=? WHERE event_type='w09_observation'",
            (json.dumps(body),),
        )
    with pytest.raises(DataError, match="content differs"):
        storage["read"]()


@pytest.mark.parametrize("location", ["request", "contract", "delta", "oversized"])
def test_malformed_persisted_shapes_fail_closed(storage: Any, location: str) -> None:
    import json

    from alpha_core import DataError

    storage["write"](storage["initial"])
    with storage["store"]._transaction(write=True) as connection:
        if location == "request":
            connection.execute("UPDATE jobs SET request_json='[]'")
        elif location == "contract":
            connection.execute("UPDATE research_contracts SET payload_json='[]'")
        else:
            body = json.loads(
                connection.execute(
                    "SELECT payload_json FROM job_events WHERE event_type='w09_observation'"
                ).fetchone()[0]
            )
            if location == "delta":
                body["delta"] = None
            else:
                body["extra"] = "x" * 20000
            connection.execute(
                "UPDATE job_events SET payload_json=? WHERE event_type='w09_observation'",
                (json.dumps(body),),
            )
    with pytest.raises(DataError):
        storage["read"]()


def test_reopen_recovers_manifest_without_worker_files_or_planning_object(storage: Any) -> None:
    import shutil

    from alpha_cli.control_store import ControlStore

    for point in storage["checkpoints"]():
        storage["write"](point)
    expected = storage["read"]()
    shutil.rmtree(storage["worker"])
    reopened = ControlStore(storage["store"]._data_dir)
    assert (
        reopened.read_w09_diagnostic(
            storage["jid"], storage["rid"], None, storage["scope"]["invocation_id"]
        )
        == expected
    )


def test_planned_ids_without_calls_are_unknown_not_completed(storage: Any) -> None:
    report = storage["write"](storage["initial"])
    assert report["components"]
    assert all(
        not component["observed"]
        and component["status"] == "unknown"
        and component["state_sha256"] is None
        for component in report["components"]
    )


@pytest.mark.parametrize("encoded", [b"{}", b"[]", b"null", b"x" * (2 * 1024 * 1024 + 1)])
def test_unsupported_or_oversized_transport_rejected(storage: Any, encoded: bytes) -> None:
    from alpha_core import DataError

    with pytest.raises(DataError):
        storage["store"].record_w09_diagnostic(
            storage["jid"],
            storage["rid"],
            storage["manifest"],
            encoded,
            worker_project=storage["worker"],
        )


def _exercise_worker_json_checkpoints(storage: Any, *, crash: bool = False) -> None:
    """A separate worker interpreter performs an ordinary synthetic call, not a fit."""
    import json
    import select
    import subprocess

    from alpha_cli.control_store import ControlStore
    from alpha_cli.ml_contract import canonical_json_bytes

    project = Path(__file__).resolve().parents[2] / "workers" / "qlib"
    script = """
import json, sys
from alpha_qlib_worker.fit_provenance import FitInvocation, observe_call
setup = json.loads(sys.stdin.readline())
def checkpoint(data):
    sys.stdout.write(data.decode())
    sys.stdout.flush()
    if sys.stdin.readline().strip() != "ack":
        raise OSError("durable acknowledgement missing")
invocation = FitInvocation(checkpoint=checkpoint, checkpoint_scope=setup["scope"])
invocation.start()
invocation.bind(setup["context"])
observe_call(invocation.new_trace(0), "normalizer", "fit", {"train": 1},
             lambda: 2, lambda x: {"state": x, "train_features": x,
                                  "other_0_features": x, "other_1_features": x})
invocation.failed(ValueError("synthetic later failure"))
"""
    process = subprocess.Popen(
        [str(project / ".venv" / "bin" / "python"), "-c", script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=project,
    )
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(
            json.dumps({"scope": storage["scope"], "context": storage["initial"]["context"]}) + "\n"
        )
        process.stdin.flush()
        statuses = []
        before = storage["accounting"]()
        for index in range(4):
            assert select.select([process.stdout], [], [], 20)[0], "checkpoint timed out"
            checkpoint = json.loads(process.stdout.readline())
            report = storage["store"].record_w09_diagnostic(
                storage["jid"],
                storage["rid"],
                storage["manifest"],
                canonical_json_bytes(checkpoint),
                worker_project=storage["worker"],
            )
            statuses.append(report["status"])
            if crash and index == 1:
                process.kill()
                process.communicate(timeout=20)
                reopened = ControlStore(storage["store"]._data_dir)
                report = reopened.read_w09_diagnostic(
                    storage["jid"],
                    storage["rid"],
                    storage["manifest"],
                    storage["scope"]["invocation_id"],
                )
                assert report["status"] == "unknown"
                recovered_snapshot = report["snapshot"]
                assert isinstance(recovered_snapshot, dict)
                assert recovered_snapshot["folds"]["0"]["events"][0]["status"] == "entered"
                assert storage["accounting"]() == before
                return
            process.stdin.write("ack\n")
            process.stdin.flush()
        _, error = process.communicate(timeout=20)
        assert process.returncode == 0, error
        assert statuses == ["unknown", "unknown", "unknown", "failed"]
        assert storage["read"]()["snapshot"]["folds"]["0"]["events"][0]["status"] == "completed"
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=20)
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None:
                stream.close()


def test_real_experiment_identity_is_supported(tmp_path: Path) -> None:
    protocol = dataclasses.replace(_protocol(_worker(tmp_path)), experiment_id="ex_" + "a" * 64)
    assert build_manifest(protocol).protocol.experiment_id == "ex_" + "a" * 64


@pytest.mark.parametrize("state", ["entered", "failed", "completed"])
def test_prefix_retains_completed_calls_and_unknown_entry(tmp_path: Path, state: str) -> None:
    worker = _worker(tmp_path)
    protocol = _protocol(worker)
    manifest = build_manifest(protocol)
    snapshot = _observations(protocol, worker)
    if state != "completed":
        snapshot["status"] = state
        snapshot["error_type"] = "ValueError" if state == "failed" else None
        events = snapshot["folds"]["0"]["events"][:5]
        events[-1].update(
            status=state, error_type=snapshot["error_type"], output_hashes={}, state_sha256=None
        )
        snapshot["folds"] = {"0": {"events": events, "trace_sha256": _hash(events)}}
    validate_prefix(manifest, snapshot, dict(fingerprint_worker(worker).files)["uv.lock"])
    assert snapshot["folds"]["0"]["events"][3]["status"] == "completed"


@pytest.mark.parametrize(
    "mutation", ["gap", "swapped", "hash", "state", "context", "unknown", "extra"]
)
def test_prefix_rejects_invalid_observations(tmp_path: Path, mutation: str) -> None:
    worker = _worker(tmp_path)
    protocol = _protocol(worker)
    snapshot: dict[str, Any] = copy.deepcopy(_observations(protocol, worker))
    events = snapshot["folds"]["0"]["events"]
    if mutation == "gap":
        del snapshot["folds"]["0"]
    elif mutation == "swapped":
        events[0], events[1] = events[1], events[0]
    elif mutation == "hash":
        events[0]["input_hashes"]["train"] = "bad"
    elif mutation == "state":
        events[0]["state_sha256"] = "f" * 64
    elif mutation == "context":
        snapshot["context"]["request_sha256"] = "f" * 64
    elif mutation == "unknown":
        events[0]["status"] = "unknown"
    else:
        events[0]["new_authority"] = True
    if "0" in snapshot["folds"]:
        snapshot["folds"]["0"]["trace_sha256"] = _hash(events)
    with pytest.raises(MLContractError):
        validate_prefix(
            build_manifest(protocol), snapshot, dict(fingerprint_worker(worker).files)["uv.lock"]
        )


@pytest.mark.parametrize("replacement", [True, 1.0])
@pytest.mark.parametrize("field", ["attempt_number", "spec_attempt_number", "spec_budget"])
def test_exact_json_scope_types_reject_numeric_aliases(
    storage: Any, field: str, replacement: Any
) -> None:
    import json

    from alpha_core import DataError

    with storage["store"]._transaction(write=True) as connection:
        row = connection.execute(
            "SELECT request_json FROM jobs WHERE job_id=?", (storage["jid"],)
        ).fetchone()
        request = json.loads(row[0])
        if field == "attempt_number":
            request[field] = replacement
        elif field == "spec_attempt_number":
            request["native_invocation_spec"]["attempt_number"] = replacement
        else:
            request["native_invocation_spec"]["approved_budget"]["variants"] = replacement
        connection.execute(
            "UPDATE jobs SET request_json=? WHERE job_id=?", (json.dumps(request), storage["jid"])
        )
    with pytest.raises(DataError):
        storage["write"](storage["initial"])


@pytest.mark.parametrize("replacement", [True, 1.0])
def test_bound_protocol_numeric_alias_rejected_on_replay_and_read(
    storage: Any, replacement: Any
) -> None:
    import json

    from alpha_core import DataError

    storage["write"](storage["initial"])
    with storage["store"]._transaction(write=True) as connection:
        row = connection.execute(
            "SELECT payload_json FROM job_events WHERE event_type='w09_observation'"
        ).fetchone()
        body = json.loads(row[0])
        body["delta"]["protocol"]["request_schema_version"] = replacement
        connection.execute(
            "UPDATE job_events SET payload_json=? WHERE event_type='w09_observation'",
            (json.dumps(body),),
        )
    with pytest.raises(DataError):
        storage["write"](storage["initial"])
    with pytest.raises(DataError):
        storage["read"]()
