"""Qlib exchange contract guards at the ALPHA process boundary."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import pytest

from alpha_cli.ml_contract import (
    INPUT_ANCHOR_FILENAME,
    MIN_ALIGNED_SESSIONS,
    MIN_SYMBOLS,
    PANEL_COLUMNS,
    PREDICTION_COLUMNS,
    MLContractError,
    canonical_json_bytes,
    compute_config_hash,
    evaluate_result_bundle,
    prepare_exchange,
    publish_replay_signal_frame,
    replay_signal_frame,
    sha256_file,
    validate_request_bundle,
    validate_result_bundle,
)


def _symbols(count: int = MIN_SYMBOLS) -> list[str]:
    return [f"S{i:02d}" for i in range(count)]


def _sessions(count: int = MIN_ALIGNED_SESSIONS) -> list[datetime]:
    start = datetime(2023, 1, 2, tzinfo=UTC)
    return [start + timedelta(days=i) for i in range(count)]


def _panel(
    *, symbols: list[str] | None = None, sessions: list[datetime] | None = None
) -> pl.DataFrame:
    resolved_symbols = symbols or _symbols()
    resolved_sessions = sessions or _sessions()
    rows: list[dict[str, object]] = []
    for session_index, session in enumerate(resolved_sessions):
        for symbol_index, symbol in enumerate(resolved_symbols):
            price = 100.0 + session_index * 0.01 + symbol_index * 0.1
            rows.append(
                {
                    "symbol": symbol,
                    "session_ts": session,
                    "available_at": session + timedelta(hours=23),
                    "open": price,
                    "high": price + 1.0,
                    "low": price - 1.0,
                    "close": price + 0.25,
                    "volume": 1_000_000.0 + symbol_index,
                }
            )
    return pl.DataFrame(rows).select(PANEL_COLUMNS)


def _draft(
    *, symbols: list[str] | None = None, sessions: list[datetime] | None = None
) -> dict[str, Any]:
    resolved_symbols = symbols or _symbols()
    resolved_sessions = sessions or _sessions()
    return {
        "schema_version": 1,
        "snapshot_hash": "a" * 64,
        "universe": resolved_symbols,
        "universe_membership": "point_in_time",
        "survivorship_warning": None,
        "feature_recipe": {"name": "alpha158", "version": 1, "parameters": {}},
        "label_recipe": {
            "name": "next_session_open_to_open",
            "decision": "close_t",
            "fill": "open_t_plus_1",
            "horizon_sessions": 1,
        },
        "model": {"name": "lightgbm", "parameters": {"num_leaves": 31}},
        "portfolio": {
            "selection": "top_quintile",
            "weighting": "equal",
            "long_only": True,
        },
        "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
        "folds": [
            {
                "fold": 0,
                "train_start": resolved_sessions[0].isoformat(),
                "train_end": resolved_sessions[503].isoformat(),
                "validation_start": resolved_sessions[509].isoformat(),
                "validation_end": resolved_sessions[628].isoformat(),
                "test_start": resolved_sessions[634].isoformat(),
                "test_end": resolved_sessions[-2].isoformat(),
            }
        ],
        "purge_sessions": 5,
        "embargo_sessions": 5,
        "seed": 7,
        "worker_lock_hash": "b" * 64,
    }


def _prepare(tmp_path: Path) -> tuple[Path, dict[str, Any], pl.DataFrame]:
    panel = _panel()
    panel_path = tmp_path / "source.parquet"
    panel.write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_draft()), encoding="utf-8")
    exchange = tmp_path / "exchange"
    request = prepare_exchange(spec_path, panel_path, exchange)
    return exchange, request, panel


def _prediction_frame(request: dict[str, Any], panel: pl.DataFrame) -> pl.DataFrame:
    sessions = panel.get_column("session_ts").unique(maintain_order=True).to_list()
    universe = request["universe"]
    fold = request["folds"][0]
    test_start = datetime.fromisoformat(fold["test_start"])
    test_end = datetime.fromisoformat(fold["test_end"])
    session_index = {session: i for i, session in enumerate(sessions)}
    target_sessions = [
        session
        for session in sessions
        if test_start <= session <= test_end and session_index[session] + 1 < len(sessions)
    ]
    rows: list[dict[str, object]] = []
    for target in target_sessions:
        origin = sessions[session_index[target] - 1]
        for symbol_index, symbol in enumerate(universe):
            rows.append(
                {
                    "symbol": symbol,
                    "origin_ts": origin,
                    "available_at": origin + timedelta(hours=23),
                    "target_ts": target,
                    "score": float(symbol_index) / len(universe),
                    "fold": 0,
                    "split": "test",
                    "model_hash": "c" * 64,
                    "config_hash": request["config_hash"],
                    "worker_lock_hash": request["worker_lock_hash"],
                    "seed": request["seed"],
                }
            )
    return pl.DataFrame(rows).select(PREDICTION_COLUMNS)


def _write_result(
    exchange: Path, request: dict[str, Any], predictions: pl.DataFrame
) -> dict[str, Any]:
    path = exchange / "predictions.parquet"
    predictions.write_parquet(path)
    result = {
        "schema_version": 1,
        "status": "succeeded",
        "request_sha256": sha256_file(exchange / "request.json"),
        "snapshot_hash": request["snapshot_hash"],
        "config_hash": request["config_hash"],
        "worker_lock_hash": request["worker_lock_hash"],
        "seed": request["seed"],
        "worker": {"kind": "fake", "implementation_version": "1"},
        "predictions": {
            "path": "predictions.parquet",
            "sha256": sha256_file(path),
            "rows": predictions.height,
        },
        "diagnostics": {},
        "diagnostic_only": True,
        "counterfactual_refit": False,
    }
    (exchange / "result.json").write_bytes(canonical_json_bytes(result))
    return result


def test_prepare_writes_canonical_validated_immutable_request(tmp_path: Path) -> None:
    exchange, request, _ = _prepare(tmp_path)

    validated = validate_request_bundle(exchange)
    assert validated.request == request
    assert validated.panel.height == MIN_SYMBOLS * MIN_ALIGNED_SESSIONS
    assert (exchange / "request.json").read_bytes() == canonical_json_bytes(request)
    assert request["config_hash"] == compute_config_hash(request)
    anchor = json.loads((exchange / INPUT_ANCHOR_FILENAME).read_text(encoding="utf-8"))
    assert anchor == {
        "schema_version": 1,
        "request_sha256": sha256_file(exchange / "request.json"),
        "panel_sha256": sha256_file(exchange / "panel.parquet"),
    }

    with pytest.raises(MLContractError, match="already exists"):
        prepare_exchange(tmp_path / "spec.json", tmp_path / "source.parquet", exchange)


@pytest.mark.parametrize(
    ("symbol_count", "session_count", "message"),
    [
        (MIN_SYMBOLS - 1, MIN_ALIGNED_SESSIONS, "at least 20 symbols"),
        (MIN_SYMBOLS, MIN_ALIGNED_SESSIONS - 1, "at least 756 aligned sessions"),
    ],
)
def test_prepare_enforces_starter_experiment_minimums(
    tmp_path: Path, symbol_count: int, session_count: int, message: str
) -> None:
    symbols = _symbols(symbol_count)
    sessions = _sessions(session_count)
    panel_path = tmp_path / "panel.parquet"
    _panel(symbols=symbols, sessions=sessions).write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(
        json.dumps(_draft(symbols=symbols, sessions=_sessions())), encoding="utf-8"
    )

    with pytest.raises(MLContractError, match=message):
        prepare_exchange(spec_path, panel_path, tmp_path / "exchange")


def test_current_membership_requires_permanent_survivorship_warning(tmp_path: Path) -> None:
    draft = _draft()
    draft["universe_membership"] = "current_membership"
    panel_path = tmp_path / "panel.parquet"
    _panel().write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(draft), encoding="utf-8")

    with pytest.raises(MLContractError, match="survivorship_warning"):
        prepare_exchange(spec_path, panel_path, tmp_path / "exchange")


def test_prepare_rejects_recipe_drift_and_unbounded_model_parameters(
    tmp_path: Path,
) -> None:
    panel_path = tmp_path / "panel.parquet"
    _panel().write_parquet(panel_path)
    mutations: list[tuple[str, Callable[[dict[str, Any]], None], str]] = [
        (
            "feature",
            lambda draft: draft["feature_recipe"].update({"parameters": {"windows": [5]}}),
            "fixed recipe",
        ),
        (
            "model",
            lambda draft: draft["model"]["parameters"].update({"device": "gpu"}),
            "unsupported LightGBM parameters",
        ),
        (
            "model-bounds",
            lambda draft: draft["model"]["parameters"].update({"num_threads": 64}),
            "between 1.0 and 8.0",
        ),
    ]
    for name, mutation, message in mutations:
        draft = _draft()
        mutation(draft)
        spec_path = tmp_path / f"{name}.json"
        spec_path.write_text(json.dumps(draft), encoding="utf-8")
        with pytest.raises(MLContractError, match=message):
            prepare_exchange(spec_path, panel_path, tmp_path / f"{name}-exchange")


def test_prepare_can_attest_the_supplied_worker_lock(tmp_path: Path) -> None:
    panel_path = tmp_path / "panel.parquet"
    _panel().write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_draft()), encoding="utf-8")
    worker_lock = tmp_path / "uv.lock"
    worker_lock.write_text("version = 1\n", encoding="utf-8")

    with pytest.raises(MLContractError, match="worker_lock_hash"):
        prepare_exchange(
            spec_path,
            panel_path,
            tmp_path / "exchange",
            worker_lock_path=worker_lock,
        )


def test_prepare_rejects_overlapping_fold_test_windows(tmp_path: Path) -> None:
    draft = _draft()
    duplicate = dict(draft["folds"][0])
    duplicate["fold"] = 1
    draft["folds"].append(duplicate)
    panel_path = tmp_path / "panel.parquet"
    _panel().write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(draft), encoding="utf-8")

    with pytest.raises(MLContractError, match="non-overlapping"):
        prepare_exchange(spec_path, panel_path, tmp_path / "exchange")


@pytest.mark.parametrize(
    ("boundary", "message"),
    [
        ("train-validation", "purge sessions, requires 1"),
        ("validation-test", "embargo sessions, requires 1"),
    ],
)
def test_prepare_requires_label_horizon_gap_when_buffer_is_zero(
    tmp_path: Path, boundary: str, message: str
) -> None:
    sessions = _sessions()
    draft = _draft()
    if boundary == "train-validation":
        draft["purge_sessions"] = 0
        draft["folds"][0]["validation_start"] = sessions[504].isoformat()
    else:
        draft["embargo_sessions"] = 0
        draft["folds"][0]["test_start"] = sessions[629].isoformat()
    panel_path = tmp_path / "panel.parquet"
    _panel().write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(draft), encoding="utf-8")

    with pytest.raises(MLContractError, match=message):
        prepare_exchange(spec_path, panel_path, tmp_path / "exchange")


def test_prepare_rejects_a_terminal_session_test_target(tmp_path: Path) -> None:
    sessions = _sessions()
    draft = _draft()
    draft["folds"][0]["test_end"] = sessions[-1].isoformat()
    panel_path = tmp_path / "panel.parquet"
    _panel().write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(draft), encoding="utf-8")

    with pytest.raises(MLContractError, match="following aligned open"):
        prepare_exchange(spec_path, panel_path, tmp_path / "exchange")


def test_request_rejects_hash_drift_and_unsafe_files(tmp_path: Path) -> None:
    exchange, request, _ = _prepare(tmp_path)
    request["snapshot_hash"] = "d" * 64
    (exchange / "request.json").write_bytes(canonical_json_bytes(request))
    with pytest.raises(MLContractError, match="config_hash"):
        validate_request_bundle(exchange)


def test_panel_and_predictions_reject_nulls(tmp_path: Path) -> None:
    panel = _panel().with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(None).otherwise(pl.col("volume")).alias("volume")
    )
    panel_path = tmp_path / "panel.parquet"
    panel.write_parquet(panel_path)
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(_draft()), encoding="utf-8")
    with pytest.raises(MLContractError, match="nulls"):
        prepare_exchange(spec_path, panel_path, tmp_path / "bad-panel")

    valid_root = tmp_path / "valid"
    valid_root.mkdir()
    exchange, request, valid_panel = _prepare(valid_root)
    predictions = _prediction_frame(request, valid_panel).with_columns(
        pl.when(pl.int_range(pl.len()) == 0).then(None).otherwise(pl.col("score")).alias("score")
    )
    _write_result(exchange, request, predictions)
    with pytest.raises(MLContractError, match="nulls"):
        validate_result_bundle(exchange)

    repaired = {**request, "config_hash": compute_config_hash(request)}
    (exchange / "request.json").write_bytes(canonical_json_bytes(repaired))
    (exchange / "model.pkl").write_bytes(b"not allowed")
    with pytest.raises(MLContractError, match="JSON and Parquet"):
        validate_request_bundle(exchange)


def test_valid_result_is_repeatably_importable_and_evaluable(tmp_path: Path) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = _prediction_frame(request, panel)
    _write_result(exchange, request, predictions)

    first = validate_result_bundle(exchange)
    second = validate_result_bundle(exchange)
    assert first.result == second.result
    assert first.predictions.equals(second.predictions)

    evaluation = evaluate_result_bundle(exchange)
    assert evaluation["rows"] == predictions.height
    assert evaluation["symbols"] == MIN_SYMBOLS
    assert evaluation["authority"] == "diagnostic_only"
    assert "ALPHA replay" in evaluation["next_required_step"]


def test_result_rejects_prediction_without_a_following_open(tmp_path: Path) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = _prediction_frame(request, panel)
    sessions = panel.get_column("session_ts").unique(maintain_order=True).to_list()
    final_target = sessions[-1]
    final_origin = sessions[-2]
    previous_last_target = predictions.get_column("target_ts").max()
    assert previous_last_target is not None
    poisoned = predictions.with_columns(
        pl.when(pl.col("target_ts") == previous_last_target)
        .then(pl.lit(final_target))
        .otherwise(pl.col("target_ts"))
        .alias("target_ts"),
        pl.when(pl.col("target_ts") == previous_last_target)
        .then(pl.lit(final_origin))
        .otherwise(pl.col("origin_ts"))
        .alias("origin_ts"),
        pl.when(pl.col("target_ts") == previous_last_target)
        .then(pl.lit(final_origin + timedelta(hours=23)))
        .otherwise(pl.col("available_at"))
        .alias("available_at"),
    ).sort(["fold", "split", "target_ts", "symbol", "origin_ts"])
    _write_result(exchange, request, poisoned)

    with pytest.raises(MLContractError, match="following aligned open"):
        validate_result_bundle(exchange)


def test_replay_signal_handoff_is_causal_equal_weight_and_immutable(tmp_path: Path) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = _prediction_frame(request, panel)
    _write_result(exchange, request, predictions)

    frame = replay_signal_frame(exchange)
    grouped = frame.group_by("entry_ts").agg(
        pl.col("selected").sum().alias("selected_count"),
        pl.col("target_weight").sum().alias("weight_sum"),
    )
    assert grouped.get_column("selected_count").unique().to_list() == [4]
    assert grouped.get_column("weight_sum").unique().to_list() == [1.0]
    assert frame.filter(pl.col("decision_ts") >= pl.col("entry_ts")).is_empty()
    assert frame.filter(pl.col("available_at") > pl.col("decision_ts")).is_empty()
    assert frame.get_column("split").unique().to_list() == ["test"]
    assert (frame.get_column("decision_ts") - frame.get_column("origin_ts")).unique().to_list() == [
        timedelta(hours=23)
    ]

    output = tmp_path / "replay_signals.parquet"
    first = publish_replay_signal_frame(exchange, output)
    second = publish_replay_signal_frame(exchange, output)
    assert first.equals(second)
    assert pl.read_parquet(output).equals(frame)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda frame: frame.with_columns(pl.lit(float("nan")).alias("score")), "finite"),
        (
            lambda frame: pl.concat([frame, frame.head(1)]),
            "duplicate prediction key",
        ),
        (lambda frame: frame.reverse(), "sorted"),
        (
            lambda frame: frame.with_columns(
                pl.when(pl.int_range(pl.len()) == 0)
                .then(pl.col("origin_ts") + pl.duration(days=1))
                .otherwise(pl.col("available_at"))
                .alias("available_at")
            ),
            "available_at",
        ),
        (
            lambda frame: frame.with_columns(pl.lit("d" * 64).alias("config_hash")),
            "config_hash",
        ),
    ],
)
def test_result_rejects_nonfinite_duplicate_disordered_late_and_hash_drift(
    tmp_path: Path,
    mutation: Callable[[pl.DataFrame], pl.DataFrame],
    message: str,
) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = mutation(_prediction_frame(request, panel))
    _write_result(exchange, request, predictions)

    with pytest.raises(MLContractError, match=message):
        validate_result_bundle(exchange)


def test_result_rejects_exact_field_fold_and_target_overlap_violations(tmp_path: Path) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = _prediction_frame(request, panel)

    extra = predictions.with_columns(pl.lit(1).alias("unexpected"))
    _write_result(exchange, request, extra)
    with pytest.raises(MLContractError, match="exact columns"):
        validate_result_bundle(exchange)

    predictions.write_parquet(exchange / "predictions.parquet")
    bad_fold = predictions.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.lit(99))
        .otherwise(pl.col("fold"))
        .alias("fold")
    )
    _write_result(exchange, request, bad_fold)
    with pytest.raises(MLContractError, match="declared fold"):
        validate_result_bundle(exchange)

    overlapping = predictions.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.col("target_ts").shift(-MIN_SYMBOLS))
        .otherwise(pl.col("target_ts"))
        .alias("target_ts")
    )
    _write_result(exchange, request, overlapping)
    with pytest.raises(MLContractError, match="target overlap|duplicate prediction key"):
        validate_result_bundle(exchange)


def test_result_requires_one_model_hash_per_fold(tmp_path: Path) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = _prediction_frame(request, panel).with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.lit("d" * 64))
        .otherwise(pl.col("model_hash"))
        .alias("model_hash")
    )
    _write_result(exchange, request, predictions)
    with pytest.raises(MLContractError, match="one model_hash"):
        validate_result_bundle(exchange)


def test_result_requires_the_complete_declared_oos_target_grid(tmp_path: Path) -> None:
    exchange, request, panel = _prepare(tmp_path)
    predictions = _prediction_frame(request, panel)
    omitted_target = predictions.get_column("target_ts").unique(maintain_order=True)[-1]
    incomplete = predictions.filter(pl.col("target_ts") != omitted_target)
    _write_result(exchange, request, incomplete)

    with pytest.raises(MLContractError, match="exact declared OOS target grid"):
        validate_result_bundle(exchange)


def test_protocol_descriptors_pin_exact_parquet_fields() -> None:
    repo = Path(__file__).parents[2]
    schema_root = repo / "workers/qlib/src/alpha_qlib_worker/schemas"
    request_schema = json.loads((schema_root / "request.schema.json").read_text())
    result_schema = json.loads((schema_root / "result.schema.json").read_text())
    panel_schema = json.loads((schema_root / "panel.parquet.schema.json").read_text())
    prediction_schema = json.loads((schema_root / "predictions.parquet.schema.json").read_text())
    assert set(request_schema["required"]) == {
        "schema_version",
        "snapshot_hash",
        "universe",
        "universe_membership",
        "survivorship_warning",
        "feature_recipe",
        "label_recipe",
        "model",
        "portfolio",
        "costs",
        "folds",
        "purge_sessions",
        "embargo_sessions",
        "seed",
        "worker_lock_hash",
        "panel",
        "config_hash",
    }
    assert result_schema["properties"]["diagnostic_only"] == {"const": True}
    assert result_schema["properties"]["counterfactual_refit"] == {"const": False}
    assert [column["name"] for column in panel_schema["columns"]] == PANEL_COLUMNS
    assert [column["name"] for column in prediction_schema["columns"]] == PREDICTION_COLUMNS
