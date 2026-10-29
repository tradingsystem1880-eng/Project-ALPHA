"""Pure provenance checks: no model fitting or experiment budget consumption."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from alpha_qlib_worker.fit_provenance import FitTrace, row_digest, value_digest
from alpha_qlib_worker.real import _normalize_features, _normalize_label


def _frame() -> pd.DataFrame:
    index = pd.MultiIndex.from_product(
        [pd.date_range("2023-01-02", periods=2, tz="UTC"), ["S00"]],
        names=["datetime", "instrument"],
    )
    return pd.DataFrame({"a": [1.0, np.nan]}, index=index)


def test_frame_digest_binds_values_and_actual_row_identity() -> None:
    original = _frame()
    changed = original.copy()
    changed.iloc[0, 0] = 7.0
    assert row_digest(original) == row_digest(changed)
    assert value_digest(original) != value_digest(changed)
    assert value_digest(original) == value_digest(original.copy())
    assert row_digest(original) != row_digest(original.iloc[::-1])


def test_trace_records_entry_then_actual_completed_outputs() -> None:
    trace = FitTrace()
    frame = _frame()
    token = trace.begin("normalizer", "fit", {"train": frame})
    with pytest.raises(RuntimeError, match="incomplete"):
        trace.seal()
    state = {"median": [1.0], "center": [1.0], "scale": [1.0]}
    trace.complete(token, {"state": state})
    sealed = trace.seal()
    event = sealed["events"][0]
    assert event["status"] == "completed"
    assert event["input_row_counts"] == {"train": 2}
    assert event["input_row_ids_sha256"] == {"train": row_digest(frame)}
    assert event["input_hashes"] == {"train": value_digest(frame)}
    assert event["state_sha256"] == value_digest(state)
    assert sealed == trace.seal()
    with pytest.raises(RuntimeError, match="already closed"):
        trace.complete(token, {"state": state})


def test_failure_is_observed_without_becoming_completed_evidence() -> None:
    trace = FitTrace()
    token = trace.begin("member.0", "fit", {"train": _frame()})
    trace.failed(token, KeyboardInterrupt())
    with pytest.raises(RuntimeError, match="incomplete"):
        trace.seal()
    snapshot = trace.seal(require_complete=False)
    event = snapshot["events"][0]
    assert event["status"] == "failed"
    assert event["error_type"] == "KeyboardInterrupt"
    assert event["state_sha256"] is None
    assert event["output_hashes"] == {}
    event["status"] = "forged"
    assert trace.seal(require_complete=False)["events"][0]["status"] == "failed"


def test_value_digest_canonicalizes_nan_payload_bits() -> None:
    first = np.array([np.nan], dtype="float64")
    second = np.array([0x7FF8000000000001], dtype="uint64").view("float64")
    assert value_digest(first) == value_digest(second)


def test_normalizer_observes_its_actual_training_argument_and_state() -> None:
    train = pd.DataFrame({"a": [1.0, 3.0, np.nan]}, index=[0, 1, 2])
    other = pd.DataFrame({"a": [900.0]}, index=[3])
    trace = FitTrace()
    normalized, _, state_hash, _ = _normalize_features(train, [other], recorder=trace)
    event = trace.seal()["events"][0]
    assert event["component"] == "normalizer"
    assert event["operation"] == "fit"
    assert event["input_row_counts"] == {"train": 3}
    assert event["input_row_ids_sha256"]["train"] == row_digest(train)
    assert event["input_hashes"]["train"] == value_digest(train)
    assert event["state_sha256"] == state_hash
    assert event["output_hashes"]["train_features"] == value_digest(normalized)


def test_leaky_normalizer_twin_exposes_wrong_fit_rows() -> None:
    train = pd.DataFrame({"a": [1.0, 3.0]}, index=[0, 1])
    future = pd.DataFrame({"a": [900.0]}, index=[2])
    trace = FitTrace()
    _normalize_features(pd.concat([train, future]), [future], recorder=trace)
    event = trace.seal()["events"][0]
    assert event["input_row_counts"]["train"] == 3
    with pytest.raises(AssertionError):
        assert event["input_row_ids_sha256"]["train"] == row_digest(train)


def test_label_transform_records_raw_and_normalized_labels_without_a_fit() -> None:
    labels = pd.Series([1.0, 3.0], index=["a", "b"], name="label")
    targets = pd.Series(pd.Timestamp("2023-01-03", tz="UTC"), index=labels.index)
    expected = _normalize_label(labels, targets)
    trace = FitTrace()
    actual = _normalize_label(labels, targets, recorder=trace, component="label.train")
    pd.testing.assert_series_equal(actual, expected, check_exact=True)
    event = trace.seal()["events"][0]
    assert event["component"] == "label.train"
    assert event["operation"] == "transform"
    assert event["input_hashes"]["labels"] == value_digest(labels)
    assert event["output_hashes"]["normalized_labels"] == value_digest(actual)
    assert event["state_sha256"] == value_digest(actual)


def test_normalizer_failure_remains_observable_without_completion() -> None:
    train = pd.DataFrame({"a": [1.0, 3.0]}, index=[0, 1])
    invalid = pd.DataFrame({"a": [np.inf]}, index=[2])
    trace = FitTrace()
    with pytest.raises(RuntimeError, match="non-finite"):
        _normalize_features(train, [invalid], recorder=trace)
    event = trace.seal(require_complete=False)["events"][0]
    assert event["status"] == "failed"
    assert event["error_type"] == "RuntimeError"
    with pytest.raises(RuntimeError, match="incomplete"):
        trace.seal()


@pytest.mark.parametrize(
    "values",
    [
        np.array([2**53, 2**53 + 1], dtype="int64"),
        np.array([1 + 2j], dtype="complex128"),
        pd.DataFrame({"value": [2**53 + 1]}),
    ],
)
def test_hashing_rejects_lossy_numeric_conversion(values: object) -> None:
    with pytest.raises(TypeError, match="floating"):
        value_digest(values)


def test_empty_or_state_free_observations_cannot_seal_success() -> None:
    trace = FitTrace()
    with pytest.raises(RuntimeError, match="incomplete"):
        trace.seal()
    token = trace.begin("normalizer", "fit", {"train": _frame()})
    with pytest.raises(ValueError, match="output"):
        trace.complete(token, {})
    with pytest.raises(RuntimeError, match="incomplete"):
        trace.seal()
