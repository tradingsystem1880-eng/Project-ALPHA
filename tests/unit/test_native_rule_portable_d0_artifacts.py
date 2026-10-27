"""Immutable seven-bar D0 artifacts; no native receipt issuance or execution authority."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pytest

from alpha_cli._native_rule_artifacts import (
    PILOT_COMMAND,
    d0_fingerprint,
    publish_rule_run,
    validate_rule_artifacts,
)
from alpha_cli._native_rule_protocol import canonical, study_data_hash
from alpha_cli.artifact_contract import artifact_metadata, verify_manifest_artifacts
from alpha_cli.control_store import ControlStore
from alpha_core import DataError
from tests.unit.test_native_rule_authority import _approve
from tests.unit.test_research_control_store import PROJECT_ID


@dataclass
class D0Case:
    root: Path
    store: ControlStore
    contract_id: str
    contract: dict[str, object]

    def publish(self) -> dict[str, Any]:
        return publish_rule_run(
            self.root,
            project_id=PROJECT_ID,
            contract_id=self.contract_id,
            contract=self.contract,
            execution_fingerprint=d0_fingerprint(self.contract),
        )


@pytest.fixture
def approved(tmp_path: Path) -> D0Case:
    # Real consumed local confirmation and ordinary human approval, using seven fixed bars.
    fingerprints = {
        key: hashlib.sha256(key.encode()).hexdigest()
        for key in ("code", "environment", "evaluator", "dependency_lock")
    }
    _approve(tmp_path, {**fingerprints, "data": study_data_hash(True)}, costed=True)
    store = ControlStore(tmp_path)
    cid = str(store.research_case_summary(PROJECT_ID)["active_contract_id"])
    contract = cast(dict[str, object], store.get_research_contract(cid)["payload"])
    return D0Case(tmp_path, store, cid, contract)


@pytest.fixture
def published(approved: D0Case) -> tuple[D0Case, Path, dict[str, Any]]:
    manifest = approved.publish()
    rdir = approved.root / "runs" / manifest["run_id"]
    validate_rule_artifacts(rdir, manifest, approved.contract)
    return approved, rdir, manifest


def _snapshot(case: D0Case) -> tuple[dict[str, bytes], tuple[str, ...]]:
    files = {
        str(path.relative_to(case.root)): path.read_bytes()
        for path in (case.root / "runs").rglob("*")
        if path.is_file()
    }
    with case.store._transaction(write=False) as connection:
        rows = tuple(connection.iterdump())
    return files, rows


def test_d0_publication_retry_preserves_exact_bytes_and_approval_state(approved: D0Case) -> None:
    before_sql = _snapshot(approved)[1]
    manifest = approved.publish()
    rdir = approved.root / "runs" / manifest["run_id"]
    assert manifest["command"] == PILOT_COMMAND
    assert manifest["evidence_zone"] == "D0"
    assert manifest["scientific_acceptance"] == "not_admitted"
    assert manifest["eligible_for_holdout_or_execution"] is False
    assert manifest["real_market_evidence"] is False
    assert manifest["places_orders"] is False
    assert set(manifest["artifacts"]) == {"baseline.json", "control.json", "d0_acceptance.json"}
    assert json.loads((rdir / "baseline.json").read_text())["positions"] == [0, 1, 0, 1, 0, 0]
    assert json.loads((rdir / "control.json").read_text())["positions"] == [0, 0, 0, 0, 0, 0]
    before = _snapshot(approved)
    assert before[1] == before_sql
    validate_rule_artifacts(rdir, manifest, approved.contract)
    assert approved.publish() == manifest
    assert _snapshot(approved) == before


def test_changed_baseline_fails_hash_verification_and_retry_cannot_repair(
    published: tuple[D0Case, Path, dict[str, Any]],
) -> None:
    case, rdir, manifest = published
    path = rdir / "baseline.json"
    payload = json.loads(path.read_text())
    payload["positions"][0] = 1
    path.write_text(canonical(payload))
    assert path.stat().st_size == manifest["artifacts"]["baseline.json"]["size_bytes"]
    corrupted = _snapshot(case)
    with pytest.raises(DataError, match="hash mismatch"):
        validate_rule_artifacts(rdir, manifest, case.contract)
    assert _snapshot(case) == corrupted
    with pytest.raises(DataError, match="immutable artifact.*different bytes"):
        case.publish()
    assert _snapshot(case) == corrupted


@pytest.mark.parametrize("role", ["baseline", "control"])
def test_rehashed_consistent_position_tampering_fails_mechanical_recomputation(
    published: tuple[D0Case, Path, dict[str, Any]], role: str
) -> None:
    case, rdir, manifest = published
    role_name = f"{role}.json"
    positions = json.loads((rdir / role_name).read_text())
    positions["positions"][0] = 1
    acceptance = json.loads((rdir / "d0_acceptance.json").read_text())
    acceptance["positions"][role][0] = 1
    for name, payload in ((role_name, positions), ("d0_acceptance.json", acceptance)):
        (rdir / name).write_text(canonical(payload))
        manifest["artifacts"][name] = artifact_metadata(rdir / name)
    (rdir / "manifest.json").write_text(canonical(manifest))
    corrupted = _snapshot(case)
    # Positive control: the rehashed artifacts agree with their complete metadata envelope.
    verify_manifest_artifacts(rdir, manifest)
    with pytest.raises(DataError, match="exact mechanical recomputation"):
        validate_rule_artifacts(rdir, manifest, case.contract)
    assert _snapshot(case) == corrupted
    with pytest.raises(DataError, match="immutable artifact.*different bytes"):
        case.publish()
    assert _snapshot(case) == corrupted


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("directory", "identity does not match directory"),
        ("run_id", "parent identity differs"),
        ("command", "command/operator changed"),
        ("operator", "command/operator changed"),
    ],
)
def test_d0_artifact_identity_mutations_are_read_only_denials(
    published: tuple[D0Case, Path, dict[str, Any]], defect: str, message: str
) -> None:
    case, rdir, original = published
    manifest = deepcopy(original)
    if defect in {"directory", "run_id"}:
        changed = rdir.with_name("f" * 16)
        assert changed.name != rdir.name
        rdir.rename(changed)
        rdir = changed
        if defect == "run_id":
            manifest["run_id"] = rdir.name
    elif defect == "command":
        manifest["command"] = "untrusted_other_command"
    else:
        assert defect == "operator"
        manifest["d0_operator"]["fingerprint"] = "0" * 64
    (rdir / "manifest.json").write_text(canonical(manifest))
    corrupted = _snapshot(case)
    if defect != "directory":
        verify_manifest_artifacts(rdir, manifest)
    with pytest.raises(DataError, match=message):
        validate_rule_artifacts(rdir, manifest, case.contract)
    assert _snapshot(case) == corrupted


def test_d0_retry_does_not_restore_a_deleted_immutable_artifact(
    published: tuple[D0Case, Path, dict[str, Any]],
) -> None:
    case, rdir, manifest = published
    (rdir / "baseline.json").unlink()
    corrupted = _snapshot(case)
    with pytest.raises(DataError, match="artifact set mismatch"):
        validate_rule_artifacts(rdir, manifest, case.contract)
    with pytest.raises(DataError, match="cannot add artifact.*after immutable manifest"):
        case.publish()
    assert _snapshot(case) == corrupted


@pytest.mark.parametrize("defect", ["missing_bytes", "mismatched_bytes", "bytes_without_receipt"])
def test_invalid_native_receipt_pair_is_rejected_before_d0_publication(
    approved: D0Case, defect: str
) -> None:
    # All cases are negative. No matching native receipt/bytes pair is ever published.
    receipt: dict[str, object] | None = {"fixture": "untrusted-negative-input"}
    captured: bytes | None = None
    message = "captured validated receipt bytes"
    if defect == "mismatched_bytes":
        captured = b'{"fixture":"different-negative-input"}'
    elif defect == "bytes_without_receipt":
        receipt, captured = None, b"{}"
        message = "D0 publication cannot carry native receipt bytes"
    before = _snapshot(approved)
    assert not (approved.root / "runs").exists()
    with pytest.raises(DataError, match=message):
        publish_rule_run(
            approved.root,
            project_id=PROJECT_ID,
            contract_id=approved.contract_id,
            contract=approved.contract,
            execution_fingerprint=d0_fingerprint(approved.contract),
            native_receipt=receipt,
            native_receipt_bytes=captured,
        )
    assert not (approved.root / "runs").exists()
    assert _snapshot(approved) == before


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("operator", "operator version or binding changed"),
        ("boundary_authority", "capability is synthetic only"),
        ("variants", "requires D0 plus baseline/control exposures"),
        ("model_calls", "forbids model and tool budgets"),
        ("input_tokens", "forbids model and tool budgets"),
        ("output_tokens", "forbids model and tool budgets"),
        ("tool_calls", "forbids model and tool budgets"),
        ("study", "analysis plan changed"),
        ("data", "data fingerprint changed"),
    ],
)
def test_closed_contract_mutations_reject_before_any_publication(
    approved: D0Case, defect: str, message: str
) -> None:
    changed = cast(dict[str, Any], deepcopy(approved.contract))
    if defect == "operator":
        changed["protocol"]["d0_operator"]["version"] += 1
    elif defect == "boundary_authority":
        changed["protocol"]["boundary_authority"]["empirical_confirmation_authorized"] = True
    elif defect == "variants":
        changed["budget"]["variants"] = 4
    elif defect in {"model_calls", "input_tokens", "output_tokens", "tool_calls"}:
        changed["budget"]["rdagent_native_v1_" + defect] = 1
    elif defect == "study":
        changed["analysis_plan"]["study"]["rules_spec"] = "{}"
    else:
        assert defect == "data"
        changed["hashes"]["data"] = "0" * 64
    before = _snapshot(approved)
    assert not (approved.root / "runs").exists()
    # Compute the fingerprint from the valid control, so publication itself rejects the mutant.
    fingerprint = d0_fingerprint(approved.contract)
    with pytest.raises(DataError, match=message):
        publish_rule_run(
            approved.root,
            project_id=PROJECT_ID,
            contract_id=approved.contract_id,
            contract=changed,
            execution_fingerprint=fingerprint,
        )
    assert not (approved.root / "runs").exists()
    assert _snapshot(approved) == before
