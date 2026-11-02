"""Retained worker instrumentation with deterministic fake models, never research fits."""

from __future__ import annotations

import importlib
import json
import shutil
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import polars as pl
import pytest
from numpy.typing import NDArray

from alpha_qlib_worker import real
from alpha_qlib_worker.contract import (
    WorkerRequest,
    canonical_json_bytes,
    compute_config_hash,
    sha256_file,
)
from alpha_qlib_worker.fit_provenance import FitInvocation, FitTrace, value_digest
from alpha_qlib_worker.rank_ensemble import rank_ensemble_v1

from .test_fake_worker import _exchange


@pytest.fixture
def fold_case(monkeypatch: pytest.MonkeyPatch) -> Any:
    dates = pd.date_range("2023-01-02", periods=4, tz="UTC")
    rows: list[dict[str, Any]] = [
        {
            "datetime": origin,
            "instrument": symbol,
            "target_ts": target,
            "label": float(i + j),
            "a": float(i + j),
            "b": float(i - j),
        }
        for i, (origin, target) in enumerate(zip(dates[:-1], dates[1:], strict=True))
        for j, symbol in enumerate(("A", "B"))
    ]
    samples = pd.DataFrame(rows)
    fold = {
        "fold": 0,
        **{
            f"{role}_{edge}": dates[i].to_pydatetime()
            for role, i in (("train", 1), ("validation", 2), ("test", 3))
            for edge in ("start", "end")
        },
    }
    panel = pl.DataFrame(
        [
            {
                "symbol": row["instrument"],
                "session_ts": row["datetime"].to_pydatetime(),
                "available_at": row["datetime"].to_pydatetime(),
            }
            for row in rows
        ]
    )
    mode: dict[str, Any] = {}

    class Booster:
        best_iteration = 2

        def model_to_string(self, **_: Any) -> str:
            return "actual fake booster state"

        def feature_importance(self, **_: Any) -> NDArray[np.float64]:
            return np.array([1.0, 2.0])

    class LightGBM:
        def __init__(self, **_: Any) -> None:
            self.model: Any = None

        def fit(self, dataset: Any, **_: Any) -> None:
            if mode.get("failure") == "lightgbm.fit":
                raise ValueError("fit failed")
            self.model = None if mode.get("failure") == "booster" else Booster()

        def predict(self, dataset: Any, **_: Any) -> pd.Series:
            if mode.get("failure") == "lightgbm.predict":
                raise LookupError("prediction failed")
            frame = dataset.prepare("test", col_set="feature")
            scores = pd.Series([1.0, 1.0] if mode.get("ties") else [1.0, 2.0], index=frame.index)
            return scores.iloc[:1] if mode.get("singleton") else scores

    class Ridge:
        def __init__(self, **kwargs: Any) -> None:
            assert kwargs["include_valid"] is False
            self.coef_ = np.array([0.25, 0.5])

        def fit(self, dataset: Any) -> None:
            if mode.get("failure") == "ridge.fit":
                raise ValueError("ridge failed")

        def predict(self, dataset: Any, **_: Any) -> pd.Series:
            if mode.get("failure") == "ridge.predict":
                raise LookupError("ridge prediction failed")
            frame = dataset.prepare("test", col_set="feature")
            scores = pd.Series([2.0, 1.0], index=frame.index)
            return scores.iloc[:1] if mode.get("singleton") else scores

    original_import = importlib.import_module

    def import_model(name: str, package: str | None = None) -> Any:
        if name == "qlib.contrib.model.gbdt":
            return SimpleNamespace(LGBModel=LightGBM)
        if name == "qlib.contrib.model.linear":
            return SimpleNamespace(LinearModel=Ridge)
        return original_import(name, package)

    monkeypatch.setattr(importlib, "import_module", import_model)
    monkeypatch.setattr(real, "alpha158_feature_names", lambda: ["a", "b"])
    monkeypatch.setattr(
        real,
        "_ensure_qlib_runtime",
        lambda _: SimpleNamespace(start=lambda **kwargs: nullcontext()),
    )
    monkeypatch.setattr(real, "_qlib_runtime_directory", nullcontext)
    original_assembly = rank_ensemble_v1

    def assemble(left: pl.DataFrame, right: pl.DataFrame) -> Any:
        mode["assembly_inputs"] = (left.clone(), right.clone())
        return original_assembly(left, right)

    monkeypatch.setattr(real, "rank_ensemble_v1", assemble)

    def run(schema: int, trace: FitTrace | None = None) -> Any:
        payload = {
            "schema_version": schema,
            "model": {"name": "lightgbm" if schema == 1 else "rank_ensemble_v1", "parameters": {}},
            "seed": 7,
            "config_hash": "c" * 64,
            "worker_lock_hash": "d" * 64,
            "snapshot_hash": "e" * 64,
            "panel": {"sha256": "f" * 64},
        }
        request = WorkerRequest(payload, panel, ("A", "B"), (), (fold,))
        return real._fold_model(
            request=request,
            samples=samples,
            fold=fold,
            qlib_module=ModuleType("qlib"),
            lightgbm_module=ModuleType("lightgbm"),
            fit_trace=trace,
        )

    return run, mode, samples


@pytest.mark.parametrize("schema,ties", [(1, False), (2, False), (2, True)])
def test_opt_in_trace_preserves_outputs_and_input_frames(
    fold_case: Any, schema: int, ties: bool
) -> None:
    run, mode, samples = fold_case
    mode["ties"] = ties
    original = samples.copy(deep=True)
    expected = run(schema)
    trace = FitTrace()
    actual = run(schema, trace)
    assert actual[0].equals(expected[0])
    assert actual[0].columns == expected[0].columns
    assert actual[1:3] == expected[1:3]
    if schema == 2:
        assert actual[3].equals(expected[3])
    else:
        assert actual[3] is expected[3] is None
    pd.testing.assert_frame_equal(samples, original, check_exact=True)
    events = trace.seal()["events"]
    assert [(e["component"], e["operation"]) for e in events] == [
        ("normalizer", "fit"),
        ("label.train", "transform"),
        ("label.validation", "transform"),
        ("lightgbm", "fit"),
        ("lightgbm", "predict"),
    ] + (
        [("ridge", "fit"), ("ridge", "predict"), ("rank_ensemble", "assemble")]
        if schema == 2
        else []
    )
    assert events[3]["state_sha256"] == value_digest(b"actual fake booster state")
    assert set(events[3]["input_row_counts"]) == {
        "train_features",
        "train_labels",
        "validation_features",
        "validation_labels",
    }
    if schema == 2:
        assert set(events[5]["input_row_counts"]) == {"train_features", "train_labels"}
        assert events[-1]["operation"] == "assemble"
        left, right = mode["assembly_inputs"]
        assert events[-1]["input_hashes"]["lightgbm_predictions"] == value_digest(left.write_json())
        assert events[-1]["input_hashes"]["ridge_predictions"] == value_digest(right.write_json())
        assert events[-1]["output_hashes"]["predictions"] == value_digest(actual[0].write_json())
        assert events[-1]["output_hashes"]["diagnostics"] == value_digest(actual[3].write_json())


@pytest.mark.parametrize(
    "failure,component,operation,error",
    [
        ("lightgbm.fit", "lightgbm", "fit", ValueError),
        ("booster", "lightgbm", "fit", RuntimeError),
        ("lightgbm.predict", "lightgbm", "predict", LookupError),
        ("ridge.fit", "ridge", "fit", ValueError),
        ("ridge.predict", "ridge", "predict", LookupError),
    ],
)
def test_failures_retain_actual_prefix_without_forged_completion(
    fold_case: Any,
    failure: str,
    component: str,
    operation: str,
    error: type[BaseException],
) -> None:
    run, mode, _ = fold_case
    mode["failure"] = failure
    trace = FitTrace()
    with pytest.raises(error):
        run(2, trace)
    events = trace.seal(require_complete=False)["events"]
    assert (events[-1]["component"], events[-1]["operation"]) == (component, operation)
    assert events[-1]["status"] == "failed"
    assert events[-1]["state_sha256"] is None
    assert all(e["status"] == "completed" for e in events[:-1])
    if component == "lightgbm" and operation == "predict":
        assert events[-2]["state_sha256"] == value_digest(b"actual fake booster state")
    with pytest.raises(RuntimeError, match="incomplete"):
        trace.seal()


def test_invocation_snapshot_is_detached_and_not_durable_authority() -> None:
    invocation = FitInvocation()
    invocation.start()
    invocation.bind({"request_sha256": "a" * 64})
    invocation.folds[0] = FitTrace()
    invocation.failed(KeyboardInterrupt())
    snapshot = invocation.snapshot()
    assert snapshot["authority"] == "invocation_local_observation_only"
    assert snapshot["status"] == "failed"
    assert snapshot["folds"]["0"]["events"] == []
    snapshot["context"]["request_sha256"] = "b" * 64
    assert invocation.snapshot()["context"]["request_sha256"] == "a" * 64
    with pytest.raises(RuntimeError, match="cannot be rebound"):
        invocation.bind({})


def test_assembly_failure_keeps_both_completed_member_fits(
    fold_case: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    run, _, _ = fold_case
    original = ArithmeticError("assembly failed")

    def fail(*args: Any) -> Any:
        raise original

    monkeypatch.setattr(real, "rank_ensemble_v1", fail)
    trace = FitTrace()
    with pytest.raises(ArithmeticError) as caught:
        run(2, trace)
    assert caught.value is original
    events = trace.seal(require_complete=False)["events"]
    assert [(e["component"], e["status"]) for e in events if e["operation"] == "fit"] == [
        ("normalizer", "completed"),
        ("lightgbm", "completed"),
        ("ridge", "completed"),
    ]
    assert events[-1]["operation"] == "assemble"
    assert events[-1]["status"] == "failed"


def test_singleton_cross_section_fails_assembly_with_or_without_observation(fold_case: Any) -> None:
    run, mode, _ = fold_case
    mode["singleton"] = True
    with pytest.raises(RuntimeError, match="at least two symbols"):
        run(2)
    trace = FitTrace()
    with pytest.raises(RuntimeError, match="at least two symbols"):
        run(2, trace)
    events = trace.seal(require_complete=False)["events"]
    assert all(e["status"] == "completed" for e in events[:-1])
    assert events[-1]["operation"] == "assemble"
    assert events[-1]["status"] == "failed"


@pytest.mark.parametrize("phase", ["later_fold", "publication"])
def test_failed_invocation_preserves_completed_fold_observations(
    fold_case: Any, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, phase: str
) -> None:
    run, _, _ = fold_case
    original = OSError(phase)

    def fail_after_fold(*args: Any, observation: FitInvocation, **kwargs: Any) -> Any:
        observation.folds[0] = FitTrace()
        run(1, observation.folds[0])
        if phase == "later_fold":
            observation.folds[1] = FitTrace()
        raise original

    monkeypatch.setattr(real, "_run_real", fail_after_fold)
    invocation = FitInvocation()
    with pytest.raises(OSError) as caught:
        real.run_real(tmp_path, worker_lock_path=tmp_path / "unused", _observation=invocation)
    assert caught.value is original
    snapshot = invocation.snapshot()
    assert snapshot["status"] == "failed"
    assert all(e["status"] == "completed" for e in snapshot["folds"]["0"]["events"])
    if phase == "later_fold":
        assert snapshot["folds"]["1"]["events"] == []


@pytest.mark.parametrize("schema", [1, 2])
def test_synthetic_real_worker_artifacts_are_identical_with_observation(
    tmp_path: Path, schema: int
) -> None:
    first = _exchange(tmp_path / "unobserved")
    payload = json.loads((first / "request.json").read_text())
    payload["schema_version"] = schema
    payload["model"] = {
        "name": "lightgbm" if schema == 1 else "rank_ensemble_v1",
        "parameters": {"num_boost_round": 2, "early_stopping_rounds": 1, "num_threads": 1},
    }
    payload["config_hash"] = compute_config_hash(payload)
    (first / "request.json").write_bytes(canonical_json_bytes(payload))
    second = tmp_path / "observed"
    shutil.copytree(first, second)
    lock = Path(__file__).parents[1] / "uv.lock"
    expected = real.run_real(first, worker_lock_path=lock)
    invocation = FitInvocation()
    actual = real.run_real(second, worker_lock_path=lock, _observation=invocation)
    assert actual == expected
    assert {p.name for p in first.iterdir()} == {p.name for p in second.iterdir()}
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    snapshot = invocation.snapshot()
    assert snapshot["status"] == "completed"
    assert snapshot["context"]["request_sha256"] == sha256_file(second / "request.json")
    assert snapshot["context"]["worker_lock_sha256"] == sha256_file(lock)
    assert len(snapshot["folds"]["0"]["events"]) == (5 if schema == 1 else 8)
    (tmp_path / "observation.json").write_bytes(canonical_json_bytes(snapshot))
