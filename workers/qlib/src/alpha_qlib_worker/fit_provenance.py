"""Deterministic observations of executed fitted-component calls.

This is an invocation-local trace, not admission, accounting, or proof of independent trials.
No timestamp, nonce, configured fit count, or model object enters the portable trace.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from alpha_qlib_worker.contract import canonical_json_bytes


def _json_digest(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _key(value: object) -> object:
    if isinstance(value, tuple):
        return [_key(part) for part in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, int | np.integer) and not isinstance(value, bool):
        return int(value)
    raise TypeError(f"unsupported provenance row/column key: {type(value).__name__}")


def row_digest(frame: pd.DataFrame | pd.Series) -> str:
    rows = [
        [_key(part) for part in row] if isinstance(row, tuple) else [_key(row)]
        for row in frame.index
    ]
    return _json_digest(rows)


def _numeric_digest(values: object, header: dict[str, Any]) -> str:
    original = np.asarray(values)
    if original.dtype.kind != "f" or original.dtype.itemsize > 8:
        raise TypeError("provenance numeric inputs require supported real floating-point values")
    data = np.array(original, dtype="<f8", order="C", copy=True)
    # Different floating-point NaN payloads represent the same missing observation.
    data[np.isnan(data)] = np.nan
    metadata = {**header, "shape": list(data.shape)}
    return hashlib.sha256(canonical_json_bytes(metadata) + data.tobytes(order="C")).hexdigest()


def value_digest(value: object) -> str:
    if isinstance(value, pd.Series):
        value = value.to_frame()
    if isinstance(value, pd.DataFrame):
        return _numeric_digest(
            value.to_numpy(),
            {
                "index_names": [_key(name) for name in value.index.names],
                "columns": [_key(column) for column in value.columns],
                "row_ids_sha256": row_digest(value),
            },
        )
    if isinstance(value, np.ndarray):
        return _numeric_digest(value, {})
    if isinstance(value, pd.Index):
        return _json_digest([_key(item) for item in value])
    if isinstance(value, bytes):
        return hashlib.sha256(value).hexdigest()
    return _json_digest(value)


class FitTrace:
    """Record entry and the observed return or failure of one actual call."""

    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []

    def begin(self, component: str, operation: str, inputs: Mapping[str, object]) -> int:
        if not component or operation not in {"fit", "transform", "select", "reweight"}:
            raise ValueError("invalid fitted-component observation")
        frames = {
            name: value
            for name, value in inputs.items()
            if isinstance(value, pd.DataFrame | pd.Series)
        }
        sequence = len(self._events)
        self._events.append(
            {
                "sequence": sequence,
                "component": component,
                "operation": operation,
                "status": "entered",
                "input_hashes": {name: value_digest(value) for name, value in inputs.items()},
                "input_row_ids_sha256": {name: row_digest(value) for name, value in frames.items()},
                "input_row_counts": {name: len(value) for name, value in frames.items()},
                "output_hashes": {},
                "state_sha256": None,
                "error_type": None,
            }
        )
        return sequence

    def _active(self, sequence: int) -> dict[str, Any]:
        if sequence < 0 or sequence >= len(self._events):
            raise ValueError("unknown fitted-component observation")
        event = self._events[sequence]
        if event["status"] != "entered":
            raise RuntimeError("fitted-component observation already closed")
        return event

    def complete(self, sequence: int, outputs: Mapping[str, object]) -> None:
        event = self._active(sequence)
        if not outputs:
            raise ValueError("completed component observations require actual outputs")
        hashes = {name: value_digest(value) for name, value in outputs.items()}
        event.update(
            status="completed",
            output_hashes=hashes,
            state_sha256=hashes.get("state", _json_digest(hashes)),
        )

    def failed(self, sequence: int, error: BaseException) -> None:
        self._active(sequence).update(status="failed", error_type=type(error).__name__)

    def seal(self, *, require_complete: bool = True) -> dict[str, Any]:
        events = copy.deepcopy(self._events)
        if require_complete and (
            not events or any(event["status"] != "completed" for event in events)
        ):
            raise RuntimeError("fitted-component observations are incomplete")
        return {"events": events, "trace_sha256": _json_digest(events)}


class FitInvocation:
    """Private, single-invocation observation; never a durable accounting record."""

    def __init__(self) -> None:
        self.status = "pending"
        self.error_type: str | None = None
        self.folds: dict[int, FitTrace] = {}

    def start(self) -> None:
        if self.status != "pending" or self.folds:
            raise RuntimeError("fitted-component observation cannot be reused")
        self.status = "entered"

    def failed(self, error: BaseException) -> None:
        self.status = "failed"
        self.error_type = type(error).__name__

    def complete(self) -> None:
        self.status = "completed"


def observe_call(
    recorder: FitTrace | None,
    component: str,
    operation: str,
    inputs: Mapping[str, object],
    call: Callable[[], Any],
    outputs: Callable[[Any], Mapping[str, object]],
) -> Any:
    """Observe an executed call; preserve its return value and BaseException behavior."""
    if recorder is None:
        return call()
    sequence = recorder.begin(component, operation, inputs)
    try:
        result = call()
        recorder.complete(sequence, outputs(result))
        return result
    except BaseException as exc:
        recorder.failed(sequence, exc)
        raise


def validate_reference_graph(
    sealed: Mapping[str, Any], *, name: str, parameters: Mapping[str, Any]
) -> str:
    """Validate observed call structure, without assigning statistical qualification."""
    ridge = name == "linear" and parameters.get("estimator") == "ridge"
    double = name == "double_ensemble"
    if not ridge and not double:
        return "outside_reference_protocol"
    events = sealed["events"]
    if sealed["trace_sha256"] != _json_digest(events):
        raise RuntimeError("fitted-component trace hash mismatch")
    for index, event in enumerate(events):
        state = event["output_hashes"].get("state")
        if (
            type(event["sequence"]) is not int
            or event["sequence"] != index
            or event["status"] != "completed"
            or event["error_type"] is not None
            or not isinstance(state, str)
            or len(state) != 64
            or any(character not in "0123456789abcdef" for character in state)
            or event["state_sha256"] != state
        ):
            raise RuntimeError("reference component has no completed observed state")
    expected = [
        ("normalizer", "fit"),
        ("label.train", "transform"),
        ("label.validation", "transform"),
        ("model", "fit"),
    ]
    if double:
        members = int(parameters["num_models"])
        for index in range(members):
            expected.append((f"member.{index}", "fit"))
            if index < members - 1:
                expected.extend(
                    [(f"reweight.{index + 1}", "reweight"), (f"selection.{index + 1}", "select")]
                )
    observed = [(event["component"], event["operation"]) for event in events]
    if observed != expected:
        raise RuntimeError("reference fitted-component call graph is incomplete")
    by_component = {event["component"]: event for event in events}

    def linked(producer: str, output: str, consumer: str, input_name: str) -> None:
        produced = by_component[producer]["output_hashes"].get(output)
        consumed = by_component[consumer]["input_hashes"].get(input_name)
        if produced is None or produced != consumed:
            raise RuntimeError(
                f"fitted-component input is unlinked: {producer}.{output}"
                f" -> {consumer}.{input_name}"
            )

    linked("normalizer", "train_features", "model", "train_features")
    linked("label.train", "normalized_labels", "model", "train_labels")
    train_rows = by_component["normalizer"]["input_row_ids_sha256"].get("train")
    for component, input_name in [
        ("label.train", "labels"),
        ("model", "train_features"),
        ("model", "train_labels"),
    ]:
        if (
            train_rows is None
            or by_component[component]["input_row_ids_sha256"].get(input_name) != train_rows
        ):
            raise RuntimeError("reference component consumed different training rows")
    if double:
        members = int(parameters["num_models"])
        linked("normalizer", "other_0_features", "model", "validation_features")
        linked("label.validation", "normalized_labels", "model", "validation_labels")
        linked("normalizer", "train_features", "member.0", "train_features")
        linked("normalizer", "other_0_features", "member.0", "validation_features")
        for index in range(members):
            member = f"member.{index}"
            linked("normalizer", "train_features", member, "source_train_features")
            linked("normalizer", "other_0_features", member, "source_validation_features")
            linked("label.train", "normalized_labels", member, "train_labels")
            linked("label.validation", "normalized_labels", member, "validation_labels")
            for input_name in ["train_features", "train_labels", "source_train_features"]:
                if by_component[member]["input_row_ids_sha256"].get(input_name) != train_rows:
                    raise RuntimeError("member training rows differ from the fitted source")
            if index:
                linked(f"reweight.{index}", "weights", member, "weights")
                linked(f"selection.{index}", "features", member, "features")
                selection = by_component[f"selection.{index}"]
                reweight = by_component[f"reweight.{index}"]
                linked("normalizer", "train_features", f"selection.{index}", "train_features")
                linked("label.train", "normalized_labels", f"selection.{index}", "train_labels")
                if reweight["input_hashes"].get("training_row_ids") != train_rows:
                    raise RuntimeError("reweighting has no aligned training-row mapping")
                train_count = by_component["normalizer"]["input_row_counts"]["train"]
                for field in ["input_hashes", "input_row_counts", "input_row_ids_sha256"]:
                    if selection[field].get("loss_values") is None or selection[field].get(
                        "loss_values"
                    ) != reweight[field].get("loss_values"):
                        raise RuntimeError("feature selection loss is unlinked from reweighting")
                for input_name in ["loss_curve", "loss_values"]:
                    if reweight["input_row_counts"].get(input_name) != train_count:
                        raise RuntimeError("reweighting loss rows differ from training rows")
                if (
                    reweight["input_hashes"].get("source_member_state")
                    != by_component[f"member.{index - 1}"]["state_sha256"]
                ):
                    raise RuntimeError("reweighting consumed an unlinked member state")
                member_states = {
                    str(previous): by_component[f"member.{previous}"]["state_sha256"]
                    for previous in range(index)
                }
                if selection["input_hashes"].get("member_state_sha256") != _json_digest(
                    member_states
                ):
                    raise RuntimeError("feature selection consumed unlinked member states")
                if by_component[member]["input_row_counts"].get("weights") != train_count:
                    raise RuntimeError("member weights differ from the training-row count")
        validation_rows = by_component["label.validation"]["input_row_ids_sha256"]["labels"]
        for component in ["model", *[f"member.{i}" for i in range(members)]]:
            for input_name in ["validation_features", "validation_labels"]:
                if (
                    by_component[component]["input_row_ids_sha256"].get(input_name)
                    != validation_rows
                ):
                    raise RuntimeError("validation rows differ between fitted components")
        for index in range(members):
            if (
                by_component[f"member.{index}"]["input_row_ids_sha256"].get(
                    "source_validation_features"
                )
                != validation_rows
            ):
                raise RuntimeError("member validation source rows are unlinked")
        member_states = {
            str(i): by_component[f"member.{i}"]["state_sha256"] for i in range(members)
        }
        member_features = {
            str(i): by_component[f"member.{i}"]["input_hashes"]["features"] for i in range(members)
        }
        if by_component["model"]["output_hashes"].get("member_state_sha256") != _json_digest(
            member_states
        ) or by_component["model"]["output_hashes"].get("member_feature_sha256") != _json_digest(
            member_features
        ):
            raise RuntimeError("ensemble assembly is unlinked from its fitted members")
    context_hash = by_component["model"]["input_hashes"].get("context")
    if context_hash is None or any(
        event["input_hashes"].get("context") != context_hash
        for event in events
        if event["component"] not in {"normalizer", "label.train", "label.validation"}
    ):
        raise RuntimeError("native components have different execution contexts")
    return "complete_reference_call_graph"
