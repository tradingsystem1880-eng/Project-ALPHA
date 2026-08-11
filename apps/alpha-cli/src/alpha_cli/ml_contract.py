"""Portable JSON/Parquet contract for the isolated Qlib worker.

This module deliberately depends only on the ALPHA CLI's normal lightweight stack.  It never
imports Qlib, LightGBM, or the worker package and it never deserializes executable model objects.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, NoReturn

import polars as pl

CONTRACT_SCHEMA_VERSION = 1
SUPPORTED_CONTRACT_SCHEMA_VERSIONS = frozenset({1, 2})
INPUT_ANCHOR_FILENAME = "input_anchor.json"
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
ENSEMBLE_DIAGNOSTIC_COLUMNS = [
    "symbol",
    "origin_ts",
    "available_at",
    "target_ts",
    "fold",
    "split",
    "lightgbm_score",
    "ridge_score",
    "lightgbm_rank",
    "ridge_rank",
    "ensemble_score",
    "disagreement",
    "lightgbm_model_hash",
    "ridge_model_hash",
    "ensemble_model_hash",
    "config_hash",
    "worker_lock_hash",
    "seed",
]

_PANEL_SORT = ["session_ts", "symbol"]
_PREDICTION_SORT = ["fold", "split", "target_ts", "symbol", "origin_ts"]
_HASH = re.compile(r"^[0-9a-f]{64}$")
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,31}$")
_SAFE_SUFFIXES = {".json", ".parquet"}
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
_DRAFT_FIELDS = _REQUEST_FIELDS - {"panel", "config_hash"}
_FOLD_FIELDS = {
    "fold",
    "train_start",
    "train_end",
    "validation_start",
    "validation_end",
    "test_start",
    "test_end",
}
_RESULT_FIELDS = {
    "schema_version",
    "status",
    "request_sha256",
    "snapshot_hash",
    "config_hash",
    "worker_lock_hash",
    "seed",
    "worker",
    "predictions",
    "diagnostics",
    "diagnostic_only",
    "counterfactual_refit",
}
_RESULT_V2_FIELDS = _RESULT_FIELDS | {"ensemble_diagnostics"}
_INPUT_ANCHOR_FIELDS = {"schema_version", "request_sha256", "panel_sha256"}


class MLContractError(ValueError):
    """An exchange bundle is unsafe, corrupt, non-canonical, or semantically invalid."""


@dataclass(frozen=True)
class ValidatedRequest:
    request: dict[str, Any]
    panel: pl.DataFrame
    universe: tuple[str, ...]
    sessions: tuple[datetime, ...]


@dataclass(frozen=True)
class ValidatedResult:
    request: ValidatedRequest
    result: dict[str, Any]
    predictions: pl.DataFrame
    ensemble_diagnostics: pl.DataFrame | None


@dataclass(frozen=True)
class InputAnchor:
    """ALPHA-owned hashes of the exact request bytes handed to the isolated worker."""

    request_sha256: str
    panel_sha256: str
    schema_version: int = CONTRACT_SCHEMA_VERSION


def _reject_constant(value: str) -> NoReturn:
    raise MLContractError(f"JSON contains forbidden non-finite constant {value}")


def _pairs_no_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MLContractError(f"JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _load_json(path: Path, *, canonical: bool) -> dict[str, Any]:
    if not path.is_file():
        raise MLContractError(f"missing required {path.name}")
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw,
            parse_constant=_reject_constant,
            object_pairs_hook=_pairs_no_duplicates,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MLContractError(f"invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise MLContractError(f"{path.name} must contain a JSON object")
    if canonical and raw != canonical_json_bytes(value):
        raise MLContractError(
            f"{path.name} is not canonical JSON (sorted keys, compact separators, trailing newline)"
        )
    return value


def canonical_json_bytes(value: object) -> bytes:
    """RFC-8259-safe, byte-stable JSON used for every exchange control record."""
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise MLContractError(f"value is not canonical-JSON encodable: {exc}") from exc
    return (encoded + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise MLContractError(f"cannot hash {path}: {exc}") from exc
    return digest.hexdigest()


def compute_config_hash(request: dict[str, Any]) -> str:
    """Hash every immutable request field except the hash itself."""
    payload = copy.deepcopy(request)
    payload.pop("config_hash", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _require_exact_keys(value: object, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MLContractError(f"{label} must be a JSON object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise MLContractError(f"{label} fields mismatch: missing={missing}, extra={extra}")
    return value


def _require_int(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise MLContractError(f"{label} must be an integer >= {minimum}")
    return value


def _require_number(value: object, label: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLContractError(f"{label} must be a finite number >= {minimum}")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise MLContractError(f"{label} must be a finite number >= {minimum}")
    return result


def _as_finite_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLContractError(f"{label} is unavailable")
    result = float(value)
    if not math.isfinite(result):
        raise MLContractError(f"{label} is not finite")
    return result


def _require_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise MLContractError(f"{label} must be a lowercase 64-character SHA-256 hex digest")
    return value


def _parse_ts(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise MLContractError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise MLContractError(f"{label} must be an ISO-8601 timestamp") from exc
    offset = parsed.utcoffset()
    if parsed.tzinfo is None or offset is None:
        raise MLContractError(f"{label} must be timezone-aware")
    if offset.total_seconds() != 0:
        raise MLContractError(f"{label} must use UTC")
    return parsed


def _validate_portable_files(exchange_dir: Path) -> None:
    if not exchange_dir.is_dir():
        raise MLContractError(f"exchange directory does not exist: {exchange_dir}")
    for path in exchange_dir.rglob("*"):
        if path.is_symlink():
            raise MLContractError(f"exchange bundle may not contain symlinks: {path.name}")
        if path.is_file() and path.suffix.lower() not in _SAFE_SUFFIXES:
            raise MLContractError(
                f"exchange files must be portable JSON and Parquet only; found {path.name}"
            )


def _input_anchor_payload(exchange_dir: Path) -> dict[str, object]:
    request = _load_json(exchange_dir / "request.json", canonical=True)
    schema_version = _require_int(
        request.get("schema_version"), "request schema_version", minimum=1
    )
    if schema_version not in SUPPORTED_CONTRACT_SCHEMA_VERSIONS:
        raise MLContractError(f"unsupported request schema_version {schema_version}")
    return {
        "schema_version": schema_version,
        "request_sha256": sha256_file(exchange_dir / "request.json"),
        "panel_sha256": sha256_file(exchange_dir / "panel.parquet"),
    }


def _write_input_anchor(exchange_dir: Path) -> InputAnchor:
    payload = _input_anchor_payload(exchange_dir)
    (exchange_dir / INPUT_ANCHOR_FILENAME).write_bytes(canonical_json_bytes(payload))
    return InputAnchor(
        request_sha256=str(payload["request_sha256"]),
        panel_sha256=str(payload["panel_sha256"]),
        schema_version=_require_int(
            payload["schema_version"], "input anchor schema_version", minimum=1
        ),
    )


def validate_input_anchor(exchange_dir: Path) -> InputAnchor:
    """Verify the persisted ALPHA input anchor against the current request and panel bytes."""
    exchange_dir = Path(exchange_dir)
    payload = _require_exact_keys(
        _load_json(exchange_dir / INPUT_ANCHOR_FILENAME, canonical=True),
        _INPUT_ANCHOR_FIELDS,
        "input anchor",
    )
    if payload["schema_version"] not in SUPPORTED_CONTRACT_SCHEMA_VERSIONS:
        raise MLContractError("input anchor schema_version is unsupported")
    anchor = InputAnchor(
        request_sha256=_require_hash(payload["request_sha256"], "input anchor request_sha256"),
        panel_sha256=_require_hash(payload["panel_sha256"], "input anchor panel_sha256"),
        schema_version=_require_int(
            payload["schema_version"], "input anchor schema_version", minimum=1
        ),
    )
    actual = _input_anchor_payload(exchange_dir)
    if anchor.request_sha256 != actual["request_sha256"]:
        raise MLContractError("request.json no longer matches the ALPHA input anchor")
    if anchor.panel_sha256 != actual["panel_sha256"]:
        raise MLContractError("panel.parquet no longer matches the ALPHA input anchor")
    return anchor


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


def _expected_prediction_schema() -> dict[str, Any]:
    utc = pl.Datetime("us", "UTC")
    return {
        "symbol": pl.String,
        "origin_ts": utc,
        "available_at": utc,
        "target_ts": utc,
        "score": pl.Float64,
        "fold": pl.Int64,
        "split": pl.String,
        "model_hash": pl.String,
        "config_hash": pl.String,
        "worker_lock_hash": pl.String,
        "seed": pl.Int64,
    }


def _read_parquet(path: Path, label: str) -> pl.DataFrame:
    if not path.is_file():
        raise MLContractError(f"missing required {label}: {path.name}")
    try:
        return pl.read_parquet(path)
    except Exception as exc:
        raise MLContractError(f"cannot read {label} {path.name}: {exc}") from exc


def _validate_panel(panel: pl.DataFrame, universe: tuple[str, ...]) -> tuple[datetime, ...]:
    if panel.columns != PANEL_COLUMNS:
        raise MLContractError(
            f"panel.parquet must have exact columns {PANEL_COLUMNS}, got {panel.columns}"
        )
    expected_schema = _expected_panel_schema()
    if panel.schema != expected_schema:
        raise MLContractError(
            f"panel.parquet schema mismatch: expected {expected_schema}, got {panel.schema}"
        )
    if any(count > 0 for count in panel.null_count().row(0)):
        raise MLContractError("panel.parquet canonical columns may not contain nulls")
    if not panel.equals(panel.sort(_PANEL_SORT)):
        raise MLContractError(f"panel.parquet must be sorted by {_PANEL_SORT}")
    if panel.select(["session_ts", "symbol"]).is_duplicated().any():
        raise MLContractError("panel.parquet contains duplicate (session_ts, symbol) keys")

    panel_symbols = tuple(panel.get_column("symbol").unique().sort().to_list())
    if panel_symbols != universe:
        raise MLContractError("panel.parquet symbols must exactly match the frozen universe")
    sessions = tuple(panel.get_column("session_ts").unique(maintain_order=True).to_list())
    if len(sessions) < MIN_ALIGNED_SESSIONS:
        raise MLContractError(
            f"starter experiment requires at least {MIN_ALIGNED_SESSIONS} aligned sessions; "
            f"got {len(sessions)}"
        )
    expected_rows = len(universe) * len(sessions)
    if panel.height != expected_rows:
        raise MLContractError(
            "panel.parquet is not a fully aligned symbol/session rectangle: "
            f"expected {expected_rows} rows, got {panel.height}"
        )

    finite = panel.select(
        [
            pl.col(name).is_finite().all().alias(name)
            for name in ("open", "high", "low", "close", "volume")
        ]
    ).row(0)
    if not all(finite):
        raise MLContractError("panel OHLCV values must all be finite")
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
        raise MLContractError("panel.parquet contains invalid OHLCV geometry")
    if panel.filter(pl.col("available_at") != pl.col("session_ts") + pl.duration(hours=23)).height:
        raise MLContractError(
            "panel available_at must equal the canonical session close (session_ts + 23h)"
        )
    return sessions


def _validate_recipe_objects(request: dict[str, Any]) -> None:
    feature = _require_exact_keys(
        request["feature_recipe"], {"name", "version", "parameters"}, "feature_recipe"
    )
    if feature["name"] != "alpha158" or feature["version"] != 1:
        raise MLContractError("starter feature_recipe must be alpha158 version 1")
    if feature["parameters"] != {}:
        raise MLContractError(
            "alpha158 version 1 has a fixed recipe; feature_recipe.parameters must be empty"
        )

    label = _require_exact_keys(
        request["label_recipe"],
        {"name", "decision", "fill", "horizon_sessions"},
        "label_recipe",
    )
    expected_label = {
        "name": "next_session_open_to_open",
        "decision": "close_t",
        "fill": "open_t_plus_1",
        "horizon_sessions": 1,
    }
    if label != expected_label:
        raise MLContractError(
            "starter label_recipe must be next-session open-to-open for a "
            "close-t decision/open-t+1 fill"
        )

    model = _require_exact_keys(request["model"], {"name", "parameters"}, "model")
    if request["schema_version"] == 1 and (
        model["name"] != "lightgbm" or not isinstance(model["parameters"], dict)
    ):
        raise MLContractError("starter model must be lightgbm with a parameters object")
    if request["schema_version"] == 2 and (
        model["name"] != "rank_ensemble_v1" or not isinstance(model["parameters"], dict)
    ):
        raise MLContractError("schema v2 model must be rank_ensemble_v1 with a parameters object")
    unknown_parameters = sorted(set(model["parameters"]) - set(_MODEL_PARAMETER_RULES))
    if unknown_parameters:
        raise MLContractError(f"unsupported LightGBM parameters: {unknown_parameters}")
    for name, value in model["parameters"].items():
        minimum, maximum, integer = _MODEL_PARAMETER_RULES[name]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise MLContractError(f"model.parameters.{name} must be a finite number")
        number = float(value)
        if not math.isfinite(number) or not minimum <= number <= maximum:
            raise MLContractError(
                f"model.parameters.{name} must be between {minimum} and {maximum}"
            )
        if integer and not number.is_integer():
            raise MLContractError(f"model.parameters.{name} must be an integer")
    portfolio = _require_exact_keys(
        request["portfolio"], {"selection", "weighting", "long_only"}, "portfolio"
    )
    if portfolio != {
        "selection": "top_quintile",
        "weighting": "equal",
        "long_only": True,
    }:
        raise MLContractError("starter portfolio must be long-only, equal-weight, top-quintile")
    costs = _require_exact_keys(request["costs"], {"fee_bps", "slippage_bps"}, "costs")
    _require_number(costs["fee_bps"], "costs.fee_bps")
    _require_number(costs["slippage_bps"], "costs.slippage_bps")


def _validate_folds(
    request: dict[str, Any], sessions: tuple[datetime, ...]
) -> dict[int, dict[str, Any]]:
    raw_folds = request["folds"]
    if not isinstance(raw_folds, list) or not raw_folds:
        raise MLContractError("folds must be a non-empty array")
    purge = max(
        _require_int(request["purge_sessions"], "purge_sessions"),
        MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    )
    embargo = max(
        _require_int(request["embargo_sessions"], "embargo_sessions"),
        MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    )
    positions = {session: index for index, session in enumerate(sessions)}
    resolved: dict[int, dict[str, Any]] = {}
    previous_test_end = -1
    for expected_fold, raw in enumerate(raw_folds):
        fold = _require_exact_keys(raw, _FOLD_FIELDS, f"folds[{expected_fold}]")
        fold_id = _require_int(fold["fold"], f"folds[{expected_fold}].fold")
        if fold_id != expected_fold:
            raise MLContractError("fold ids must be unique, sorted, and contiguous from zero")
        parsed = {
            name: _parse_ts(fold[name], f"folds[{fold_id}].{name}")
            for name in _FOLD_FIELDS - {"fold"}
        }
        try:
            indices = {name: positions[value] for name, value in parsed.items()}
        except KeyError as exc:
            raise MLContractError(
                f"fold {fold_id} boundary {exc.args[0].isoformat()} is not an aligned session"
            ) from None
        if not (
            indices["train_start"]
            <= indices["train_end"]
            < indices["validation_start"]
            <= indices["validation_end"]
            < indices["test_start"]
            <= indices["test_end"]
        ):
            raise MLContractError(
                f"fold {fold_id} must order non-empty train, validation, and test windows"
            )
        purge_gap = indices["validation_start"] - indices["train_end"] - 1
        embargo_gap = indices["test_start"] - indices["validation_end"] - 1
        if purge_gap < purge:
            raise MLContractError(
                f"fold {fold_id} provides {purge_gap} purge sessions, requires {purge}"
            )
        if embargo_gap < embargo:
            raise MLContractError(
                f"fold {fold_id} provides {embargo_gap} embargo sessions, requires {embargo}"
            )
        if indices["test_start"] <= previous_test_end:
            raise MLContractError(
                "fold test windows must be strictly increasing and non-overlapping"
            )
        if indices["test_end"] >= len(sessions) - 1:
            raise MLContractError(
                f"fold {fold_id} test_end must retain a following aligned open for every target"
            )
        previous_test_end = indices["test_end"]
        resolved[fold_id] = {**fold, **parsed}
    return resolved


def _validate_request_payload(
    request: dict[str, Any], panel: pl.DataFrame, *, verify_config_hash: bool = True
) -> ValidatedRequest:
    _require_exact_keys(request, _REQUEST_FIELDS, "request")
    if request["schema_version"] not in SUPPORTED_CONTRACT_SCHEMA_VERSIONS:
        raise MLContractError(
            f"unsupported request schema_version {request['schema_version']!r}; "
            f"expected one of {sorted(SUPPORTED_CONTRACT_SCHEMA_VERSIONS)}"
        )
    _require_hash(request["snapshot_hash"], "snapshot_hash")
    _require_hash(request["worker_lock_hash"], "worker_lock_hash")
    _require_int(request["seed"], "seed")
    universe_raw = request["universe"]
    if not isinstance(universe_raw, list) or not all(isinstance(s, str) for s in universe_raw):
        raise MLContractError("universe must be an array of symbols")
    universe = tuple(universe_raw)
    if len(universe) < MIN_SYMBOLS:
        raise MLContractError(
            f"starter experiment requires at least {MIN_SYMBOLS} symbols; got {len(universe)}"
        )
    if tuple(sorted(set(universe))) != universe or any(
        _SYMBOL.fullmatch(s) is None for s in universe
    ):
        raise MLContractError("universe symbols must be valid, sorted, and unique")
    membership = request["universe_membership"]
    warning = request["survivorship_warning"]
    if membership not in {"point_in_time", "current_membership"}:
        raise MLContractError("universe_membership must be 'point_in_time' or 'current_membership'")
    if membership == "current_membership" and (not isinstance(warning, str) or not warning.strip()):
        raise MLContractError(
            "current_membership requires a permanent non-empty survivorship_warning"
        )
    if warning is not None and not isinstance(warning, str):
        raise MLContractError("survivorship_warning must be null or a string")
    _validate_recipe_objects(request)

    panel_meta = _require_exact_keys(request["panel"], {"path", "sha256", "rows"}, "panel")
    if panel_meta["path"] != "panel.parquet":
        raise MLContractError("panel.path must be exactly 'panel.parquet'")
    _require_hash(panel_meta["sha256"], "panel.sha256")
    if _require_int(panel_meta["rows"], "panel.rows", minimum=1) != panel.height:
        raise MLContractError("panel.rows does not match panel.parquet")
    sessions = _validate_panel(panel, universe)
    _validate_folds(request, sessions)
    expected_hash = compute_config_hash(request)
    if verify_config_hash and request["config_hash"] != expected_hash:
        raise MLContractError(
            f"config_hash mismatch: expected {expected_hash}, got {request['config_hash']!r}"
        )
    _require_hash(request["config_hash"], "config_hash")
    return ValidatedRequest(request=request, panel=panel, universe=universe, sessions=sessions)


def prepare_exchange(
    spec_path: Path,
    panel_path: Path,
    exchange_dir: Path,
    *,
    worker_lock_path: Path | None = None,
) -> dict[str, Any]:
    """Validate source inputs and atomically publish an immutable worker request bundle."""
    spec_path = Path(spec_path)
    panel_path = Path(panel_path)
    exchange_dir = Path(exchange_dir)
    if exchange_dir.exists():
        raise MLContractError(f"exchange directory already exists: {exchange_dir}")
    if panel_path.is_symlink() or not panel_path.is_file():
        raise MLContractError(f"panel source must be a regular Parquet file: {panel_path}")
    draft = _load_json(spec_path, canonical=False)
    _require_exact_keys(draft, _DRAFT_FIELDS, "experiment spec")
    panel = _read_parquet(panel_path, "panel source")
    request = copy.deepcopy(draft)
    request["panel"] = {
        "path": "panel.parquet",
        "sha256": sha256_file(panel_path),
        "rows": panel.height,
    }
    if worker_lock_path is not None:
        worker_lock_path = Path(worker_lock_path)
        if worker_lock_path.is_symlink() or not worker_lock_path.is_file():
            raise MLContractError(f"worker lock must be a regular file: {worker_lock_path}")
        actual_lock_hash = sha256_file(worker_lock_path)
        if request["worker_lock_hash"] != actual_lock_hash:
            raise MLContractError(
                "worker_lock_hash does not match the supplied worker lock: "
                f"expected {actual_lock_hash}"
            )
    request["config_hash"] = compute_config_hash(request)
    _validate_request_payload(request, panel)

    exchange_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(
        tempfile.mkdtemp(prefix=f".{exchange_dir.name}.", suffix=".tmp", dir=exchange_dir.parent)
    )
    try:
        shutil.copyfile(panel_path, temp_dir / "panel.parquet")
        (temp_dir / "request.json").write_bytes(canonical_json_bytes(request))
        _write_input_anchor(temp_dir)
        validate_request_bundle(temp_dir)
        os.replace(temp_dir, exchange_dir)
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return request


def validate_request_bundle(
    exchange_dir: Path, *, expected_input_anchor: InputAnchor | None = None
) -> ValidatedRequest:
    exchange_dir = Path(exchange_dir)
    _validate_portable_files(exchange_dir)
    request_path = exchange_dir / "request.json"
    request = _load_json(request_path, canonical=True)
    panel = _read_parquet(exchange_dir / "panel.parquet", "panel")
    panel_meta = request.get("panel")
    if isinstance(panel_meta, dict) and panel_meta.get("sha256") != sha256_file(
        exchange_dir / "panel.parquet"
    ):
        raise MLContractError("panel hash does not match panel.parquet")
    validated = _validate_request_payload(request, panel)
    input_anchor = validate_input_anchor(exchange_dir)
    if expected_input_anchor is not None and input_anchor != expected_input_anchor:
        raise MLContractError("ALPHA input anchor changed after worker launch")
    return validated


def _validate_result_payload(
    validated_request: ValidatedRequest,
    result: dict[str, Any],
    predictions: pl.DataFrame,
    *,
    exchange_dir: Path,
) -> None:
    request_schema = int(validated_request.request["schema_version"])
    expected_fields = _RESULT_FIELDS if request_schema == 1 else _RESULT_V2_FIELDS
    _require_exact_keys(result, expected_fields, "result")
    if result["schema_version"] != request_schema:
        raise MLContractError("result schema_version is unsupported")
    if result["status"] != "succeeded":
        raise MLContractError("result status must be 'succeeded'")
    request = validated_request.request
    expected_scalars = {
        "request_sha256": sha256_file(exchange_dir / "request.json"),
        "snapshot_hash": request["snapshot_hash"],
        "config_hash": request["config_hash"],
        "worker_lock_hash": request["worker_lock_hash"],
        "seed": request["seed"],
    }
    for name, expected in expected_scalars.items():
        if result[name] != expected:
            raise MLContractError(f"result {name} mismatch: expected {expected!r}")
    worker = _require_exact_keys(
        result["worker"], {"kind", "implementation_version"}, "result.worker"
    )
    if worker["kind"] not in {"fake", "qlib"} or not isinstance(
        worker["implementation_version"], str
    ):
        raise MLContractError("result.worker must identify fake or qlib and a version string")
    prediction_meta = _require_exact_keys(
        result["predictions"], {"path", "sha256", "rows"}, "result.predictions"
    )
    if prediction_meta["path"] != "predictions.parquet":
        raise MLContractError("result.predictions.path must be exactly 'predictions.parquet'")
    if prediction_meta["sha256"] != sha256_file(exchange_dir / "predictions.parquet"):
        raise MLContractError("prediction hash does not match predictions.parquet")
    if prediction_meta["rows"] != predictions.height:
        raise MLContractError("result.predictions.rows does not match predictions.parquet")
    if not isinstance(result["diagnostics"], dict):
        raise MLContractError("result.diagnostics must be a portable JSON object")
    if result["diagnostic_only"] is not True or result["counterfactual_refit"] is not False:
        raise MLContractError(
            "worker results must remain diagnostic_only with counterfactual_refit=false"
        )


def _expected_ensemble_diagnostic_schema() -> dict[str, Any]:
    utc = pl.Datetime("us", "UTC")
    return {
        "symbol": pl.String,
        "origin_ts": utc,
        "available_at": utc,
        "target_ts": utc,
        "fold": pl.Int64,
        "split": pl.String,
        "lightgbm_score": pl.Float64,
        "ridge_score": pl.Float64,
        "lightgbm_rank": pl.Float64,
        "ridge_rank": pl.Float64,
        "ensemble_score": pl.Float64,
        "disagreement": pl.Float64,
        "lightgbm_model_hash": pl.String,
        "ridge_model_hash": pl.String,
        "ensemble_model_hash": pl.String,
        "config_hash": pl.String,
        "worker_lock_hash": pl.String,
        "seed": pl.Int64,
    }


def _validate_ensemble_diagnostics(
    validated: ValidatedRequest,
    result: dict[str, Any],
    predictions: pl.DataFrame,
    diagnostics: pl.DataFrame,
    *,
    exchange_dir: Path,
) -> None:
    metadata = _require_exact_keys(
        result["ensemble_diagnostics"],
        {"schema", "schema_version", "path", "sha256", "rows"},
        "result.ensemble_diagnostics",
    )
    if metadata["schema"] != "QlibRankEnsembleDiagnosticsV1" or metadata["schema_version"] != 1:
        raise MLContractError("unsupported ensemble diagnostic schema")
    if metadata["path"] != "ensemble_diagnostics.parquet":
        raise MLContractError("ensemble diagnostic path must be ensemble_diagnostics.parquet")
    path = exchange_dir / "ensemble_diagnostics.parquet"
    if metadata["sha256"] != sha256_file(path) or metadata["rows"] != diagnostics.height:
        raise MLContractError("ensemble diagnostic hash or row count mismatch")
    if diagnostics.columns != ENSEMBLE_DIAGNOSTIC_COLUMNS:
        raise MLContractError("ensemble diagnostics columns do not match v1")
    if diagnostics.schema != _expected_ensemble_diagnostic_schema():
        raise MLContractError("ensemble diagnostics schema does not match v1")
    if diagnostics.height != predictions.height or any(
        count > 0 for count in diagnostics.null_count().row(0)
    ):
        raise MLContractError("ensemble diagnostics must align one-for-one without nulls")
    numeric = [
        "lightgbm_score",
        "ridge_score",
        "lightgbm_rank",
        "ridge_rank",
        "ensemble_score",
        "disagreement",
    ]
    if not all(diagnostics.get_column(name).is_finite().all() for name in numeric):
        raise MLContractError("ensemble diagnostic scores must be finite")
    if diagnostics.filter(
        (pl.col("lightgbm_rank") < 0)
        | (pl.col("lightgbm_rank") > 1)
        | (pl.col("ridge_rank") < 0)
        | (pl.col("ridge_rank") > 1)
        | (pl.col("disagreement") < 0)
        | (pl.col("disagreement") > 1)
    ).height:
        raise MLContractError("ensemble ranks and disagreement must lie in [0, 1]")
    keys = ["symbol", "origin_ts", "available_at", "target_ts", "fold", "split"]
    if not diagnostics.select(keys).equals(predictions.select(keys)):
        raise MLContractError("ensemble diagnostic keys must match canonical predictions")
    if not diagnostics.get_column("ensemble_score").equals(predictions.get_column("score")):
        raise MLContractError("ensemble_score must equal canonical prediction score")
    if not diagnostics.get_column("ensemble_model_hash").equals(
        predictions.get_column("model_hash")
    ):
        raise MLContractError("ensemble model hash must equal canonical prediction model_hash")
    if diagnostics.get_column("config_hash").unique().to_list() != [
        validated.request["config_hash"]
    ]:
        raise MLContractError("ensemble diagnostic config_hash mismatch")


def _validate_predictions(validated: ValidatedRequest, predictions: pl.DataFrame) -> None:
    if predictions.columns != PREDICTION_COLUMNS:
        raise MLContractError(
            f"predictions.parquet must have exact columns {PREDICTION_COLUMNS}, "
            f"got {predictions.columns}"
        )
    expected_schema = _expected_prediction_schema()
    if predictions.schema != expected_schema:
        raise MLContractError(
            "predictions.parquet schema mismatch: "
            f"expected {expected_schema}, got {predictions.schema}"
        )
    if any(count > 0 for count in predictions.null_count().row(0)):
        raise MLContractError("predictions.parquet canonical columns may not contain nulls")
    if predictions.is_empty():
        raise MLContractError("predictions.parquet may not be empty")
    duplicate_keys = ["symbol", "origin_ts", "target_ts", "fold", "split"]
    if predictions.select(duplicate_keys).is_duplicated().any():
        raise MLContractError("predictions.parquet contains a duplicate prediction key")
    if not predictions.get_column("score").is_finite().all():
        raise MLContractError("prediction scores must all be finite")

    request = validated.request
    fold_defs = _validate_folds(request, validated.sessions)
    declared_folds = set(fold_defs)
    actual_folds = set(predictions.get_column("fold").unique().to_list())
    if actual_folds != declared_folds:
        raise MLContractError("predictions must cover every declared fold exactly")
    splits = set(predictions.get_column("split").unique().to_list())
    if splits != {"test"}:
        raise MLContractError(
            "prediction split set must contain exactly the starter OOS 'test' split"
        )
    for name in ("model_hash", "config_hash", "worker_lock_hash"):
        values = predictions.get_column(name).unique().to_list()
        if any(not isinstance(value, str) or _HASH.fullmatch(value) is None for value in values):
            raise MLContractError(f"prediction {name} values must be SHA-256 hex digests")
    model_counts = predictions.group_by("fold").agg(pl.col("model_hash").n_unique())
    if model_counts.filter(pl.col("model_hash") != 1).height:
        raise MLContractError("each prediction fold must carry exactly one model_hash")
    if predictions.get_column("config_hash").unique().to_list() != [request["config_hash"]]:
        raise MLContractError("prediction config_hash does not match the request")
    if predictions.get_column("worker_lock_hash").unique().to_list() != [
        request["worker_lock_hash"]
    ]:
        raise MLContractError("prediction worker_lock_hash does not match the request")
    if predictions.get_column("seed").unique().to_list() != [request["seed"]]:
        raise MLContractError("prediction seed does not match the request")

    if predictions.select(["symbol", "target_ts"]).is_duplicated().any():
        raise MLContractError("prediction target overlap: a symbol/target appears more than once")
    session_position = {session: index for index, session in enumerate(validated.sessions)}
    panel_availability = {
        (row[0], row[1]): row[2]
        for row in validated.panel.select("symbol", "session_ts", "available_at").iter_rows()
    }
    universe_set = set(validated.universe)
    grouped_symbols: dict[tuple[int, str, datetime], set[str]] = {}
    for row in predictions.iter_rows(named=True):
        symbol = row["symbol"]
        origin = row["origin_ts"]
        available = row["available_at"]
        target = row["target_ts"]
        fold_id = row["fold"]
        split = row["split"]
        if symbol not in universe_set:
            raise MLContractError(f"prediction symbol {symbol!r} is outside the frozen universe")
        if available > origin + DECISION_CLOSE_OFFSET:
            raise MLContractError("prediction available_at may not be later than decision close")
        expected_available = panel_availability.get((symbol, origin))
        if expected_available is None or expected_available != available:
            raise MLContractError(
                "prediction available_at must equal the source panel availability at origin_ts"
            )
        target_index = session_position.get(target)
        origin_index = session_position.get(origin)
        if target_index is None or origin_index is None or target_index != origin_index + 1:
            raise MLContractError(
                "prediction target_ts must be the aligned session immediately after origin_ts"
            )
        if target_index + 1 >= len(validated.sessions):
            raise MLContractError(
                "prediction target_ts must have a following aligned open for its open-to-open label"
            )
        fold = fold_defs[fold_id]
        window_start = fold[f"{split}_start"]
        window_end = fold[f"{split}_end"]
        if not window_start <= target <= window_end:
            raise MLContractError(
                f"prediction target_ts is outside declared fold {fold_id} {split} window"
            )
        key = (fold_id, split, target)
        grouped_symbols.setdefault(key, set()).add(symbol)
    for key, symbols in grouped_symbols.items():
        if symbols != universe_set:
            raise MLContractError(
                f"prediction cross-section {key} must contain the complete frozen universe"
            )
    expected_cross_sections = {
        (fold_id, "test", session)
        for fold_id, fold in fold_defs.items()
        for session in validated.sessions
        if fold["test_start"] <= session <= fold["test_end"]
    }
    actual_cross_sections = set(grouped_symbols)
    if actual_cross_sections != expected_cross_sections:
        missing = len(expected_cross_sections - actual_cross_sections)
        unexpected = len(actual_cross_sections - expected_cross_sections)
        raise MLContractError(
            "predictions must contain the exact declared OOS target grid "
            f"(missing={missing}, unexpected={unexpected})"
        )
    if not predictions.equals(predictions.sort(_PREDICTION_SORT)):
        raise MLContractError(f"predictions.parquet must be sorted by {_PREDICTION_SORT}")


def validate_result_bundle(
    exchange_dir: Path, *, expected_input_anchor: InputAnchor | None = None
) -> ValidatedResult:
    exchange_dir = Path(exchange_dir)
    validated_request = validate_request_bundle(
        exchange_dir, expected_input_anchor=expected_input_anchor
    )
    _validate_portable_files(exchange_dir)
    result = _load_json(exchange_dir / "result.json", canonical=True)
    predictions = _read_parquet(exchange_dir / "predictions.parquet", "predictions")
    _validate_result_payload(validated_request, result, predictions, exchange_dir=exchange_dir)
    _validate_predictions(validated_request, predictions)
    ensemble_diagnostics: pl.DataFrame | None = None
    if validated_request.request["schema_version"] == 2:
        ensemble_diagnostics = _read_parquet(
            exchange_dir / "ensemble_diagnostics.parquet", "ensemble diagnostics"
        )
        _validate_ensemble_diagnostics(
            validated_request,
            result,
            predictions,
            ensemble_diagnostics,
            exchange_dir=exchange_dir,
        )
    return ValidatedResult(
        request=validated_request,
        result=result,
        predictions=predictions,
        ensemble_diagnostics=ensemble_diagnostics,
    )


def evaluate_result_bundle(exchange_dir: Path) -> dict[str, Any]:
    """Return portable diagnostics only; canonical ALPHA replay remains a later explicit step."""
    validated = validate_result_bundle(exchange_dir)
    scores = validated.predictions.get_column("score")
    score_min = _as_finite_float(scores.min(), "prediction score minimum")
    score_max = _as_finite_float(scores.max(), "prediction score maximum")
    score_mean = _as_finite_float(scores.mean(), "prediction score mean")
    score_std = _as_finite_float(scores.std(ddof=0), "prediction score standard deviation")
    return {
        "schema_version": validated.request.request["schema_version"],
        "authority": "diagnostic_only",
        "rows": validated.predictions.height,
        "symbols": validated.predictions.get_column("symbol").n_unique(),
        "targets": validated.predictions.get_column("target_ts").n_unique(),
        "folds": sorted(validated.predictions.get_column("fold").unique().to_list()),
        "score": {
            "min": score_min,
            "max": score_max,
            "mean": score_mean,
            "std": score_std,
        },
        "config_hash": validated.request.request["config_hash"],
        "worker_lock_hash": validated.request.request["worker_lock_hash"],
        "counterfactual_refit": False,
        "label": "OOS prediction contract validated — canonical ALPHA replay pending",
        "diagnostics": validated.result["diagnostics"],
        "next_required_step": (
            "canonical ALPHA replay: run `alpha ml replay EXCHANGE`; counterfactual refit remains "
            "required for null verdicts"
        ),
    }


def replay_signal_frame(exchange_dir: Path) -> pl.DataFrame:
    """Build the deterministic top-quintile/equal-weight handoff for the ALPHA composer.

    This is a causal signal contract, not a returns-level substitute for canonical engine replay.
    The current engine seam is single-instrument; the handoff keeps that remaining integration gap
    explicit while making every intended position inspectable and hashable.
    """
    validated = validate_result_bundle(exchange_dir)
    rows: list[dict[str, Any]] = []
    predictions = validated.predictions.filter(pl.col("split") == "test")
    for key, cross_section in predictions.group_by(
        ["fold", "split", "target_ts"], maintain_order=True
    ):
        fold, split, target_ts = key
        ranked = cross_section.sort(
            ["score", "symbol"], descending=[True, False], maintain_order=True
        )
        selected_count = max(1, math.ceil(ranked.height * 0.2))
        weight = 1.0 / selected_count
        for rank, row in enumerate(ranked.iter_rows(named=True), start=1):
            selected = rank <= selected_count
            rows.append(
                {
                    "symbol": row["symbol"],
                    "origin_ts": row["origin_ts"],
                    "decision_ts": row["available_at"],
                    "available_at": row["available_at"],
                    "entry_ts": row["target_ts"],
                    "score": row["score"],
                    "cross_section_rank": rank,
                    "selected": selected,
                    "target_weight": weight if selected else 0.0,
                    "fold": int(fold),
                    "split": str(split),
                    "model_hash": row["model_hash"],
                    "config_hash": row["config_hash"],
                }
            )
    return pl.DataFrame(
        rows,
        schema={
            "symbol": pl.String,
            "origin_ts": pl.Datetime("us", "UTC"),
            "decision_ts": pl.Datetime("us", "UTC"),
            "available_at": pl.Datetime("us", "UTC"),
            "entry_ts": pl.Datetime("us", "UTC"),
            "score": pl.Float64,
            "cross_section_rank": pl.Int64,
            "selected": pl.Boolean,
            "target_weight": pl.Float64,
            "fold": pl.Int64,
            "split": pl.String,
            "model_hash": pl.String,
            "config_hash": pl.String,
        },
    ).sort(["fold", "split", "entry_ts", "cross_section_rank", "symbol"])


def publish_replay_signal_frame(exchange_dir: Path, output_path: Path) -> pl.DataFrame:
    """Atomically publish or verify an immutable portable replay-signal handoff."""
    frame = replay_signal_frame(exchange_dir)
    output_path = Path(output_path)
    if output_path.suffix.lower() != ".parquet":
        raise MLContractError("replay handoff output must use a .parquet suffix")
    if output_path.is_symlink():
        raise MLContractError("replay handoff output may not be a symlink")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fd, raw_temp = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    os.close(fd)
    temp = Path(raw_temp)
    try:
        frame.write_parquet(temp)
        if output_path.exists():
            if sha256_file(output_path) == sha256_file(temp):
                return frame
            raise MLContractError(
                f"immutable replay handoff {output_path} already exists with different bytes"
            )
        try:
            os.link(temp, output_path)
        except FileExistsError:
            if sha256_file(output_path) != sha256_file(temp):
                raise MLContractError(
                    f"replay handoff {output_path} was concurrently published differently"
                ) from None
    finally:
        temp.unlink(missing_ok=True)
    return frame
