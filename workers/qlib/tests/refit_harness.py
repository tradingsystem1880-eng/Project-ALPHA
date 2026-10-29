"""Private frozen synthetic W11 fixtures; no CLI, scheduler, ledger or admission."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl

from alpha_qlib_worker.contract import (
    PANEL_COLUMNS,
    PREDICTION_COLUMNS,
    canonical_json_bytes,
    compute_config_hash,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.fit_provenance import FitInvocation, validate_reference_graph
from alpha_qlib_worker.real import run_real, source_fingerprint

from .test_fake_worker import _exchange

_WORKER = Path(__file__).resolve().parents[1]
_START = datetime(2023, 1, 2, tzinfo=UTC)
_CUTOFF = _START + timedelta(days=560, hours=23)
_WORLDS = frozenset(
    {
        "observed",
        "renamed",
        "unavailable_future",
        "appended_future",
        "past_change",
        "common_exposure",
        "cost_stress",
    }
)
_LIMITS = {
    "max_pipeline_fits": 2,
    "max_native_fits": 2,
    "max_panel_rows": 16000,
    "max_features": 158,
    "max_folds": 2,
    "max_members": 2,
    "max_rounds": 3,
    "cpu_threads": 1,
    "max_seconds": 300,
    "max_rss_bytes": 1610612736,
    "automatic_retries": 0,
}


def _digest(encoded: bytes) -> str:
    return hashlib.sha256(encoded).hexdigest()


def _regular_bytes(path: Path, *, limit: int = 16 * 1024 * 1024) -> bytes:
    """Read a bounded regular file and reject mutation during this read."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
                raise RuntimeError("fixture input requires a bounded regular file")
            encoded = handle.read(limit + 1)
            after = os.fstat(handle.fileno())
            current = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise RuntimeError(f"fixture input unavailable: {path}") from exc
    signatures = {
        (
            item.st_dev,
            item.st_ino,
            item.st_mode,
            item.st_size,
            item.st_mtime_ns,
            item.st_ctime_ns,
        )
        for item in (before, after, current)
    }
    if len(signatures) != 1 or len(encoded) != before.st_size or len(encoded) > limit:
        raise RuntimeError("fixture input changed during its read")
    return encoded


def _lock_hash(worker_lock_path: Path) -> str:
    supplied = _digest(_regular_bytes(Path(worker_lock_path)))
    if supplied != _digest(_regular_bytes(_WORKER / "uv.lock")):
        raise RuntimeError("fixture requires the current pinned worker lock")
    return supplied


def _model(recipe: str) -> dict[str, Any]:
    if recipe == "linear":
        return {"name": "linear", "parameters": {"estimator": "ridge", "alpha": 1.0}}
    if recipe == "double_ensemble":
        return {
            "name": "double_ensemble",
            "parameters": {
                "num_models": 2,
                "num_boost_round": 3,
                "early_stopping_rounds": 2,
                "min_data_in_leaf": 5,
                "num_threads": 1,
            },
        }
    raise RuntimeError("fixture supports only frozen ridge and DoubleEnsemble")


def _fixture_source_fingerprint() -> str:
    files = {
        name: _digest(_regular_bytes(Path(__file__).parent / name))
        for name in ("refit_harness.py", "test_fake_worker.py")
    }
    return _digest(canonical_json_bytes(files))


def _fixture_exchange(path: Path, *, world_id: str, recipe: str, worker_lock_path: Path) -> Path:
    """Generate one raw fixture exchange in a new directory, without fitting."""
    if not isinstance(world_id, str) or world_id not in _WORLDS:
        raise RuntimeError("unsupported fixture world")
    model = _model(recipe)
    lock_hash = _lock_hash(worker_lock_path)
    exchange = _exchange(Path(path))
    panel_path = exchange / "panel.parquet"
    rows = pl.read_parquet(panel_path).to_dicts()
    if len(rows) != 20 * 756:
        raise RuntimeError("reused fixture no longer has the frozen base geometry")
    if world_id == "appended_future":
        for index in range(756, 776):
            session = _START + timedelta(days=index)
            for symbol_index in range(20):
                price = 100.0 + index * 0.01 + symbol_index * 0.1
                rows.append(
                    {
                        "symbol": f"S{symbol_index:02d}",
                        "session_ts": session,
                        "available_at": session + timedelta(hours=23),
                        "open": price,
                        "high": price + 1,
                        "low": price - 1,
                        "close": price + 0.25,
                        "volume": 1_000_000.0,
                    }
                )
    for row in rows:
        index = (row["session_ts"] - _START).days
        symbol_index = int(row["symbol"][1:])
        factor = 1.0
        if world_id == "unavailable_future" and index > 560:
            factor = 1 + 0.2 * (1 + symbol_index % 3)
        elif world_id == "past_change" and 300 <= index <= 390:
            factor = 1 + 0.25 * (symbol_index % 2)
        if world_id == "common_exposure":
            price = (100 + symbol_index * 0.1) * 1.0001**index
            row.update(open=price, high=price + 1, low=price - 1, close=price + 0.25)
        elif factor != 1:
            for column in ("open", "high", "low", "close"):
                row[column] *= factor
    pl.DataFrame(rows).select(PANEL_COLUMNS).write_parquet(panel_path)
    request_path = exchange / "request.json"
    request = json.loads(request_path.read_bytes())
    request.update(schema_version=3, model=model, worker_lock_hash=lock_hash)
    request["folds"] = [
        {
            "fold": fold,
            **{
                key: (_START + timedelta(days=index)).isoformat()
                for key, index in zip(
                    (
                        "train_start",
                        "train_end",
                        "validation_start",
                        "validation_end",
                        "test_start",
                        "test_end",
                    ),
                    bounds,
                    strict=True,
                )
            },
        }
        for fold, bounds in enumerate(((0, 400, 406, 500, 506, 620), (0, 503, 509, 628, 634, 754)))
    ]
    request["panel"] = {
        "path": "panel.parquet",
        "sha256": sha256_file(panel_path),
        "rows": len(rows),
    }
    if world_id == "cost_stress":
        request["costs"] = {"fee_bps": 100.0, "slippage_bps": 100.0}
    request["config_hash"] = compute_config_hash(request)
    request_path.write_bytes(canonical_json_bytes(request))
    validate_request(exchange)
    return exchange


def _fixture_protocol(
    parent_exchange: Path,
    world_exchange: Path,
    *,
    world_id: str,
    recipe: str,
    worker_lock_path: Path,
) -> dict[str, Any]:
    """Construct a frozen pair descriptor; callers publish it before any fit."""
    if not isinstance(world_id, str) or world_id not in _WORLDS:
        raise RuntimeError("unsupported fixture world")
    dimensions = (
        []
        if world_id in {"observed", "renamed"}
        else ["costs"]
        if world_id == "cost_stress"
        else ["panel"]
    )
    protocol: dict[str, Any] = {
        "schema_version": 1,
        "authority": "engineering_provenance_only",
        "original_request_sha256": _digest(
            _regular_bytes(parent_exchange / "request.json", limit=64 * 1024)
        ),
        "changed_request_sha256": _digest(
            _regular_bytes(world_exchange / "request.json", limit=64 * 1024)
        ),
        "worker_source_sha256": source_fingerprint(),
        "worker_lock_sha256": _lock_hash(worker_lock_path),
        "model": _model(recipe),
        "expected_relation": "changed_world" if dimensions else "same_evidence",
        "changed_dimensions": dimensions,
        "fixture": {
            "generator": "qlib_w11_fixture",
            "version": 2,
            "world": world_id,
            "source_sha256": _fixture_source_fingerprint(),
            "limits": {
                **_LIMITS,
                "max_native_fits": 4 if recipe == "double_ensemble" else 2,
            },
        },
    }
    if world_id == "unavailable_future":
        protocol["cutoff"] = _CUTOFF.isoformat()
    return protocol


def _validate_fixture_pair(
    world_exchange: Path,
    *,
    parent_exchange: Path,
    protocol_path: Path,
    expected_protocol_sha256: str,
    world_id: str,
    worker_lock_path: Path,
) -> dict[str, Any]:
    """Reject arbitrary exchanges before fitting, even when internally hash-consistent."""
    if not isinstance(world_id, str) or world_id not in _WORLDS:
        raise RuntimeError("unsupported fixture world")
    if (
        not isinstance(expected_protocol_sha256, str)
        or len(expected_protocol_sha256) != 64
        or any(char not in "0123456789abcdef" for char in expected_protocol_sha256)
    ):
        raise RuntimeError("fixture requires a frozen lowercase protocol SHA-256")
    encoded = _regular_bytes(protocol_path, limit=64 * 1024)
    if _digest(encoded) != expected_protocol_sha256:
        raise RuntimeError("fixture protocol differs from its frozen hash")
    try:
        payload = json.loads(encoded)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise RuntimeError("fixture protocol is invalid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("model"), dict):
        raise RuntimeError("fixture protocol requires the frozen model")
    recipe = payload["model"].get("name")
    expected = _fixture_protocol(
        parent_exchange,
        world_exchange,
        world_id=world_id,
        recipe=recipe,
        worker_lock_path=worker_lock_path,
    )
    if encoded != canonical_json_bytes(expected):
        raise RuntimeError("fixture protocol differs from the frozen construction")
    actual = {
        (role, name): _regular_bytes(exchange / name)
        for role, exchange in (("parent", parent_exchange), ("world", world_exchange))
        for name in ("request.json", "panel.parquet")
    }
    with tempfile.TemporaryDirectory(prefix="alpha-w11-eligibility-") as temporary:
        for role, world in (("parent", "observed"), ("world", world_id)):
            regenerated = _fixture_exchange(
                Path(temporary) / role,
                world_id=world,
                recipe=recipe,
                worker_lock_path=worker_lock_path,
            )
            for name in ("request.json", "panel.parquet"):
                if actual[role, name] != _regular_bytes(regenerated / name):
                    raise RuntimeError(f"{role} {name} is not the declared frozen fixture")
    for exchange in (parent_exchange, world_exchange):
        validate_request(exchange)
    current = _fixture_protocol(
        parent_exchange,
        world_exchange,
        world_id=world_id,
        recipe=recipe,
        worker_lock_path=worker_lock_path,
    )
    if canonical_json_bytes(current) != encoded:
        raise RuntimeError("fixture identities changed during validation")
    for role, exchange in (("parent", parent_exchange), ("world", world_exchange)):
        for name in ("request.json", "panel.parquet"):
            if actual[role, name] != _regular_bytes(exchange / name):
                raise RuntimeError("fixture inputs changed during validation")
    if _regular_bytes(protocol_path, limit=64 * 1024) != encoded:
        raise RuntimeError("fixture protocol changed during validation")
    return expected


def _assert_fit_scope_binding(fold: dict[str, Any]) -> None:
    """Verify portable observations against declared raw scopes, without fitting."""
    events = {event["component"]: event for event in fold["events"]}
    for component, input_name, role, value_name in (
        ("normalizer", "train", "train", "feature_values_sha256"),
        ("label.train", "labels", "train", "label_values_sha256"),
        ("label.validation", "labels", "validation", "label_values_sha256"),
    ):
        event, scope = events[component], fold["scopes"][role]
        if (
            event["input_hashes"].get(input_name) != scope[value_name]
            or event["input_row_ids_sha256"].get(input_name) != scope["row_ids_sha256"]
            or event["input_row_counts"].get(input_name) != scope["row_count"]
        ):
            raise RuntimeError("fitted input differs from its declared scope")
        if component.startswith("label.") and (
            event["input_hashes"].get("target_sessions") != scope["target_sessions_sha256"]
        ):
            raise RuntimeError("label grouping differs from its declared target sessions")
    if fold["scopes"]["test"]["label_values_sha256"] is not None:
        raise RuntimeError("fitted provenance must not consume a test-label digest")


def _fixture_evidence(
    exchange: Path, protocol: dict[str, Any], *, request_field: str
) -> tuple[dict[str, Any], dict[str, Any], pl.DataFrame]:
    """Reverify portable output bytes; hashes alone never establish fresh execution."""
    request = validate_request(exchange).payload
    result_bytes = _regular_bytes(exchange / "result.json")
    result = json.loads(result_bytes)
    request_hash = _digest(_regular_bytes(exchange / "request.json", limit=64 * 1024))
    if (
        result_bytes != canonical_json_bytes(result)
        or result["status"] != "succeeded"
        or result["schema_version"] != 3
        or result["diagnostic_only"] is not True
        or result["counterfactual_refit"] is not False
        or result.get("promotion_eligible", False) is not False
        or result["request_sha256"] != request_hash
        or request_hash != protocol[request_field]
        or result["config_hash"] != request["config_hash"]
        or result["worker_lock_hash"] != protocol["worker_lock_sha256"]
        or result["seed"] != request["seed"]
        or result["snapshot_hash"] != request["snapshot_hash"]
    ):
        raise RuntimeError("fixture result has invalid identity or authority flags")
    provenance = result["diagnostics"]["fit_provenance"]
    expected_identity = {
        "schema_version": 1,
        "authority": "engineering_provenance_only",
        "request_sha256": request_hash,
        "panel_sha256": request["panel"]["sha256"],
        "worker_source_sha256": protocol["worker_source_sha256"],
        "worker_lock_sha256": protocol["worker_lock_sha256"],
        "seed": request["seed"],
        "model": protocol["model"],
    }
    unhashed = {key: value for key, value in provenance.items() if key != "provenance_sha256"}
    if (
        any(provenance[key] != value for key, value in expected_identity.items())
        or provenance["provenance_sha256"] != _digest(canonical_json_bytes(unhashed))
        or [fold["fold"] for fold in provenance["folds"]] != [0, 1]
    ):
        raise RuntimeError("fixture fitted provenance has invalid identity")
    for fold in provenance["folds"]:
        graph = validate_reference_graph(
            fold, name=protocol["model"]["name"], parameters=protocol["model"]["parameters"]
        )
        if graph != "complete_reference_call_graph" or fold["graph_status"] != graph:
            raise RuntimeError("fixture reference call graph is incomplete")
        _assert_fit_scope_binding(fold)
    prediction_bytes = _regular_bytes(exchange / "predictions.parquet")
    predictions = pl.read_parquet(io.BytesIO(prediction_bytes))
    metadata = result["predictions"]
    if (
        metadata["path"] != "predictions.parquet"
        or metadata["sha256"] != _digest(prediction_bytes)
        or metadata["rows"] != predictions.height
        or predictions.is_empty()
        or predictions.columns != PREDICTION_COLUMNS
        or not predictions["score"].is_finite().all()
        or predictions.select(_FORECAST_KEYS).is_duplicated().any()
    ):
        raise RuntimeError("fixture predictions are invalid or differ from their result")
    for fold in provenance["folds"]:
        rows = predictions.filter(pl.col("fold") == fold["fold"])
        if rows.is_empty() or rows["model_hash"].unique().to_list() != [fold["model_hash"]]:
            raise RuntimeError("fixture forecasts are unlinked from their fitted fold")
    if (
        _regular_bytes(exchange / "result.json") != result_bytes
        or _regular_bytes(exchange / "predictions.parquet") != prediction_bytes
    ):
        raise RuntimeError("fixture outputs changed during verification")
    return result, provenance, predictions


_FORECAST_KEYS = ["fold", "split", "target_ts", "symbol", "origin_ts", "available_at"]


def _fitted_projection(fold: dict[str, Any]) -> dict[str, Any]:
    events = copy.deepcopy(fold["events"])
    for event in events:
        if event["component"] == "normalizer":
            event["output_hashes"].pop("other_1_features", None)
    # Omitted test scope/output and whole-trace identity stay bound by outer provenance.
    return {
        "fold": fold["fold"],
        "model_hash": fold["model_hash"],
        "scopes": {role: fold["scopes"][role] for role in ("train", "validation")},
        "exclusions": fold["exclusions"],
        "events": events,
    }


def _compare_fixture_evidence(
    original: dict[str, Any],
    original_forecasts: pl.DataFrame,
    changed: dict[str, Any],
    changed_forecasts: pl.DataFrame,
    *,
    world_id: str,
) -> dict[str, Any]:
    """Mechanical controls only; economic controls remain in canonical ALPHA replay."""
    if not isinstance(world_id, str) or world_id not in _WORLDS:
        raise RuntimeError("unsupported fixture world")
    earlier = world_id in {"unavailable_future", "past_change"}
    selected = [0] if earlier else [0, 1]
    left = [_fitted_projection(original["folds"][index]) for index in selected]
    right = [_fitted_projection(changed["folds"][index]) for index in selected]
    frames = []
    for forecasts in (original_forecasts, changed_forecasts):
        if earlier:
            forecasts = forecasts.filter(pl.col("available_at") <= _CUTOFF)
        frame = forecasts.select([*_FORECAST_KEYS, "score"]).sort(_FORECAST_KEYS)
        if frame.is_empty():
            raise RuntimeError("fixture forecast comparison is empty")
        frames.append(frame)
    keys_equal = frames[0].select(_FORECAST_KEYS).equals(frames[1].select(_FORECAST_KEYS))
    scores_equal = keys_equal and frames[0].equals(frames[1])
    state_equal = left == right
    report: dict[str, Any] = {
        "world": world_id,
        "status": "PASS" if state_equal and scores_equal else "FAIL",
        "permitted_fold_ids": selected,
        "cutoff": _CUTOFF.isoformat() if earlier else None,
        "forecast_rows_compared": frames[0].height,
        "forecast_keys_equal": keys_equal,
        "forecast_scores_equal": scores_equal,
        "permitted_fitted_state_equal": state_equal,
        "canonical_replay_required": world_id in {"common_exposure", "cost_stress"},
        "diagnostic_only": True,
        "counterfactual_refit": False,
        "promotion_eligible": False,
        "independent_observation_count": 0,
    }
    if world_id == "past_change":
        inputs_changed = (
            original["folds"][0]["scopes"]["train"] != changed["folds"][0]["scopes"]["train"]
        )

        def learned(evidence: dict[str, Any]) -> dict[str, Any]:
            return {
                event["component"]: event["state_sha256"]
                for event in evidence["folds"][0]["events"]
                if event["component"] in {"normalizer", "model"}
                or event["component"].startswith("member.")
            }

        states_changed = learned(original) != learned(changed)
        report.update(
            fit_inputs_changed=inputs_changed,
            learned_state_changed=states_changed,
            status="PASS"
            if inputs_changed and states_changed and keys_equal and not scores_equal
            else "INCONCLUSIVE",
        )
    elif world_id == "common_exposure":
        report.update(status="INCONCLUSIVE", reason="canonical_replay_required")
    return report


def _fixture_world_oracle(
    observed_exchange: Path,
    world_exchange: Path,
    *,
    protocol_path: Path,
    expected_protocol_sha256: str,
    world_id: str,
    worker_lock_path: Path,
) -> dict[str, Any]:
    protocol = _validate_fixture_pair(
        world_exchange,
        parent_exchange=observed_exchange,
        protocol_path=protocol_path,
        expected_protocol_sha256=expected_protocol_sha256,
        world_id=world_id,
        worker_lock_path=worker_lock_path,
    )
    _, original, forecasts = _fixture_evidence(
        observed_exchange, protocol, request_field="original_request_sha256"
    )
    _, changed, changed_forecasts = _fixture_evidence(
        world_exchange, protocol, request_field="changed_request_sha256"
    )
    report = _compare_fixture_evidence(
        original, forecasts, changed, changed_forecasts, world_id=world_id
    )
    report.update(
        protocol_sha256=expected_protocol_sha256,
        original_provenance_sha256=original["provenance_sha256"],
        changed_provenance_sha256=changed["provenance_sha256"],
    )
    return report


def _component_operations(folds: list[dict[str, Any]], recipe: str) -> dict[str, int]:
    counts = dict.fromkeys(
        [
            "normalizer_fits",
            "estimator_fits",
            "member_fits",
            "selections",
            "reweightings",
            "label_transforms",
            "outer_assemblies",
        ],
        0,
    )
    for fold in folds:
        for event in fold["events"]:
            component = event["component"]
            if event["status"] != "completed":
                raise RuntimeError("fixture component observation is incomplete")
            if component == "normalizer":
                counts["normalizer_fits"] += 1
            elif component == "model":
                counts["estimator_fits" if recipe == "linear" else "outer_assemblies"] += 1
            elif component.startswith("member."):
                counts["member_fits"] += 1
            elif component.startswith("selection."):
                counts["selections"] += 1
            elif component.startswith("reweight."):
                counts["reweightings"] += 1
            elif component.startswith("label."):
                counts["label_transforms"] += 1
            else:
                raise RuntimeError("fixture observed an unexpected component")
    expected = {
        "normalizer_fits": 2,
        "estimator_fits": 2 if recipe == "linear" else 0,
        "member_fits": 4 if recipe == "double_ensemble" else 0,
        "selections": 2 if recipe == "double_ensemble" else 0,
        "reweightings": 2 if recipe == "double_ensemble" else 0,
        "label_transforms": 4,
        "outer_assemblies": 2 if recipe == "double_ensemble" else 0,
    }
    if counts != expected:
        raise RuntimeError("fixture component operations differ from the frozen programme")
    return counts


def _measurements(started: float) -> dict[str, Any]:
    if sys.platform not in {"darwin", "linux"}:
        raise RuntimeError("fixture RSS measurement is unqualified on this platform")
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {
        "elapsed_seconds": time.monotonic() - started,
        "process_peak_rss_bytes": int(peak if sys.platform == "darwin" else peak * 1024),
        "rss_scope": "process_lifetime_high_water_not_per_invocation_attribution",
        "hard_os_memory_limit": False,
        "caller_owned_process_timeout_required": True,
    }


def _check_measurements(measured: dict[str, Any], limits: dict[str, int]) -> None:
    if measured["elapsed_seconds"] > limits["max_seconds"]:
        raise RuntimeError(f"fixture exceeded elapsed ceiling: {measured['elapsed_seconds']}")
    if measured["process_peak_rss_bytes"] > limits["max_rss_bytes"]:
        raise RuntimeError(
            f"fixture exceeded observed RSS ceiling: {measured['process_peak_rss_bytes']}"
        )


def _refit_fixture_world(
    world_exchange: Path,
    *,
    parent_exchange: Path,
    protocol_path: Path,
    expected_protocol_sha256: str,
    world_id: str,
    worker_lock_path: Path,
    _observation: FitInvocation | None = None,
) -> dict[str, Any]:
    """One fresh private fixture call; the parent supplies ancestry, never fitted state.

    Caller owns timeout, immutable case outcomes and zero-retry programme control. This API
    observes operations and process metrics; it provides no restart-resistant fit allowance.
    """
    observation = _observation if _observation is not None else FitInvocation()
    if observation.status != "pending" or observation.folds:
        raise RuntimeError("fixture observation cannot be reused")
    started = time.monotonic()
    _measurements(started)  # Reject unsupported resource measurement before fitting.
    try:
        protocol = _validate_fixture_pair(
            world_exchange,
            parent_exchange=parent_exchange,
            protocol_path=protocol_path,
            expected_protocol_sha256=expected_protocol_sha256,
            world_id=world_id,
            worker_lock_path=worker_lock_path,
        )
        limits = protocol["fixture"]["limits"]
        _check_measurements(_measurements(started), limits)
        result = run_real(
            world_exchange, worker_lock_path=worker_lock_path, _observation=observation
        )
        verified, provenance, _ = _fixture_evidence(
            world_exchange, protocol, request_field="changed_request_sha256"
        )
        if (
            result != verified
            or observation.status != "completed"
            or observation.error_type is not None
        ):
            raise RuntimeError("fixture invocation did not complete with its published result")
        observed = {fold: trace.seal() for fold, trace in observation.folds.items()}
        if set(observed) != {0, 1} or any(
            observed[fold["fold"]]["events"] != fold["events"] for fold in provenance["folds"]
        ):
            raise RuntimeError("fixture result differs from actual invocation observations")
        counts = _component_operations(provenance["folds"], protocol["model"]["name"])
        measured = _measurements(started)
        _check_measurements(measured, limits)
        return {
            "schema_version": 1,
            "kind": "qlib_w11_private_fixture_invocation",
            "authority": "engineering_provenance_only",
            "world": world_id,
            "protocol_sha256": expected_protocol_sha256,
            "worker_result": result,
            "component_operations": counts,
            "measurements": measured,
            "observation_status": observation.status,
            "automatic_retries": 0,
            "independent_observation_count": 0,
            "diagnostic_only": True,
            "counterfactual_refit": False,
            "promotion_eligible": False,
        }
    except BaseException as exc:
        exc.add_note(
            "W11 measured invocation: " + json.dumps(_measurements(started), sort_keys=True)
        )
        raise
