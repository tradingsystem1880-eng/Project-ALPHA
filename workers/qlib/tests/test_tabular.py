"""Contract and real-adapter checks for the additive tabular workflow."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import polars as pl
import pytest

from alpha_qlib_worker.contract import (
    canonical_json_bytes,
    compute_config_hash,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.real import (
    _diagnostic_signal_analysis,
    _MemoryDataset,
    _normalize_features,
    _qlib_frame,
    run_real,
)
from alpha_qlib_worker.tabular import backend_capabilities, require_backend, resolve_parameters
from alpha_qlib_worker.tabular_adapters import fit_tabular

from .test_fake_worker import _exchange


@pytest.mark.parametrize("name", ["lightgbm", "linear", "catboost", "xgboost", "double_ensemble"])
def test_schema_three_selects_each_tabular_backend(tmp_path: Path, name: str) -> None:
    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    request.update(schema_version=3, model={"name": name, "parameters": {}})
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    assert validate_request(exchange).payload["model"]["name"] == name


@pytest.mark.parametrize(
    ("name", "parameters"),
    [
        ("linear", {"include_valid": 1}),
        ("linear", {"alpha": float("nan")}),
        ("catboost", {"task_type": "GPU"}),
        ("xgboost", {"num_threads": 9}),
        ("double_ensemble", {"num_models": 1}),
        ("double_ensemble", {"seed": 3}),
    ],
)
def test_backend_parameters_are_bounded(name: str, parameters: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        resolve_parameters(name, parameters)


def test_capabilities_identify_missing_optional_dependencies() -> None:
    result = backend_capabilities()
    backends = {row["name"]: row for row in result["backends"]}
    assert set(backends) == {"lightgbm", "linear", "catboost", "xgboost", "double_ensemble"}
    assert backends["linear"]["status"] == "available"
    assert backends["double_ensemble"]["versions"]["pyqlib"] == "0.9.7"
    for name in ("catboost", "xgboost"):
        if backends[name]["status"] == "missing_dependency":
            assert name in backends[name]["reason"]


def _dataset() -> _MemoryDataset:
    index = pd.MultiIndex.from_product([pd.date_range("2023-01-01", periods=24), ["A", "B"]])
    generator = np.random.default_rng(17)
    features = pd.DataFrame(generator.normal(size=(48, 6)), index=index, columns=list("abcdef"))
    labels = pd.Series(features["a"] * 0.7 - features["b"] * 0.4, index=index)
    return _MemoryDataset(
        {
            "train": _qlib_frame(features.iloc[:32], labels.iloc[:32]),
            "valid": _qlib_frame(features.iloc[32:40], labels.iloc[32:40]),
            "test": _qlib_frame(features.iloc[40:]),
        },
        flatten_single=True,
    )


@pytest.mark.parametrize("name", ["linear", "double_ensemble"])
def test_real_adapters_are_reproducible_and_restore_random_state(name: str) -> None:
    parameters = (
        {}
        if name == "linear"
        else {
            "num_models": 2,
            "num_boost_round": 3,
            "early_stopping_rounds": 2,
            "min_data_in_leaf": 2,
            "num_threads": 1,
        }
    )
    np.random.seed(123)
    before = np.random.get_state(legacy=True)
    first = fit_tabular(_dataset(), name=name, raw=parameters, seed=7)
    after = np.random.get_state(legacy=True)
    second = fit_tabular(_dataset(), name=name, raw=parameters, seed=7)
    pd.testing.assert_series_equal(first.scores, second.scores, check_exact=True)
    assert first.model_hash == second.model_hash
    assert first.diagnostics["fit_count"] == (2 if name == "double_ensemble" else 1)
    assert isinstance(before, tuple) and isinstance(after, tuple)
    assert before[0] == after[0]
    np.testing.assert_array_equal(before[1], after[1])
    assert before[2:] == after[2:]


def test_transform_statistics_are_train_only_and_nonfinite_fails() -> None:
    train = pd.DataFrame({"a": [1.0, 3.0, np.nan], "missing": [np.nan] * 3})
    held_out = pd.DataFrame({"a": [1e9], "missing": [5.0]})
    first, _, digest, missing = _normalize_features(train, [held_out])
    second, _, changed_digest, _ = _normalize_features(train, [held_out * 100])
    pd.testing.assert_frame_equal(first, second, check_exact=True)
    assert digest == changed_digest
    assert missing == 1
    with pytest.raises(RuntimeError, match="non-finite"):
        _normalize_features(train, [pd.DataFrame({"a": [np.inf], "missing": [0.0]})])


@pytest.mark.parametrize("name", ["linear", "lightgbm", "catboost", "xgboost"])
def test_real_schema_three_publishes_fold_lineage_without_worker_economics(
    tmp_path: Path,
    name: str,
) -> None:
    first = _exchange(tmp_path / "first")
    path = first / "request.json"
    request = json.loads(path.read_text())
    parameters = (
        {}
        if name == "linear"
        else {"num_threads": 1, "num_boost_round": 3, "early_stopping_rounds": 2}
    )
    request.update(schema_version=3, model={"name": name, "parameters": parameters})
    original_fold = request["folds"][0]
    sessions = validate_request(_exchange(tmp_path / "sessions")).sessions
    request["folds"] = [
        {
            **original_fold,
            "train_end": sessions[400].isoformat(),
            "validation_start": sessions[406].isoformat(),
            "validation_end": sessions[500].isoformat(),
            "test_start": sessions[506].isoformat(),
            "test_end": sessions[620].isoformat(),
        },
        {**original_fold, "fold": 1},
    ]
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    second = tmp_path / "second"
    shutil.copytree(first, second)
    future = tmp_path / "future"
    shutil.copytree(first, future)
    altered_panel = pl.read_parquet(future / "panel.parquet").with_columns(
        [
            pl.when(pl.col("session_ts") > sessions[620])
            .then(pl.col(column) * 7)
            .otherwise(pl.col(column))
            .alias(column)
            for column in ("open", "high", "low", "close")
        ]
    )
    altered_panel.write_parquet(future / "panel.parquet")
    altered_request = json.loads((future / "request.json").read_text())
    altered_request["panel"]["sha256"] = sha256_file(future / "panel.parquet")
    altered_request["config_hash"] = compute_config_hash(altered_request)
    (future / "request.json").write_bytes(canonical_json_bytes(altered_request))
    lock = Path(__file__).parents[1] / "uv.lock"
    result = run_real(first, worker_lock_path=lock)
    repeated = run_real(second, worker_lock_path=lock)
    run_real(future, worker_lock_path=lock)
    assert result == repeated
    diagnostic = result["diagnostics"]
    assert diagnostic["model_backend"] == name
    assert len(diagnostic["adapter_source_hash"]) == 64
    assert diagnostic["signal_analysis"]["portfolio"] is None
    assert len(diagnostic["folds"]) == 2
    assert len({fold["model_hash"] for fold in diagnostic["folds"]}) == 2
    assert all(fold["fit_count"] == 1 for fold in diagnostic["folds"])
    assert (
        diagnostic["folds"][0]["normalization"]["statistics_hash"]
        != diagnostic["folds"][1]["normalization"]["statistics_hash"]
    )
    if name == "linear":
        assert diagnostic["feature_importance"] == []
        assert diagnostic["folds"][0]["resolved_parameters"] == {"alpha": 1.0, "estimator": "ridge"}
    assert pl.read_parquet(first / "predictions.parquet").get_column("score").is_finite().all()
    baseline = pl.read_parquet(first / "predictions.parquet").filter(pl.col("fold") == 0)
    poisoned = pl.read_parquet(future / "predictions.parquet").filter(pl.col("fold") == 0)
    comparison = ["symbol", "origin_ts", "target_ts", "score", "model_hash"]
    assert baseline.select(comparison).equals(poisoned.select(comparison))
    frozen = (first / "result.json").read_bytes()
    with pytest.raises(RuntimeError, match="already exists"):
        run_real(first, worker_lock_path=lock)
    assert (first / "result.json").read_bytes() == frozen


@pytest.mark.parametrize("name", ["linear", "catboost", "xgboost"])
def test_interrupted_real_fit_never_publishes_success(tmp_path: Path, name: str) -> None:
    exchange = _exchange(tmp_path / "interrupted")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    request.update(schema_version=3, model={"name": name, "parameters": {}})
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    with (
        patch("alpha_qlib_worker.real.fit_tabular", side_effect=KeyboardInterrupt),
        pytest.raises(KeyboardInterrupt),
    ):
        run_real(exchange, worker_lock_path=Path(__file__).parents[1] / "uv.lock")
    assert not (exchange / "result.json").exists()
    assert not (exchange / "predictions.parquet").exists()


@pytest.mark.parametrize("name", ["double_ensemble", "catboost", "xgboost"])
def test_ensemble_and_optional_backends_are_reproducible_across_python_hash_seeds(
    name: str,
) -> None:
    parameters = {"num_boost_round": 3, "early_stopping_rounds": 2, "num_threads": 1}
    if name == "double_ensemble":
        parameters.update(num_models=2, min_data_in_leaf=2)
    script = f"""
from tests.test_tabular import _dataset
from alpha_qlib_worker.tabular_adapters import fit_tabular
import json
fitted = fit_tabular(_dataset(), name={name!r}, seed=7, raw={parameters!r})
print(json.dumps({{'hash': fitted.model_hash, 'scores': fitted.scores.tolist()}}))
"""
    project = Path(__file__).parents[1]
    outputs = []
    for seed in ("13", "91"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=project,
            env={
                "PYTHONHASHSEED": seed,
                "PYTHONPATH": str(project / "src"),
                "OPENBLAS_NUM_THREADS": "1",
            },
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]


@pytest.mark.parametrize("estimator", ["ols", "ridge", "lasso", "nnls"])
def test_all_linear_estimators_fit_real_qlib(estimator: str) -> None:
    parameters = {"estimator": estimator}
    first = fit_tabular(_dataset(), name="linear", raw=parameters, seed=7)
    second = fit_tabular(_dataset(), name="linear", raw=parameters, seed=7)
    pd.testing.assert_series_equal(first.scores, second.scores, check_exact=True)
    assert first.model_hash == second.model_hash
    assert first.diagnostics["resolved_parameters"]["estimator"] == estimator
    assert first.diagnostics["state_roundtrip"]["status"] == "verified"


@pytest.mark.parametrize("distribution", ["pyqlib", "lightgbm", "scikit-learn"])
def test_capabilities_reject_unqualified_installed_versions(distribution: str) -> None:
    from importlib.metadata import version

    def altered(name: str) -> str:
        return "999.0" if name == distribution else version(name)

    with patch("alpha_qlib_worker.tabular.importlib.metadata.version", side_effect=altered):
        rows = {row["name"]: row for row in backend_capabilities()["backends"]}
    name = "linear" if distribution == "scikit-learn" else "lightgbm"
    assert rows[name]["status"] == "incompatible_dependency"
    assert distribution in rows[name]["reason"]


def test_capabilities_report_import_failure_and_no_backend_fallback() -> None:
    with patch(
        "alpha_qlib_worker.tabular.importlib.import_module", side_effect=ImportError("broken ABI")
    ):
        rows = {row["name"]: row for row in backend_capabilities()["backends"]}
        assert rows["lightgbm"]["status"] == "incompatible_dependency"
        with pytest.raises(RuntimeError, match="broken ABI.*no fallback"):
            require_backend("lightgbm")


@pytest.mark.parametrize("name", ["catboost", "xgboost"])
def test_unavailable_real_backend_fails_before_result_publication(
    tmp_path: Path, name: str
) -> None:
    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    request = json.loads(path.read_text())
    request.update(schema_version=3, model={"name": name, "parameters": {}})
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    lock = Path(__file__).parents[1] / "uv.lock"
    from importlib.metadata import PackageNotFoundError, version

    from alpha_qlib_worker.tabular import _backend_distribution

    absent = _backend_distribution(name)

    def missing(distribution: str) -> str:
        if distribution == absent:
            raise PackageNotFoundError(distribution)
        return version(distribution)

    with (
        patch("alpha_qlib_worker.tabular.importlib.metadata.version", side_effect=missing),
        pytest.raises(RuntimeError, match=f"{name} unavailable.*no fallback"),
    ):
        run_real(exchange, worker_lock_path=lock)
    assert not (exchange / "result.json").exists()
    assert not (exchange / "predictions.parquet").exists()


def test_nonconverged_lasso_fails_instead_of_publishing_finite_predictions() -> None:
    generator = np.random.default_rng(7)
    values = generator.normal(size=(200, 1)) + 0.01 * generator.normal(size=(200, 158))
    index = pd.MultiIndex.from_product([pd.date_range("2023-01-01", periods=100), ["A", "B"]])
    features = pd.DataFrame(values, index=index)
    labels = pd.Series(generator.normal(size=200), index=index)
    dataset = _MemoryDataset(
        {
            "train": _qlib_frame(features.iloc[:150], labels.iloc[:150]),
            "valid": _qlib_frame(features.iloc[150:175], labels.iloc[150:175]),
            "test": _qlib_frame(features.iloc[175:]),
        },
        flatten_single=True,
    )
    with pytest.raises(RuntimeError, match="did not converge"):
        fit_tabular(dataset, name="linear", raw={"estimator": "lasso", "alpha": 1e-10}, seed=7)


def test_lasso_design_preset_is_informative_for_known_linear_target() -> None:
    first = fit_tabular(_dataset(), name="linear", raw={"estimator": "lasso"}, seed=7)
    second = fit_tabular(_dataset(), name="linear", raw={"estimator": "lasso"}, seed=7)
    assert first.diagnostics["resolved_parameters"]["alpha"] == 0.01
    assert first.diagnostics["native_thread_limit"] == 1
    assert first.scores.nunique() > 1
    pd.testing.assert_series_equal(first.scores, second.scores, check_exact=True)
    expected = _dataset().prepare("test", col_set="feature")
    target = expected["a"] * 0.7 - expected["b"] * 0.4
    assert np.corrcoef(first.scores.to_numpy(), target.to_numpy())[0, 1] > 0.99


def test_schema_three_degenerate_scores_have_no_alphabetical_quantiles(tmp_path: Path) -> None:
    from alpha_qlib_worker.fake import run_fake

    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    payload = json.loads(path.read_text())
    payload.update(schema_version=3, model={"name": "linear", "parameters": {}})
    payload["config_hash"] = compute_config_hash(payload)
    path.write_bytes(canonical_json_bytes(payload))
    request = validate_request(exchange)
    run_fake(exchange, worker_lock_path=Path(__file__).parents[1] / "uv.lock")
    predictions = pl.read_parquet(exchange / "predictions.parquet").with_columns(
        pl.lit(0.0).alias("score")
    )
    analysis = _diagnostic_signal_analysis(request, predictions)
    assert analysis["quantile_returns"] == []
    assert analysis["ic"]["mean"] is None
    assert analysis["diagnostic_state"]["score_status"] == "degenerate"
    assert analysis["diagnostic_state"]["quantile_cross_sections"] == 0
    assert "tied" in analysis["diagnostic_state"]["reason"]


def test_source_drift_during_fit_cannot_publish_completion(tmp_path: Path) -> None:
    exchange = _exchange(tmp_path / "drift")
    path = exchange / "request.json"
    payload = json.loads(path.read_text())
    payload.update(schema_version=3, model={"name": "linear", "parameters": {}})
    payload["config_hash"] = compute_config_hash(payload)
    path.write_bytes(canonical_json_bytes(payload))
    with (
        patch("alpha_qlib_worker.real.source_fingerprint", side_effect=["a" * 64, "b" * 64]),
        pytest.raises(RuntimeError, match="adapter source changed"),
    ):
        run_real(exchange, worker_lock_path=Path(__file__).parents[1] / "uv.lock")
    assert not (exchange / "result.json").exists()
    assert not (exchange / "predictions.parquet").exists()
