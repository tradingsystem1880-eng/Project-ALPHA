"""Frozen engineering protocol references confer no research authority."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import ml_refit
from alpha_cli.main import app
from alpha_cli.ml_contract import (
    MLContractError,
    canonical_json_bytes,
    prepare_exchange,
    validate_request_bundle,
)
from alpha_cli.ml_refit import (
    plan_refit,
    publish_refit_plan,
    read_engineering_protocol,
    status_refit_plan,
)
from alpha_cli.research_analysis_plan import analysis_family_catalog
from tests.unit.test_ml_contract import _draft, _panel


def _protocol() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "authority": "engineering_provenance_only",
        "original_request_sha256": "a" * 64,
        "changed_request_sha256": "b" * 64,
        "worker_source_sha256": "c" * 64,
        "worker_lock_sha256": "d" * 64,
        "model": {"name": "linear", "parameters": {"estimator": "ridge", "alpha": 1}},
        "fixture": {
            "generator": "qlib_w11_fixture",
            "version": 2,
            "world": "past_change",
            "source_sha256": "f" * 64,
            "limits": {
                "max_pipeline_fits": 2,
                "max_native_fits": 2,
                "max_panel_rows": 16000,
                "max_features": 158,
                "max_folds": 2,
                "max_members": 2,
                "max_rounds": 3,
                "cpu_threads": 1,
                "max_seconds": 300,
                "max_rss_bytes": 1610612736,
                "automatic_retries": 0,
            },
        },
        "expected_relation": "changed_world",
        "changed_dimensions": ["panel"],
    }


def _write(path: Path, payload: object) -> str:
    encoded = canonical_json_bytes(payload)
    path.write_bytes(encoded)
    return hashlib.sha256(encoded).hexdigest()


def test_protocol_requires_exact_frozen_bytes(tmp_path: Path) -> None:
    path = tmp_path / "protocol.json"
    payload = _protocol()
    digest = _write(path, payload)
    assert read_engineering_protocol(path, expected_sha256=digest) == payload
    with pytest.raises(MLContractError, match="hash"):
        read_engineering_protocol(path, expected_sha256="e" * 64)


@pytest.mark.parametrize("cutoff", ["2025-06-30T00:00:00+00:00", "2025-06-30T00:00:00Z"])
def test_protocol_accepts_an_explicit_utc_cutoff(tmp_path: Path, cutoff: str) -> None:
    path = tmp_path / "protocol.json"
    payload = {**_protocol(), "cutoff": cutoff}
    digest = _write(path, payload)
    assert read_engineering_protocol(path, expected_sha256=digest)["cutoff"] == cutoff


@pytest.mark.parametrize(
    "cutoff",
    [
        "2025-06-30T00:00:00",
        "2025-06-30T10:00:00+10:00",
        "2025-06-30",
        "2025-13-30T00:00:00+00:00",
        "not-a-timestamp",
        20250630,
        None,
    ],
)
def test_protocol_rejects_a_cutoff_that_is_not_explicit_utc(tmp_path: Path, cutoff: object) -> None:
    path = tmp_path / "protocol.json"
    digest = _write(path, {**_protocol(), "cutoff": cutoff})
    with pytest.raises(MLContractError, match="cutoff must be an explicit UTC timestamp"):
        read_engineering_protocol(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", True),
        ("schema_version", 1.0),
        ("authority", "native_admission"),
        ("original_request_sha256", "not-a-hash"),
        ("worker_source_sha256", "C" * 64),
        ("worker_lock_sha256", None),
        ("expected_relation", "independent_replication"),
        ("changed_dimensions", ["panel", "panel"]),
        ("changed_dimensions", ["unknown"]),
        ("changed_dimensions", "panel"),
        ("model", {"name": "catboost", "parameters": {}}),
        ("model", {"name": "linear", "parameters": {"estimator": "lasso", "alpha": 1}}),
        ("model", {"name": "linear", "parameters": {"estimator": "ridge", "alpha": True}}),
        ("model", {"name": "linear", "parameters": {"estimator": "ridge", "alpha": 10**400}}),
    ],
)
def test_protocol_rejects_malformed_fields(tmp_path: Path, field: str, value: object) -> None:
    path = tmp_path / "protocol.json"
    digest = _write(path, {**_protocol(), field: value})
    with pytest.raises(MLContractError):
        read_engineering_protocol(path, expected_sha256=digest)


@pytest.mark.parametrize("change", ["missing", "extra", "unchanged_world", "false_reuse"])
def test_protocol_rejects_scope_or_identity_mismatch(tmp_path: Path, change: str) -> None:
    path = tmp_path / "protocol.json"
    payload = _protocol()
    if change == "missing":
        payload.pop("worker_lock_sha256")
    elif change == "extra":
        payload["counterfactual_refit"] = True
    elif change == "unchanged_world":
        payload["changed_request_sha256"] = payload["original_request_sha256"]
    else:
        payload["expected_relation"] = "same_evidence"
        payload["changed_dimensions"] = []
    digest = _write(path, payload)
    with pytest.raises(MLContractError):
        read_engineering_protocol(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "encoded",
    [
        b'{"schema_version":1,"schema_version":1}',
        b'{"x":NaN}',
        b"[]",
        b"{",
        pytest.param(b'{"x":' + b"1" * 5000 + b"}\n", id="oversized_integer"),
        pytest.param(b"[" * 2000 + b"0" + b"]" * 2000, id="excessive_nesting"),
        pytest.param(b'{"alpha":1e999}\n', id="numeric_overflow"),
    ],
)
def test_protocol_rejects_ambiguous_or_malformed_json(tmp_path: Path, encoded: bytes) -> None:
    path = tmp_path / "protocol.json"
    path.write_bytes(encoded)
    with pytest.raises(MLContractError):
        read_engineering_protocol(path, expected_sha256=hashlib.sha256(encoded).hexdigest())


def test_protocol_rejects_noncanonical_and_symlink_inputs(tmp_path: Path) -> None:
    path = tmp_path / "protocol.json"
    encoded = json.dumps(_protocol(), indent=2).encode()
    path.write_bytes(encoded)
    with pytest.raises(MLContractError, match="canonical"):
        read_engineering_protocol(path, expected_sha256=hashlib.sha256(encoded).hexdigest())
    digest = _write(path, _protocol())
    alias = tmp_path / "alias.json"
    alias.symlink_to(path)
    with pytest.raises(MLContractError, match="regular"):
        read_engineering_protocol(alias, expected_sha256=digest)


def test_identical_evidence_protocol_requires_no_declared_change(tmp_path: Path) -> None:
    path = tmp_path / "protocol.json"
    payload = _protocol()
    payload.update(
        changed_request_sha256=payload["original_request_sha256"],
        expected_relation="same_evidence",
        changed_dimensions=[],
    )
    payload["fixture"]["world"] = "renamed"
    digest = _write(path, payload)
    assert read_engineering_protocol(path, expected_sha256=digest) == payload


def test_double_ensemble_protocol_has_fixed_bounded_recipe(tmp_path: Path) -> None:
    path = tmp_path / "protocol.json"
    payload = _protocol()
    payload["model"] = {
        "name": "double_ensemble",
        "parameters": {
            "num_models": 2,
            "num_boost_round": 3,
            "early_stopping_rounds": 2,
            "min_data_in_leaf": 5,
            "num_threads": 1,
        },
    }
    payload["fixture"]["limits"]["max_native_fits"] = 4
    digest = _write(path, payload)
    assert read_engineering_protocol(path, expected_sha256=digest) == payload
    payload["model"]["parameters"]["num_models"] = True
    digest = _write(path, payload)
    with pytest.raises(MLContractError):
        read_engineering_protocol(path, expected_sha256=digest)


@pytest.mark.parametrize(
    "world",
    [
        "observed",
        "renamed",
        "unavailable_future",
        "appended_future",
        "past_change",
        "common_exposure",
        "cost_stress",
    ],
)
def test_protocol_accepts_only_the_declared_fixture_world_relation(
    tmp_path: Path, world: str
) -> None:
    path = tmp_path / "protocol.json"
    payload = _protocol()
    payload["fixture"]["world"] = world
    if world in {"observed", "renamed"}:
        payload["changed_request_sha256"] = payload["original_request_sha256"]
        payload["expected_relation"] = "same_evidence"
        payload["changed_dimensions"] = []
    elif world == "cost_stress":
        payload["changed_dimensions"] = ["costs"]
    digest = _write(path, payload)
    assert read_engineering_protocol(path, expected_sha256=digest) == payload


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "extra",
        "generator",
        "version",
        "unknown_world",
        "hash",
        "missing_limit",
        "boolean_limit",
        "retry",
        "native_fit_limit",
        "wrong_world_dimension",
        "seed_world",
        "fold_world",
    ],
)
def test_protocol_rejects_missing_or_expanded_fixture_scope(tmp_path: Path, change: str) -> None:
    path = tmp_path / "protocol.json"
    payload = _protocol()
    fixture = payload["fixture"]
    if change == "missing":
        payload.pop("fixture")
    elif change == "extra":
        fixture["eligible"] = True
    elif change == "generator":
        fixture["generator"] = "arbitrary_exchange"
    elif change == "version":
        fixture["version"] = True
    elif change == "unknown_world":
        fixture["world"] = "another_attempt"
    elif change == "hash":
        fixture["source_sha256"] = "not-a-hash"
    elif change == "missing_limit":
        fixture["limits"].pop("max_seconds")
    elif change == "boolean_limit":
        fixture["limits"]["cpu_threads"] = True
    elif change == "retry":
        fixture["limits"]["automatic_retries"] = 1
    elif change == "native_fit_limit":
        fixture["limits"]["max_native_fits"] = 4
    elif change == "wrong_world_dimension":
        fixture["world"] = "cost_stress"
    elif change == "seed_world":
        payload["changed_dimensions"] = ["seed"]
    else:
        payload["changed_dimensions"] = ["folds"]
    digest = _write(path, payload)
    with pytest.raises(MLContractError):
        read_engineering_protocol(path, expected_sha256=digest)


def _plan_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, changed_seed: int | None = None
) -> tuple[Path, Path, Path, str, Path]:
    worker = tmp_path / "worker"
    source = worker / "src" / "alpha_qlib_worker"
    source.mkdir(parents=True)
    tests = worker / "tests"
    tests.mkdir()
    names = (
        "real.py",
        "features.py",
        "contract.py",
        "tabular.py",
        "tabular_contract.py",
        "tabular_adapters.py",
        "fit_provenance.py",
    )
    for name in names:
        (source / name).write_text(f"# synthetic source {name}\n")
    for name in ("refit_harness.py", "test_fake_worker.py"):
        (tests / name).write_text(f"# synthetic generator dependency {name}\n")
    lock = worker / "uv.lock"
    lock.write_text("synthetic lock\n")
    monkeypatch.setattr(ml_refit, "_worker_root", lambda: worker)
    payload = _protocol()
    payload["worker_source_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in names}
        )
    ).hexdigest()
    payload["fixture"]["source_sha256"] = hashlib.sha256(
        canonical_json_bytes(
            {
                name: hashlib.sha256((tests / name).read_bytes()).hexdigest()
                for name in ("refit_harness.py", "test_fake_worker.py")
            }
        )
    ).hexdigest()
    payload["worker_lock_sha256"] = hashlib.sha256(lock.read_bytes()).hexdigest()
    exchanges = []
    for role in ("original", "changed"):
        directory = tmp_path / role
        directory.mkdir()
        draft = _draft()
        draft["worker_lock_hash"] = payload["worker_lock_sha256"]
        if role == "changed" and changed_seed is not None:
            draft["seed"] = changed_seed
        spec = directory / "spec.json"
        spec.write_bytes(canonical_json_bytes(draft))
        panel = _panel()
        if role == "changed":
            panel = panel.with_columns((pl.col("volume") + 1).alias("volume"))
        panel_path = directory / "panel.parquet"
        panel.write_parquet(panel_path)
        exchange = directory / "exchange"
        prepare_exchange(
            spec, panel_path, exchange, worker_lock_path=lock, model_override=payload["model"]
        )
        payload[f"{role}_request_sha256"] = hashlib.sha256(
            (exchange / "request.json").read_bytes()
        ).hexdigest()
        exchanges.append(exchange)
    protocol = tmp_path / "protocol.json"
    digest = _write(protocol, payload)
    return exchanges[0], exchanges[1], protocol, digest, worker


def test_plan_verifies_inputs_without_conferring_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, _ = _plan_inputs(tmp_path, monkeypatch)
    report = plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)
    assert report["trace_status"] == "NOT_INSPECTED"
    assert report["causality_status"] == "NOT_EVALUATED"
    assert report["fixture_generation_status"] == "NOT_EVALUATED"
    assert report["governed_execution"] == "BLOCKED_QLIB_NATIVE_PROTOCOL_UNREGISTERED"
    assert report["independent_observation_count"] == 0
    assert report["distinct_request_count"] == 2
    assert report["distinct_panel_count"] == 2
    assert report["counterfactual_refit"] is False
    assert report["promotion_eligible"] is False
    assert str(tmp_path) not in json.dumps(report)


def test_native_source_availability_does_not_qualify_qlib_fits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, _ = _plan_inputs(tmp_path, monkeypatch)
    report = plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)
    assert report["native_contract_source"] == "INTEGRATED_CANDIDATE_CONSUMER_ACCEPTANCE_PENDING"
    assert report["fit_reservation"] == "BLOCKED_QLIB_FIT_UNIT_MAPPING_UNQUALIFIED"
    assert report["fit_accounting"] == "BLOCKED_QLIB_FIT_ACCOUNTING_UNQUALIFIED"
    assert report["native_ancestry"] == "BLOCKED_QLIB_ANCESTRY_REUSE_UNQUALIFIED"
    assert report["native_runtime_qualification"] == "CONSUMER_PROFILE_UNQUALIFIED"
    assert report["native_planning_diagnostics"] == {
        "registered_analysis_family_ids": [item["id"] for item in analysis_family_catalog()],
        "protocol_mapping": "ENGINEERING_PROTOCOL_HAS_NO_NATIVE_ADMISSION_MAPPING",
        "resource_unit_mapping": "ML_FITS_NOT_MAPPED_TO_LLM_CALLS_OR_TOKENS",
        "fit_count_manifest": "NOT_ACCEPTED_REQUIRES_OWNER_AND_PROTOCOL_APPROVAL",
    }
    assert report["observed_fit_counts"] is None
    assert report["independent_observation_count"] == 0
    assert report["counterfactual_refit"] is False


def test_count_manifest_cannot_expand_the_engineering_protocol(tmp_path: Path) -> None:
    payload = _protocol()
    payload["fit_count_manifest"] = {"native_fits": 2, "accepted": True}
    protocol = tmp_path / "protocol.json"
    digest = _write(protocol, payload)
    with pytest.raises(MLContractError):
        read_engineering_protocol(protocol, expected_sha256=digest)


def test_catalog_name_alone_cannot_supply_native_protocol_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, _ = _plan_inputs(tmp_path, monkeypatch)
    monkeypatch.setattr(ml_refit, "analysis_family_catalog", lambda: [{"id": "linear"}])
    report = plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)
    assert report["native_planning_diagnostics"]["registered_analysis_family_ids"] == ["linear"]
    assert report["governed_execution"] == "BLOCKED_QLIB_NATIVE_PROTOCOL_UNREGISTERED"
    assert report["fit_reservation"] == "BLOCKED_QLIB_FIT_UNIT_MAPPING_UNQUALIFIED"
    assert report["counterfactual_refit"] is False


def test_plan_identity_survives_directory_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, _ = _plan_inputs(tmp_path, monkeypatch)
    before = plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)
    alias = tmp_path / "renamed"
    shutil.copytree(changed, alias)
    after = plan_refit(original, alias, protocol_path=protocol, expected_protocol_sha256=digest)
    assert before == after


@pytest.mark.parametrize("name", ["fit_provenance.py", "test_fake_worker.py", "uv.lock"])
def test_plan_rejects_stale_code_generator_or_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    original, changed, protocol, digest, worker = _plan_inputs(tmp_path, monkeypatch)
    if name == "uv.lock":
        target = worker / "uv.lock"
    elif name == "test_fake_worker.py":
        target = worker / "tests" / name
    else:
        target = worker / "src" / "alpha_qlib_worker" / name
    target.write_bytes(target.read_bytes() + b"# changed\n")
    with pytest.raises(MLContractError):
        plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)


def test_plan_rejects_undeclared_seed_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, _ = _plan_inputs(tmp_path, monkeypatch, changed_seed=11)
    with pytest.raises(MLContractError, match="dimensions"):
        plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)


def test_plan_detects_change_and_byte_restoration_during_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, worker = _plan_inputs(tmp_path, monkeypatch)
    validate = validate_request_bundle
    target = worker / "src" / "alpha_qlib_worker" / "real.py"
    saved = target.read_bytes()

    def raced(exchange: Path) -> Any:
        result = validate(exchange)
        target.write_bytes(saved + b"# transient change\n")
        target.write_bytes(saved)
        return result

    monkeypatch.setattr(ml_refit, "validate_request_bundle", raced)
    with pytest.raises(MLContractError, match="changed during"):
        plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)


def test_plan_publication_and_status_reverify_current_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, worker = _plan_inputs(tmp_path, monkeypatch)
    report = plan_refit(original, changed, protocol_path=protocol, expected_protocol_sha256=digest)
    output = tmp_path / "plan.json"
    publish_refit_plan(report, output)
    published = output.read_bytes()
    publish_refit_plan(report, output)
    assert output.read_bytes() == published
    status = status_refit_plan(
        output, original, changed, protocol_path=protocol, expected_protocol_sha256=digest
    )
    assert status["record_status"] == "CURRENT"
    assert status["trace_status"] == "NOT_INSPECTED"
    assert status["independent_observation_count"] == 0
    for key in (
        "native_contract_source",
        "governed_execution",
        "fit_reservation",
        "fit_accounting",
        "native_ancestry",
        "native_runtime_qualification",
        "native_planning_diagnostics",
    ):
        assert status[key] == report[key]
    with pytest.raises(MLContractError):
        publish_refit_plan({**report, "distinct_request_count": 99}, output)
    target = worker / "src" / "alpha_qlib_worker" / "real.py"
    target.write_bytes(target.read_bytes() + b"# stale\n")
    with pytest.raises(MLContractError):
        status_refit_plan(
            output, original, changed, protocol_path=protocol, expected_protocol_sha256=digest
        )


def test_readonly_refit_cli_reverifies_without_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, digest, _ = _plan_inputs(tmp_path, monkeypatch)
    output = tmp_path / "plan.json"
    runner = CliRunner()
    planned = runner.invoke(
        app,
        [
            "ml",
            "refit-plan",
            str(original),
            str(changed),
            "--protocol",
            str(protocol),
            "--protocol-sha256",
            digest,
            "--output",
            str(output),
            "--json",
        ],
    )
    assert planned.exit_code == 0, planned.output
    report = json.loads(planned.output)
    assert report["governed_execution"] == "BLOCKED_QLIB_NATIVE_PROTOCOL_UNREGISTERED"
    assert report["observed_fit_counts"] is None
    status = runner.invoke(
        app,
        [
            "ml",
            "refit-status",
            str(output),
            str(original),
            str(changed),
            "--protocol",
            str(protocol),
            "--protocol-sha256",
            digest,
            "--json",
        ],
    )
    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["record_status"] == "CURRENT"
    assert not (changed / "result.json").exists()
    assert not (changed / "predictions.parquet").exists()


def test_readonly_refit_cli_rejects_wrong_protocol_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original, changed, protocol, _, _ = _plan_inputs(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        app,
        [
            "ml",
            "refit-plan",
            str(original),
            str(changed),
            "--protocol",
            str(protocol),
            "--protocol-sha256",
            "0" * 64,
            "--json",
        ],
    )
    assert result.exit_code != 0
    assert "hash" in result.output
    assert not (changed / "result.json").exists()
