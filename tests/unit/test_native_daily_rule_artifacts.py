"""Artificial captured-format publication fixtures, never native/market acceptance."""

from __future__ import annotations

import copy
import hashlib
import json
import runpy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli._native_daily_rule_artifacts import (
    _prepared_parent_manifest,
    _publication_bytes,
    publish_daily_rule_run,
    validate_daily_economics,
    validate_daily_rule_artifacts,
)
from alpha_cli._native_daily_rule_protocol import (
    daily_position_payload,
    daily_worker_request,
    draft_daily_contract,
    sha,
)
from alpha_cli._native_daily_rule_study import bind_daily_study, daily_rule_terms_proposal
from alpha_cli.crypto_price_snapshot_query import query_binance_daily_price_snapshot
from alpha_core import DataError
from tests.unit.test_crypto_price_snapshot_query import _full_discovery_fixture


def make_daily_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Any, dict[str, Any], dict[str, Any]]:
    import alpha_cli.crypto_bulk_store as backend

    store, snapshot, manifest = _full_discovery_fixture(tmp_path)
    root = tmp_path / "control"
    config = root / "crypto" / "storage-config.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text('{"fixture":"artificial unit backend"}')
    snapshots = root / "crypto" / "snapshots"
    snapshots.mkdir()
    (snapshots / (snapshot.snapshot_id + ".json")).write_text(json.dumps(snapshot.to_dict()))
    end = datetime(2023, 1, 1, tzinfo=UTC)
    query = query_binance_daily_price_snapshot(
        snapshot,
        store,
        normalized_manifest_id=manifest,
        start=datetime(2020, 1, 1, tzinfo=UTC),
        end=end,
        available_by=end,
    )
    economics, resources = daily_rule_terms_proposal()
    study = bind_daily_study(
        query,
        snapshot_sha256=snapshot.snapshot_id,
        runtime_profile_sha256="a" * 64,
        storage_config_sha256=hashlib.sha256(config.read_bytes()).hexdigest(),
        container_image_id="sha256:" + "b" * 64,
        economics=economics,
        resources=resources,
        data_origin="artificial_fixture",
    )
    monkeypatch.setattr(backend, "configured_crypto_bulk_store", lambda selected: store)
    contract = draft_daily_contract(
        "sp_" + "1" * 64,
        {
            "data": study.query_sha256,
            "environment": study.runtime_profile_sha256,
            "code": "c" * 64,
            "dependency_lock": "d" * 64,
            "evaluator": "e" * 64,
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
    worker = runpy.run_path(str(Path(__file__).parents[2] / "workers/rdagent/costed_probe.py"))
    request = daily_worker_request(study)
    replay = worker["execute"]({**study.to_dict(), "bars": request["bars"]})
    admission = {
        "schema": "DailyNativeAdmissionV1",
        "rule_request": request,
        "study_id": study.content_sha256,
        "query_sha256": study.query_sha256,
        "image_id": study.container_image_id,
        "trial_id": "trial",
        "reservation_id": "trial",
        "spec_sha256": "f" * 64,
    }
    # This wrapper is a test fixture, not an actual observed native process receipt.
    receipt = {
        "admission": admission,
        "binding_sha256": sha(admission),
        "rule_positions": daily_position_payload(study),
        "economics": replay,
    }
    return root, study, contract, receipt


@pytest.fixture
def daily_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Any, dict[str, Any], dict[str, Any]]:
    return make_daily_fixture(tmp_path, monkeypatch)


def test_daily_actual_engine_accounting_and_immutable_projection_reopen(
    daily_fixture: tuple[Path, Any, dict[str, Any], dict[str, Any]],
) -> None:
    root, study, contract, receipt = daily_fixture
    validate_daily_economics(study, receipt["economics"])
    raw = json.dumps(receipt, sort_keys=True).encode()
    manifest = publish_daily_rule_run(
        root,
        project_id="fixture-project",
        contract_id="rc_fixture",
        contract=contract,
        execution_fingerprint="f" * 64,
        native_receipt=receipt,
        native_receipt_bytes=raw,
    )
    rdir = root / "runs" / manifest["run_id"]
    validate_daily_rule_artifacts(rdir, manifest, contract)
    assert manifest["data_origin"] == "artificial_fixture"
    assert manifest["real_market_evidence"] is False
    assert "ARTIFICIAL" in manifest["research_gate"]["watermark"]
    selectors = json.loads((rdir / "projections.json").read_text())
    assert selectors["crypto_snapshot_id"] == study.snapshot_sha256
    assert selectors["chart_snapshot_id"] != study.snapshot_sha256
    assert selectors["chart_snapshot_hash"] != study.snapshot_sha256
    before = {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "manifests" not in path.parts
    }
    assert (
        publish_daily_rule_run(
            root,
            project_id="fixture-project",
            contract_id="rc_fixture",
            contract=contract,
            execution_fingerprint="f" * 64,
            native_receipt=receipt,
            native_receipt_bytes=raw,
        )
        == manifest
    )
    after = {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and "manifests" not in path.parts
    }
    assert before == after


@pytest.mark.parametrize(
    "mutation",
    [
        "cash",
        "fees",
        "units",
        "fill_time",
        "signal",
        "origin",
        "nan",
        "counts",
        "missing_quote",
        "fill_price",
    ],
)
def test_daily_replay_rejects_accounting_chronology_and_claim_tampering(
    daily_fixture: tuple[Path, Any, dict[str, Any], dict[str, Any]], mutation: str
) -> None:
    _, study, _, receipt = daily_fixture
    result = copy.deepcopy(receipt["economics"])
    if mutation in {"cash", "fees", "units"}:
        fill = next(row for row in result["accounting"]["baseline"] if row["event"] == "fill")
        fill[{"cash": "cash", "fees": "fees_total", "units": "position_units"}[mutation]] += 1
    elif mutation == "fill_time":
        result["baseline"]["fill_trace"][0]["ts"] = "2020-01-21T00:00:00.000001+00:00"
    elif mutation == "signal":
        result["baseline"]["decision_trace"][0]["signal"] = 0
    elif mutation == "fill_price":
        result["baseline"]["fill_trace"][0]["price"] += 1
    elif mutation == "origin":
        result["data_origin"] = "captured_provider_history"
    elif mutation == "nan":
        result["baseline"]["equity_curve"][0][1] = float("nan")
    elif mutation == "missing_quote":
        result["accounting"]["baseline"].pop(0)
    else:
        result["baseline"]["fills"] = True
    with pytest.raises(DataError):
        validate_daily_economics(study, result)


def test_interrupted_parent_publication_reuses_same_completed_projection(
    daily_fixture: tuple[Path, Any, dict[str, Any], dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_cli import _artifacts

    root, _, contract, receipt = daily_fixture
    original = _artifacts.write_manifest

    def interrupted(path: Path, manifest: dict[str, Any]) -> None:
        if manifest["command"] == "research_daily_rule_native_v1":
            raise OSError("artificial parent publication interruption")
        original(path, manifest)

    monkeypatch.setattr(_artifacts, "write_manifest", interrupted)
    raw = json.dumps(receipt, sort_keys=True).encode()
    options: dict[str, Any] = dict(
        project_id="fixture-project",
        contract_id="rc_fixture",
        contract=contract,
        execution_fingerprint="f" * 64,
        native_receipt=receipt,
        native_receipt_bytes=raw,
    )
    with pytest.raises(OSError, match="interruption"):
        publish_daily_rule_run(root, **options)
    projections = {
        path.parent.name: path.read_bytes() for path in (root / "runs").glob("*/manifest.json")
    }
    assert len(projections) == 2
    monkeypatch.setattr(_artifacts, "write_manifest", original)
    manifest = publish_daily_rule_run(root, **options)
    validate_daily_rule_artifacts(root / "runs" / manifest["run_id"], manifest, contract)
    assert all(
        (root / "runs" / run_id / "manifest.json").read_bytes() == content
        for run_id, content in projections.items()
    )


def test_unaffordable_first_control_entry_stays_distinct_inconclusive(
    daily_fixture: tuple[Path, Any, dict[str, Any], dict[str, Any]],
) -> None:
    _, original, _, _ = daily_fixture
    study = original.model_copy(
        update={"economics": original.economics.model_copy(update={"starting_cash": 1.0})}
    )
    request = daily_worker_request(study)
    worker = runpy.run_path(str(Path(__file__).parents[2] / "workers/rdagent/costed_probe.py"))
    result = worker["execute"]({**study.to_dict(), "bars": request["bars"]})
    assert result["outcome"] == "accounting_rejection_inconclusive"
    assert result["control"]["fills"] == 0
    assert result["control"]["orders"] == 0
    assert result["control"]["rejected"] == 1
    validate_daily_economics(study, result)


def test_first_publication_and_restore_count_exact_parent_manifest_at_cap(
    daily_fixture: tuple[Path, Any, dict[str, Any], dict[str, Any]],
) -> None:
    root, study, contract, receipt = daily_fixture
    manifest = publish_daily_rule_run(
        root,
        project_id="fixture-project",
        contract_id="rc_fixture",
        contract=contract,
        execution_fingerprint="f" * 64,
        native_receipt=receipt,
        native_receipt_bytes=json.dumps(receipt, sort_keys=True).encode(),
    )
    run_id = manifest["run_id"]
    rdir = root / "runs" / run_id
    selectors = json.loads((rdir / "projections.json").read_text())
    actual_marker = (rdir / "manifest.json").read_bytes()
    (rdir / "manifest.json").unlink()
    prepared = _prepared_parent_manifest(rdir, manifest)
    assert prepared == actual_marker
    roots = [
        rdir,
        *(root / "runs" / value["run_id"] for value in selectors["roles"].values()),
        root / "snapshots" / selectors["chart_snapshot_id"],
    ]
    existing = [path for directory in roots for path in directory.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in existing) + len(prepared)
    bounded = study.model_copy(
        update={"resources": study.resources.model_copy(update={"max_artifact_bytes": total})}
    )
    too_small = study.model_copy(
        update={"resources": study.resources.model_copy(update={"max_artifact_bytes": total - 1})}
    )
    # Exactly 64 published files, including the not-yet-written completion marker.
    for index in range(64 - len(existing) - 1):
        (rdir / f".count-boundary-{index}").touch()
    _publication_bytes(root, run_id, selectors, bounded, parent_manifest=prepared)
    with pytest.raises(DataError, match="aggregate"):
        _publication_bytes(root, run_id, selectors, too_small, parent_manifest=prepared)
    (rdir / "manifest.json").write_bytes(actual_marker)
    _publication_bytes(root, run_id, selectors, bounded)
    _publication_bytes(root, run_id, selectors, bounded, parent_manifest=prepared)
    with pytest.raises(DataError, match="aggregate"):
        _publication_bytes(root, run_id, selectors, too_small)
    (rdir / ".one-file-over").touch()
    with pytest.raises(DataError, match="aggregate"):
        _publication_bytes(root, run_id, selectors, bounded)
    (rdir / "manifest.json").unlink()
    with pytest.raises(DataError, match="aggregate"):
        _publication_bytes(root, run_id, selectors, bounded, parent_manifest=prepared)


def test_daily_d0_publishes_only_independent_artificial_fixture(
    daily_fixture: tuple[Path, Any, dict[str, Any], dict[str, Any]],
) -> None:
    root, _, contract, _ = daily_fixture
    manifest = publish_daily_rule_run(
        root,
        project_id="fixture-project",
        contract_id="rc_fixture",
        contract=contract,
        execution_fingerprint="0" * 64,
    )
    rdir = root / "runs" / manifest["run_id"]
    validate_daily_rule_artifacts(rdir, manifest, contract)
    acceptance = json.loads((rdir / "d0_acceptance.json").read_text())
    assert acceptance["positions"]["real_market_evidence"] is False
    assert acceptance["study"]["provider"] == "synthetic"
    assert not (rdir / "economics.json").exists()
