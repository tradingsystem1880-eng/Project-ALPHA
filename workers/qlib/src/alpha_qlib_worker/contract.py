"""Worker-side validation for the immutable ALPHA exchange request.

This is intentionally independent of ``alpha_cli`` so the worker can be installed, locked, and
removed without placing its dependency graph in the ALPHA process.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

import polars as pl

CONTRACT_SCHEMA_VERSION = 1
SUPPORTED_CONTRACT_SCHEMA_VERSIONS = frozenset({1, 2})
MIN_SYMBOLS = 20
MIN_ALIGNED_SESSIONS = 756
MIN_LABEL_BOUNDARY_GAP_SESSIONS = 1
DECISION_CLOSE_OFFSET = timedelta(hours=23)

PANEL_COLUMNS = [
    "symbol",
    "session_ts",
    "available_at",
    "open",
    "high",
    "low",
    "close",
    "volume",
]
PREDICTION_COLUMNS = [
    "symbol",
    "origin_ts",
    "available_at",
    "target_ts",
    "score",
    "fold",
    "split",
    "model_hash",
    "config_hash",
    "worker_lock_hash",
    "seed",
]

_REQUEST_FIELDS = {
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
_FOLD_FIELDS = {
    "fold",
    "train_start",
    "train_end",
    "validation_start",
    "validation_end",
    "test_start",
    "test_end",
}
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")
_MODEL_PARAMETER_RULES: dict[str, tuple[float, float, bool]] = {
    "bagging_fraction": (0.01, 1.0, False),
    "early_stopping_rounds": (1.0, 1000.0, True),
    "feature_fraction": (0.01, 1.0, False),
    "lambda_l1": (0.0, 1_000_000.0, False),
    "lambda_l2": (0.0, 1_000_000.0, False),
    "learning_rate": (0.0001, 1.0, False),
    "max_depth": (-1.0, 64.0, True),
    "min_data_in_leaf": (1.0, 1_000_000.0, True),
    "num_boost_round": (1.0, 5000.0, True),
    "num_leaves": (2.0, 4096.0, True),
    "num_threads": (1.0, 8.0, True),
}


@dataclass(frozen=True)
class WorkerRequest:
    payload: dict[str, Any]
    panel: pl.DataFrame
    universe: tuple[str, ...]
    sessions: tuple[datetime, ...]
    folds: tuple[dict[str, Any], ...]


def _fail(message: str) -> NoReturn:
    raise RuntimeError(message)


def _reject_constant(value: str) -> NoReturn:
    _fail(f"JSON contains forbidden non-finite constant {value}")


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def canonical_json_bytes(value: object) -> bytes:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        _fail(f"value is not canonical-JSON encodable: {exc}")
    return (encoded + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        _fail(f"cannot hash {path}: {exc}")
    return digest.hexdigest()


def compute_config_hash(request: dict[str, Any]) -> str:
    payload = copy.deepcopy(request)
    payload.pop("config_hash", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _exact(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(f"{label} must be an object")
    if set(value) != expected:
        _fail(
            f"{label} fields mismatch: missing={sorted(expected - set(value))}, "
            f"extra={sorted(set(value) - expected)}"
        )
    return value


def _timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        _fail(f"{label} must be a UTC ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        _fail(f"{label} must be a UTC ISO-8601 timestamp")
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None or offset.total_seconds() != 0:
        _fail(f"{label} must be a UTC ISO-8601 timestamp")
    return parsed


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        _fail(f"{label} must be a non-negative integer")
    return value


def _expected_panel_schema() -> dict[str, Any]:
    utc = pl.Datetime("us", "UTC")
    return {
        "symbol": pl.String,
        "session_ts": utc,
        "available_at": utc,
        "open": pl.Float64,
        "high": pl.Float64,
        "low": pl.Float64,
        "close": pl.Float64,
        "volume": pl.Float64,
    }


def _validate_panel(panel: pl.DataFrame, universe: tuple[str, ...]) -> tuple[datetime, ...]:
    if panel.columns != PANEL_COLUMNS or panel.schema != _expected_panel_schema():
        _fail("panel.parquet does not match the canonical panel schema")
    if any(count > 0 for count in panel.null_count().row(0)):
        _fail("panel.parquet canonical columns may not contain nulls")
    if not panel.equals(panel.sort(["session_ts", "symbol"])):
        _fail("panel.parquet must be sorted by session_ts, symbol")
    if panel.select(["session_ts", "symbol"]).is_duplicated().any():
        _fail("panel.parquet contains duplicate keys")
    if tuple(panel.get_column("symbol").unique().sort().to_list()) != universe:
        _fail("panel symbols do not match the frozen universe")
    sessions = tuple(panel.get_column("session_ts").unique(maintain_order=True).to_list())
    if len(universe) < MIN_SYMBOLS:
        _fail(f"starter experiment requires at least {MIN_SYMBOLS} symbols")
    if len(sessions) < MIN_ALIGNED_SESSIONS:
        _fail(f"starter experiment requires at least {MIN_ALIGNED_SESSIONS} aligned sessions")
    if panel.height != len(universe) * len(sessions):
        _fail("panel is not a fully aligned symbol/session rectangle")
    finite = panel.select(
        [
            pl.col(name).is_finite().all().alias(name)
            for name in ("open", "high", "low", "close", "volume")
        ]
    ).row(0)
    if not all(finite):
        _fail("panel OHLCV values must be finite")
    if panel.filter(
        (pl.col("open") <= 0)
        | (pl.col("high") <= 0)
        | (pl.col("low") <= 0)
        | (pl.col("close") <= 0)
        | (pl.col("volume") < 0)
        | (pl.col("low") > pl.min_horizontal("open", "close"))
        | (pl.col("high") < pl.max_horizontal("open", "close"))
        | (pl.col("low") > pl.col("high"))
    ).height:
        _fail("panel.parquet contains invalid OHLCV geometry")
    if panel.filter(pl.col("available_at") != pl.col("session_ts") + pl.duration(hours=23)).height:
        _fail("panel available_at must equal the canonical session close (session_ts + 23h)")
    return sessions


def _validate_folds(
    raw_folds: object,
    sessions: tuple[datetime, ...],
    *,
    purge: int,
    embargo: int,
) -> tuple[dict[str, Any], ...]:
    if not isinstance(raw_folds, list) or not raw_folds:
        _fail("folds must be a non-empty array")
    positions = {session: index for index, session in enumerate(sessions)}
    result: list[dict[str, Any]] = []
    previous_test_end = -1
    for expected_id, raw in enumerate(raw_folds):
        fold = _exact(raw, _FOLD_FIELDS, f"fold {expected_id}")
        if fold["fold"] != expected_id:
            _fail("fold ids must be sorted and contiguous from zero")
        parsed = {
            name: _timestamp(fold[name], f"fold {expected_id}.{name}")
            for name in _FOLD_FIELDS - {"fold"}
        }
        try:
            index = {name: positions[value] for name, value in parsed.items()}
        except KeyError:
            _fail(f"fold {expected_id} boundary is outside aligned sessions")
        if not (
            index["train_start"]
            <= index["train_end"]
            < index["validation_start"]
            <= index["validation_end"]
            < index["test_start"]
            <= index["test_end"]
        ):
            _fail(f"fold {expected_id} windows are not strictly ordered")
        if index["validation_start"] - index["train_end"] - 1 < purge:
            _fail(f"fold {expected_id} violates purge_sessions")
        if index["test_start"] - index["validation_end"] - 1 < embargo:
            _fail(f"fold {expected_id} violates embargo_sessions")
        if index["test_start"] <= previous_test_end:
            _fail("fold test windows must be strictly increasing and non-overlapping")
        if index["test_end"] >= len(sessions) - 1:
            _fail(f"fold {expected_id} test_end must retain a following aligned open")
        previous_test_end = index["test_end"]
        result.append({**fold, **parsed})
    return tuple(result)


def validate_request(exchange_dir: Path) -> WorkerRequest:
    exchange_dir = Path(exchange_dir)
    for path in exchange_dir.rglob("*"):
        if path.is_symlink() or (
            path.is_file() and path.suffix.lower() not in {".json", ".parquet"}
        ):
            _fail("exchange contains a non-portable file; only JSON and Parquet are allowed")
    request_path = exchange_dir / "request.json"
    panel_path = exchange_dir / "panel.parquet"
    if not request_path.is_file() or not panel_path.is_file():
        _fail("exchange requires request.json and panel.parquet")
    raw = request_path.read_bytes()
    try:
        request = json.loads(
            raw,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_no_duplicates,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        _fail(f"invalid request.json: {exc}")
    request = _exact(request, _REQUEST_FIELDS, "request")
    if raw != canonical_json_bytes(request):
        _fail("request.json is not canonical JSON")
    if request["schema_version"] not in SUPPORTED_CONTRACT_SCHEMA_VERSIONS:
        _fail("unsupported request schema_version")
    for name in ("snapshot_hash", "worker_lock_hash", "config_hash"):
        if not isinstance(request[name], str) or _HASH.fullmatch(request[name]) is None:
            _fail(f"{name} must be a SHA-256 hex digest")
    if request["config_hash"] != compute_config_hash(request):
        _fail("config_hash mismatch")
    _integer(request["seed"], "seed")
    universe_raw = request["universe"]
    if not isinstance(universe_raw, list) or not all(
        isinstance(item, str) for item in universe_raw
    ):
        _fail("universe must be an array of symbols")
    universe = tuple(universe_raw)
    if tuple(sorted(set(universe))) != universe or any(
        _SYMBOL.fullmatch(symbol) is None for symbol in universe
    ):
        _fail("universe must contain valid, sorted, unique symbols")
    panel_meta = _exact(request["panel"], {"path", "sha256", "rows"}, "panel")
    if panel_meta["path"] != "panel.parquet":
        _fail("panel.path must be panel.parquet")
    if panel_meta["sha256"] != sha256_file(panel_path):
        _fail("panel hash does not match panel.parquet")
    try:
        panel = pl.read_parquet(panel_path)
    except Exception as exc:
        _fail(f"cannot read panel.parquet: {exc}")
    if panel_meta["rows"] != panel.height:
        _fail("panel row count mismatch")
    sessions = _validate_panel(panel, universe)
    purge = max(
        _integer(request["purge_sessions"], "purge_sessions"),
        MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    )
    embargo = max(
        _integer(request["embargo_sessions"], "embargo_sessions"),
        MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    )
    folds = _validate_folds(request["folds"], sessions, purge=purge, embargo=embargo)

    feature = _exact(request["feature_recipe"], {"name", "version", "parameters"}, "feature_recipe")
    if feature["name"] != "alpha158" or feature["version"] != 1 or feature["parameters"] != {}:
        _fail("unsupported feature recipe")
    label = _exact(
        request["label_recipe"],
        {"name", "decision", "fill", "horizon_sessions"},
        "label_recipe",
    )
    if label != {
        "name": "next_session_open_to_open",
        "decision": "close_t",
        "fill": "open_t_plus_1",
        "horizon_sessions": 1,
    }:
        _fail("unsupported label recipe")
    model = _exact(request["model"], {"name", "parameters"}, "model")
    expected_model = "lightgbm" if request["schema_version"] == 1 else "rank_ensemble_v1"
    if model["name"] != expected_model or not isinstance(model["parameters"], dict):
        _fail("unsupported model recipe")
    unknown_model_parameters = sorted(set(model["parameters"]) - set(_MODEL_PARAMETER_RULES))
    if unknown_model_parameters:
        _fail(f"unsupported model parameters: {unknown_model_parameters}")
    for name, value in model["parameters"].items():
        minimum, maximum, integer = _MODEL_PARAMETER_RULES[name]
        if isinstance(value, bool) or not isinstance(value, int | float):
            _fail(f"model parameter {name} must be a finite number")
        number = float(value)
        if not math.isfinite(number) or not minimum <= number <= maximum:
            _fail(f"model parameter {name} is outside its bounded CPU recipe")
        if integer and not number.is_integer():
            _fail(f"model parameter {name} must be an integer")
    portfolio = _exact(request["portfolio"], {"selection", "weighting", "long_only"}, "portfolio")
    if portfolio != {
        "selection": "top_quintile",
        "weighting": "equal",
        "long_only": True,
    }:
        _fail("unsupported portfolio recipe")
    costs = _exact(request["costs"], {"fee_bps", "slippage_bps"}, "costs")
    for name in ("fee_bps", "slippage_bps"):
        value = costs[name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            _fail(f"costs.{name} must be a finite non-negative number")
    membership = request["universe_membership"]
    warning = request["survivorship_warning"]
    if membership not in {"point_in_time", "current_membership"}:
        _fail("unsupported universe_membership")
    if membership == "current_membership" and (not isinstance(warning, str) or not warning.strip()):
        _fail("current membership requires a permanent survivorship warning")
    return WorkerRequest(
        payload=request,
        panel=panel,
        universe=universe,
        sessions=sessions,
        folds=folds,
    )
