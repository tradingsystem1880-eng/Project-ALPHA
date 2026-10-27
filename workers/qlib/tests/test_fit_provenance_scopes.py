"""Pure scope/assembly checks; no Qlib fit or fixture programme is executed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import pytest

from alpha_qlib_worker import real
from alpha_qlib_worker.contract import WorkerRequest
from alpha_qlib_worker.fit_provenance import FitInvocation, FitTrace, row_digest, value_digest


def _inputs() -> tuple[WorkerRequest, pd.DataFrame, dict[str, Any], dict[str, Any]]:
    sessions = tuple(pd.date_range("2023-01-02", periods=20, tz="UTC").to_pydatetime())
    panel = pl.DataFrame(
        {
            "session_ts": sessions,
            "symbol": ["S00"] * 20,
            "available_at": [stamp + pd.Timedelta(hours=23) for stamp in sessions],
        }
    )
    fold = {
        "fold": 0,
        "train_start": sessions[1],
        "train_end": sessions[3],
        "validation_start": sessions[6],
        "validation_end": sessions[8],
        "test_start": sessions[11],
        "test_end": sessions[14],
    }
    samples = pd.DataFrame(
        {
            "datetime": sessions[:-2],
            "instrument": "S00",
            "target_ts": sessions[1:-1],
            "a": [float(i) for i in range(18)],
            "label": [float(i) / 10 for i in range(18)],
        }
    )
    request = WorkerRequest(
        {"purge_sessions": 2, "embargo_sessions": 2}, panel, ("S00",), sessions, (fold,)
    )

    def segment(role: str, labelled: bool = True) -> tuple[Any, Any, Any]:
        selected = samples.loc[
            samples.target_ts.between(fold[f"{role}_start"], fold[f"{role}_end"])
        ].set_index(["datetime", "instrument"])
        return selected[["a"]], selected.label if labelled else None, selected[["target_ts"]]

    segments = {
        "train": segment("train"),
        "validation": segment("validation"),
        "test": segment("test", False),
    }
    return request, samples, fold, segments


def _provenance() -> tuple[dict[str, Any], dict[str, Any]]:
    request, samples, fold, segments = _inputs()
    return real._fold_input_provenance(request, samples, fold, **segments), segments


def test_scopes_bind_raw_rows_values_intervals_and_availability() -> None:
    observed, segments = _provenance()
    train_x, train_y, _ = segments["train"]
    scope = observed["scopes"]["train"]
    assert scope["row_count"] == 3
    assert scope["origin_session_count"] == scope["target_session_count"] == 3
    assert scope["outcome_interval_count"] == scope["event_cluster_count"] == 3
    assert scope["row_ids_sha256"] == row_digest(train_x)
    assert scope["feature_values_sha256"] == value_digest(train_x)
    assert scope["label_values_sha256"] == value_digest(train_y)
    assert scope["windows"]["target_start"] == "2023-01-03T00:00:00+00:00"
    assert scope["windows"]["label_end_end"] == "2023-01-06T00:00:00+00:00"
    assert scope["windows"]["label_known_at_end"] == "2023-01-06T23:00:00+00:00"
    assert observed["scopes"]["test"]["label_values_sha256"] is None
    assert observed["exclusions"]["train_validation"]["row_count"] == 2
    assert observed["exclusions"]["validation_test"]["row_count"] == 2
    assert observed["exclusions"]["cross_split_interval_overlap_count"] == 0
    assert observed["exclusions"]["general_event_clusters"] == "not_evaluated"


def test_scope_is_deterministic_and_feature_values_are_bound() -> None:
    request, samples, fold, segments = _inputs()
    first = real._fold_input_provenance(request, samples, fold, **segments)
    assert first == real._fold_input_provenance(request, samples, fold, **segments)
    segments["train"][0].iloc[0, 0] += 1.0
    changed = real._fold_input_provenance(request, samples, fold, **segments)
    assert (
        first["scopes"]["train"]["row_ids_sha256"] == changed["scopes"]["train"]["row_ids_sha256"]
    )
    assert (
        first["scopes"]["train"]["feature_values_sha256"]
        != changed["scopes"]["train"]["feature_values_sha256"]
    )


def test_scope_rejects_misaligned_labels() -> None:
    request, samples, fold, segments = _inputs()
    x, y, meta = segments["train"]
    segments["train"] = x, y.iloc[::-1], meta
    with pytest.raises(RuntimeError, match="misaligned"):
        real._fold_input_provenance(request, samples, fold, **segments)


def test_scope_rejects_noncanonical_target_geometry() -> None:
    request, samples, fold, segments = _inputs()
    segments["train"][2].iloc[0, 0] = request.sessions[2]
    with pytest.raises(RuntimeError, match="one-session"):
        real._fold_input_provenance(request, samples, fold, **segments)


def test_scope_rejects_labels_unavailable_at_next_origin() -> None:
    request, samples, fold, segments = _inputs()
    x, y, meta = segments["validation"]
    early_index = pd.MultiIndex.from_tuples(
        [(request.sessions[i], "S00") for i in [4, 5, 6]], names=x.index.names
    )
    segments["validation"] = (
        x.set_axis(early_index),
        y.set_axis(early_index),
        pd.DataFrame({"target_ts": [request.sessions[i] for i in [5, 6, 7]]}, index=early_index),
    )
    # Training labels end at session4 +23h, exactly the earliest validation origin clock.
    real._fold_input_provenance(request, samples, fold, **segments)
    early_index = pd.MultiIndex.from_tuples(
        [(request.sessions[i], "S00") for i in [3, 4, 5]], names=x.index.names
    )
    segments["validation"] = (
        x.set_axis(early_index),
        y.set_axis(early_index),
        pd.DataFrame({"target_ts": [request.sessions[i] for i in [4, 5, 6]]}, index=early_index),
    )
    with pytest.raises(RuntimeError, match="unavailable"):
        real._fold_input_provenance(request, samples, fold, **segments)


@pytest.mark.parametrize("poison", ["rows", "values"])
def test_raw_normalizer_scope_binding_detects_leaky_or_changed_fit(poison: str) -> None:
    inputs, segments = _provenance()
    train_x, train_y, train_meta = segments["train"]
    valid_x, valid_y, valid_meta = segments["validation"]
    altered = pd.concat([train_x, valid_x]) if poison == "rows" else train_x + 17.0
    trace = FitTrace()
    real._normalize_features(altered, [valid_x, segments["test"][0]], recorder=trace)
    real._normalize_label(train_y, train_meta.target_ts, recorder=trace, component="label.train")
    real._normalize_label(
        valid_y, valid_meta.target_ts, recorder=trace, component="label.validation"
    )
    with pytest.raises(RuntimeError, match="raw training scope"):
        real._seal_fold_provenance(
            trace, fold=0, model_hash="a" * 64, inputs=inputs, model_name="catboost", parameters={}
        )


@pytest.mark.parametrize("poison", ["labels", "groups"])
def test_raw_label_scope_binding_rejects_changed_transform_inputs(poison: str) -> None:
    inputs, segments = _provenance()
    trace = FitTrace()
    real._normalize_features(
        segments["train"][0], [segments["validation"][0], segments["test"][0]], recorder=trace
    )
    for role in ["train", "validation"]:
        _, labels, meta = segments[role]
        groups = meta.target_ts + pd.Timedelta(days=1) if poison == "groups" else meta.target_ts
        real._normalize_label(
            labels + 1.0 if poison == "labels" else labels,
            groups,
            recorder=trace,
            component=f"label.{role}",
        )
    with pytest.raises(RuntimeError, match="raw label scope"):
        real._seal_fold_provenance(
            trace, fold=0, model_hash="a" * 64, inputs=inputs, model_name="catboost", parameters={}
        )


def test_fold_assembly_is_deterministic_and_does_not_qualify_other_backends() -> None:
    inputs, segments = _provenance()
    trace = FitTrace()
    real._normalize_features(
        segments["train"][0], [segments["validation"][0], segments["test"][0]], recorder=trace
    )
    for role in ["train", "validation"]:
        _, labels, meta = segments[role]
        real._normalize_label(labels, meta.target_ts, recorder=trace, component=f"label.{role}")
    first = real._seal_fold_provenance(
        trace, fold=0, model_hash="a" * 64, inputs=inputs, model_name="catboost", parameters={}
    )
    assert first == real._seal_fold_provenance(
        trace, fold=0, model_hash="a" * 64, inputs=inputs, model_name="catboost", parameters={}
    )
    assert first["graph_status"] == "outside_reference_protocol"
    assert first["model_hash"] == "a" * 64


@pytest.mark.parametrize("error", [KeyboardInterrupt, RuntimeError])
def test_invocation_observes_failure_without_success_artifact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: type[BaseException]
) -> None:
    def interrupted(*args: Any, **kwargs: Any) -> Any:
        raise error("stopped")

    monkeypatch.setattr(real, "_run_real", interrupted)
    observation = FitInvocation()
    with pytest.raises(error, match="stopped"):
        real.run_real(tmp_path, worker_lock_path=tmp_path / "lock", _observation=observation)
    assert observation.status == "failed"
    assert observation.error_type == error.__name__
    assert not (tmp_path / "result.json").exists()


def test_invocation_preserves_return_and_refuses_reuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = {"status": "succeeded"}
    monkeypatch.setattr(real, "_run_real", lambda *args, **kwargs: expected)
    observation = FitInvocation()
    assert (
        real.run_real(tmp_path, worker_lock_path=tmp_path / "lock", _observation=observation)
        is expected
    )
    assert observation.status == "completed"
    with pytest.raises(RuntimeError, match="cannot be reused"):
        real.run_real(tmp_path, worker_lock_path=tmp_path / "lock", _observation=observation)
