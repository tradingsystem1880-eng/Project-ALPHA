"""Artificial admission fixtures; no real-market study or owner approval is inferred."""

from __future__ import annotations

import hashlib
import json
import subprocess
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._native_daily_rule_protocol import (
    daily_operator,
    daily_position_payload,
    daily_resource_command,
    draft_daily_contract,
    reopen_daily_study,
    study_from_contract,
    validate_daily_contract,
)
from alpha_cli._native_daily_rule_study import bind_daily_study, daily_rule_terms_proposal
from alpha_cli._native_rule_protocol import is_rule_contract, validate_rule_contract
from alpha_cli.control_store import _research_d2_topology
from alpha_cli.crypto_price_snapshot_query import query_binance_daily_price_snapshot
from alpha_core import DataError
from tests.unit.test_crypto_price_snapshot_query import _full_discovery_fixture
from tests.unit.test_native_daily_rule_study import _study


def _contract(tmp_path: Path) -> dict[str, Any]:
    study = _study(tmp_path)
    study = type(study).model_validate(
        {**study.to_dict(), "runtime_profile_sha256": hashlib.sha256(b"runtime").hexdigest()}
    )
    return draft_daily_contract(
        "sp_" + "1" * 64,
        {
            "data": study.query_sha256,
            "environment": study.runtime_profile_sha256,
            "code": hashlib.sha256(b"code").hexdigest(),
            "dependency_lock": hashlib.sha256(b"dependency").hexdigest(),
            "evaluator": hashlib.sha256(b"evaluator").hexdigest(),
        },
        {
            "variants": 5,
            "wall_seconds": 60,
            "source_requests": 0,
            "rdagent_native_v1_model_calls": 0,
            "rdagent_native_v1_input_tokens": 0,
            "rdagent_native_v1_output_tokens": 0,
            "rdagent_native_v1_tool_calls": 0,
            "rdagent_native_v1_loop_steps": 5,
            "rdagent_native_v1_cpu_milliseconds": 10000,
        },
        study,
    )


def test_registered_daily_route_is_distinct_and_has_no_protected_samples(tmp_path: Path) -> None:
    contract = _contract(tmp_path)
    study = study_from_contract(contract)
    assert is_rule_contract(contract)
    assert validate_rule_contract(contract) == daily_operator(study)
    assert validate_daily_contract(contract) == daily_operator(study)
    protected, _ = _research_d2_topology(contract)
    assert protected["available"] is False
    assert protected["share"] == pytest.approx(0)
    assert contract["protocol"]["evidence_topology"]["D1"]["share"] == pytest.approx(1)
    assert daily_position_payload(study)["real_market_evidence"] is False
    assert daily_position_payload(study)["data_origin"] == "artificial_fixture"


@pytest.mark.parametrize(
    "mutation",
    [
        "version",
        "query",
        "profile",
        "origin",
        "scope",
        "authority",
        "d2",
        "variants",
        "models",
        "cpu",
        "wall",
    ],
)
def test_daily_admission_changes_fail_closed(tmp_path: Path, mutation: str) -> None:
    contract = _contract(tmp_path)
    changed = deepcopy(contract)
    if mutation == "version":
        changed["protocol"]["d0_operator"]["version"] = 2
    elif mutation in {"query", "profile", "origin"}:
        key = {
            "query": "query_sha256",
            "profile": "runtime_profile_sha256",
            "origin": "data_origin",
        }[mutation]
        changed["analysis_plan"]["study"][key] = (
            "captured_provider_history" if mutation == "origin" else "f" * 64
        )
    elif mutation == "scope":
        changed["scope"] = "confirmation"
    elif mutation == "authority":
        changed["protocol"]["boundary_authority"]["empirical_confirmation_authorized"] = True
    elif mutation == "d2":
        changed["protocol"]["evidence_topology"]["D2"]["available"] = True
    else:
        key = {
            "variants": "variants",
            "models": "rdagent_native_v1_model_calls",
            "cpu": "rdagent_native_v1_cpu_milliseconds",
            "wall": "wall_seconds",
        }[mutation]
        changed["budget"][key] = {"variants": 6, "models": 1, "cpu": 61000, "wall": 61}[mutation]
    with pytest.raises(DataError):
        validate_rule_contract(changed)


def test_actual_snapshot_reopen_rechecks_storage_source_and_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import alpha_cli.crypto_bulk_store as backend

    store, snapshot, manifest_id = _full_discovery_fixture(tmp_path)
    root = tmp_path / "control"
    config = root / "crypto" / "storage-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"fixture":"explicit artificial backend"}')
    snapshots = root / "crypto" / "snapshots"
    snapshots.mkdir()
    (snapshots / (snapshot.snapshot_id + ".json")).write_text(json.dumps(snapshot.to_dict()))
    end = datetime(2023, 1, 1, tzinfo=UTC)
    query = query_binance_daily_price_snapshot(
        snapshot,
        store,
        normalized_manifest_id=manifest_id,
        start=datetime(2020, 1, 1, tzinfo=UTC),
        end=end,
        available_by=end,
    )
    economics, resources = daily_rule_terms_proposal()
    study = bind_daily_study(
        query,
        snapshot_sha256=snapshot.snapshot_id,
        runtime_profile_sha256="a" * 64,
        container_image_id="sha256:" + "c" * 64,
        storage_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        economics=economics,
        resources=resources,
        data_origin="artificial_fixture",
    )
    monkeypatch.setattr(backend, "configured_crypto_bulk_store", lambda selected: store)
    reopen_daily_study(root, study)
    config.write_text('{"fixture":"changed"}')
    with pytest.raises(DataError, match="storage profile changed"):
        reopen_daily_study(root, study)


def test_daily_resource_wrapper_is_fixed_and_enforces_memory_file_and_cpu_bounds() -> None:
    _, resources = daily_rule_terms_proposal()
    command = daily_resource_command(["/usr/bin/true"], resources, 60, 10000)
    assert command[0] == "/usr/bin/taskset"
    assert "--as=1073741824" in command
    assert "--cpu=10" in command
    assert "--fsize=33554432" in command
    assert subprocess.run(command, check=False, capture_output=True).returncode == 0
    with pytest.raises(DataError, match="resource reservation"):
        daily_resource_command(["/usr/bin/true"], resources, 1, 61000)


def test_daily_approval_requires_exact_consumed_owner_confirmation(tmp_path: Path) -> None:
    from alpha_cli import owner_auth
    from alpha_cli._native_rule_authority import RuleAuthority
    from alpha_cli.control_store import ControlStore, research_case_revision
    from tests.unit.test_research_control_store import PROJECT_ID, START

    payload = _contract(tmp_path)
    store = ControlStore(tmp_path)
    store.create_project(
        name="Artificial daily admission",
        hypothesis="Mechanics only",
        falsification_criterion="Reject changed bindings",
        project_id=PROJECT_ID,
        at=START,
    )
    source = store.create_research_source(
        PROJECT_ID,
        title="Artificial provider-format fixture",
        locator="artificial:binance-daily",
        provider="synthetic",
        access_mode="metadata_only",
        metadata={"artificial_fixture": True},
        at=START,
    )
    pack = store.create_research_source_pack(
        PROJECT_ID,
        source_ids=[str(source["source_id"])],
        definition={"artificial_fixture": True},
        at=START,
    )
    payload["source_pack_id"] = pack["pack_id"]
    created = store.create_research_contract(
        PROJECT_ID,
        scope="exploration",
        payload=payload,
        created_by="test-agent",
        author_kind="agent",
        at=START,
    )
    cid = str(created["contract_id"])
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="triage",
        contract_id=cid,
        actor="test-agent",
        reason="Artificial fixture",
        next_action="Review",
        responsibility="owner",
        at=START,
    )
    store.transition_research_phase(
        PROJECT_ID,
        to_phase="exploration_review",
        contract_id=cid,
        actor="test-agent",
        reason="Artificial fixture",
        next_action="Confirm",
        responsibility="owner",
        at=START,
    )
    review: dict[str, Any] = {
        "scope": "exploration",
        "decision": "approve",
        "actor": "owner:local-confirmation",
        "actor_kind": "human",
        "reason": "Artificial fixture",
        "at": START,
    }
    with pytest.raises(DataError, match="consumed owner confirmation"):
        store.review_research_contract(PROJECT_ID, cid, **review)
    request = {"contract_id": cid}
    binding = owner_auth.action_binding(
        data_dir=tmp_path,
        action_type="approve_exploration",
        project_id=PROJECT_ID,
        artifact_hash=cid.removeprefix("rc_"),
        expected_case_revision=research_case_revision(store.research_case_summary(PROJECT_ID)),
        consequence_summary="Artificial admission fixture only",
        reason="Test ceremony",
        payload=request,
    )
    envelope = owner_auth.local_confirmation_options(data_dir=tmp_path, binding=binding, now=START)
    owner_auth.verify_local_confirmation(
        data_dir=tmp_path,
        challenge_id=str(envelope["challenge_id"]),
        confirmation_token=str(envelope["confirmation_token"]),
        payload=request,
        now=START,
    )
    store.review_research_contract(PROJECT_ID, cid, **review)
    authority = RuleAuthority(tmp_path, PROJECT_ID, cid)
    assert authority.verify() == payload
    # Actual data/config reopening remains mandatory and absent here; no effects are launched.
    with pytest.raises(DataError, match="storage/snapshot is unavailable"):
        authority.reopen_daily_inputs()
    assert not (tmp_path / "daily-rule-workspace.json").exists()
    with pytest.raises(DataError):
        RuleAuthority(tmp_path, "wrong-project", cid).verify()


def test_large_daily_identity_requires_full_registered_validation(tmp_path: Path) -> None:
    from alpha_cli._control_json import _canonical_json
    from alpha_cli.control_store import _daily_control_limit

    contract = _contract(tmp_path)
    assert _daily_control_limit(contract) == 16 * 1024 * 1024
    assert len(_canonical_json(contract, "daily", max_bytes=_daily_control_limit(contract))) > 65536
    with pytest.raises(DataError, match="JSON exceeds 65536"):
        _canonical_json(contract, "generic")
    unknown = deepcopy(contract)
    unknown["protocol"]["d0_operator"]["name"] = "unknown_daily_route"
    assert _daily_control_limit(unknown) == 65536
    with pytest.raises(DataError, match="JSON exceeds 65536"):
        _canonical_json(unknown, "unknown", max_bytes=_daily_control_limit(unknown))
    changed = deepcopy(contract)
    changed["arbitrary_unrelated_payload"] = "x" * 70000
    with pytest.raises(DataError):
        _daily_control_limit(changed)
    with pytest.raises(DataError, match="JSON exceeds 16777216"):
        _canonical_json(
            {"bounded": "x" * (16 * 1024 * 1024)}, "daily-cap", max_bytes=16 * 1024 * 1024
        )


def test_synthetic_owner_cannot_issue_daily_container_event() -> None:
    import sys

    if sys.platform != "linux":
        pytest.skip("requires Linux retained native ownership")
    from alpha_cli.control_store import ControlStore
    from alpha_cli.native_supervisor import _open_lock, _Owner, synthetic_workspace
    from tests.unit.test_research_control_store import _approved_native_d1, _native_d1_job, _project

    with synthetic_workspace() as root:
        store = ControlStore(root)
        _project(store)
        cid, _ = _approved_native_d1(store)
        job = "b47ec09f-949f-4b87-b3d2-52bda3833f39"
        _native_d1_job(store, cid, job_id=job)
        with _open_lock(root, job) as lock:
            owner = _Owner(root, job, "success", 1, lock)
            store.claim_native_fixture(job, owner)
            observed = owner._issue(
                "native_container_created",
                {
                    "container_id": "a" * 64,
                    "container_name": None,
                    "image_id": None,
                    "resource_fingerprint": None,
                    "deadline_monotonic_ns": None,
                },
            )
            with pytest.raises(DataError, match="exact daily owner resource"):
                store.record_native_fixture_observation(job, observed)
        assert store.native_fixture_status(job)["state"] == "quarantined"


def test_daily_workspace_admission_caps_are_regular_whitelisted_and_aggregate(
    tmp_path: Path,
) -> None:
    from alpha_cli._native_daily_rule_artifacts import validate_daily_workspace

    study = _study(tmp_path)
    work = tmp_path / "bounded-work"
    work.mkdir()
    (work / "receipt.json").write_bytes(b"{}")
    validate_daily_workspace(work, study)
    unknown = work / "generated-shell.sh"
    unknown.write_bytes(b"")
    with pytest.raises(DataError, match="unregistered or unsafe"):
        validate_daily_workspace(work, study)
    unknown.unlink()
    for name in ("receipt.json", "daily-admission.json"):
        with (work / name).open("wb") as stream:
            stream.truncate(17 * 1024 * 1024)
    with pytest.raises(DataError, match="aggregate admitted artifact allowance"):
        validate_daily_workspace(work, study)
    (work / "receipt.json").unlink()
    (work / "daily-admission.json").unlink()
    logs = work / "logs/Loop_0/record/time_info/7"
    logs.mkdir(parents=True)
    for index in range(65):
        (logs / f"2026-10-31_00-00-00-{index:06d}.pkl").write_bytes(b"")
    with pytest.raises(DataError, match="aggregate admitted artifact allowance"):
        validate_daily_workspace(work, study)
