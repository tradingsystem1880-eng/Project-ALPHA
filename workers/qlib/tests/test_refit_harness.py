"""Frozen fixture eligibility tests; zero native fits and no operational stores."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd
import polars as pl
import pytest

from alpha_qlib_worker.contract import (
    canonical_json_bytes,
    compute_config_hash,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.features import alpha158_features
from alpha_qlib_worker.fit_provenance import FitInvocation, FitTrace, row_digest, value_digest
from alpha_qlib_worker.real import (
    _normalize_features,
    _normalize_label,
    _sample_table,
    _select_split,
)

from . import refit_harness as harness
from .test_fit_provenance_native import _ridge_graph


def _pair(
    tmp_path: Path, *, world: str = "observed", recipe: str = "linear"
) -> tuple[Path, Path, Path, dict[str, Any]]:
    lock = Path(__file__).parents[1] / "uv.lock"
    parent = harness._fixture_exchange(
        tmp_path / "parent", world_id="observed", recipe=recipe, worker_lock_path=lock
    )
    child = harness._fixture_exchange(
        tmp_path / "child", world_id=world, recipe=recipe, worker_lock_path=lock
    )
    protocol = harness._fixture_protocol(
        parent, child, world_id=world, recipe=recipe, worker_lock_path=lock
    )
    path = tmp_path / "protocol.json"
    path.write_bytes(canonical_json_bytes(protocol))
    return parent, child, path, protocol


def _validate(parent: Path, child: Path, path: Path, world: str) -> dict[str, Any]:
    return harness._validate_fixture_pair(
        child,
        parent_exchange=parent,
        protocol_path=path,
        expected_protocol_sha256=sha256_file(path),
        world_id=world,
        worker_lock_path=Path(__file__).parents[1] / "uv.lock",
    )


@pytest.mark.parametrize("world", sorted(harness._WORLDS))
def test_all_frozen_worlds_validate_without_fitting(tmp_path: Path, world: str) -> None:
    parent, child, path, protocol = _pair(tmp_path, world=world)
    # Extra JSON tolerance only: this is not a valid ALPHA input-anchor claim.
    (child / "input_anchor.json").write_bytes(canonical_json_bytes({"fixture_only": True}))
    assert _validate(parent, child, path, world) == protocol
    assert not (child / "result.json").exists()
    assert not (child / "predictions.parquet").exists()
    request = json.loads((child / "request.json").read_bytes())
    assert request["seed"] == 7
    assert len(request["folds"]) == 2
    assert request["panel"]["rows"] == (15520 if world == "appended_future" else 15120)


def test_double_recipe_retains_its_distinct_native_fit_ceiling(tmp_path: Path) -> None:
    parent, child, path, protocol = _pair(tmp_path, recipe="double_ensemble")
    assert protocol["fixture"]["limits"]["max_native_fits"] == 4
    assert _validate(parent, child, path, "observed") == protocol


@pytest.mark.parametrize("change", ["seed", "folds", "panel"])
def test_self_consistent_arbitrary_inputs_are_ineligible(tmp_path: Path, change: str) -> None:
    parent, child, path, _ = _pair(tmp_path)
    request_path = child / "request.json"
    request = json.loads(request_path.read_bytes())
    if change == "seed":
        request["seed"] = 8
    elif change == "folds":
        request["folds"][0]["train_end"] = request["folds"][0]["train_start"]
    else:
        panel_path = child / "panel.parquet"
        panel = pl.read_parquet(panel_path).with_columns(
            [(pl.col(column) * 2).alias(column) for column in ("open", "high", "low", "close")]
        )
        panel.write_parquet(panel_path)
        request["panel"]["sha256"] = sha256_file(panel_path)
    request["config_hash"] = compute_config_hash(request)
    request_path.write_bytes(canonical_json_bytes(request))
    # Rebinding every declared input hash cannot establish fixture eligibility.
    protocol = harness._fixture_protocol(
        parent,
        child,
        world_id="observed",
        recipe="linear",
        worker_lock_path=Path(__file__).parents[1] / "uv.lock",
    )
    path.write_bytes(canonical_json_bytes(protocol))
    with pytest.raises(RuntimeError, match="not the declared frozen fixture"):
        _validate(parent, child, path, "observed")
    assert not (child / "result.json").exists()


@pytest.mark.parametrize("malformation", ["extra", "duplicate", "noncanonical", "overflow"])
def test_complete_protocol_bytes_are_validated(tmp_path: Path, malformation: str) -> None:
    parent, child, path, protocol = _pair(tmp_path)
    if malformation == "extra":
        protocol["fixture_only"] = True
        encoded = canonical_json_bytes(protocol)
    elif malformation == "duplicate":
        encoded = b'{"schema_version":1,' + canonical_json_bytes(protocol)[1:]
    elif malformation == "noncanonical":
        encoded = json.dumps(protocol, indent=2).encode()
    else:
        encoded = canonical_json_bytes(protocol).replace(b'"alpha":1.0', b'"alpha":1e999')
    path.write_bytes(encoded)
    with pytest.raises(RuntimeError, match="frozen construction"):
        _validate(parent, child, path, "observed")


def test_future_cutoff_is_mandatory_and_cannot_be_retuned(tmp_path: Path) -> None:
    parent, child, path, protocol = _pair(tmp_path, world="unavailable_future")
    for cutoff in (None, "2024-01-01T00:00:00+00:00"):
        changed = dict(protocol)
        if cutoff is None:
            changed.pop("cutoff")
        else:
            changed["cutoff"] = cutoff
        path.write_bytes(canonical_json_bytes(changed))
        with pytest.raises(RuntimeError, match="frozen construction"):
            _validate(parent, child, path, "unavailable_future")


def test_actual_current_source_and_protocol_hash_are_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child, path, _ = _pair(tmp_path)
    with pytest.raises(RuntimeError, match="frozen hash"):
        harness._validate_fixture_pair(
            child,
            parent_exchange=parent,
            protocol_path=path,
            expected_protocol_sha256=hashlib.sha256(b"stale").hexdigest(),
            world_id="observed",
            worker_lock_path=Path(__file__).parents[1] / "uv.lock",
        )
    monkeypatch.setattr(harness, "source_fingerprint", lambda: "b" * 64)
    with pytest.raises(RuntimeError, match="frozen construction"):
        _validate(parent, child, path, "observed")


def test_future_panel_constructions_preserve_the_declared_prefix(tmp_path: Path) -> None:
    lock = Path(__file__).parents[1] / "uv.lock"
    panels = {
        world: pl.read_parquet(
            harness._fixture_exchange(
                tmp_path / world, world_id=world, recipe="linear", worker_lock_path=lock
            )
            / "panel.parquet"
        )
        for world in ("observed", "renamed", "unavailable_future", "appended_future", "cost_stress")
    }
    original = panels["observed"]
    assert panels["renamed"].equals(original)
    assert panels["cost_stress"].equals(original)
    prefix = pl.col("available_at") <= harness._CUTOFF
    assert panels["unavailable_future"].filter(prefix).equals(original.filter(prefix))
    assert not panels["unavailable_future"].equals(original)
    assert panels["appended_future"].head(original.height).equals(original)


@pytest.mark.parametrize("world", [[], {}, None, "unapproved"])
def test_malformed_world_fails_before_generation(tmp_path: Path, world: Any) -> None:
    with pytest.raises(RuntimeError, match="unsupported fixture world"):
        harness._fixture_exchange(
            tmp_path / "unused",
            world_id=world,
            recipe="linear",
            worker_lock_path=Path(__file__).parents[1] / "uv.lock",
        )
    assert not (tmp_path / "unused").exists()


def test_leaky_twin_rejected_on_actual_w11_training_rows(tmp_path: Path) -> None:
    """Implementation control only: no model fitting and no main-programme attempt."""
    parent, _, _, _ = _pair(tmp_path)
    request = validate_request(parent)
    samples = _sample_table(request, alpha158_features(request.panel))
    fold = request.folds[0]
    split = {
        role: _select_split(
            samples,
            start=fold[f"{name}_start"],
            end=fold[f"{name}_end"],
            require_label=role != "test",
        )
        for role, name in (("train", "train"), ("validation", "validation"), ("test", "test"))
    }
    scopes = {
        role: {
            "row_count": len(features),
            "row_ids_sha256": row_digest(features),
            "feature_values_sha256": value_digest(features),
            "label_values_sha256": None if role == "test" else value_digest(labels),
            "target_sessions_sha256": value_digest(pd.Index(metadata["target_ts"])),
        }
        for role, (features, labels, metadata) in split.items()
    }
    for leaky in (False, True):
        trace = FitTrace()
        fitting = split["train"][0]
        if leaky:
            fitting = pd.concat([split[role][0] for role in ("train", "validation", "test")])
        _normalize_features(fitting, [split["validation"][0], split["test"][0]], recorder=trace)
        for role in ("train", "validation"):
            _, labels, metadata = split[role]
            _normalize_label(
                labels, metadata["target_ts"], recorder=trace, component=f"label.{role}"
            )
        evidence = {"scopes": scopes, "events": trace.seal()["events"]}
        if leaky:
            with pytest.raises(RuntimeError, match="fitted input differs from its declared scope"):
                harness._assert_fit_scope_binding(evidence)
        else:
            harness._assert_fit_scope_binding(evidence)


def test_wrong_label_grouping_is_rejected_even_with_identical_rows_and_labels() -> None:
    features = pd.DataFrame({"a": [1.0, 2.0]}, index=[0, 1])
    labels = pd.Series([1.0, 2.0], index=features.index, name="label")
    targets = pd.Series(pd.date_range("2023-01-02", periods=2, tz="UTC"), index=features.index)
    scope = {
        "row_count": len(features),
        "row_ids_sha256": row_digest(features),
        "feature_values_sha256": value_digest(features),
        "label_values_sha256": value_digest(labels),
        "target_sessions_sha256": value_digest(pd.Index(targets)),
    }
    for wrong_grouping in (False, True):
        trace = FitTrace()
        _normalize_features(features, [features, features], recorder=trace)
        _normalize_label(labels, targets, recorder=trace, component="label.train")
        validation_targets = targets.copy()
        if wrong_grouping:
            validation_targets.iloc[1] = validation_targets.iloc[0]
        _normalize_label(labels, validation_targets, recorder=trace, component="label.validation")
        fold = {
            "events": trace.seal()["events"],
            "scopes": {"train": scope, "validation": scope, "test": {"label_values_sha256": None}},
        }
        if wrong_grouping:
            with pytest.raises(RuntimeError, match="label grouping differs"):
                harness._assert_fit_scope_binding(fold)
        else:
            harness._assert_fit_scope_binding(fold)


def _oracle_inputs() -> tuple[dict[str, Any], pl.DataFrame]:
    fold = {
        "fold": 0,
        "model_hash": "model",
        "scopes": {
            "train": {"feature_values_sha256": "train", "label_values_sha256": "labels"},
            "validation": {"feature_values_sha256": "valid"},
            "test": {"feature_values_sha256": "heldout"},
        },
        "exclusions": {"horizon_sessions": 1},
        "events": [
            {
                "component": "normalizer",
                "state_sha256": "normalizer-state",
                "input_hashes": {"train": "train"},
                "output_hashes": {"state": "normalizer-state", "other_1_features": "heldout"},
            },
            {
                "component": "model",
                "state_sha256": "model-state",
                "input_hashes": {"context": "context"},
                "output_hashes": {"state": "model-state"},
            },
        ],
    }
    second = copy.deepcopy(fold)
    second["fold"] = 1
    provenance = {"folds": [fold, second]}
    sessions = [harness._CUTOFF - pd.Timedelta(days=1), harness._CUTOFF + pd.Timedelta(days=1)]
    frame = pl.DataFrame(
        {
            "symbol": ["S00", "S00"],
            "origin_ts": sessions,
            "available_at": sessions,
            "target_ts": sessions,
            "fold": [0, 1],
            "split": ["test", "test"],
            "score": [1.0, 2.0],
        }
    )
    return provenance, frame


def test_prefix_oracle_excludes_only_heldout_projection() -> None:
    original, forecasts = _oracle_inputs()
    changed = copy.deepcopy(original)
    changed["folds"][0]["scopes"]["test"]["feature_values_sha256"] = "future"
    changed["folds"][0]["events"][0]["output_hashes"]["other_1_features"] = "future"
    changed["folds"][1]["events"][1]["state_sha256"] = "later-fold"
    future = forecasts.with_columns(
        pl.when(pl.col("fold") == 1).then(999.0).otherwise(pl.col("score")).alias("score")
    )
    report = harness._compare_fixture_evidence(
        original, forecasts, changed, future, world_id="unavailable_future"
    )
    assert report["status"] == "PASS"
    assert report["forecast_rows_compared"] == 1
    changed["folds"][0]["events"][1]["input_hashes"]["context"] = "changed-context"
    assert (
        harness._compare_fixture_evidence(
            original, forecasts, changed, future, world_id="unavailable_future"
        )["status"]
        == "FAIL"
    )


def test_append_checks_both_folds_and_past_control_can_be_inconclusive() -> None:
    original, forecasts = _oracle_inputs()
    changed = copy.deepcopy(original)
    changed["folds"][1]["events"][1]["state_sha256"] = "changed-state"
    assert (
        harness._compare_fixture_evidence(
            original, forecasts, changed, forecasts, world_id="appended_future"
        )["status"]
        == "FAIL"
    )
    assert (
        harness._compare_fixture_evidence(
            original, forecasts, original, forecasts, world_id="past_change"
        )["status"]
        == "INCONCLUSIVE"
    )
    changed["folds"][0]["scopes"]["train"]["feature_values_sha256"] = "past-input"
    changed["folds"][0]["events"][0]["state_sha256"] = "past-state"
    assert (
        harness._compare_fixture_evidence(
            original,
            forecasts,
            changed,
            forecasts.with_columns(pl.col("score") + 1),
            world_id="past_change",
        )["status"]
        == "PASS"
    )


def test_private_runner_rejects_ineligible_inputs_before_calling_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child, path, _ = _pair(tmp_path)
    path.write_bytes(b"{}\n")

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("worker must not be called")

    monkeypatch.setattr(harness, "run_real", forbidden)
    observation = FitInvocation()
    with pytest.raises(RuntimeError, match="frozen hash"):
        harness._refit_fixture_world(
            child,
            parent_exchange=parent,
            protocol_path=path,
            expected_protocol_sha256="a" * 64,
            world_id="observed",
            worker_lock_path=Path(__file__).parents[1] / "uv.lock",
            _observation=observation,
        )
    assert observation.status == "pending"
    assert not observation.folds


def test_private_runner_propagates_cancellation_and_keeps_partial_observation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child, path, _ = _pair(tmp_path)

    def cancel(*args: Any, _observation: FitInvocation, **kwargs: Any) -> Any:
        _observation.start()
        _observation.folds[0] = FitTrace()
        _observation.folds[0].begin("normalizer", "fit", {"train": None})
        interruption = KeyboardInterrupt()
        _observation.failed(interruption)
        raise interruption

    monkeypatch.setattr(harness, "run_real", cancel)
    observation = FitInvocation()
    with pytest.raises(KeyboardInterrupt) as raised:
        harness._refit_fixture_world(
            child,
            parent_exchange=parent,
            protocol_path=path,
            expected_protocol_sha256=sha256_file(path),
            world_id="observed",
            worker_lock_path=Path(__file__).parents[1] / "uv.lock",
            _observation=observation,
        )
    assert observation.status == "failed"
    assert observation.error_type == "KeyboardInterrupt"
    assert observation.folds[0].seal(require_complete=False)["events"][0]["status"] == "entered"
    assert any("process_peak_rss_bytes" in note for note in raised.value.__notes__)
    assert not (child / "result.json").exists()


def test_private_runner_records_separate_operations_with_a_fake_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent, child, path, _ = _pair(tmp_path)
    result = {"fake_only": True}

    def fake(*args: Any, _observation: FitInvocation, **kwargs: Any) -> dict[str, Any]:
        _observation.start()
        for fold in (0, 1):
            trace = FitTrace()
            # Explicit fake implementation test; no native fit and no success artifact.
            for component, operation in (
                ("normalizer", "fit"),
                ("label.train", "transform"),
                ("label.validation", "transform"),
                ("model", "fit"),
            ):
                token = trace.begin(component, operation, {"fake_only": True})
                trace.complete(token, {"state": [fold]})
            _observation.folds[fold] = trace
        _observation.complete()
        return result

    observation = FitInvocation()
    monkeypatch.setattr(harness, "run_real", fake)

    def evidence(*args: Any, **kwargs: Any) -> tuple[Any, Any, Any]:
        return (
            result,
            {
                "folds": [
                    {"fold": fold, **trace.seal()} for fold, trace in observation.folds.items()
                ]
            },
            pl.DataFrame(),
        )

    monkeypatch.setattr(harness, "_fixture_evidence", evidence)
    report = harness._refit_fixture_world(
        child,
        parent_exchange=parent,
        protocol_path=path,
        expected_protocol_sha256=sha256_file(path),
        world_id="observed",
        worker_lock_path=Path(__file__).parents[1] / "uv.lock",
        _observation=observation,
    )
    assert report["component_operations"] == {
        "normalizer_fits": 2,
        "estimator_fits": 2,
        "member_fits": 0,
        "selections": 0,
        "reweightings": 0,
        "label_transforms": 4,
        "outer_assemblies": 0,
    }
    assert report["measurements"]["hard_os_memory_limit"] is False
    assert report["independent_observation_count"] == 0
    assert report["counterfactual_refit"] is False
    assert report["promotion_eligible"] is False
    with pytest.raises(RuntimeError, match="cannot be reused"):
        harness._refit_fixture_world(
            child,
            parent_exchange=parent,
            protocol_path=path,
            expected_protocol_sha256=sha256_file(path),
            world_id="observed",
            worker_lock_path=Path(__file__).parents[1] / "uv.lock",
            _observation=observation,
        )


@pytest.mark.parametrize("resource", ["elapsed_seconds", "process_peak_rss_bytes"])
def test_resource_violations_before_fit_keep_worker_unentered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, resource: str
) -> None:
    parent, child, path, _ = _pair(tmp_path)
    measured = {"elapsed_seconds": 0.0, "process_peak_rss_bytes": 1}
    measured[resource] = 301 if resource == "elapsed_seconds" else 1610612737
    monkeypatch.setattr(harness, "_measurements", lambda started: measured)

    def forbidden(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("worker must not be called after a measured limit violation")

    monkeypatch.setattr(harness, "run_real", forbidden)
    observation = FitInvocation()
    with pytest.raises(RuntimeError, match="ceiling"):
        harness._refit_fixture_world(
            child,
            parent_exchange=parent,
            protocol_path=path,
            expected_protocol_sha256=sha256_file(path),
            world_id="observed",
            worker_lock_path=Path(__file__).parents[1] / "uv.lock",
            _observation=observation,
        )
    assert observation.status == "pending"
    assert not observation.folds


def test_stored_evidence_rejects_a_rehashed_but_unlinked_trace(tmp_path: Path) -> None:
    parent, _, _, protocol = _pair(tmp_path)
    request = json.loads((parent / "request.json").read_bytes())
    graph = _ridge_graph()  # Existing fake fitter; never a native model invocation.
    events = {event["component"]: event for event in graph["events"]}

    def scope(role: str) -> dict[str, Any]:
        label = events[f"label.{role}"]
        return {
            "row_count": label["input_row_counts"]["labels"],
            "row_ids_sha256": label["input_row_ids_sha256"]["labels"],
            "label_values_sha256": label["input_hashes"]["labels"],
            "feature_values_sha256": events["normalizer"]["input_hashes"]["train"],
        }

    folds = [
        {
            "fold": fold,
            "model_hash": "a" * 64,
            **copy.deepcopy(graph),
            "graph_status": "complete_reference_call_graph",
            "scopes": {
                "train": scope("train"),
                "validation": scope("validation"),
                "test": {"label_values_sha256": None},
            },
        }
        for fold in (0, 1)
    ]
    # Preserve every outer hash while breaking the native input link.
    folds[0]["events"][3]["input_hashes"]["train_features"] = "b" * 64
    folds[0]["trace_sha256"] = value_digest(folds[0]["events"])
    provenance = {
        "schema_version": 1,
        "authority": "engineering_provenance_only",
        "request_sha256": sha256_file(parent / "request.json"),
        "panel_sha256": request["panel"]["sha256"],
        "worker_source_sha256": protocol["worker_source_sha256"],
        "worker_lock_sha256": protocol["worker_lock_sha256"],
        "seed": 7,
        "model": protocol["model"],
        "folds": folds,
    }
    provenance["provenance_sha256"] = value_digest(provenance)
    result = {
        "schema_version": 3,
        "status": "succeeded",
        "diagnostic_only": True,
        "counterfactual_refit": False,
        "request_sha256": sha256_file(parent / "request.json"),
        "config_hash": request["config_hash"],
        "snapshot_hash": request["snapshot_hash"],
        "worker_lock_hash": request["worker_lock_hash"],
        "seed": 7,
        "diagnostics": {"fit_provenance": provenance},
    }
    (parent / "result.json").write_bytes(canonical_json_bytes(result))
    with pytest.raises(RuntimeError, match="input is unlinked"):
        harness._fixture_evidence(parent, protocol, request_field="original_request_sha256")
    assert not (parent / "predictions.parquet").exists()
