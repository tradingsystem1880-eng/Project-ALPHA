"""Portable synthetic numerical/artifact checks; fixture lineage is not native authority."""

from __future__ import annotations

import copy
import hashlib
import json
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest
from pydantic import TypeAdapter, ValidationError

from alpha_backtest.results import BacktestResult
from alpha_cli import _artifacts
from alpha_cli._native_rule_artifacts import publish_rule_run, validate_rule_artifacts
from alpha_cli._native_rule_economics import fixed_costed_study, validate_costed_result
from alpha_cli._native_rule_projection import publish_projections, validate_projections
from alpha_cli._native_rule_protocol import (
    canonical,
    position_payload,
    selected_study,
    sha,
    worker_request,
)
from alpha_cli.artifact_contract import artifact_metadata
from alpha_core import DataError
from tests.unit.test_native_rule_portable_d0_artifacts import (
    D0Case,
    _snapshot,
)
from tests.unit.test_native_rule_portable_d0_artifacts import (
    approved as approved,
)
from tests.unit.test_research_control_store import PROJECT_ID

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def canonical_economics() -> dict[str, Any]:
    # Exactly the existing pure canonical-engine wrapper: two roles, seven synthetic bars.
    # This imports no native owner/profile and issues no admission, receipt or observation.
    namespace = runpy.run_path(str(ROOT / "workers/rdagent/costed_probe.py"))
    execute = cast(Callable[[dict[str, object]], dict[str, Any]], namespace["execute"])
    return execute(fixed_costed_study().to_dict())


def test_canonical_fixture_matches_independent_fill_and_cash_references(
    canonical_economics: dict[str, Any],
) -> None:
    baseline, control = canonical_economics["baseline"], canonical_economics["control"]
    assert [(f["ts"], f["side"], f["quantity"], f["price"]) for f in baseline["fill_trace"]] == [
        ("2000-01-04T00:00:00+00:00", "BUY", 100.0, 10.10),
        ("2000-01-05T00:00:00+00:00", "SELL", 100.0, 15.84),
        ("2000-01-06T00:00:00+00:00", "BUY", 75.0, 8.08),
        ("2000-01-07T00:00:00+00:00", "SELL", 75.0, 7.92),
    ]
    # Four independently specified fills, 10bps fees and 100bps slippage, no terminal fill.
    assert baseline["equity_curve"][-1][1] == 12558.21
    assert control["fill_trace"] == []
    assert all(row[1] == 12000.0 for row in control["equity_curve"])
    before = copy.deepcopy(canonical_economics)
    assert validate_costed_result(canonical_economics) == before
    assert canonical_economics == before
    assert canonical_economics["scientific_acceptance"] == "not_admitted"
    assert canonical_economics["real_market_evidence"] is False


@pytest.mark.parametrize(
    "mutation",
    [
        "shape",
        "authority",
        "outcome",
        "real_market",
        "baseline",
        "fills",
        "fill_side",
        "orders",
        "final_cash",
        "control_curve",
        "bool_control_count",
    ],
)
def test_costed_validator_rejects_discriminating_mutations_without_repair(
    canonical_economics: dict[str, Any],
    mutation: str,
) -> None:
    value = copy.deepcopy(canonical_economics)
    if mutation == "shape":
        value["extra"] = "unapproved"
    elif mutation == "authority":
        value["scientific_acceptance"] = "accepted"
    elif mutation == "outcome":
        value["outcome"] = "SUPPORTED"
    elif mutation == "real_market":
        value["real_market_evidence"] = True
    elif mutation == "baseline":
        value["baseline"] = None
    elif mutation == "fills":
        value["baseline"]["fill_trace"] = []
    elif mutation == "fill_side":
        value["baseline"]["fill_trace"][0]["side"] = "SELL"
    elif mutation == "orders":
        value["baseline"]["orders"] = 3
    elif mutation == "final_cash":
        value["baseline"]["equity_curve"][-1][1] += 1
    elif mutation == "control_curve":
        value["control"]["equity_curve"][1][1] += 1
    else:
        assert mutation == "bool_control_count"
        value["control"]["fills"] = False
    before = copy.deepcopy(value)
    with pytest.raises(DataError):
        validate_costed_result(value)
    assert value == before


@pytest.mark.parametrize("role", ["baseline", "control"])
@pytest.mark.parametrize("field", ["fills", "orders", "rejected"])
def test_costed_counts_require_integers_even_when_numeric_values_match(
    canonical_economics: dict[str, Any],
    role: str,
    field: str,
) -> None:
    value = copy.deepcopy(canonical_economics)
    value[role][field] = float(value[role][field])
    before = copy.deepcopy(value)
    with pytest.raises(DataError, match="accounting"):
        validate_costed_result(value)
    assert value == before


@pytest.mark.parametrize("field", ["sequence_id", "order_sequence_id"])
@pytest.mark.parametrize("value", [True, 1.0])
def test_fill_identifiers_require_exact_integers(
    canonical_economics: dict[str, Any],
    field: str,
    value: object,
) -> None:
    result = copy.deepcopy(canonical_economics)
    result["baseline"]["fill_trace"][0][field] = value
    with pytest.raises(DataError, match="fill"):
        validate_costed_result(result)


def test_control_without_fill_trace_is_a_typed_rejection(
    canonical_economics: dict[str, Any],
) -> None:
    result = copy.deepcopy(canonical_economics)
    del result["control"]["fill_trace"]
    with pytest.raises(DataError, match="flat control"):
        validate_costed_result(result)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("schema", "scientific authority"),
        ("control_not_object", "requires baseline and control"),
        ("fill_not_object", "canonical fill differs"),
        ("rejected_nonzero", "baseline accounting"),
        ("curve_length", "baseline accounting"),
        ("curve_time_not_text", "baseline accounting"),
        ("bool_equity", "baseline accounting"),
        ("trades_length", "baseline accounting"),
        ("trades_not_list", "baseline accounting"),
        ("control_fill_trace", "flat control"),
    ],
)
def test_each_costed_guard_rejects_its_own_defect(
    canonical_economics: dict[str, Any],
    mutation: str,
    message: str,
) -> None:
    # Each mutant is caught only by the named guard, so removing that guard is detected.
    value = copy.deepcopy(canonical_economics)
    baseline = value["baseline"]
    if mutation == "schema":
        value["schema"] = "SyntheticCostedReplayResultV0"
    elif mutation == "control_not_object":
        value["control"] = None
    elif mutation == "fill_not_object":
        baseline["fill_trace"][0] = None
    elif mutation == "rejected_nonzero":
        baseline["rejected"] = 1
    elif mutation == "curve_length":
        baseline["equity_curve"].pop(0)
    elif mutation == "curve_time_not_text":
        baseline["equity_curve"][0][0] = 946771200
    elif mutation == "bool_equity":
        baseline["equity_curve"][0][1] = True
    elif mutation == "trades_length":
        baseline["trades"].pop()
    elif mutation == "trades_not_list":
        baseline["trades"] = dict(enumerate(baseline["trades"]))
    else:
        assert mutation == "control_fill_trace"
        value["control"]["fill_trace"] = copy.deepcopy(baseline["fill_trace"][:1])
    before = copy.deepcopy(value)
    with pytest.raises(DataError, match=message):
        validate_costed_result(value)
    assert value == before


@pytest.mark.parametrize(
    ("role", "mutation"),
    [
        ("baseline", "curve_time_not_datetime"),
        ("baseline", "trades_not_objects"),
        ("baseline", "trade_missing_field"),
        ("baseline", "order_trace_malformed"),
        ("control", "decision_trace_malformed"),
    ],
)
def test_costed_validator_rejects_results_the_backtest_reader_cannot_parse(
    canonical_economics: dict[str, Any],
    role: str,
    mutation: str,
) -> None:
    value = copy.deepcopy(canonical_economics)
    result = value[role]
    if mutation == "curve_time_not_datetime":
        result["equity_curve"][0][0] = "not-a-session-time"
    elif mutation == "trades_not_objects":
        result["trades"] = [1, 2]
    elif mutation == "trade_missing_field":
        del result["trades"][0]["exit_price"]
    elif mutation == "order_trace_malformed":
        result["order_trace"] = [1]
    else:
        assert mutation == "decision_trace_malformed"
        result["decision_trace"] = "not-a-trace"
    # The projection reader parses every role as a BacktestResult and rejects this mutant.
    with pytest.raises(ValidationError):
        TypeAdapter(BacktestResult).validate_python(result)
    before = copy.deepcopy(value)
    with pytest.raises(DataError, match=f"costed {role} result does not match"):
        validate_costed_result(value)
    assert value == before


def _bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture
def projection(
    tmp_path: Path,
    canonical_economics: dict[str, Any],
) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    # These are inert serialization IDs, NOT issued native admission/owner/observation evidence.
    # This fixture is never passed to native completion, admission, claim or launch APIs.
    receipt = {
        "economics": copy.deepcopy(canonical_economics),
        "admission": {"trial_id": "untrusted-serialization-fixture", "spec_sha256": "a" * 64},
    }
    selectors = publish_projections(tmp_path, "b" * 16, receipt, source_fingerprint="c" * 64)
    return tmp_path, receipt, selectors


def _verify_projection(
    root: Path, receipt: dict[str, Any], selectors: object, source: str = "c" * 64
) -> None:
    validate_projections(
        root, selectors, receipt, parent_run_id="b" * 16, source_fingerprint=source
    )


def test_projection_roundtrip_and_retry_preserve_actual_canonical_result(
    projection: tuple[Path, dict[str, Any], dict[str, Any]],
) -> None:
    root, receipt, selectors = projection
    before = _bytes(root)
    _verify_projection(root, receipt, selectors)
    assert publish_projections(root, "b" * 16, receipt, source_fingerprint="c" * 64) == selectors
    assert _bytes(root) == before
    for role in ("baseline", "control"):
        rdir = _artifacts.run_dir(root, selectors["roles"][role]["run_id"])
        assert json.loads((rdir / "raw_result.json").read_text()) == receipt["economics"][role]
        manifest = _artifacts.read_manifest(rdir)
        assert manifest["scientific_acceptance"] == "not_admitted"
        assert manifest["real_market_evidence"] is False
        assert manifest["places_orders"] is False
        assert manifest["eligible_for_holdout_or_execution"] is False


@pytest.mark.parametrize(
    "mutation", ["shape", "parent", "trial", "roles", "run_id", "digest", "source"]
)
def test_projection_identity_mutations_reject_without_repair(
    projection: tuple[Path, dict[str, Any], dict[str, Any]],
    mutation: str,
) -> None:
    root, receipt, original = projection
    selectors = copy.deepcopy(original)
    source = "c" * 64
    if mutation == "shape":
        selectors["extra"] = True
    elif mutation == "parent":
        selectors["parent_run_id"] = "d" * 16
    elif mutation == "trial":
        selectors["trial_id"] = "different-fixture-trial"
    elif mutation == "roles":
        del selectors["roles"]["control"]
    elif mutation == "run_id":
        selectors["roles"]["baseline"]["run_id"] = "e" * 16
    elif mutation == "digest":
        selectors["roles"]["baseline"]["manifest_sha256"] = "0" * 64
    else:
        assert mutation == "source"
        source = "d" * 64
    before = _bytes(root)
    with pytest.raises(DataError, match="projection"):
        _verify_projection(root, receipt, selectors, source)
    assert _bytes(root) == before
    _verify_projection(root, receipt, original)


@pytest.mark.parametrize("artifact", ["raw_result.json", "equity_curve.parquet"])
def test_rehashed_projection_corruption_fails_mechanical_check_and_is_not_repaired(
    projection: tuple[Path, dict[str, Any], dict[str, Any]],
    artifact: str,
) -> None:
    root, receipt, selectors = projection
    rdir = _artifacts.run_dir(root, selectors["roles"]["baseline"]["run_id"])
    manifest = _artifacts.read_manifest(rdir)
    path = rdir / artifact
    if artifact.endswith("json"):
        raw = json.loads(path.read_text())
        raw["orders"] += 1
        path.write_text(json.dumps(raw))
    else:
        frame = pl.read_parquet(path)
        frame.with_columns((pl.col("equity") + 1).alias("equity")).write_parquet(path)
    # Simulate self-consistent malicious rehashing only in the disposable fixture.
    manifest["artifacts"][artifact] = artifact_metadata(path)
    manifest_path = rdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True))
    selectors["roles"]["baseline"]["manifest_sha256"] = hashlib.sha256(
        manifest_path.read_bytes()
    ).hexdigest()
    assert _artifacts.read_manifest(rdir) == manifest  # Generic file hashes really do verify.
    before = _bytes(root)
    with pytest.raises(DataError, match="projection"):
        _verify_projection(root, receipt, selectors)
    assert _bytes(root) == before
    with pytest.raises(DataError, match="immutable"):
        publish_projections(root, "b" * 16, receipt, source_fingerprint="c" * 64)
    assert _bytes(root) == before


@pytest.mark.parametrize("role", ["baseline", "control"])
@pytest.mark.parametrize(
    "row", [None, [], ["2000-01-02T00:00:00+00:00"], ["2000-01-02T00:00:00+00:00", float("nan")]]
)
def test_malformed_curve_rows_are_typed_rejections(
    canonical_economics: dict[str, Any],
    role: str,
    row: object,
) -> None:
    result = copy.deepcopy(canonical_economics)
    result[role]["equity_curve"][0] = row
    before = json.dumps(result, sort_keys=True)
    with pytest.raises(DataError, match="accounting"):
        validate_costed_result(result)
    assert json.dumps(result, sort_keys=True) == before


@pytest.mark.parametrize(
    ("role", "field"), [("baseline", "rejected"), ("control", "orders"), ("control", "rejected")]
)
def test_boolean_zero_counts_are_not_integers(
    canonical_economics: dict[str, Any],
    role: str,
    field: str,
) -> None:
    result = copy.deepcopy(canonical_economics)
    result[role][field] = False
    with pytest.raises(DataError, match="accounting"):
        validate_costed_result(result)


def _untrusted_native_shaped_serialization(canonical_economics: dict[str, Any]) -> dict[str, Any]:
    admission = {
        "trial_id": "untrusted-fixture-trial",
        "reservation_id": "untrusted-fixture-trial",
        "spec_sha256": "a" * 64,
        "rule_request": worker_request(True),
        "study_id": selected_study(True).content_sha256,
    }
    # Deliberately NOT a valid issued worker receipt: no owner identity/runtime observation.
    return {
        "schema": "UNTRUSTED_SERIALIZATION_FIXTURE_NOT_NATIVE_RECEIPT",
        "admission": admission,
        "binding_sha256": sha(admission),
        "rule_positions": position_payload(True),
        "economics": copy.deepcopy(canonical_economics),
    }


def test_native_shaped_files_roundtrip_has_no_native_provenance_or_accounting_effect(
    approved: D0Case,
    canonical_economics: dict[str, Any],
) -> None:
    receipt = _untrusted_native_shaped_serialization(canonical_economics)
    before_sql = _snapshot(approved)[1]
    manifest = publish_rule_run(
        approved.root,
        project_id=PROJECT_ID,
        contract_id=approved.contract_id,
        contract=approved.contract,
        execution_fingerprint="a" * 64,
        native_receipt=receipt,
        native_receipt_bytes=canonical(receipt).encode(),
    )
    rdir = _artifacts.run_dir(approved.root, manifest["run_id"])
    validate_rule_artifacts(rdir, manifest, approved.contract)
    before = _snapshot(approved)
    assert (
        publish_rule_run(
            approved.root,
            project_id=PROJECT_ID,
            contract_id=approved.contract_id,
            contract=approved.contract,
            execution_fingerprint="a" * 64,
            native_receipt=receipt,
            native_receipt_bytes=canonical(receipt).encode(),
        )
        == manifest
    )
    assert _snapshot(approved) == before
    assert _snapshot(approved)[1] == before_sql
    assert approved.store.list_jobs() == []
    with approved.store._transaction(write=False) as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM research_attempt_records").fetchone()[0] == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM research_launch_reservations").fetchone()[0]
            == 0
        )
    for key in ("real_market_evidence", "eligible_for_holdout_or_execution", "places_orders"):
        assert manifest[key] is False
    assert manifest["scientific_acceptance"] == "not_admitted"


@pytest.mark.parametrize("mutation", ["binding", "study", "trial", "positions", "economics"])
def test_native_shaped_rehashed_serialization_is_not_a_trusted_observation(
    approved: D0Case,
    canonical_economics: dict[str, Any],
    mutation: str,
) -> None:
    receipt = _untrusted_native_shaped_serialization(canonical_economics)
    manifest = publish_rule_run(
        approved.root,
        project_id=PROJECT_ID,
        contract_id=approved.contract_id,
        contract=approved.contract,
        execution_fingerprint="a" * 64,
        native_receipt=receipt,
        native_receipt_bytes=canonical(receipt).encode(),
    )
    rdir = _artifacts.run_dir(approved.root, manifest["run_id"])
    if mutation == "binding":
        receipt["binding_sha256"] = "0" * 64
    elif mutation == "study":
        receipt["admission"]["study_id"] = "0" * 64
    elif mutation == "trial":
        receipt["admission"]["trial_id"] = "different-fixture"
    elif mutation == "positions":
        receipt["rule_positions"]["baseline"][0] = 99
    else:
        assert mutation == "economics"
        receipt["economics"]["baseline"]["equity_curve"][-1][1] += 1
    path = rdir / "native_receipt.json"
    path.write_text(canonical(receipt))
    manifest["artifacts"][path.name] = artifact_metadata(path)
    (rdir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    assert _artifacts.read_manifest(rdir) == manifest
    before = _snapshot(approved)
    with pytest.raises(DataError):
        validate_rule_artifacts(rdir, manifest, approved.contract)
    assert _snapshot(approved) == before


def test_rehashed_economics_artifact_differing_from_its_receipt_is_rejected(
    approved: D0Case,
    canonical_economics: dict[str, Any],
) -> None:
    receipt = _untrusted_native_shaped_serialization(canonical_economics)
    manifest = publish_rule_run(
        approved.root,
        project_id=PROJECT_ID,
        contract_id=approved.contract_id,
        contract=approved.contract,
        execution_fingerprint="a" * 64,
        native_receipt=receipt,
        native_receipt_bytes=canonical(receipt).encode(),
    )
    rdir = _artifacts.run_dir(approved.root, manifest["run_id"])
    path = rdir / "economics.json"
    economics = json.loads(path.read_text())
    economics["baseline"]["equity_curve"][-1][1] += 1
    path.write_text(canonical(economics))
    manifest["artifacts"][path.name] = artifact_metadata(path)
    (rdir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    assert _artifacts.read_manifest(rdir) == manifest  # Generic file hashes really do verify.
    before = _snapshot(approved)
    with pytest.raises(DataError, match="costed raw artifact differs"):
        validate_rule_artifacts(rdir, manifest, approved.contract)
    assert _snapshot(approved) == before


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("accounting", "costed baseline accounting differs"),
        ("reader_schema", "costed baseline result does not match the canonical backtest schema"),
    ],
)
def test_costed_native_publication_rejects_invalid_economics_before_any_artifact(
    approved: D0Case,
    canonical_economics: dict[str, Any],
    defect: str,
    message: str,
) -> None:
    receipt = _untrusted_native_shaped_serialization(canonical_economics)
    if defect == "accounting":
        receipt["economics"]["baseline"]["orders"] = 3
    else:
        assert defect == "reader_schema"
        del receipt["economics"]["baseline"]["trades"][0]["exit_price"]
    before = _snapshot(approved)
    # publish_projections would create data_dir/snapshots/synthetic-rule-* before parsing roles.
    effects = (approved.root / "runs", approved.root / "snapshots")
    assert not any(path.exists() for path in effects)
    with pytest.raises(DataError, match=message):
        publish_rule_run(
            approved.root,
            project_id=PROJECT_ID,
            contract_id=approved.contract_id,
            contract=approved.contract,
            execution_fingerprint="a" * 64,
            native_receipt=receipt,
            native_receipt_bytes=canonical(receipt).encode(),
        )
    assert not any(path.exists() for path in effects)
    assert _snapshot(approved) == before


@pytest.mark.parametrize("role", ["baseline", "control"])
def test_oversized_equity_integer_is_a_typed_rejection(
    canonical_economics: dict[str, Any],
    role: str,
) -> None:
    result = copy.deepcopy(canonical_economics)
    result[role]["equity_curve"][0][1] = 10**400
    before = copy.deepcopy(result)
    with pytest.raises(DataError, match="accounting"):
        validate_costed_result(result)
    assert result == before
