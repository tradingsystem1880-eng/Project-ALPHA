"""Portable evidence guards over artificial canonical executions.

Hand-bound receipt envelopes below test validation only. They establish no Docker
execution, process observation, owner approval, or real-market acceptance.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import daily_rule_report
from alpha_cli._native_daily_rule_artifacts import (
    publish_daily_rule_run,
    read_json_artifact,
    same_artifact,
    validate_daily_economics,
    validate_daily_native_result,
    validate_daily_workspace,
)
from alpha_cli._native_daily_rule_protocol import canonical, sha
from alpha_cli._native_loop_admission import SOURCE_SHA256, WORKER, WORKER_FILES
from alpha_cli.artifact_contract import artifact_metadata
from alpha_core import DataError
from tests.unit.test_native_daily_rule_artifacts import make_daily_fixture

Fixture = tuple[Path, Any, dict[str, Any], dict[str, Any], dict[str, Any]]


@pytest.fixture(scope="module")
def artificial_evidence(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Fixture]:
    # The helper runs the real canonical engine once over artificial provider-format
    # bars. Its local storage adapter still verifies actual bytes, hashes and query.
    with pytest.MonkeyPatch.context() as patch:
        root, study, contract, receipt = make_daily_fixture(
            tmp_path_factory.mktemp("daily-guard-fixture"), patch
        )
        manifest = publish_daily_rule_run(
            root,
            project_id="fixture-project",
            contract_id="rc_fixture",
            contract=contract,
            execution_fingerprint="f" * 64,
            native_receipt=receipt,
            native_receipt_bytes=json.dumps(receipt, sort_keys=True).encode(),
        )
        yield root, study, contract, receipt, manifest


def _receipt_workspace(
    root: Path,
    evidence: Fixture,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    _, study, _, fixture_receipt, _ = evidence
    admission = copy.deepcopy(fixture_receipt["admission"])
    admission.update(
        job_id="portable-validation-only",
        reservation_id="portable-reservation",
        trial_id="portable-reservation",
        manifest_sha256="1" * 64,
        owner_id="fixture-owner",
        mode="INCONCLUSIVE",
        loop_steps=5,
        rule_profile=study.runtime_profile_sha256,
        owner_receipt_id="fixture-not-an-owner-receipt",
        cpu_milliseconds=10000,
        container_name="fixture-no-container-started",
        container_id="2" * 64,
        resource_fingerprint="3" * 64,
        deadline_monotonic_ns=1,
    )
    helpers = {
        name.removesuffix(".py"): hashlib.sha256((WORKER / name).read_bytes()).hexdigest()
        for name in (*WORKER_FILES, "rule_probe.py", "costed_probe.py")
        if name.endswith(".py") and name != "fixture_entry.py"
    }
    receipt = {
        **copy.deepcopy(fixture_receipt),
        "admission": admission,
        "binding_sha256": sha(admission),
        "authority": "none",
        "synthetic": True,
        "routes_enabled": False,
        "imported_worker_sha256": helpers,
        "scientific_acceptance": "not_admitted",
        "source_tree_sha256": SOURCE_SHA256,
        "checkpoint_binding_verified": True,
        "checks": {"events": ["direct_exp_gen", "coding", "running", "feedback", "record"]},
    }
    root.mkdir()
    for role in ("baseline", "control"):
        (root / (role + ".json")).write_text(
            canonical(
                {
                    "schema": "RulePositionArtifactV1",
                    "unit": "position",
                    "positions": receipt["rule_positions"][role],
                }
            )
        )
    (root / "receipt.json").write_text(canonical(receipt))
    return admission, receipt, helpers


def test_hand_bound_receipt_validation_is_read_only_not_process_acceptance(
    tmp_path: Path,
    artificial_evidence: Fixture,
) -> None:
    work = tmp_path / "work"
    admission, _, helpers = _receipt_workspace(work, artificial_evidence)
    before = {path.name: path.read_bytes() for path in work.iterdir()}
    assert (
        validate_daily_native_result(work, admission, artificial_evidence[1], helpers)
        == before["receipt.json"]
    )
    assert {path.name: path.read_bytes() for path in work.iterdir()} == before


@pytest.mark.parametrize(
    "defect",
    [
        "changed_admission",
        "image",
        "query",
        "rules_request",
        "positions",
        "authority",
        "real_claim",
        "routes",
        "helper_bytes",
        "binding",
        "source_pin",
        "checkpoint",
        "stage_order",
    ],
)
def test_receipt_cannot_rebind_frozen_inputs_or_upgrade_its_claim(
    tmp_path: Path,
    artificial_evidence: Fixture,
    defect: str,
) -> None:
    work = tmp_path / "work"
    admission, receipt, helpers = _receipt_workspace(work, artificial_evidence)
    if defect == "changed_admission":
        receipt["admission"] = {**admission, "owner_id": "different-owner"}
    elif defect in {"image", "query", "rules_request"}:
        key = {"image": "image_id", "query": "query_sha256", "rules_request": "rule_request"}[
            defect
        ]
        admission[key] = "sha256:" + "4" * 64 if defect == "image" else "4" * 64
        receipt["binding_sha256"] = sha(admission)
    elif defect == "positions":
        receipt["rule_positions"]["baseline"][0] = 0
    elif defect == "authority":
        receipt["authority"] = "promoted"
    elif defect == "real_claim":
        receipt["synthetic"] = False
    elif defect == "routes":
        receipt["routes_enabled"] = True
    elif defect == "helper_bytes":
        receipt["imported_worker_sha256"] = {**helpers, "rule_probe": "5" * 64}
    elif defect == "binding":
        receipt["binding_sha256"] = "6" * 64
    elif defect == "source_pin":
        receipt["source_tree_sha256"] = "7" * 64
    elif defect == "checkpoint":
        receipt["checkpoint_binding_verified"] = False
    else:
        receipt["checks"]["events"] = ["running", "direct_exp_gen", "coding", "feedback", "record"]
    (work / "receipt.json").write_text(canonical(receipt))
    with pytest.raises(DataError, match="identity/source/positions"):
        validate_daily_native_result(work, admission, artificial_evidence[1], helpers)


@pytest.mark.parametrize(
    "defect", ["missing", "malformed", "position", "unregistered", "symlink", "fifo"]
)
def test_native_evidence_availability_and_file_safety_fail_closed(
    tmp_path: Path,
    artificial_evidence: Fixture,
    defect: str,
) -> None:
    work = tmp_path / "work"
    admission, _, helpers = _receipt_workspace(work, artificial_evidence)
    if defect == "missing":
        (work / "receipt.json").unlink()
    elif defect == "malformed":
        (work / "receipt.json").write_bytes(b"{")
    elif defect == "position":
        (work / "baseline.json").write_text('{"positions":[0]}')
    elif defect == "unregistered":
        (work / "generated.sh").write_text("exit 0")
    elif defect == "symlink":
        (work / "control.json").unlink()
        (work / "control.json").symlink_to(work / "baseline.json")
    else:
        os.mkfifo(work / "progress.json")
    with pytest.raises(DataError):
        validate_daily_native_result(work, admission, artificial_evidence[1], helpers)


def test_allowed_native_logs_still_cannot_exceed_aggregate_file_or_byte_allowance(
    tmp_path: Path,
    artificial_evidence: Fixture,
) -> None:
    _, study, _, _, _ = artificial_evidence
    work = tmp_path / "work"
    work.mkdir()
    logs = work / "logs/Loop_0/running/time_info/0"
    logs.mkdir(parents=True)
    for index in range(65):
        (logs / f"2026-01-01T00:00:{index:02d}.pkl").touch()
    with pytest.raises(DataError, match="aggregate"):
        validate_daily_workspace(work, study)
    for path in logs.iterdir():
        path.unlink()
    with (work / "receipt.json").open("wb") as stream:
        stream.truncate(study.resources.max_artifact_bytes + 1)
    with pytest.raises(DataError, match="aggregate"):
        validate_daily_workspace(work, study)


@pytest.mark.parametrize(
    "defect",
    [
        "missing_accounting",
        "empty",
        "too_many",
        "shape",
        "bad_time",
        "naive_time",
        "reversed",
        "currency",
        "boolean_cash",
        "negative_fee",
        "negative_free_cash",
        "fill_sequence",
        "fill_timestamp",
        "quote_is_fill",
        "unknown_event",
        "missing_fill",
        "missing_quote",
        "wrong_fee",
        "outcome",
        "canonical_result",
        "control_late",
    ],
)
def test_actual_accounting_rejects_independent_chronological_and_unit_mutations(
    artificial_evidence: Fixture,
    defect: str,
) -> None:
    _, study, _, receipt, _ = artificial_evidence
    value = copy.deepcopy(receipt["economics"])
    rows = value["accounting"]["baseline"]
    fill = next(row for row in rows if row["event"] == "fill")
    if defect == "missing_accounting":
        value["accounting"] = {"baseline": rows}
    elif defect == "empty":
        value["accounting"]["baseline"] = []
    elif defect == "too_many":
        value["accounting"]["baseline"] = [rows[0]] * 4401
    elif defect == "shape":
        rows[0]["free_cash_usd"] = rows[0].pop("cash_free")
    elif defect == "bad_time":
        rows[0]["ts"] = "not-a-time"
    elif defect == "naive_time":
        rows[0]["ts"] = "2020-01-21T00:00:00"
    elif defect == "reversed":
        rows[0]["ts"] = rows[-1]["ts"]
    elif defect == "currency":
        rows[0]["currency"] = "USD"
    elif defect == "boolean_cash":
        rows[0]["cash"] = True
    elif defect == "negative_fee":
        fill["commission"] = -0.01
    elif defect == "negative_free_cash":
        rows[0]["cash_free"] = -1.0
    elif defect == "fill_sequence":
        fill["fill_sequence_id"] = True
    elif defect == "fill_timestamp":
        fill["ts"] = rows[0]["ts"]
    elif defect == "quote_is_fill":
        rows[0]["fill_sequence_id"] = 1
    elif defect == "unknown_event":
        rows[0]["event"] = "paper_order"
    elif defect == "missing_fill":
        value["accounting"]["baseline"] = [row for row in rows if row["event"] != "fill"]
        for row in value["accounting"]["baseline"]:
            row.update(cash=study.economics.starting_cash, position_units=0, fees_total=0)
    elif defect == "missing_quote":
        rows.pop(0)
    elif defect == "wrong_fee":
        fill["commission"] += 0.001
    elif defect == "outcome":
        value["outcome"] = "accounting_rejection_inconclusive"
    elif defect == "canonical_result":
        del value["baseline"]["equity_curve"]
    else:
        value["control"]["fill_trace"][0]["ts"] = "2020-01-23T00:00:00.000001+00:00"
    with pytest.raises(DataError):
        validate_daily_economics(study, value)


@pytest.mark.parametrize("payload", [b"{", b"[]", b'{"equity":NaN}'])
def test_report_json_rejects_malformed_nonobject_or_nonfinite_payload(
    tmp_path: Path,
    payload: bytes,
) -> None:
    path = tmp_path / "receipt.json"
    path.write_bytes(payload)
    with pytest.raises(DataError):
        daily_rule_report._json(path)


def test_artifact_read_limits_and_symlinks_are_checked_without_loading_oversized_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "artifact.json"
    path.write_bytes(b'{"ok":true}')
    assert same_artifact(path, b'{"ok":true}')
    assert not same_artifact(path, b"{}")
    assert read_json_artifact(path, maximum_bytes=11) == {"ok": True}
    with pytest.raises(DataError, match="byte bound"):
        read_json_artifact(path, maximum_bytes=10)
    path.write_bytes(b"{")
    with pytest.raises(DataError, match="malformed"):
        read_json_artifact(path, maximum_bytes=11)
    link = tmp_path / "link.json"
    link.symlink_to(path)
    assert not same_artifact(link, b"{")
    with pytest.raises(DataError, match="unsafe"):
        read_json_artifact(link, maximum_bytes=11)
    with pytest.raises(DataError, match="unavailable"):
        daily_rule_report._json(link)
    with path.open("wb") as stream:
        stream.truncate(32 * 1024 * 1024 + 1)
    with pytest.raises(DataError, match="bound"):
        daily_rule_report._json(path)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("project_id", None, "project identity"),
        ("research_fingerprints", {}, "source fingerprint"),
        ("schema_version", 2, "versioned immutable"),
    ],
)
def test_report_rejects_missing_identity_before_artifact_verification(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    run_id = "a" * 16
    path = tmp_path / "runs" / run_id
    path.mkdir(parents=True)
    manifest = {
        "command": "research_daily_rule_native_v1",
        "project_id": "fixture",
        "research_fingerprints": {"code": "b" * 64},
        "schema_version": 3,
    }
    manifest[field] = value
    (path / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(DataError, match=message):
        daily_rule_report._run(tmp_path, run_id)


@pytest.mark.parametrize(
    "role,limit,offset",
    [
        ("unknown", 10, 0),
        ("baseline", True, 0),
        ("control", 1001, 0),
        ("baseline", 10, True),
        ("control", 10, -1),
        ("baseline", 10, 100001),
    ],
)
def test_report_rejects_invalid_paging_before_any_run_read(
    tmp_path: Path,
    role: str,
    limit: int,
    offset: int,
) -> None:
    with pytest.raises(DataError, match="role|limit|offset"):
        daily_rule_report.daily_rule_evidence(
            "missing", data_dir=tmp_path, role=role, limit=limit, offset=offset
        )


@pytest.mark.parametrize("defect", ["selectors", "study", "query", "economics", "lineage"])
def test_report_rejects_semantically_rehashed_evidence(
    tmp_path: Path,
    artificial_evidence: Fixture,
    defect: str,
) -> None:
    original, _, _, _, parent_manifest = artificial_evidence
    root = tmp_path / "copied"
    shutil.copytree(original, root)
    parent = root / "runs" / parent_manifest["run_id"]
    file = {
        "selectors": "projections.json",
        "study": "study.json",
        "query": "query.json",
        "economics": "economics.json",
        "lineage": "projections.json",
    }[defect]
    if defect == "lineage":
        selectors = json.loads((parent / "projections.json").read_text())
        projection = root / "runs" / selectors["roles"]["baseline"]["run_id"]
        path = projection / "lineage.json"
        value = json.loads(path.read_text())
        value["crypto_snapshot_id"] = "9" * 64
        path.write_text(canonical(value))
        projection_manifest = json.loads((projection / "manifest.json").read_text())
        projection_manifest["artifacts"][path.name] = artifact_metadata(path)
        (projection / "manifest.json").write_text(json.dumps(projection_manifest))
        selectors["roles"]["baseline"]["manifest_sha256"] = hashlib.sha256(
            (projection / "manifest.json").read_bytes()
        ).hexdigest()
        value, path = selectors, parent / "projections.json"
    else:
        path = parent / file
        value = json.loads(path.read_text())
        if defect == "selectors":
            value["parent_run_id"] = "1" * 16
        elif defect == "study":
            value["authority"] = "promoted"
        elif defect == "query":
            value["rows"][0]["close"] += 1
        else:
            value["baseline"]["equity_curve"][-1][1] += 1
    path.write_text(canonical(value))
    updated = json.loads((parent / "manifest.json").read_text())
    updated["artifacts"][path.name] = artifact_metadata(path)
    (parent / "manifest.json").write_text(json.dumps(updated))
    with pytest.raises(DataError):
        daily_rule_report.daily_rule_evidence(parent_manifest["run_id"], data_dir=root)
