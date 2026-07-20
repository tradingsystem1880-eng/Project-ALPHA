"""High-value failure-path coverage for the isolated ML process boundary."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest
import typer

from alpha_cli import ml_cmds, ml_contract, ml_input
from alpha_cli.ml_contract import (
    INPUT_ANCHOR_FILENAME,
    MIN_ALIGNED_SESSIONS,
    MIN_SYMBOLS,
    PANEL_COLUMNS,
    PREDICTION_COLUMNS,
    MLContractError,
    canonical_json_bytes,
    compute_config_hash,
    prepare_exchange,
    publish_replay_signal_frame,
    sha256_file,
    validate_request_bundle,
    validate_result_bundle,
)
from alpha_core import DataError


def _symbols() -> list[str]:
    return [f"S{index:02d}" for index in range(MIN_SYMBOLS)]


def _sessions() -> list[datetime]:
    start = datetime(2023, 1, 2, tzinfo=UTC)
    return [start + timedelta(days=index) for index in range(MIN_ALIGNED_SESSIONS)]


def _panel() -> pl.DataFrame:
    rows: list[dict[str, object]] = []
    for session_index, session in enumerate(_sessions()):
        for symbol_index, symbol in enumerate(_symbols()):
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


def _draft(worker_lock_hash: str) -> dict[str, Any]:
    sessions = _sessions()
    return {
        "schema_version": 1,
        "snapshot_hash": "a" * 64,
        "universe": _symbols(),
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
                "train_start": sessions[0].isoformat(),
                "train_end": sessions[503].isoformat(),
                "validation_start": sessions[509].isoformat(),
                "validation_end": sessions[628].isoformat(),
                "test_start": sessions[634].isoformat(),
                "test_end": sessions[-2].isoformat(),
            }
        ],
        "purge_sessions": 5,
        "embargo_sessions": 5,
        "seed": 7,
        "worker_lock_hash": worker_lock_hash,
    }


def _predictions(request: dict[str, Any], panel: pl.DataFrame) -> pl.DataFrame:
    sessions = panel.get_column("session_ts").unique(maintain_order=True).to_list()
    positions = {session: index for index, session in enumerate(sessions)}
    rows: list[dict[str, object]] = []
    for fold in request["folds"]:
        start = datetime.fromisoformat(fold["test_start"])
        end = datetime.fromisoformat(fold["test_end"])
        for target in sessions:
            if not start <= target <= end:
                continue
            origin = sessions[positions[target] - 1]
            for index, symbol in enumerate(request["universe"]):
                rows.append(
                    {
                        "symbol": symbol,
                        "origin_ts": origin,
                        "available_at": origin + timedelta(hours=23),
                        "target_ts": target,
                        "score": float(index) / len(request["universe"]),
                        "fold": fold["fold"],
                        "split": "test",
                        "model_hash": "c" * 64,
                        "config_hash": request["config_hash"],
                        "worker_lock_hash": request["worker_lock_hash"],
                        "seed": request["seed"],
                    }
                )
    return pl.DataFrame(rows).select(PREDICTION_COLUMNS)


def _write_result(exchange: Path, request: dict[str, Any], predictions: pl.DataFrame) -> None:
    prediction_path = exchange / "predictions.parquet"
    predictions.write_parquet(prediction_path)
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
            "sha256": sha256_file(prediction_path),
            "rows": predictions.height,
        },
        "diagnostics": {},
        "diagnostic_only": True,
        "counterfactual_refit": False,
    }
    (exchange / "result.json").write_bytes(canonical_json_bytes(result))


@pytest.fixture(scope="module")
def boundary_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("ml-boundary")
    worker = root / "worker"
    worker.mkdir()
    (worker / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    lock = worker / "uv.lock"
    lock.write_text("version = 1\n")
    lock_hash = hashlib.sha256(lock.read_bytes()).hexdigest()
    panel = _panel()
    panel_path = root / "source.parquet"
    panel.write_parquet(panel_path)
    spec_path = root / "spec.json"
    spec_path.write_text(json.dumps(_draft(lock_hash)), encoding="utf-8")
    request_exchange = root / "request-exchange"
    request = prepare_exchange(spec_path, panel_path, request_exchange, worker_lock_path=lock)
    result_exchange = root / "result-exchange"
    shutil.copytree(request_exchange, result_exchange)
    _write_result(result_exchange, request, _predictions(request, panel))
    return {
        "root": root,
        "worker": worker,
        "lock": lock,
        "spec": spec_path,
        "panel": panel_path,
        "request": request_exchange,
        "result": result_exchange,
    }


def _clone(source: Path, tmp_path: Path, name: str = "exchange") -> Path:
    destination = tmp_path / name
    shutil.copytree(source, destination)
    return destination


def _rewrite_request(
    exchange: Path,
    mutation: Callable[[dict[str, Any]], None],
) -> dict[str, Any]:
    path = exchange / "request.json"
    request = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    mutation(request)
    request["config_hash"] = compute_config_hash(request)
    path.write_bytes(canonical_json_bytes(request))
    return request


def _rewrite_panel(exchange: Path, frame: pl.DataFrame) -> None:
    panel_path = exchange / "panel.parquet"
    frame.write_parquet(panel_path)

    def update(request: dict[str, Any]) -> None:
        request["panel"] = {
            "path": "panel.parquet",
            "sha256": sha256_file(panel_path),
            "rows": frame.height,
        }

    _rewrite_request(exchange, update)


def _rewrite_result(exchange: Path, mutation: Callable[[dict[str, Any]], None]) -> None:
    path = exchange / "result.json"
    result = json.loads(path.read_text(encoding="utf-8"))
    mutation(result)
    path.write_bytes(canonical_json_bytes(result))


def _rewrite_predictions(exchange: Path, predictions: pl.DataFrame) -> None:
    path = exchange / "predictions.parquet"
    predictions.write_parquet(path)

    def update(result: dict[str, Any]) -> None:
        result["predictions"] = {
            "path": "predictions.parquet",
            "sha256": sha256_file(path),
            "rows": predictions.height,
        }

    _rewrite_result(exchange, update)


def _rewrite_input_anchor(exchange: Path) -> None:
    payload = {
        "schema_version": 1,
        "request_sha256": sha256_file(exchange / "request.json"),
        "panel_sha256": sha256_file(exchange / "panel.parquet"),
    }
    (exchange / INPUT_ANCHOR_FILENAME).write_bytes(canonical_json_bytes(payload))


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b'{"value":NaN}\n', "non-finite constant"),
        (b'{"value":1,"value":2}\n', "duplicate key"),
        (b'{"value":', "invalid JSON"),
        (b"[]\n", "JSON object"),
        (b'{"value": 1}\n', "not canonical JSON"),
    ],
)
def test_request_json_rejects_unsafe_or_noncanonical_bytes(
    tmp_path: Path, raw: bytes, message: str
) -> None:
    exchange = tmp_path / "exchange"
    exchange.mkdir()
    (exchange / "request.json").write_bytes(raw)
    with pytest.raises(MLContractError, match=message):
        validate_request_bundle(exchange)


def test_json_and_file_helpers_fail_loudly(tmp_path: Path) -> None:
    with pytest.raises(MLContractError, match="canonical-JSON encodable"):
        canonical_json_bytes({"value": float("nan")})
    with pytest.raises(MLContractError, match="cannot hash"):
        sha256_file(tmp_path / "missing")
    with pytest.raises(MLContractError, match="unavailable"):
        ml_contract._as_finite_float(True, "score")
    with pytest.raises(MLContractError, match="not finite"):
        ml_contract._as_finite_float(float("inf"), "score")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        (3, "ISO-8601"),
        ("not-a-date", "ISO-8601"),
        ("2023-01-01T00:00:00", "timezone-aware"),
        ("2023-01-01T01:00:00+01:00", "use UTC"),
    ],
)
def test_timestamp_parser_rejects_ambiguous_boundaries(value: object, message: str) -> None:
    with pytest.raises(MLContractError, match=message):
        ml_contract._parse_ts(value, "boundary")


RequestMutation = Callable[[dict[str, Any]], None]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda request: request.update({"unexpected": True}), "fields mismatch"),
        (lambda request: request.update({"schema_version": 2}), "unsupported request"),
        (lambda request: request.update({"snapshot_hash": "BAD"}), "SHA-256"),
        (lambda request: request.update({"seed": True}), "seed must be an integer"),
        (lambda request: request.update({"universe": "S00"}), "array of symbols"),
        (
            lambda request: request.update({"universe": list(reversed(request["universe"]))}),
            "valid, sorted, and unique",
        ),
        (lambda request: request.update({"universe_membership": "latest"}), "point_in_time"),
        (lambda request: request.update({"survivorship_warning": 7}), "null or a string"),
        (lambda request: request.update({"feature_recipe": []}), "JSON object"),
        (
            lambda request: request.update(
                {"feature_recipe": {"name": "other", "version": 1, "parameters": {}}}
            ),
            "alpha158 version 1",
        ),
        (
            lambda request: request.update(
                {
                    "label_recipe": {
                        "name": "close_to_close",
                        "decision": "close_t",
                        "fill": "open_t_plus_1",
                        "horizon_sessions": 1,
                    }
                }
            ),
            "next-session open-to-open",
        ),
        (
            lambda request: request.update({"model": {"name": "xgboost", "parameters": {}}}),
            "starter model",
        ),
        (
            lambda request: request.update(
                {"model": {"name": "lightgbm", "parameters": {"num_leaves": "31"}}}
            ),
            "finite number",
        ),
        (
            lambda request: request.update(
                {"model": {"name": "lightgbm", "parameters": {"num_leaves": 31.5}}}
            ),
            "must be an integer",
        ),
        (
            lambda request: request.update(
                {"portfolio": {"selection": "all", "weighting": "equal", "long_only": True}}
            ),
            "long-only",
        ),
        (
            lambda request: request.update({"costs": {"fee_bps": True, "slippage_bps": 2.0}}),
            "finite number",
        ),
        (
            lambda request: request.update({"costs": {"fee_bps": -1.0, "slippage_bps": 2.0}}),
            "finite number",
        ),
        (lambda request: request.update({"folds": []}), "non-empty array"),
        (
            lambda request: request["folds"][0].update({"fold": 1}),
            "contiguous from zero",
        ),
        (
            lambda request: request["folds"][0].update(
                {"train_start": "2010-01-01T00:00:00+00:00"}
            ),
            "not an aligned session",
        ),
        (
            lambda request: request["folds"][0].update(
                {"train_end": request["folds"][0]["validation_start"]}
            ),
            "must order non-empty",
        ),
        (
            lambda request: request["folds"][0].update(
                {
                    "validation_start": (
                        datetime.fromisoformat(request["folds"][0]["train_end"]) + timedelta(days=2)
                    ).isoformat()
                }
            ),
            "purge sessions",
        ),
        (
            lambda request: request["folds"][0].update(
                {
                    "test_start": (
                        datetime.fromisoformat(request["folds"][0]["validation_end"])
                        + timedelta(days=2)
                    ).isoformat()
                }
            ),
            "embargo sessions",
        ),
        (
            lambda request: request.update(
                {"panel": {**request["panel"], "path": "other.parquet"}}
            ),
            "panel.path",
        ),
        (
            lambda request: request.update(
                {"panel": {**request["panel"], "rows": request["panel"]["rows"] + 1}}
            ),
            "panel.rows",
        ),
    ],
)
def test_request_contract_rejects_semantic_drift(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    mutation: RequestMutation,
    message: str,
) -> None:
    exchange = _clone(boundary_fixture["request"], tmp_path)
    _rewrite_request(exchange, mutation)
    with pytest.raises(MLContractError, match=message):
        validate_request_bundle(exchange)


def _wrong_columns(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.drop("volume")


def _wrong_schema(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(pl.col("open").cast(pl.Float32))


def _disordered(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.reverse()


def _duplicate_key(frame: pl.DataFrame) -> pl.DataFrame:
    return pl.concat([frame.slice(0, frame.height - 1), frame.head(1)]).sort(
        ["session_ts", "symbol"]
    )


def _wrong_symbol(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.col("symbol") == "S00")
        .then(pl.lit("ZZZ"))
        .otherwise(pl.col("symbol"))
        .alias("symbol")
    ).sort(["session_ts", "symbol"])


def _incomplete_rectangle(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.head(frame.height - 1)


def _nonfinite_panel(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.lit(float("inf")))
        .otherwise(pl.col("open"))
        .alias("open")
    )


def _invalid_geometry(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.col("high") + 1.0)
        .otherwise(pl.col("low"))
        .alias("low")
    )


def _late_panel(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.col("session_ts") + pl.duration(hours=1))
        .otherwise(pl.col("available_at"))
        .alias("available_at")
    )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_wrong_columns, "exact columns"),
        (_wrong_schema, "schema mismatch"),
        (_disordered, "must be sorted"),
        (_duplicate_key, "duplicate"),
        (_wrong_symbol, "exactly match"),
        (_incomplete_rectangle, "fully aligned"),
        (_nonfinite_panel, "all be finite"),
        (_invalid_geometry, "invalid OHLCV"),
        (_late_panel, "available_at"),
    ],
)
def test_panel_contract_rejects_noncanonical_market_data(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    mutation: Callable[[pl.DataFrame], pl.DataFrame],
    message: str,
) -> None:
    exchange = _clone(boundary_fixture["request"], tmp_path)
    frame = pl.read_parquet(exchange / "panel.parquet")
    _rewrite_panel(exchange, mutation(frame))
    with pytest.raises(MLContractError, match=message):
        validate_request_bundle(exchange)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda result: result.update({"schema_version": 2}), "schema_version"),
        (lambda result: result.update({"status": "failed"}), "status"),
        (lambda result: result.update({"request_sha256": "d" * 64}), "request_sha256"),
        (
            lambda result: result.update(
                {"worker": {"kind": "other", "implementation_version": "1"}}
            ),
            "identify fake or qlib",
        ),
        (
            lambda result: result.update(
                {"predictions": {**result["predictions"], "path": "other.parquet"}}
            ),
            "predictions.path",
        ),
        (
            lambda result: result.update(
                {"predictions": {**result["predictions"], "sha256": "d" * 64}}
            ),
            "prediction hash",
        ),
        (
            lambda result: result.update({"predictions": {**result["predictions"], "rows": 999}}),
            "predictions.rows",
        ),
        (lambda result: result.update({"diagnostics": []}), "portable JSON object"),
        (lambda result: result.update({"diagnostic_only": False}), "diagnostic_only"),
    ],
)
def test_result_control_record_rejects_untrusted_worker_claims(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    mutation: Callable[[dict[str, Any]], None],
    message: str,
) -> None:
    exchange = _clone(boundary_fixture["result"], tmp_path)
    _rewrite_result(exchange, mutation)
    with pytest.raises(MLContractError, match=message):
        validate_result_bundle(exchange)


def _prediction_schema_drift(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(pl.col("score").cast(pl.Float32))


def _empty_predictions(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.head(0)


def _invalid_split(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(pl.lit("train").alias("split"))


def _invalid_model_hash(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(pl.lit("bad").alias("model_hash"))


def _wrong_worker_hash(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(pl.lit("d" * 64).alias("worker_lock_hash"))


def _wrong_seed(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(pl.lit(8, dtype=pl.Int64).alias("seed"))


def _outside_symbol(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.lit("ZZZ"))
        .otherwise(pl.col("symbol"))
        .alias("symbol")
    ).sort(["fold", "split", "target_ts", "symbol", "origin_ts"])


def _wrong_source_availability(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.col("origin_ts") - pl.duration(hours=1))
        .otherwise(pl.col("available_at"))
        .alias("available_at")
    )


def _nonadjacent_target(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.col("origin_ts") - pl.duration(days=1))
        .otherwise(pl.col("origin_ts"))
        .alias("origin_ts"),
        pl.when(pl.int_range(pl.len()) == 0)
        .then(pl.col("available_at") - pl.duration(days=1))
        .otherwise(pl.col("available_at"))
        .alias("available_at"),
    ).sort(["fold", "split", "target_ts", "symbol", "origin_ts"])


def _outside_test_window(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(
        (pl.col("origin_ts") - pl.duration(days=1)).alias("origin_ts"),
        (pl.col("available_at") - pl.duration(days=1)).alias("available_at"),
        (pl.col("target_ts") - pl.duration(days=1)).alias("target_ts"),
    )


def _incomplete_cross_section(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.head(frame.height - 1)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (_prediction_schema_drift, "schema mismatch"),
        (_empty_predictions, "may not be empty"),
        (_invalid_split, "prediction split"),
        (_invalid_model_hash, "SHA-256"),
        (_wrong_worker_hash, "worker_lock_hash"),
        (_wrong_seed, "prediction seed"),
        (_outside_symbol, "outside the frozen universe"),
        (_wrong_source_availability, "source panel availability"),
        (_nonadjacent_target, "immediately after origin_ts"),
        (_outside_test_window, "outside declared fold"),
        (_incomplete_cross_section, "complete frozen universe"),
    ],
)
def test_prediction_contract_rejects_leakage_and_lineage_drift(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    mutation: Callable[[pl.DataFrame], pl.DataFrame],
    message: str,
) -> None:
    exchange = _clone(boundary_fixture["result"], tmp_path)
    predictions = pl.read_parquet(exchange / "predictions.parquet")
    _rewrite_predictions(exchange, mutation(predictions))
    with pytest.raises(MLContractError, match=message):
        validate_result_bundle(exchange)


def test_portable_bundle_and_parquet_guards(
    tmp_path: Path, boundary_fixture: dict[str, Path]
) -> None:
    with pytest.raises(MLContractError, match="does not exist"):
        validate_request_bundle(tmp_path / "missing")

    symlink_exchange = _clone(boundary_fixture["request"], tmp_path, "symlink-exchange")
    (symlink_exchange / "unsafe.json").symlink_to(symlink_exchange / "request.json")
    with pytest.raises(MLContractError, match="symlinks"):
        validate_request_bundle(symlink_exchange)

    missing_panel = _clone(boundary_fixture["request"], tmp_path, "missing-panel")
    (missing_panel / "panel.parquet").unlink()
    with pytest.raises(MLContractError, match="missing required panel"):
        validate_request_bundle(missing_panel)

    corrupt_panel = _clone(boundary_fixture["request"], tmp_path, "corrupt-panel")
    (corrupt_panel / "panel.parquet").write_bytes(b"not parquet")
    with pytest.raises(MLContractError, match="cannot read panel"):
        validate_request_bundle(corrupt_panel)

    hash_drift = _clone(boundary_fixture["request"], tmp_path, "hash-drift")
    frame = pl.read_parquet(hash_drift / "panel.parquet").with_columns(
        (pl.col("close") + 0.01).alias("close")
    )
    frame.write_parquet(hash_drift / "panel.parquet")
    with pytest.raises(MLContractError, match="panel hash"):
        validate_request_bundle(hash_drift)


def test_prepare_cleans_staging_after_atomic_publish_failure(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_replace(source: Path, destination: Path) -> None:
        del source, destination
        raise OSError("publish failed")

    monkeypatch.setattr("alpha_cli.ml_contract.os.replace", fail_replace)
    output = tmp_path / "exchange"
    with pytest.raises(OSError, match="publish failed"):
        prepare_exchange(
            boundary_fixture["spec"],
            boundary_fixture["panel"],
            output,
            worker_lock_path=boundary_fixture["lock"],
        )
    assert not output.exists()
    assert not list(tmp_path.glob(".exchange.*.tmp"))


def test_prepare_and_replay_outputs_reject_unsafe_paths(
    tmp_path: Path, boundary_fixture: dict[str, Path]
) -> None:
    with pytest.raises(MLContractError, match="regular Parquet"):
        prepare_exchange(
            boundary_fixture["spec"],
            tmp_path / "missing.parquet",
            tmp_path / "missing-panel-exchange",
        )
    with pytest.raises(MLContractError, match="worker lock must be a regular file"):
        prepare_exchange(
            boundary_fixture["spec"],
            boundary_fixture["panel"],
            tmp_path / "missing-lock-exchange",
            worker_lock_path=tmp_path / "missing.lock",
        )

    exchange = _clone(boundary_fixture["result"], tmp_path, "replay-exchange")
    with pytest.raises(MLContractError, match=".parquet suffix"):
        publish_replay_signal_frame(exchange, tmp_path / "signals.csv")

    real = tmp_path / "real.parquet"
    real.write_bytes(b"target")
    symlink = tmp_path / "signals.parquet"
    symlink.symlink_to(real)
    with pytest.raises(MLContractError, match="may not be a symlink"):
        publish_replay_signal_frame(exchange, symlink)

    different = tmp_path / "different.parquet"
    different.write_bytes(b"different")
    with pytest.raises(MLContractError, match="different bytes"):
        publish_replay_signal_frame(exchange, different)


def test_replay_publish_detects_a_different_concurrent_winner(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _clone(boundary_fixture["result"], tmp_path)
    output = tmp_path / "signals.parquet"

    def collide(source: Path, destination: Path) -> None:
        del source
        Path(destination).write_bytes(b"different")
        raise FileExistsError

    monkeypatch.setattr("alpha_cli.ml_contract.os.link", collide)
    with pytest.raises(MLContractError, match="concurrently published differently"):
        publish_replay_signal_frame(exchange, output)


def _valid_input_experiment() -> dict[str, object]:
    return {
        "universe": _symbols(),
        "split_policy": {"train": 504, "test": 63, "purge": 5, "embargo": 5},
        "stage_config": {"ml": {"validation_sessions": 120}},
        "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
        "seeds": {"master": 7},
    }


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda: ml_input._object([], "object"), "JSON object"),
        (lambda: ml_input._positive_int(0, "positive", default=1), "integer >= 1"),
        (lambda: ml_input._nonnegative_int(-1, "nonnegative", default=0), "integer >= 0"),
        (lambda: ml_input._finite_nonnegative(True, "number"), "finite number"),
        (lambda: ml_input._finite_nonnegative(float("inf"), "number"), "finite number"),
    ],
)
def test_ml_input_scalar_guards(call: Callable[[], object], message: str) -> None:
    with pytest.raises(DataError, match=message):
        call()


def test_ml_input_projection_and_split_guards(tmp_path: Path) -> None:
    class FakeControl:
        def __init__(self, projection: object) -> None:
            self.projection = projection

        def get_project(self, project_id: str) -> dict[str, object]:
            del project_id
            return {"experiments": self.projection}

    with pytest.raises(DataError, match="corrupt experiment"):
        ml_input._experiment(cast(Any, FakeControl("bad")), "project", "experiment")
    with pytest.raises(DataError, match="not linked"):
        ml_input._experiment(cast(Any, FakeControl([])), "project", "experiment")
    with pytest.raises(DataError, match="fully aligned sessions"):
        ml_input._aligned_panel(data_dir=tmp_path, snapshot_id="snapshot", universe=[])
    with pytest.raises(DataError, match="needs at least"):
        ml_input._folds(
            [datetime(2023, 1, 1, tzinfo=UTC)],
            train_sessions=1,
            validation_sessions=1,
            test_sessions=1,
            purge_sessions=1,
            embargo_sessions=1,
        )


def test_ml_input_draft_rejects_bad_project_configuration() -> None:
    sessions = _sessions()
    invalid_universe = _valid_input_experiment()
    invalid_universe["universe"] = "S00"
    with pytest.raises(DataError, match="universe must be an array"):
        ml_input._draft_spec(
            experiment=invalid_universe,
            sessions=sessions,
            snapshot_hash="a" * 64,
            worker_lock_hash="b" * 64,
        )

    invalid_membership = copy.deepcopy(_valid_input_experiment())
    cast(dict[str, object], invalid_membership["stage_config"])["ml"] = {
        "universe_membership": "latest"
    }
    with pytest.raises(DataError, match="point_in_time or current_membership"):
        ml_input._draft_spec(
            experiment=invalid_membership,
            sessions=sessions,
            snapshot_hash="a" * 64,
            worker_lock_hash="b" * 64,
        )


@pytest.mark.parametrize(
    ("experiment", "message"),
    [
        ({**_valid_input_experiment(), "snapshot_id": None}, "no immutable snapshot"),
        (
            {**_valid_input_experiment(), "snapshot_id": "snapshot", "universe": "S00"},
            "universe must be an array",
        ),
        (
            {
                **_valid_input_experiment(),
                "snapshot_id": "snapshot",
                "universe": _symbols()[:-1],
            },
            "at least 20 frozen symbols",
        ),
    ],
)
def test_export_input_rejects_incomplete_experiment_projections(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    experiment: dict[str, object],
    message: str,
) -> None:
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "uv.lock").write_text("version = 1\n")
    monkeypatch.setattr(ml_input, "_experiment", lambda *args: experiment)
    with pytest.raises(DataError, match=message):
        ml_input.export_project_input(
            data_dir=tmp_path / "data",
            project_id="project",
            experiment_id="experiment",
            output_dir=tmp_path / "output",
            worker_project=worker,
        )


def test_export_input_rejects_existing_output_and_missing_worker_lock(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    with pytest.raises(DataError, match="already exists"):
        ml_input.export_project_input(
            data_dir=tmp_path,
            project_id="project",
            experiment_id="experiment",
            output_dir=output,
        )

    worker = tmp_path / "worker"
    worker.mkdir()
    with pytest.raises(DataError, match="worker lock is unavailable"):
        ml_input.export_project_input(
            data_dir=tmp_path,
            project_id="project",
            experiment_id="experiment",
            output_dir=tmp_path / "new-output",
            worker_project=worker,
        )


def test_export_input_reports_a_concurrent_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "uv.lock").write_text("version = 1\n")
    experiment = {**_valid_input_experiment(), "snapshot_id": "snapshot"}
    sessions = _sessions()
    panel = pl.DataFrame(
        {
            "symbol": ["S00"],
            "session_ts": [sessions[0]],
            "available_at": [sessions[0] + timedelta(hours=23)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1_000.0],
        }
    ).select(PANEL_COLUMNS)
    monkeypatch.setattr(ml_input, "_experiment", lambda *args: experiment)
    monkeypatch.setattr("alpha_cli.ml_input._runner.verified_snapshot_hash", lambda *args: "a" * 64)
    monkeypatch.setattr(ml_input, "_aligned_panel", lambda **kwargs: (panel, tuple(sessions)))

    def accept_contract(
        spec_path: Path,
        panel_path: Path,
        exchange_dir: Path,
        *,
        worker_lock_path: Path | None = None,
    ) -> dict[str, object]:
        del spec_path, panel_path, worker_lock_path
        exchange_dir.mkdir()
        return {}

    output = tmp_path / "output"

    def concurrent_rename(source: Path, destination: Path) -> None:
        del source
        Path(destination).mkdir()
        raise OSError("already published")

    monkeypatch.setattr(ml_input, "prepare_exchange", accept_contract)
    monkeypatch.setattr("alpha_cli.ml_input.os.rename", concurrent_rename)
    with pytest.raises(DataError, match="already exists"):
        ml_input.export_project_input(
            data_dir=tmp_path / "data",
            project_id="project",
            experiment_id="experiment",
            output_dir=output,
            worker_project=worker,
        )


def test_worker_project_validation_and_plain_emission(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert ml_cmds._default_worker_project().name == "qlib"
    with pytest.raises(MLContractError, match="regular directory"):
        ml_cmds._worker_project(tmp_path / "missing")

    worker = tmp_path / "worker"
    worker.mkdir()
    with pytest.raises(MLContractError, match="pyproject.toml"):
        ml_cmds._worker_project(worker)
    (worker / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0'\n")
    with pytest.raises(MLContractError, match="regular uv.lock"):
        ml_cmds._worker_project(worker)
    (worker / "uv.lock").write_text("version = 1\n")
    assert ml_cmds._worker_project(worker) == (worker, worker / "uv.lock")

    ml_cmds._emit({"status": "ok", "rows": 20}, as_json=False)
    assert "status: ok" in capsys.readouterr().out


def test_export_and_prepare_commands_translate_boundary_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        ml_cmds,
        "export_project_input",
        lambda **kwargs: {"status": "generated", "project_id": kwargs["project_id"]},
    )
    ml_cmds.export_input("project", "experiment", tmp_path / "output", as_json=True)
    assert json.loads(capsys.readouterr().out)["status"] == "generated"

    def fail_export(**kwargs: object) -> dict[str, object]:
        del kwargs
        raise DataError("bad project")

    monkeypatch.setattr(ml_cmds, "export_project_input", fail_export)
    with pytest.raises(typer.BadParameter, match="bad project"):
        ml_cmds.export_input("project", "experiment", tmp_path / "output", as_json=True)

    with pytest.raises(typer.BadParameter, match="panel source"):
        ml_cmds.prepare(
            tmp_path / "spec.json",
            tmp_path / "panel.parquet",
            tmp_path / "exchange",
            worker_lock=None,
            as_json=True,
        )


def test_train_command_runs_a_locked_fake_worker(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exchange = _clone(boundary_fixture["result"], tmp_path)
    captured: dict[str, object] = {}

    def complete(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["command"] = command
        captured.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("alpha_cli.ml_cmds.shutil.which", lambda executable: f"/bin/{executable}")
    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", complete)
    ml_cmds.train(
        exchange,
        mode="fake",
        worker_project=boundary_fixture["worker"],
        no_sync=True,
        timeout_seconds=60,
        as_json=True,
    )
    summary = json.loads(capsys.readouterr().out)
    command = cast(list[str], captured["command"])
    environment = cast(dict[str, str], captured["env"])
    assert summary["status"] == "trained"
    assert "--no-sync" in command
    assert environment["PYTHONHASHSEED"] == "7"


def test_train_rejects_worker_that_rewrites_inputs_and_anchor_coherently(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _clone(boundary_fixture["result"], tmp_path)

    def tamper(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        request = _rewrite_request(
            exchange,
            lambda payload: payload.update({"snapshot_hash": "d" * 64}),
        )
        predictions = pl.read_parquet(exchange / "predictions.parquet").with_columns(
            pl.lit(request["config_hash"]).alias("config_hash")
        )
        _rewrite_predictions(exchange, predictions)
        _rewrite_result(
            exchange,
            lambda result: result.update(
                {
                    "request_sha256": sha256_file(exchange / "request.json"),
                    "snapshot_hash": request["snapshot_hash"],
                    "config_hash": request["config_hash"],
                }
            ),
        )
        _rewrite_input_anchor(exchange)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("alpha_cli.ml_cmds.shutil.which", lambda executable: f"/bin/{executable}")
    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", tamper)

    with pytest.raises(typer.BadParameter, match="changed after worker launch"):
        ml_cmds.train(
            exchange,
            mode="fake",
            worker_project=boundary_fixture["worker"],
            no_sync=True,
            timeout_seconds=60,
            as_json=True,
        )


def test_train_command_rejects_mode_lock_uv_failure_and_timeout(
    tmp_path: Path,
    boundary_fixture: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exchange = _clone(boundary_fixture["result"], tmp_path)
    with pytest.raises(typer.BadParameter, match="--mode"):
        ml_cmds.train(
            exchange,
            mode="gpu",
            worker_project=boundary_fixture["worker"],
            no_sync=False,
            timeout_seconds=60,
            as_json=True,
        )

    wrong_worker = tmp_path / "wrong-worker"
    shutil.copytree(boundary_fixture["worker"], wrong_worker)
    (wrong_worker / "uv.lock").write_text("version = 2\n")
    with pytest.raises(typer.BadParameter, match="does not match"):
        ml_cmds.train(
            exchange,
            mode="fake",
            worker_project=wrong_worker,
            no_sync=False,
            timeout_seconds=60,
            as_json=True,
        )

    monkeypatch.setattr("alpha_cli.ml_cmds.shutil.which", lambda executable: None)
    with pytest.raises(typer.BadParameter, match="uv is required"):
        ml_cmds.train(
            exchange,
            mode="fake",
            worker_project=boundary_fixture["worker"],
            no_sync=False,
            timeout_seconds=60,
            as_json=True,
        )

    monkeypatch.setattr("alpha_cli.ml_cmds.shutil.which", lambda executable: f"/bin/{executable}")

    def fail(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(command, 3, stdout="worker out\n", stderr="worker err\n")

    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", fail)
    with pytest.raises(typer.BadParameter, match="failed with exit 3"):
        ml_cmds.train(
            exchange,
            mode="fake",
            worker_project=boundary_fixture["worker"],
            no_sync=False,
            timeout_seconds=60,
            as_json=True,
        )

    def timeout(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del kwargs
        raise subprocess.TimeoutExpired(command, 60)

    monkeypatch.setattr("alpha_cli.ml_cmds.subprocess.run", timeout)
    with pytest.raises(typer.BadParameter, match="exceeded 60 seconds"):
        ml_cmds.train(
            exchange,
            mode="fake",
            worker_project=boundary_fixture["worker"],
            no_sync=False,
            timeout_seconds=60,
            as_json=True,
        )


def test_evaluate_prepare_replay_and_replay_translate_contract_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(typer.BadParameter, match="request.json"):
        ml_cmds.evaluate(tmp_path, as_json=True)
    with pytest.raises(typer.BadParameter, match="request.json"):
        ml_cmds.prepare_replay(tmp_path, tmp_path / "signals.parquet", as_json=True)

    monkeypatch.setattr(
        ml_cmds,
        "run_ml_replay",
        lambda *args, **kwargs: (_ for _ in ()).throw(DataError("replay rejected")),
    )
    with pytest.raises(typer.BadParameter, match="replay rejected"):
        ml_cmds.replay(tmp_path, starting_cash=1_000.0, periods_per_year=252, as_json=True)
