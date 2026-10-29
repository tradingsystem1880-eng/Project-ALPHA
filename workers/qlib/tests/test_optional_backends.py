"""Real CPU execution of the newly pinned, isolated tabular backends."""

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from alpha_qlib_worker.contract import canonical_json_bytes, compute_config_hash
from alpha_qlib_worker.real import run_real
from alpha_qlib_worker.tabular import backend_capabilities, resolve_parameters
from alpha_qlib_worker.tabular_adapters import fit_tabular

from .test_fake_worker import _exchange
from .test_tabular import _dataset


@pytest.mark.parametrize("name", ["catboost", "xgboost"])
def test_real_optional_backend_fit_is_deterministic_and_roundtrips(name: str) -> None:
    parameters = {"num_boost_round": 8, "early_stopping_rounds": 2, "num_threads": 1}
    first = fit_tabular(_dataset(), name=name, raw=parameters, seed=7)
    second = fit_tabular(_dataset(), name=name, raw=parameters, seed=7)
    pd.testing.assert_series_equal(first.scores, second.scores, check_exact=True)
    assert first.model_hash == second.model_hash
    assert np.isfinite(first.scores.to_numpy()).all()
    assert first.diagnostics["state_roundtrip"]["status"] == "verified"
    assert first.diagnostics["selected_tree_count"] > 0
    if name == "catboost":
        assert first.importance == []
        assert first.diagnostics["importance_kind"] == "not_available"


def test_xgboost_early_stopping_uses_same_selected_state_for_every_artifact() -> None:
    import xgboost as xgb
    from qlib.contrib.model.xgboost import XGBModel

    dataset = _dataset()
    dataset._frames["valid"].loc[:, ("label", "LABEL0")] *= -1
    captured: dict[str, Any] = {}
    original_fit = XGBModel.fit

    def fit_and_capture(self: Any, data: Any, **kwargs: Any) -> None:
        original_fit(self, data, **kwargs)
        full = self.model
        best = int(full.best_iteration)
        test = xgb.DMatrix(data.prepare("test", col_set="feature"))
        selected = full[: best + 1]
        captured.update(
            full=full.predict(test),
            selected=selected.predict(test),
            trained=full.num_boosted_rounds(),
            selected_count=selected.num_boosted_rounds(),
            best=best,
            payload=bytes(selected.save_raw(raw_format="json")),
            importance=selected.get_score(importance_type="gain"),
        )

    with patch.object(XGBModel, "fit", fit_and_capture):
        fitted = fit_tabular(
            dataset,
            name="xgboost",
            seed=7,
            raw={
                "num_boost_round": 30,
                "early_stopping_rounds": 2,
                "num_threads": 1,
                "max_depth": 2,
                "learning_rate": 0.1,
            },
        )
    assert captured["trained"] > captured["selected_count"]
    assert not np.allclose(captured["full"], captured["selected"], rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(
        fitted.scores.to_numpy(), captured["selected"], rtol=1e-12, atol=1e-12
    )
    assert fitted.diagnostics["selected_tree_count"] == captured["best"] + 1
    assert fitted.diagnostics["best_iteration"] == captured["selected_count"]
    assert fitted.diagnostics["state_roundtrip"]["status"] == "verified"
    expected_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "backend": "xgboost",
                "seed": 7,
                "parameters": resolve_parameters(
                    "xgboost",
                    {
                        "num_boost_round": 30,
                        "early_stopping_rounds": 2,
                        "num_threads": 1,
                        "max_depth": 2,
                        "learning_rate": 0.1,
                    },
                ),
            }
        )
        + captured["payload"]
    ).hexdigest()
    assert fitted.model_hash == expected_hash
    expected_gain = [captured["importance"].get(f"f{index}", 0.0) for index in range(6)]
    np.testing.assert_allclose(
        [gain for _, gain, _ in fitted.importance], expected_gain, rtol=1e-12, atol=1e-12
    )


def test_xgboost_uses_cpu_library_build() -> None:
    import xgboost

    assert xgboost.build_info()["USE_CUDA"] is False


@pytest.mark.parametrize("threads", [1, 2])
def test_every_catboost_prediction_including_reload_has_explicit_thread_bound(threads: int) -> None:
    CatBoost = importlib.import_module("catboost").CatBoost

    calls: list[int] = []
    original = CatBoost.predict

    def record(self: Any, data: Any, *args: Any, **kwargs: Any) -> Any:
        calls.append(kwargs.get("thread_count", -1))
        return original(self, data, *args, **kwargs)

    with patch.object(CatBoost, "predict", record):
        fitted = fit_tabular(
            _dataset(),
            name="catboost",
            raw={
                "num_boost_round": 3,
                "early_stopping_rounds": 2,
                "num_threads": threads,
            },
            seed=7,
        )
    assert len(calls) == 2  # Original selected model plus native reload.
    assert calls == [threads, threads]
    assert fitted.diagnostics["native_thread_limit"] == threads


@pytest.mark.parametrize("threads", [1, 2])
def test_every_xgboost_prediction_and_matrix_including_reload_is_bounded(threads: int) -> None:
    import xgboost as xgb

    calls: list[tuple[int, int, str]] = []
    original = xgb.Booster.predict

    def record(self: Any, data: Any, *args: Any, **kwargs: Any) -> Any:
        config = json.loads(self.save_config())["learner"]["generic_param"]
        calls.append((int(config["nthread"]), int(data.nthread), config["device"]))
        return original(self, data, *args, **kwargs)

    with patch.object(xgb.Booster, "predict", record):
        fitted = fit_tabular(
            _dataset(),
            name="xgboost",
            raw={
                "num_boost_round": 3,
                "early_stopping_rounds": 2,
                "num_threads": threads,
            },
            seed=7,
        )
    assert len(calls) == 2
    assert calls == [(threads, threads, "cpu"), (threads, threads, "cpu")]
    assert fitted.diagnostics["native_thread_limit"] == threads


@pytest.mark.parametrize("name", ["catboost", "xgboost"])
@pytest.mark.parametrize("failure", ["nonfinite", "misaligned"])
def test_invalid_optional_predictions_never_publish_success(
    tmp_path: Path,
    name: str,
    failure: str,
) -> None:
    exchange = _exchange(tmp_path / "exchange")
    path = exchange / "request.json"
    payload = json.loads(path.read_text())
    payload.update(
        schema_version=3,
        model={
            "name": name,
            "parameters": {
                "num_boost_round": 3,
                "early_stopping_rounds": 2,
                "num_threads": 1,
            },
        },
    )
    payload["config_hash"] = compute_config_hash(payload)
    path.write_bytes(canonical_json_bytes(payload))
    module = importlib.import_module(name)
    cls = module.CatBoost if name == "catboost" else module.Booster

    def corrupt_predict(self: Any, data: Any, *args: Any, **kwargs: Any) -> Any:
        rows = len(data) if name == "catboost" else data.num_row()
        result = np.zeros(rows, dtype="float64")
        if failure == "nonfinite":
            result[0] = float("nan")
            return result
        return result[:-1]

    with (
        patch.object(cls, "predict", corrupt_predict),
        pytest.raises(RuntimeError, match="non-finite|index differs"),
    ):
        run_real(exchange, worker_lock_path=Path(__file__).parents[1] / "uv.lock")
    assert not (exchange / "result.json").exists()
    assert not (exchange / "predictions.parquet").exists()


def test_linux_cpu_distribution_alias_and_dual_install_failure() -> None:
    version = importlib.metadata.version

    def cpu_versions(name: str) -> str:
        if name == "xgboost":
            raise importlib.metadata.PackageNotFoundError(name)
        return "3.4.1" if name == "xgboost-cpu" else version(name)

    with (
        patch("alpha_qlib_worker.tabular.platform.system", return_value="Linux"),
        patch("alpha_qlib_worker.tabular.platform.machine", return_value="aarch64"),
        patch("alpha_qlib_worker.tabular.importlib.metadata.version", side_effect=cpu_versions),
        patch("alpha_qlib_worker.tabular.importlib.import_module"),
    ):
        row = next(row for row in backend_capabilities()["backends"] if row["name"] == "xgboost")
        assert row["status"] == "available"
        assert row["versions"]["xgboost-cpu"] == "3.4.1"

    def both_versions(name: str) -> str:
        return "3.4.1" if name in {"xgboost", "xgboost-cpu"} else version(name)

    with patch("alpha_qlib_worker.tabular.importlib.metadata.version", side_effect=both_versions):
        row = next(row for row in backend_capabilities()["backends"] if row["name"] == "xgboost")
        assert row["status"] == "incompatible_dependency"
        assert "ambiguous" in row["reason"]


def test_unsupported_catboost_platform_is_explicit() -> None:
    with (
        patch("alpha_qlib_worker.tabular.platform.system", return_value="Windows"),
        patch("alpha_qlib_worker.tabular.platform.machine", return_value="ARM64"),
    ):
        row = next(row for row in backend_capabilities()["backends"] if row["name"] == "catboost")
        assert row["status"] == "incompatible_dependency"
        assert "unsupported wheel platform" in row["reason"]
