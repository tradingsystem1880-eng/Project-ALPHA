"""Synthetic checkpoint failures; no model, research or external store execution."""

from __future__ import annotations

import json
from typing import Any

import pytest

from alpha_qlib_worker.fit_provenance import FitInvocation, observe_call


def test_checkpoint_before_call_and_after_completion() -> None:
    saved: list[dict[str, Any]] = []
    invocation = FitInvocation(checkpoint=lambda data: saved.append(json.loads(data)["snapshot"]))
    invocation.start()
    invocation.bind({"request": "synthetic"})
    trace = invocation.new_trace(0)

    def call() -> str:
        assert saved[-1]["folds"]["0"]["events"][0]["status"] == "entered"
        return "actual result"

    assert observe_call(trace, "lightgbm", "fit", {"x": 1}, call, lambda x: {"state": x}) == (
        "actual result"
    )
    invocation.complete()
    assert saved[-1]["status"] == "completed"
    assert saved[-1]["folds"]["0"]["events"][0]["status"] == "completed"
    saved[-1]["folds"].clear()
    assert invocation.snapshot()["folds"]


def test_failed_entry_ack_prevents_call() -> None:
    entered = False

    def sink(data: bytes) -> None:
        if json.loads(data)["snapshot"]["folds"]:
            raise OSError("lost entry acknowledgement")

    invocation = FitInvocation(checkpoint=sink)
    invocation.start()
    invocation.bind({"request": "synthetic"})

    def call() -> int:
        nonlocal entered
        entered = True
        return 1

    with pytest.raises(OSError, match="lost entry"):
        observe_call(invocation.new_trace(0), "lightgbm", "fit", {}, call, lambda x: {"state": x})
    assert not entered
    assert invocation.snapshot()["folds"]["0"]["events"][0]["status"] == "entered"


def test_lost_completion_ack_preserves_completed_call() -> None:
    def sink(data: bytes) -> None:
        snapshot = json.loads(data)["snapshot"]
        if snapshot["folds"] and snapshot["folds"]["0"]["events"][0]["status"] == "completed":
            raise OSError("lost completion acknowledgement")

    invocation = FitInvocation(checkpoint=sink)
    invocation.start()
    invocation.bind({"request": "synthetic"})
    with pytest.raises(OSError, match="lost completion"):
        observe_call(
            invocation.new_trace(0), "lightgbm", "fit", {}, lambda: 1, lambda x: {"state": x}
        )
    assert invocation.snapshot()["folds"]["0"]["events"][0]["status"] == "completed"


def test_original_call_failure_survives_failed_checkpoint() -> None:
    original = ValueError("model failed")

    def sink(data: bytes) -> None:
        snapshot = json.loads(data)["snapshot"]
        if snapshot["folds"] and snapshot["folds"]["0"]["events"][0]["status"] == "failed":
            raise OSError("journal unavailable")

    invocation = FitInvocation(checkpoint=sink)
    invocation.start()
    invocation.bind({"request": "synthetic"})

    def call() -> int:
        raise original

    with pytest.raises(ValueError) as caught:
        observe_call(invocation.new_trace(0), "lightgbm", "fit", {}, call, lambda x: {"state": x})
    assert caught.value is original
    assert isinstance(caught.value.__cause__, OSError)
    assert invocation.snapshot()["folds"]["0"]["events"][0]["status"] == "failed"


def test_duplicate_fold_rejected() -> None:
    invocation = FitInvocation()
    invocation.start()
    invocation.new_trace(0)
    with pytest.raises(RuntimeError, match="reused"):
        invocation.new_trace(0)


def test_requested_sink_rejects_unbound_trace() -> None:
    invocation = FitInvocation(checkpoint=lambda _: None)
    invocation.start()
    with pytest.raises(RuntimeError, match="supported bound"):
        invocation.new_trace(0)


def test_failure_before_first_call_does_not_invent_an_observed_fold() -> None:
    saved = []
    invocation = FitInvocation(checkpoint=lambda data: saved.append(json.loads(data)))
    invocation.start()
    invocation.bind({"request": "synthetic"})
    invocation.new_trace(0)
    invocation.failed(ValueError("pre-call validation"))
    assert saved[-1]["snapshot"]["status"] == "failed"
    assert saved[-1]["snapshot"]["folds"] == {}
    assert invocation.snapshot()["folds"]["0"]["events"] == []


def test_requested_sink_rejects_v3_before_model_dependencies(
    tmp_path: Any, monkeypatch: Any
) -> None:
    from types import SimpleNamespace

    from alpha_qlib_worker import real
    from alpha_qlib_worker.fit_provenance import value_digest

    lock = tmp_path / "uv.lock"
    lock.write_text("synthetic")
    payload = {"schema_version": 3, "worker_lock_hash": "a" * 64, "panel": {"sha256": "b" * 64}}
    monkeypatch.setattr(real, "validate_request", lambda _: SimpleNamespace(payload=payload))
    monkeypatch.setattr(real, "source_fingerprint", lambda: "c" * 64)
    hashes = {"uv.lock": "a" * 64, "panel.parquet": "b" * 64, "request.json": value_digest(payload)}
    monkeypatch.setattr(real, "sha256_file", lambda path: hashes[path.name])
    monkeypatch.setattr(real, "require_real_dependencies", lambda: pytest.fail("model entry"))
    with pytest.raises(RuntimeError, match="supported bound"):
        real.run_real(
            tmp_path, worker_lock_path=lock, _observation=FitInvocation(checkpoint=lambda _: None)
        )


@pytest.mark.parametrize("component", ["features", "labels"])
def test_preprocessing_completion_ack_failure_preserves_original_error(component: str) -> None:
    import pandas as pd

    from alpha_qlib_worker import real
    from alpha_qlib_worker.fit_provenance import FitTrace

    original = OSError("lost completed preprocessing acknowledgement")

    def sink() -> None:
        if trace.seal(require_complete=False)["events"][-1]["status"] == "completed":
            raise original

    trace = FitTrace(checkpoint=sink)
    values = pd.Series([1.0, 2.0])
    with pytest.raises(OSError) as caught:
        if component == "features":
            real._normalize_features(values.to_frame(), [], recorder=trace)
        else:
            targets = pd.Series(pd.to_datetime(["2020-01-01", "2020-01-01"], utc=True))
            real._normalize_label(values, targets, recorder=trace)
    assert caught.value is original
    assert trace.seal()["events"][0]["status"] == "completed"
