"""Executed-boundary and graph oracles using fake fitters, never native model fits."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

import numpy as np
import pandas as pd
import pytest

from alpha_qlib_worker.contract import canonical_json_bytes
from alpha_qlib_worker.fit_provenance import (
    FitTrace,
    observe_call,
    validate_reference_graph,
    value_digest,
)
from alpha_qlib_worker.real import (
    _MemoryDataset,
    _normalize_features,
    _normalize_label,
    _qlib_frame,
)
from alpha_qlib_worker.tabular_adapters import _observed_linear_class, _ordered_double_class


def _prefix() -> tuple[FitTrace, _MemoryDataset]:
    index = pd.MultiIndex.from_product(
        [pd.date_range("2023-01-02", periods=6, tz="UTC"), ["A", "B"]],
        names=["datetime", "instrument"],
    )
    values = pd.DataFrame(
        {"a": np.arange(12, dtype="float64"), "b": np.arange(12, dtype="float64") ** 2},
        index=index,
    )
    labels = pd.Series(np.arange(12, dtype="float64"), index=index, name="label")
    trace = FitTrace()
    train, (valid, test), _, _ = _normalize_features(
        values.iloc[:4], [values.iloc[4:8], values.iloc[8:]], recorder=trace
    )
    targets = pd.Series(index.get_level_values(0), index=index)
    train_y = _normalize_label(
        labels.iloc[:4], targets.iloc[:4], recorder=trace, component="label.train"
    )
    valid_y = _normalize_label(
        labels.iloc[4:8], targets.iloc[4:8], recorder=trace, component="label.validation"
    )
    return trace, _MemoryDataset(
        {
            "train": _qlib_frame(train, train_y),
            "valid": _qlib_frame(valid, valid_y),
            "test": _qlib_frame(test),
        },
        flatten_single=True,
    )


def test_observe_call_preserves_actual_return_and_interruption() -> None:
    trace = FitTrace()
    value = object()
    assert (
        observe_call(trace, "model", "fit", {"input": 1}, lambda: value, lambda _: {"state": [1]})
        is value
    )
    assert trace.seal()["events"][0]["status"] == "completed"
    interrupted = FitTrace()

    def stop() -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        observe_call(interrupted, "model", "fit", {}, stop, lambda _: {"state": [1]})
    assert (
        interrupted.seal(require_complete=False)["events"][0]["error_type"] == "KeyboardInterrupt"
    )
    with pytest.raises(RuntimeError, match="incomplete"):
        interrupted.seal()


class _Linear:
    calls = 0

    def _fit(self, x: Any, y: Any, weights: Any) -> str:
        self.calls += 1
        self.coef_ = np.zeros(x.shape[1], dtype="float64")
        self.intercept_ = 0.0
        return "actual fake fit"

    def _fit_nnls(self, x: Any, y: Any, weights: Any = None) -> str:
        return self._fit(x, y, weights)


def _ridge_graph() -> dict[str, Any]:
    trace, dataset = _prefix()
    frame = dataset.prepare("train", col_set=["feature", "label"])
    cls = _observed_linear_class(_Linear, dataset=dataset, recorder=trace, context={"seed": 7})
    model = cls()
    assert (
        model._fit(frame["feature"].values, frame["label"].values.squeeze(), None)
        == "actual fake fit"
    )
    assert model.calls == 1
    sealed = trace.seal()
    assert (
        validate_reference_graph(sealed, name="linear", parameters={"estimator": "ridge"})
        == "complete_reference_call_graph"
    )
    return sealed


def test_linear_native_boundary_observes_consumed_arrays() -> None:
    _ridge_graph()


def test_linear_rejects_changed_arrays_before_base_fit() -> None:
    trace, dataset = _prefix()
    frame = dataset.prepare("train", col_set=["feature", "label"])
    cls = _observed_linear_class(_Linear, dataset=dataset, recorder=trace, context={"seed": 7})
    model = cls()
    with pytest.raises(RuntimeError, match="native inputs"):
        model._fit(frame["feature"].values + 1, frame["label"].values.squeeze(), None)
    assert model.calls == 0
    assert trace.seal(require_complete=False)["events"][-1]["status"] == "failed"


@pytest.mark.parametrize(
    "corruption", ["missing", "reordered", "empty_state", "state_hash", "unlinked", "trace_hash"]
)
def test_reference_graph_rejects_missing_or_unlinked_calls(corruption: str) -> None:
    sealed = copy.deepcopy(_ridge_graph())
    if corruption == "missing":
        sealed["events"].pop()
    elif corruption == "reordered":
        sealed["events"][0], sealed["events"][1] = sealed["events"][1], sealed["events"][0]
    elif corruption == "empty_state":
        sealed["events"][-1]["output_hashes"] = {}
    elif corruption == "state_hash":
        sealed["events"][-1]["state_sha256"] = "0" * 64
    elif corruption == "unlinked":
        sealed["events"][-1]["input_hashes"]["train_features"] = "0" * 64
    if corruption != "trace_hash":
        sealed["trace_sha256"] = hashlib.sha256(canonical_json_bytes(sealed["events"])).hexdigest()
    else:
        sealed["trace_sha256"] = "0" * 64
    with pytest.raises(RuntimeError):
        validate_reference_graph(sealed, name="linear", parameters={"estimator": "ridge"})


class _Booster:
    best_iteration = 1

    def __init__(self, value: int) -> None:
        self.value = value

    def model_to_string(self, **kwargs: Any) -> str:
        return f"fake native state {self.value}"


class _Double:
    alpha1 = 1.0
    alpha2 = 1.0
    bins_sr = 10
    bins_fs = 5
    decay = 1.0
    sample_ratios = [0.8, 0.7, 0.6, 0.5, 0.4]

    def __init__(self) -> None:
        self.ensemble: list[_Booster] = []
        self.sub_features: list[pd.Index] = []

    def train_submodel(self, train: Any, valid: Any, weights: Any, features: Any) -> _Booster:
        return _Booster(len(self.ensemble))

    def sample_reweight(self, loss_curve: Any, loss_values: Any, k_th: Any) -> pd.Series:
        return pd.Series(np.ones(len(loss_values), dtype="float64"))

    def feature_selection(self, train: Any, loss_values: Any) -> pd.Index:
        return pd.Index(["b"])


def test_double_native_boundaries_record_learned_inputs_and_links() -> None:
    trace, dataset = _prefix()
    train = dataset.prepare("train", col_set=["feature", "label"])
    valid = dataset.prepare("valid", col_set=["feature", "label"])
    context = {"seed": 7}
    model = _ordered_double_class(_Double, recorder=trace, context=context)()
    inputs = {
        "context": context,
        "train_features": train["feature"],
        "train_labels": train["label"].iloc[:, 0].rename("label"),
        "validation_features": valid["feature"],
        "validation_labels": valid["label"].iloc[:, 0].rename("label"),
    }

    def fit() -> None:
        weights = pd.Series(np.ones(len(train), dtype="float64"))
        features = train["feature"].columns
        model.sub_features.append(features)
        model.ensemble.append(model.train_submodel(train, valid, weights, features))
        loss_curve = pd.DataFrame(np.zeros((len(train), 2), dtype="float64"))
        loss_values = pd.Series(np.zeros(len(train), dtype="float64"))
        weights = model.sample_reweight(loss_curve, loss_values, 1)
        features = model.feature_selection(train, loss_values)
        model.sub_features.append(features)
        model.ensemble.append(model.train_submodel(train, valid, weights, features))

    observe_call(
        trace,
        "model",
        "fit",
        inputs,
        fit,
        lambda _: {
            "state": ["assembled"],
            "member_state_sha256": {
                str(i): value_digest(booster.model_to_string().encode())
                for i, booster in enumerate(model.ensemble)
            },
            "member_feature_sha256": {
                str(i): value_digest(pd.Index(subset))
                for i, subset in enumerate(model.sub_features)
            },
        },
    )
    sealed = trace.seal()
    assert (
        validate_reference_graph(sealed, name="double_ensemble", parameters={"num_models": 2})
        == "complete_reference_call_graph"
    )
    assert len([e for e in sealed["events"] if e["component"].startswith("member.")]) == 2
    for field in ["input_hashes", "input_row_counts", "input_row_ids_sha256"]:
        corrupted = copy.deepcopy(sealed)
        selection = next(e for e in corrupted["events"] if e["component"] == "selection.1")
        selection[field]["loss_values"] = 1 if field == "input_row_counts" else "0" * 64
        corrupted["trace_sha256"] = value_digest(corrupted["events"])
        with pytest.raises(RuntimeError, match="selection loss"):
            validate_reference_graph(
                corrupted, name="double_ensemble", parameters={"num_models": 2}
            )
    invalid = copy.deepcopy(sealed)
    invalid["events"][-1]["input_hashes"]["weights"] = "0" * 64
    invalid["trace_sha256"] = hashlib.sha256(canonical_json_bytes(invalid["events"])).hexdigest()
    with pytest.raises(RuntimeError):
        validate_reference_graph(invalid, name="double_ensemble", parameters={"num_models": 2})
