"""Comparisons require identical frozen research inputs, not similar display labels."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.ml_compare import compare_exchanges, publish_comparison
from alpha_cli.ml_contract import (
    MLContractError,
    ValidatedResult,
    canonical_json_bytes,
    prepare_exchange,
    validate_result_bundle,
)
from tests.unit.test_ml_contract import _draft, _panel, _prediction_frame, _write_result


def _completed(tmp_path: Path, name: str, **changes: object) -> Path:
    root = tmp_path / name
    root.mkdir()
    panel = _panel()
    panel.write_parquet(root / "panel.parquet")
    draft = _draft()
    draft["model"]["parameters"]["num_leaves"] = 31 if name == "a" else 15
    draft.update(changes)
    (root / "spec.json").write_text(json.dumps(draft))
    exchange = root / "exchange"
    request = prepare_exchange(root / "spec.json", root / "panel.parquet", exchange)
    _write_result(exchange, request, _prediction_frame(request, panel))
    return exchange


def test_comparison_is_order_independent_and_lineage_bound(tmp_path: Path) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")
    report = compare_exchanges([a, b])
    assert report == compare_exchanges([b, a])
    assert report["authority"] == "predictive_diagnostics_only"
    assert report["worker_kind"] == "fake"
    assert report["promotion_eligible"] is False
    assert len(report["candidates"]) == 2
    assert len(report["comparison_hash"]) == 64
    for candidate in report["candidates"]:
        assert candidate["prediction_rows"] > 0
        assert len(candidate["request_sha256"]) == 64
        assert len(candidate["result_sha256"]) == 64
        assert candidate["model_hashes"] == ["c" * 64]
        assert "costed_return" not in candidate
    assert "canonical" in report["economics"]


@pytest.mark.parametrize(
    "changes",
    [{"seed": 8}, {"snapshot_hash": "d" * 64}, {"costs": {"fee_bps": 2.0, "slippage_bps": 2.0}}],
)
def test_comparison_rejects_different_frozen_inputs(
    tmp_path: Path, changes: dict[str, object]
) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b", **changes)
    with pytest.raises(MLContractError, match="frozen inputs"):
        compare_exchanges([a, b])


def test_comparison_rejects_duplicates_and_incomplete_inputs(tmp_path: Path) -> None:
    a = _completed(tmp_path, "a")
    with pytest.raises(MLContractError, match="2 to 10"):
        compare_exchanges([a])
    with pytest.raises(MLContractError, match="duplicate"):
        compare_exchanges([a, a])
    with pytest.raises(MLContractError, match="does not exist"):
        compare_exchanges([a, tmp_path / "incomplete"])


def test_comparison_reverifies_prediction_bytes(tmp_path: Path) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")
    predictions = b / "predictions.parquet"
    pl.read_parquet(predictions).with_columns(pl.lit(0.0).alias("score")).write_parquet(predictions)
    with pytest.raises(MLContractError, match="hash"):
        compare_exchanges([a, b])


@pytest.mark.parametrize("change", ["worker_kind", "adapter_source_hash"])
def test_comparison_rejects_mixed_worker_lineage(tmp_path: Path, change: str) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")
    path = b / "result.json"
    result = json.loads(path.read_text())
    if change == "worker_kind":
        result["worker"]["kind"] = "qlib"
    else:
        result["diagnostics"]["adapter_source_hash"] = "e" * 64
    path.write_bytes(canonical_json_bytes(result))
    with pytest.raises(MLContractError, match="worker"):
        compare_exchanges([a, b])


def test_comparison_reads_recorded_predictive_ic(tmp_path: Path) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")
    for exchange in (a, b):
        path = exchange / "result.json"
        result = json.loads(path.read_text())
        result["diagnostics"]["signal_analysis"] = {"ic": {"mean": 0.5, "rank_mean": 0.4}}
        path.write_bytes(canonical_json_bytes(result))
    report = compare_exchanges([a, b])
    assert all(
        candidate["worker_reported_ic"] == {"mean": 0.5, "rank_mean": 0.4}
        for candidate in report["candidates"]
    )


def test_comparison_rejects_replacement_after_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")

    def replaced(exchange: Path) -> ValidatedResult:
        validated = validate_result_bundle(exchange)
        path = exchange / "result.json"
        result = json.loads(path.read_text())
        result["diagnostics"]["signal_analysis"] = {"ic": {"mean": -0.5}}
        path.write_bytes(canonical_json_bytes(result))
        return validated

    monkeypatch.setattr("alpha_cli.ml_compare.validate_result_bundle", replaced)
    with pytest.raises(MLContractError, match="source changed"):
        compare_exchanges([a, b])


def test_publication_is_immutable_idempotent_and_rejects_symlink(tmp_path: Path) -> None:
    report = {"comparison_hash": "a" * 64, "authority": "predictive_diagnostics_only"}
    output = tmp_path / "comparison.json"
    publish_comparison(report, output)
    assert output.read_bytes() == canonical_json_bytes(report)
    publish_comparison(report, output)
    with pytest.raises(MLContractError, match="different"):
        publish_comparison({**report, "comparison_hash": "b" * 64}, output)
    alias = tmp_path / "alias.json"
    alias.symlink_to(output)
    with pytest.raises(MLContractError, match="symlink"):
        publish_comparison(report, alias)


def test_interrupted_publication_leaves_no_completion_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def interrupted(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr("alpha_cli.ml_compare.os.link", interrupted)
    output = tmp_path / "comparison.json"
    with pytest.raises(KeyboardInterrupt):
        publish_comparison({"comparison_hash": "a" * 64}, output)
    assert not output.exists()


_PROVENANCE: dict[str, object] = {
    "adapter_source_hash": "a" * 64,
    "model_backend": "linear",
    "backend_versions": {"pyqlib": "0.9.6"},
    "model_parameters": {},
}


def _schema3_real(
    tmp_path: Path, name: str, diagnostics: dict[str, object], *, kind: str = "qlib"
) -> Path:
    estimator = "ols" if name == "a" else "ridge"
    exchange = _completed(
        tmp_path,
        name,
        schema_version=3,
        model={"name": "linear", "parameters": {"estimator": estimator}},
    )
    # Result bytes stand in for the isolated Qlib worker's output boundary; no backend runs.
    path = exchange / "result.json"
    result = json.loads(path.read_text())
    result["schema_version"] = 3
    result["worker"]["kind"] = kind
    result["diagnostics"] = diagnostics
    path.write_bytes(canonical_json_bytes(result))
    return exchange


def test_schema3_real_comparison_records_adapter_backend_provenance(tmp_path: Path) -> None:
    a = _schema3_real(tmp_path, "a", _PROVENANCE)
    b = _schema3_real(tmp_path, "b", _PROVENANCE)
    report = compare_exchanges([a, b])
    assert report["worker_kind"] == "qlib"
    assert [candidate["schema_version"] for candidate in report["candidates"]] == [3, 3]
    for candidate in report["candidates"]:
        assert candidate["adapter_source_hash"] == "a" * 64
        assert candidate["backend_versions"] == {"pyqlib": "0.9.6"}
    assert report["promotion_eligible"] is False


@pytest.mark.parametrize(
    "defect",
    [
        {"adapter_source_hash": None},
        {"adapter_source_hash": "A" * 64},
        {"adapter_source_hash": "a" * 63},
        {"model_backend": "lightgbm"},
        {"backend_versions": {}},
        {"backend_versions": {"pyqlib": 96}},
        {"model_parameters": None},
    ],
)
def test_schema3_real_comparison_requires_adapter_backend_provenance(
    tmp_path: Path, defect: dict[str, object]
) -> None:
    diagnostics = {**_PROVENANCE, **defect}
    diagnostics = {key: value for key, value in diagnostics.items() if value is not None}
    a = _schema3_real(tmp_path, "a", diagnostics)
    b = _schema3_real(tmp_path, "b", diagnostics)
    with pytest.raises(MLContractError, match="requires adapter/backend provenance"):
        compare_exchanges([a, b])


@pytest.mark.parametrize(("schema_version", "kind"), [(3, "fake"), (1, "qlib")])
def test_provenance_is_required_only_for_schema3_real_workers(
    tmp_path: Path, schema_version: int, kind: str
) -> None:
    exchanges = []
    for name in ("a", "b"):
        if schema_version == 3:
            exchanges.append(_schema3_real(tmp_path, name, {}, kind=kind))
            continue
        exchange = _completed(tmp_path, name)
        path = exchange / "result.json"
        result = json.loads(path.read_text())
        result["worker"]["kind"] = kind
        path.write_bytes(canonical_json_bytes(result))
        exchanges.append(exchange)
    report = compare_exchanges(exchanges)
    assert report["worker_kind"] == kind
    assert {candidate["schema_version"] for candidate in report["candidates"]} == {schema_version}


def test_comparison_rejects_symlinked_artifacts_before_validation(tmp_path: Path) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")
    predictions = b / "predictions.parquet"
    moved = tmp_path / "moved-predictions.parquet"
    predictions.rename(moved)
    predictions.symlink_to(moved)
    with pytest.raises(MLContractError, match="may not be symlinks"):
        compare_exchanges([a, b])


def test_compare_command_publishes_the_report_and_rejects_invalid_requests(
    tmp_path: Path,
) -> None:
    a, b = _completed(tmp_path, "a"), _completed(tmp_path, "b")
    output = tmp_path / "reports" / "comparison.json"
    runner = CliRunner()
    published = runner.invoke(
        app, ["ml", "compare", str(a), str(b), "--output", str(output), "--json"]
    )
    assert published.exit_code == 0, published.output
    report = json.loads(published.stdout)
    assert report == compare_exchanges([a, b])
    assert output.read_bytes() == canonical_json_bytes(report)
    for args, message in (
        ([str(a)], "2 to 10"),
        ([str(a), str(b), "--output", str(tmp_path / "comparison.txt")], ".json suffix"),
    ):
        rejected = runner.invoke(app, ["ml", "compare", *args, "--json"])
        assert rejected.exit_code == 2
        assert message in " ".join(rejected.output.replace("\u2502", " ").split())
    assert not (tmp_path / "comparison.txt").exists()
