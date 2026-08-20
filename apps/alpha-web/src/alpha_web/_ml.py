"""Bounded Workstation projections and actions for the isolated Qlib worker.

The web process never imports Qlib or LightGBM and never accepts a filesystem path from a client.
Opaque identifiers resolve under the CLI-owned ``data/control/ml`` exchange root.  Every mutation
is an allowlisted ``alpha ml`` subprocess and every background action is mirrored into the durable
``alpha project job-*`` journal.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import subprocess
import threading
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, NoReturn, cast

import polars as pl

from alpha_cli.artifact_contract import sha256_file, verify_manifest_artifacts
from alpha_cli.durable_lease import (
    DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    DurableJobLease,
    DurableLeaseCancelled,
    DurableLeaseError,
    terminate_and_reap,
)
from alpha_cli.job_capacity import HEAVYWEIGHT_JOB_CAPACITY, HEAVYWEIGHT_JOB_KINDS
from alpha_cli.ml_contract import MIN_ALIGNED_SESSIONS, MIN_SYMBOLS
from alpha_cli.run_store import find_run_dir, read_manifest
from alpha_core import DataError
from alpha_web._catalog import _cli_environment, _command, _run_json, _strip_ansi
from alpha_web._catalog import commands as _catalog_commands

MlAction = Literal[
    "export-input",
    "prepare",
    "train",
    "import",
    "prepare-replay",
    "replay",
    "generate-experiment",
]

_ID = re.compile(r"^[0-9a-f]{16,64}$")
_MAX_CONTROL_JSON_BYTES = 16 * 1024 * 1024
_TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}
_ACTIVE_STATUSES = {"queued", "running"}
_DURABLE_HEARTBEAT_INTERVAL_S = DEFAULT_HEARTBEAT_INTERVAL_SECONDS
_DURABLE_HEARTBEAT_TIMEOUT_S = 5.0
_JOB_KIND: dict[MlAction, str] = {
    "export-input": "ml_export_input",
    "prepare": "ml_prepare",
    "train": "ml_train",
    "import": "ml_import",
    "prepare-replay": "ml_prepare_replay",
    "replay": "ml_replay",
    "generate-experiment": "ml_prepare",
}


class MlError(RuntimeError):
    """The bounded ML control surface cannot satisfy a request safely."""


class MlNotFoundError(MlError):
    """An opaque ML resource identifier is invalid or absent."""


class MlBusyError(MlError):
    """The one-heavy-job workstation limit is already occupied."""


def _worker_project() -> Path:
    return Path(__file__).resolve().parents[4] / "workers" / "qlib"


def _ml_root(data_dir: Path) -> Path:
    return Path(data_dir) / "control" / "ml"


def _safe_id(value: str, label: str) -> str:
    if _ID.fullmatch(value) is None:
        raise MlNotFoundError(f"invalid {label}")
    return value


def _resource_dir(data_dir: Path, collection: str, resource_id: str, label: str) -> Path:
    safe = _safe_id(resource_id, label)
    path = _ml_root(data_dir) / collection / safe
    if path.is_symlink() or not path.is_dir():
        raise MlNotFoundError(f"{label} must resolve to an existing regular directory")
    return path


def _exchange_dir(exchange_id: str, *, data_dir: Path) -> Path:
    return _resource_dir(data_dir, "exchanges", exchange_id, "exchange_id")


def _reject_constant(value: str) -> NoReturn:
    raise MlError(f"immutable JSON contains forbidden non-finite constant {value}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise MlError(f"immutable JSON contains duplicate key {key!r}")
        result[key] = value
    return result


def _json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            raise MlError(f"invalid immutable {label}")
        size = path.stat().st_size
        if size > _MAX_CONTROL_JSON_BYTES:
            raise MlError(f"{label} exceeds the bounded control-record size")
        value: object = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_pairs,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MlError(f"invalid immutable {label}") from exc
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MlError(f"invalid immutable {label}")
    return cast(dict[str, Any], value)


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise MlError(f"invalid {label} projection")
    return cast(dict[str, Any], value)


def _objects(value: object, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise MlError(f"invalid {label} projection")
    return [_object(item, label) for item in value]


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise MlError(f"{label} must be finite")
    result = float(value)
    if not math.isfinite(result):
        raise MlError(f"{label} must be finite")
    return result


def _optional_finite(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _finite(value, label)


def _page(items: Sequence[dict[str, Any]], *, limit: int, offset: int) -> dict[str, Any]:
    return {
        "items": list(items[offset : offset + limit]),
        "limit": limit,
        "offset": offset,
        "total": len(items),
        "has_more": offset + limit < len(items),
    }


def _input_summary(input_id: str, path: Path) -> dict[str, Any]:
    spec = path / "spec.json"
    panel = path / "panel.parquet"
    spec_present = spec.is_file() and not spec.is_symlink()
    panel_present = panel.is_file() and not panel.is_symlink()
    return {
        "input_bundle_id": input_id,
        "spec_present": spec_present,
        "panel_present": panel_present,
        "ready": spec_present and panel_present,
    }


def input_bundle(input_bundle_id: str, *, data_dir: Path) -> dict[str, Any]:
    path = _resource_dir(data_dir, "inputs", input_bundle_id, "input_bundle_id")
    return _input_summary(input_bundle_id, path)


def list_input_bundles(*, data_dir: Path, limit: int, offset: int) -> dict[str, Any]:
    root = _ml_root(data_dir) / "inputs"
    if not root.is_dir():
        return _page([], limit=limit, offset=offset)
    items = [
        _input_summary(path.name, path)
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if _ID.fullmatch(path.name) is not None and path.is_dir() and not path.is_symlink()
    ]
    return _page(items, limit=limit, offset=offset)


def _contract(request: Mapping[str, Any]) -> dict[str, Any]:
    panel = _object(request.get("panel"), "ML panel contract")
    return {
        "schema_version": request.get("schema_version"),
        "snapshot_hash": request.get("snapshot_hash"),
        "config_hash": request.get("config_hash"),
        "worker_lock_hash": request.get("worker_lock_hash"),
        "universe": request.get("universe"),
        "universe_count": len(request.get("universe", [])),
        "universe_membership": request.get("universe_membership"),
        "survivorship_warning": request.get("survivorship_warning"),
        "feature_recipe": request.get("feature_recipe"),
        "label_recipe": request.get("label_recipe"),
        "model": request.get("model"),
        "portfolio": request.get("portfolio"),
        "costs": request.get("costs"),
        "folds": request.get("folds"),
        "purge_sessions": request.get("purge_sessions"),
        "embargo_sessions": request.get("embargo_sessions"),
        "seed": request.get("seed"),
        "panel_sha256": panel.get("sha256"),
        "panel_rows": panel.get("rows"),
    }


def _exchange_summary(exchange_id: str, path: Path) -> dict[str, Any]:
    request_path = path / "request.json"
    result_path = path / "result.json"
    request = _json_object(request_path, "ML request") if request_path.is_file() else None
    result = _json_object(result_path, "ML result") if result_path.is_file() else None
    status = "empty"
    if request is not None:
        status = "prepared"
    if result is not None:
        status = "trained"
    if (path / "replay_signals.parquet").is_file():
        status = "replay_handoff_prepared"
    return {
        "exchange_id": exchange_id,
        "status": status,
        "config_hash": None if request is None else request.get("config_hash"),
        "snapshot_hash": None if request is None else request.get("snapshot_hash"),
        "worker_kind": (
            None if result is None else _object(result.get("worker"), "worker").get("kind")
        ),
        "prediction_rows": (
            None
            if result is None
            else _object(result.get("predictions"), "predictions").get("rows")
        ),
        "diagnostic_only": None if result is None else result.get("diagnostic_only"),
        "counterfactual_refit": None if result is None else result.get("counterfactual_refit"),
    }


def list_exchanges(*, data_dir: Path, limit: int, offset: int) -> dict[str, Any]:
    root = _ml_root(data_dir) / "exchanges"
    if not root.is_dir():
        return _page([], limit=limit, offset=offset)
    items = [
        _exchange_summary(path.name, path)
        for path in sorted(root.iterdir(), key=lambda item: item.name, reverse=True)
        if _ID.fullmatch(path.name) is not None and path.is_dir() and not path.is_symlink()
    ]
    return _page(items, limit=limit, offset=offset)


def exchange_detail(exchange_id: str, *, data_dir: Path) -> dict[str, Any]:
    path = _exchange_dir(exchange_id, data_dir=data_dir)
    summary = _exchange_summary(exchange_id, path)
    request = _json_object(path / "request.json", "ML request")
    result_path = path / "result.json"
    result_summary: dict[str, Any] | None = None
    if result_path.is_file():
        _run_json(["ml", "import", str(path), "--json"], data_dir=data_dir)
        result = _json_object(result_path, "ML result")
        worker = _object(result.get("worker"), "worker")
        predictions = _object(result.get("predictions"), "predictions")
        result_summary = {
            "status": result.get("status"),
            "worker_kind": worker.get("kind"),
            "worker_implementation_version": worker.get("implementation_version"),
            "prediction_rows": predictions.get("rows"),
            "prediction_sha256": predictions.get("sha256"),
            "diagnostic_only": result.get("diagnostic_only"),
            "counterfactual_refit": result.get("counterfactual_refit"),
        }
    return {**summary, "contract": _contract(request), "result": result_summary}


def exchange_result(exchange_id: str, *, data_dir: Path) -> dict[str, Any]:
    """One validated worker completion summary, without executable model material."""
    result = exchange_detail(exchange_id, data_dir=data_dir)["result"]
    if not isinstance(result, dict):
        raise MlNotFoundError("worker result is not available")
    return cast(dict[str, Any], result)


def evaluate_exchange(exchange_id: str, *, data_dir: Path) -> dict[str, Any]:
    path = _exchange_dir(exchange_id, data_dir=data_dir)
    result = _run_json(["ml", "evaluate", str(path), "--json"], data_dir=data_dir)
    body = _object(result, "ML evaluation")
    body.pop("exchange", None)
    return body


def _bounded_series(values: object, limit: int) -> list[float]:
    if not isinstance(values, list):
        raise MlError("training history must contain arrays")
    resolved = [_finite(value, "training history") for value in values]
    if len(resolved) <= limit:
        return resolved
    if limit == 1:
        return [resolved[-1]]
    indices = [round(index * (len(resolved) - 1) / (limit - 1)) for index in range(limit)]
    return [resolved[index] for index in indices]


def _fold_diagnostics(raw: object, *, history_limit: int) -> list[dict[str, Any]]:
    folds = _objects(raw, "fold diagnostics")
    result: list[dict[str, Any]] = []
    for fold in folds[:50]:
        training = _object(fold.get("training_history"), "training history")
        bounded_history: dict[str, dict[str, list[float]]] = {}
        for split, raw_metrics in training.items():
            metrics = _object(raw_metrics, "training metrics")
            bounded_history[split] = {
                metric: _bounded_series(values, history_limit) for metric, values in metrics.items()
            }
        normalization = _object(fold.get("normalization"), "normalization")
        boundaries = _object(fold.get("boundaries"), "fold boundaries")
        result.append(
            {
                "fold": fold.get("fold"),
                "fit_count": fold.get("fit_count"),
                "train_rows": fold.get("train_rows"),
                "validation_rows": fold.get("validation_rows"),
                "test_rows": fold.get("test_rows"),
                "best_iteration": fold.get("best_iteration"),
                "model_hash": fold.get("model_hash"),
                "normalization": {
                    "method": normalization.get("method"),
                    "statistics_hash": normalization.get("statistics_hash"),
                    "all_missing_train_features": normalization.get("all_missing_train_features"),
                },
                "training_history": bounded_history,
                "boundaries": {
                    name: boundaries.get(name)
                    for name in (
                        "train_start",
                        "train_end",
                        "validation_start",
                        "validation_end",
                        "test_start",
                        "test_end",
                    )
                },
            }
        )
    return result


def exchange_tearsheet(
    exchange_id: str,
    *,
    data_dir: Path,
    feature_limit: int,
    timeline_limit: int,
    timeline_offset: int,
    history_limit: int,
) -> dict[str, Any]:
    path = _exchange_dir(exchange_id, data_dir=data_dir)
    result_path = path / "result.json"
    if not result_path.is_file():
        return {
            "available": False,
            "exchange_id": exchange_id,
            "authority": "unavailable",
            "label": "Worker result is not available",
            "counterfactual_refit": False,
            "versions": None,
            "feature_recipe": None,
            "label_recipe": None,
            "score_distribution": None,
            "ic": None,
            "quantile_returns": [],
            "portfolio": None,
            "feature_importance": [],
            "feature_importance_truncated": False,
            "folds": [],
            "timeline_total": 0,
            "timeline_offset": timeline_offset,
            "timeline_limit": timeline_limit,
            "timeline_has_more": False,
        }
    evaluation = evaluate_exchange(exchange_id, data_dir=data_dir)
    diagnostics = _object(evaluation.get("diagnostics"), "worker diagnostics")
    if diagnostics.get("authority") != "qlib_diagnostic_only":
        return {
            "available": False,
            "exchange_id": exchange_id,
            "authority": "diagnostic_unavailable",
            "label": "Typed Qlib diagnostics are unavailable for this worker mode",
            "counterfactual_refit": False,
            "versions": None,
            "feature_recipe": None,
            "label_recipe": None,
            "score_distribution": None,
            "ic": None,
            "quantile_returns": [],
            "portfolio": None,
            "feature_importance": [],
            "feature_importance_truncated": False,
            "folds": [],
            "timeline_total": 0,
            "timeline_offset": timeline_offset,
            "timeline_limit": timeline_limit,
            "timeline_has_more": False,
        }
    signal = _object(diagnostics.get("signal_analysis"), "signal analysis")
    raw_ic = _object(signal.get("ic"), "IC diagnostics")
    ic_rows = _objects(raw_ic.get("by_target"), "IC timeline")
    raw_portfolio = _object(signal.get("portfolio"), "diagnostic portfolio")
    portfolio_rows = _objects(raw_portfolio.get("timeline"), "portfolio timeline")
    if len(ic_rows) != len(portfolio_rows):
        raise MlError("Qlib IC and portfolio diagnostic timelines are misaligned")
    selected_ic = ic_rows[timeline_offset : timeline_offset + timeline_limit]
    selected_portfolio = portfolio_rows[timeline_offset : timeline_offset + timeline_limit]
    feature_rows = _objects(diagnostics.get("feature_importance"), "feature importance")
    score = _object(diagnostics.get("score_distribution"), "score distribution")
    portfolio = {
        key: raw_portfolio.get(key)
        for key in (
            "selection",
            "declared_costs",
            "periods",
            "gross_total_return",
            "costed_total_return",
            "benchmark_total_return",
            "costed_excess_total_return",
            "mean_turnover",
        )
    }
    portfolio["timeline"] = selected_portfolio
    return {
        "available": True,
        "exchange_id": exchange_id,
        "authority": diagnostics.get("authority"),
        "label": diagnostics.get("label"),
        "counterfactual_refit": diagnostics.get("counterfactual_refit"),
        "versions": diagnostics.get("versions"),
        "feature_recipe": diagnostics.get("feature_recipe"),
        "label_recipe": diagnostics.get("label_recipe"),
        "score_distribution": {
            name: _finite(score.get(name), f"score_distribution.{name}")
            for name in ("min", "max", "mean", "std", "q05", "q25", "q50", "q75", "q95")
        },
        "ic": {
            "mean": _optional_finite(raw_ic.get("mean"), "IC mean"),
            "rank_mean": _optional_finite(raw_ic.get("rank_mean"), "RankIC mean"),
            "by_target": selected_ic,
        },
        "quantile_returns": signal.get("quantile_returns"),
        "portfolio": portfolio,
        "feature_importance": feature_rows[:feature_limit],
        "feature_importance_truncated": len(feature_rows) > feature_limit,
        "folds": _fold_diagnostics(diagnostics.get("folds"), history_limit=history_limit),
        "timeline_total": len(portfolio_rows),
        "timeline_offset": timeline_offset,
        "timeline_limit": timeline_limit,
        "timeline_has_more": timeline_offset + timeline_limit < len(portfolio_rows),
    }


def _iso_rows(frame: pl.DataFrame) -> list[dict[str, Any]]:
    rows = frame.to_dicts()
    for row in rows:
        for key, value in list(row.items()):
            if hasattr(value, "isoformat"):
                row[key] = value.isoformat()
    return rows


def replay_tearsheet(run_id: str, *, data_dir: Path, limit: int, offset: int) -> dict[str, Any]:
    rdir = find_run_dir(data_dir, run_id)
    if rdir is None:
        raise MlNotFoundError("unknown ML replay run")
    manifest = read_manifest(rdir)
    if manifest.get("command") != "ml_replay":
        raise MlNotFoundError("run is not an ML replay")
    try:
        verify_manifest_artifacts(rdir, manifest)
    except DataError as exc:
        raise MlError("ML replay artifact contract failed verification") from exc
    artifacts = _object(manifest.get("artifacts"), "artifact contract")
    required = {
        "ml_predictions.parquet",
        "ml_signals.parquet",
        "ml_periods.parquet",
        "folds.parquet",
    }
    if not required <= set(artifacts):
        raise MlError("ML replay is missing required typed artifacts")
    predictions = pl.read_parquet(rdir / "ml_predictions.parquet")
    signals = pl.read_parquet(rdir / "ml_signals.parquet")
    periods = pl.read_parquet(rdir / "ml_periods.parquet").sort("target_ts")
    folds = pl.read_parquet(rdir / "folds.parquet").sort("fold")
    if "selected" not in signals.columns:
        raise MlError("ML signal artifact is missing selected")
    page = periods.slice(offset, limit)
    validation = _object(manifest.get("validation"), "ML replay validation")
    provenance = {
        name: _object(artifacts[name], f"artifact {name}").get("sha256")
        for name in sorted(required)
    }
    return {
        "run_id": run_id,
        "authority": manifest.get("authority"),
        "label": manifest.get("label"),
        "config_hash": manifest.get("config_hash"),
        "snapshot_hash": manifest.get("snapshot_hash"),
        "worker_lock_hash": manifest.get("worker_lock_hash"),
        "universe": manifest.get("universe"),
        "universe_membership": manifest.get("universe_membership"),
        "survivorship_warning": manifest.get("survivorship_warning"),
        "metrics": manifest.get("metrics"),
        "validation": validation,
        "promotion_eligible": bool(validation.get("promotion_eligible", False)),
        "counterfactual_refit": bool(validation.get("counterfactual_refit", False)),
        "prediction_rows": predictions.height,
        "signal_rows": signals.height,
        "selected_signals": signals.filter(pl.col("selected")).height,
        "folds": _iso_rows(folds.head(50)),
        "periods": _iso_rows(page),
        "periods_total": periods.height,
        "periods_limit": limit,
        "periods_offset": offset,
        "periods_has_more": offset + limit < periods.height,
        "artifact_provenance": provenance,
    }


def _durable_jobs(*, data_dir: Path) -> list[dict[str, Any]]:
    value = _run_json(
        ["project", "job-list", "--limit", "100", "--offset", "0", "--json"],
        data_dir=data_dir,
    )
    return _objects(value, "durable job list")


def _heavy_busy(*, data_dir: Path) -> bool:
    return bool(_heavy_capacity(data_dir=data_dir)["busy"])


def _heavy_capacity(*, data_dir: Path) -> dict[str, Any]:
    value = _object(
        _run_json(["project", "job-capacity", "--json"], data_dir=data_dir),
        "heavyweight job capacity",
    )
    if (
        value.get("capacity_class") != "heavyweight"
        or value.get("limit") != HEAVYWEIGHT_JOB_CAPACITY
        or not isinstance(value.get("busy"), bool)
    ):
        raise MlError("invalid heavyweight job capacity projection")
    active = _objects(value.get("active_jobs"), "active heavyweight jobs")
    for row in active:
        if row.get("kind") not in HEAVYWEIGHT_JOB_KINDS:
            raise MlError("invalid heavyweight job kind in capacity projection")
        if row.get("status") not in _ACTIVE_STATUSES:
            raise MlError("invalid terminal job in active heavyweight capacity")
    if value.get("active_count") != len(active) or value["busy"] != (
        len(active) >= HEAVYWEIGHT_JOB_CAPACITY
    ):
        raise MlError("inconsistent heavyweight job capacity projection")
    value["active_jobs"] = active
    return value


def readiness(*, data_dir: Path) -> dict[str, Any]:
    project = _worker_project()
    lock = project / "uv.lock"
    root_qlib = importlib.util.find_spec("qlib") is not None
    root_lightgbm = importlib.util.find_spec("lightgbm") is not None
    project_present = (
        project.is_dir() and not project.is_symlink() and (project / "pyproject.toml").is_file()
    )
    lock_present = lock.is_file() and not lock.is_symlink()
    environment_present = (project / ".venv" / "pyvenv.cfg").is_file()
    return {
        "schema_version": 1,
        "worker_project_present": project_present,
        "worker_lock_present": lock_present,
        "worker_environment_present": environment_present,
        "worker_lock_hash": sha256_file(lock) if lock_present else None,
        "root_qlib_importable": root_qlib,
        "root_lightgbm_importable": root_lightgbm,
        "isolation_ready": project_present and lock_present and not root_qlib and not root_lightgbm,
        "heavy_job_limit": HEAVYWEIGHT_JOB_CAPACITY,
        "heavy_job_busy": _heavy_busy(data_dir=data_dir),
        "supported_modes": ["fake", "real"],
    }


def _has_input_producer(*, data_dir: Path) -> bool:
    return any(
        row.get("id") in {"ml export-input", "ml prepare-input"}
        for row in _catalog_commands(data_dir=data_dir)
    )


def service_status(*, data_dir: Path) -> dict[str, Any]:
    """Compact compatibility projection consumed by the v3 ML Research panel."""
    isolation = readiness(data_dir=data_dir)
    capacity = _heavy_capacity(data_dir=data_dir)
    active_jobs = cast(list[dict[str, Any]], capacity["active_jobs"])
    active = active_jobs[0] if active_jobs else None
    producer = _has_input_producer(data_dir=data_dir)
    isolation_ready = bool(isolation["isolation_ready"])
    message: str | None = None
    if not isolation_ready:
        message = "The isolated Qlib worker project/lock is unavailable or root isolation failed."
    elif not producer:
        message = (
            "Worker isolation is ready; the CLI-owned frozen-snapshot panel producer is "
            "not yet available."
        )
    elif active is not None:
        message = "One heavyweight Qlib or Kronos job is already active."
    return {
        "available": isolation_ready,
        "worker_ready": isolation_ready and producer,
        "isolation": "separate worker project, lock, process, and portable artifact boundary",
        "concurrency_limit": HEAVYWEIGHT_JOB_CAPACITY,
        "active_job_id": None if active is None else active.get("job_id"),
        "min_symbols": 20,
        "min_aligned_sessions": 756,
        "message": message,
    }


def _preflight_check(
    check_id: str,
    passed: bool,
    message: str,
    recovery_action: str,
) -> dict[str, str]:
    return {
        "check_id": check_id,
        "state": "pass" if passed else "blocked",
        "message": message,
        "recovery_action": "" if passed else recovery_action,
    }


def _aligned_history_count(*, data_dir: Path, snapshot_id: str, universe: Sequence[str]) -> int:
    """Read the verified frozen snapshot through the CLI-owned PIT boundary."""
    aligned: set[float] | None = None
    for symbol in universe:
        payload = _object(
            _run_json(
                ["data", "candles", symbol, "--snapshot", snapshot_id, "--json"],
                data_dir=data_dir,
            ),
            "snapshot candles",
        )
        bars = _objects(payload.get("bars"), "snapshot bars")
        sessions: set[float] = set()
        for bar in bars:
            timestamp = _finite(bar.get("t"), "snapshot bar timestamp")
            sessions.add(timestamp)
        aligned = sessions if aligned is None else aligned.intersection(sessions)
    return len(aligned or ())


def experiment_preflight(
    *, project_id: str, data_dir: Path, experiment_id: str | None = None
) -> dict[str, Any]:
    """Recompute every local prerequisite before the UI can launch an ML experiment."""
    status = service_status(data_dir=data_dir)
    project = _object(
        _run_json(
            ["project", "show", project_id, "--lineage-limit", "100", "--json"],
            data_dir=data_dir,
        ),
        "project",
    )
    selected_experiment_id = experiment_id or project.get("current_experiment_id")
    experiments = _objects(project.get("experiments"), "project experiments")
    experiment = next(
        (
            candidate
            for candidate in experiments
            if isinstance(selected_experiment_id, str)
            and candidate.get("experiment_id") == selected_experiment_id
        ),
        None,
    )
    snapshot_id = experiment.get("snapshot_id") if experiment is not None else None
    universe_value = experiment.get("universe") if experiment is not None else None
    universe = (
        cast(list[str], universe_value)
        if isinstance(universe_value, list)
        and all(isinstance(symbol, str) and symbol for symbol in universe_value)
        else []
    )
    gate_state = project.get("research_gate_state")
    active_job_id = status.get("active_job_id")

    history_count = 0
    history_readable = False
    if isinstance(snapshot_id, str) and snapshot_id and universe:
        try:
            history_count = _aligned_history_count(
                data_dir=data_dir,
                snapshot_id=snapshot_id,
                universe=universe,
            )
            history_readable = True
        except (DataError, OSError, RuntimeError):
            # The public projection intentionally does not repeat backend paths or raw store errors.
            history_readable = False

    experiment_ready = experiment is not None and isinstance(selected_experiment_id, str)
    snapshot_ready = isinstance(snapshot_id, str) and bool(snapshot_id) and history_readable
    gate_ready = gate_state in {"passed", "not_required", "overridden"}
    worker_ready = status.get("worker_ready") is True
    universe_ready = len(universe) >= MIN_SYMBOLS
    history_ready = history_readable and history_count >= MIN_ALIGNED_SESSIONS
    capacity_ready = active_job_id is None
    checks = [
        _preflight_check(
            "experiment",
            experiment_ready,
            "A current immutable experiment is selected."
            if experiment_ready
            else "No current immutable experiment is selected.",
            "Create or select an experiment in Development Center.",
        ),
        _preflight_check(
            "snapshot",
            snapshot_ready,
            "The frozen snapshot is readable for every selected symbol."
            if snapshot_ready
            else "The experiment snapshot is missing or unreadable.",
            "Bind a verified frozen snapshot to the experiment.",
        ),
        _preflight_check(
            "research_gate",
            gate_ready,
            f"Research gate state is {gate_state}."
            if gate_ready
            else "The project research gate is still open.",
            "Complete the Research Case before strategy development.",
        ),
        _preflight_check(
            "worker",
            worker_ready,
            "The isolated Qlib worker and input producer are ready."
            if worker_ready
            else "The isolated Qlib worker or input producer is unavailable.",
            "Repair the isolated worker readiness checks, then run preflight again.",
        ),
        _preflight_check(
            "universe",
            universe_ready,
            f"The frozen universe contains {len(universe)} symbols.",
            f"Freeze at least {MIN_SYMBOLS} symbols in the experiment universe.",
        ),
        _preflight_check(
            "aligned_history",
            history_ready,
            f"The snapshot provides {history_count} fully aligned sessions.",
            f"Provide at least {MIN_ALIGNED_SESSIONS} fully aligned sessions for every symbol.",
        ),
        _preflight_check(
            "active_job",
            capacity_ready,
            "The single heavyweight-job slot is available."
            if capacity_ready
            else "A heavyweight Qlib or Kronos job is already active.",
            "Wait for or cancel the active job before launching another.",
        ),
    ]
    return {
        "schema_version": 1,
        "project_id": project_id,
        "experiment_id": (
            selected_experiment_id if isinstance(selected_experiment_id, str) else None
        ),
        "snapshot_id": snapshot_id if isinstance(snapshot_id, str) else None,
        "universe_count": len(universe),
        "aligned_sessions": history_count,
        "active_job_id": active_job_id if isinstance(active_job_id, str) else None,
        "ready": all(check["state"] == "pass" for check in checks),
        "checks": checks,
    }


def _job_exchange(row: Mapping[str, Any]) -> str | None:
    request = row.get("request")
    if not isinstance(request, dict):
        return None
    value = request.get("exchange_id")
    if value is None and row.get("kind") == "suite:qlib":
        governance = request.get("governance")
        if isinstance(governance, dict):
            value = governance.get("managed_resource_id")
    return value if isinstance(value, str) and _ID.fullmatch(value) is not None else None


def _diagnostic_metrics(result: Mapping[str, Any] | None) -> dict[str, float | None]:
    empty: dict[str, float | None] = {
        "ic": None,
        "rank_ic": None,
        "turnover": None,
        "costed_return": None,
    }
    if result is None:
        return empty
    diagnostics = result.get("diagnostics")
    if not isinstance(diagnostics, dict):
        return empty
    signal = diagnostics.get("signal_analysis")
    if not isinstance(signal, dict):
        return empty
    ic = signal.get("ic")
    portfolio = signal.get("portfolio")
    if not isinstance(ic, dict) or not isinstance(portfolio, dict):
        return empty
    return {
        "ic": _optional_finite(ic.get("mean"), "IC mean"),
        "rank_ic": _optional_finite(ic.get("rank_mean"), "RankIC mean"),
        "turnover": _optional_finite(portfolio.get("mean_turnover"), "turnover"),
        "costed_return": _optional_finite(
            portfolio.get("costed_total_return"), "costed total return"
        ),
    }


def list_experiments(
    *,
    data_dir: Path,
    project_id: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    """Project-aware summaries of portable exchange experiments for the ML Research panel."""
    jobs = _durable_jobs(data_dir=data_dir)
    project_by_exchange: dict[str, str | None] = {}
    replay_by_exchange: dict[str, str] = {}
    for job in jobs:
        exchange_id = _job_exchange(job)
        if exchange_id is None:
            continue
        if exchange_id not in project_by_exchange:
            linked_project = job.get("project_id")
            project_by_exchange[exchange_id] = (
                linked_project if isinstance(linked_project, str) else None
            )
        result_run_id = job.get("result_run_id")
        if (
            job.get("kind") in {"ml_replay", "suite:qlib"}
            and job.get("status") == "succeeded"
            and isinstance(result_run_id, str)
        ):
            replay_by_exchange.setdefault(exchange_id, result_run_id)

    root = _ml_root(data_dir) / "exchanges"
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.iterdir(), key=lambda item: item.name, reverse=True):
            if (
                _ID.fullmatch(path.name) is None
                or path.is_symlink()
                or not path.is_dir()
                or not (path / "request.json").is_file()
            ):
                continue
            linked_project = project_by_exchange.get(path.name)
            if project_id is not None and linked_project != project_id:
                continue
            request = _json_object(path / "request.json", "ML request")
            result_path = path / "result.json"
            result = _json_object(result_path, "ML result") if result_path.is_file() else None
            universe = request.get("universe")
            folds = request.get("folds")
            panel = _object(request.get("panel"), "ML panel contract")
            feature = _object(request.get("feature_recipe"), "feature recipe")
            model = _object(request.get("model"), "model recipe")
            universe_size = len(universe) if isinstance(universe, list) else 0
            panel_rows = panel.get("rows")
            aligned_sessions = (
                int(panel_rows) // universe_size
                if isinstance(panel_rows, int) and universe_size > 0
                else 0
            )
            summary = _exchange_summary(path.name, path)
            items.append(
                {
                    "experiment_id": path.name,
                    "project_id": linked_project,
                    "status": summary["status"],
                    "universe_size": universe_size,
                    "aligned_sessions": aligned_sessions,
                    "feature_recipe": feature.get("name"),
                    "model": model.get("name"),
                    "folds": len(folds) if isinstance(folds, list) else 0,
                    "snapshot_hash": request.get("snapshot_hash"),
                    "config_hash": request.get("config_hash"),
                    "replay_run_id": replay_by_exchange.get(path.name),
                    "diagnostic_only": (
                        True if result is None else bool(result.get("diagnostic_only", True))
                    ),
                    "counterfactual_refit": (
                        False if result is None else bool(result.get("counterfactual_refit", False))
                    ),
                    "metrics": _diagnostic_metrics(result),
                }
            )
    return {
        "items": items[offset : offset + limit],
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < len(items),
    }


def _canonical_json(value: Mapping[str, object]) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise MlError("ML job request must be finite JSON") from exc


def _journal(
    args: list[str], *, data_dir: Path, timeout_seconds: float | None = None
) -> dict[str, Any]:
    if timeout_seconds is None:
        # inherit _run_json's bounded default — journal calls are never unbounded
        value = _run_json(args, data_dir=data_dir)
    else:
        value = _run_json(args, data_dir=data_dir, timeout_seconds=timeout_seconds)
    return _object(value, "durable job")


def _renew_job_heartbeat(job_id: str, *, data_dir: Path) -> bool:
    row = _journal(
        [
            "project",
            "job-event",
            job_id,
            "heartbeat",
            "--payload-json",
            '{"surface":"workstation_ml"}',
            "--json",
        ],
        data_dir=data_dir,
        timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
    )
    requested = row.get("cancel_requested")
    if not isinstance(requested, bool):
        raise MlError("durable heartbeat omitted its cancellation state")
    return requested


def _sanitize_message(value: str, *, data_dir: Path) -> str:
    sanitized = value
    for raw, replacement in (
        (str(data_dir), "<ALPHA_DATA_DIR>"),
        (str(data_dir.resolve()), "<ALPHA_DATA_DIR>"),
        (str(_worker_project()), "<QLIB_WORKER>"),
        (str(_worker_project().resolve()), "<QLIB_WORKER>"),
    ):
        sanitized = sanitized.replace(raw, replacement)
    return sanitized[-2000:]


def _parse_process_output(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        try:
            value: object = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and all(isinstance(key, str) for key in value):
            return cast(dict[str, Any], value)
    raise MlError("alpha ml returned no machine-readable completion record")


def _run_process(
    args: list[str],
    *,
    data_dir: Path,
    timeout_seconds: int,
    job_id: str | None = None,
) -> tuple[int, str, str]:
    environment = _cli_environment(data_dir, args)
    if job_id is not None:
        process = subprocess.Popen(
            _command(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
            start_new_session=True,
        )
        cancel_state = [False]

        def renew() -> None:
            cancel_state[0] = _renew_job_heartbeat(job_id, data_dir=data_dir)

        lease = DurableJobLease.start_for_process(
            process,
            renew=renew,
            fail_journal=lambda message: _journal(
                [
                    "project",
                    "job-status",
                    job_id,
                    "failed",
                    "--terminal-error",
                    _sanitize_message(message, data_dir=data_dir),
                    "--json",
                ],
                data_dir=data_dir,
                timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
            ),
            cancel_requested=lambda: cancel_state[0],
            cancel_journal=lambda: _journal(
                ["project", "job-status", job_id, "cancelled", "--json"],
                data_dir=data_dir,
                timeout_seconds=_DURABLE_HEARTBEAT_TIMEOUT_S,
            ),
            interval_seconds=_DURABLE_HEARTBEAT_INTERVAL_S,
            label="workstation ML child",
        )
        try:
            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                terminate_and_reap(process)
                process.communicate()
                raise
        finally:
            lease.stop()
            lease.raise_if_cancelled()
            lease.raise_if_failed()
        return process.returncode, stdout, stderr
    completed = subprocess.run(
        _command(args),
        capture_output=True,
        text=True,
        env=environment,
        timeout=timeout_seconds,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def _execute_job(
    job_id: str,
    action: MlAction,
    args: list[str],
    *,
    data_dir: Path,
    timeout_seconds: int,
) -> None:
    try:
        returncode, stdout, stderr = _run_process(
            args,
            data_dir=data_dir,
            timeout_seconds=timeout_seconds,
            job_id=job_id,
        )
        if returncode != 0:
            detail = _sanitize_message(
                _strip_ansi(stderr).strip() or _strip_ansi(stdout).strip(), data_dir=data_dir
            )
            _journal(
                [
                    "project",
                    "job-status",
                    job_id,
                    "failed",
                    "--terminal-error",
                    detail or f"alpha ml {action} exited {returncode}",
                    "--json",
                ],
                data_dir=data_dir,
            )
            return
        result = _parse_process_output(stdout)
        safe_result = {
            key: value
            for key, value in result.items()
            if key
            in {
                "status",
                "mode",
                "rows",
                "config_hash",
                "worker_lock_hash",
                "run_id",
                "authority",
                "label",
                "input_bundle_id",
                "project_id",
                "experiment_id",
                "symbols",
                "sessions",
                "folds",
            }
        }
        _journal(
            [
                "project",
                "job-event",
                job_id,
                "progress",
                "--payload-json",
                _canonical_json(cast(dict[str, object], safe_result)),
                "--json",
            ],
            data_dir=data_dir,
        )
        status_args = ["project", "job-status", job_id, "succeeded"]
        run_id = result.get("run_id")
        if action == "replay" and isinstance(run_id, str):
            status_args.extend(["--result-run-id", run_id])
        status_args.append("--json")
        _journal(status_args, data_dir=data_dir)
    except (DurableLeaseCancelled, DurableLeaseError):
        return
    except subprocess.TimeoutExpired:
        _journal(
            [
                "project",
                "job-status",
                job_id,
                "failed",
                "--terminal-error",
                f"alpha ml {action} exceeded {timeout_seconds} seconds",
                "--json",
            ],
            data_dir=data_dir,
        )
    except (MlError, OSError, RuntimeError) as exc:
        _journal(
            [
                "project",
                "job-status",
                job_id,
                "failed",
                "--terminal-error",
                _sanitize_message(str(exc), data_dir=data_dir),
                "--json",
            ],
            data_dir=data_dir,
        )


def _start_job(
    job_id: str,
    action: MlAction,
    args: list[str],
    *,
    data_dir: Path,
    timeout_seconds: int,
) -> None:
    threading.Thread(
        target=_execute_job,
        args=(job_id, action, args),
        kwargs={"data_dir": data_dir, "timeout_seconds": timeout_seconds},
        daemon=True,
        name=f"alpha-ml-{action}-{job_id[:8]}",
    ).start()


def _execute_pipeline(
    job_id: str,
    steps: list[tuple[str, list[str], int]],
    *,
    data_dir: Path,
) -> None:
    """Run a fixed CLI-owned export→prepare pipeline under one durable journal."""
    try:
        for step, args, timeout_seconds in steps:
            try:
                returncode, stdout, stderr = _run_process(
                    args,
                    data_dir=data_dir,
                    timeout_seconds=timeout_seconds,
                    job_id=job_id,
                )
            except (DurableLeaseCancelled, DurableLeaseError):
                return
            except subprocess.TimeoutExpired:
                _journal(
                    [
                        "project",
                        "job-status",
                        job_id,
                        "failed",
                        "--terminal-error",
                        f"alpha ml {step} exceeded {timeout_seconds} seconds",
                        "--json",
                    ],
                    data_dir=data_dir,
                )
                return
            if returncode != 0:
                detail = _sanitize_message(
                    _strip_ansi(stderr).strip() or _strip_ansi(stdout).strip(), data_dir=data_dir
                )
                _journal(
                    [
                        "project",
                        "job-status",
                        job_id,
                        "failed",
                        "--terminal-error",
                        detail or f"alpha ml {step} exited {returncode}",
                        "--json",
                    ],
                    data_dir=data_dir,
                )
                return
            result = _parse_process_output(stdout)
            safe_result: dict[str, object] = {"step": step}
            for key in (
                "status",
                "input_bundle_id",
                "project_id",
                "experiment_id",
                "snapshot_hash",
                "symbols",
                "sessions",
                "rows",
                "folds",
                "config_hash",
                "worker_lock_hash",
            ):
                value = result.get(key)
                if isinstance(value, str | int | float | bool) or value is None:
                    safe_result[key] = value
            _journal(
                [
                    "project",
                    "job-event",
                    job_id,
                    "progress",
                    "--payload-json",
                    _canonical_json(safe_result),
                    "--json",
                ],
                data_dir=data_dir,
            )
        _journal(
            ["project", "job-status", job_id, "succeeded", "--json"],
            data_dir=data_dir,
        )
    except (MlError, OSError, RuntimeError) as exc:
        _journal(
            [
                "project",
                "job-status",
                job_id,
                "failed",
                "--terminal-error",
                _sanitize_message(str(exc), data_dir=data_dir),
                "--json",
            ],
            data_dir=data_dir,
        )


def _start_pipeline(
    job_id: str,
    steps: list[tuple[str, list[str], int]],
    *,
    data_dir: Path,
) -> None:
    threading.Thread(
        target=_execute_pipeline,
        args=(job_id, steps),
        kwargs={"data_dir": data_dir},
        daemon=True,
        name=f"alpha-ml-generate-{job_id[:8]}",
    ).start()


def _create_job(
    *,
    data_dir: Path,
    kind: str,
    request: Mapping[str, object],
    project_id: str | None,
    experiment_id: str | None,
) -> str:
    args = [
        "project",
        "job-create",
        kind,
        "--request-json",
        _canonical_json(request),
    ]
    if project_id is not None:
        args.extend(["--project-id", project_id])
    if experiment_id is not None:
        args.extend(["--experiment-id", experiment_id])
    args.append("--json")
    try:
        job = _journal(args, data_dir=data_dir)
    except RuntimeError as exc:
        if "heavyweight job capacity is occupied" in str(exc):
            raise MlBusyError("one heavyweight Qlib or Kronos job is already active") from exc
        raise
    job_id = job.get("job_id")
    if not isinstance(job_id, str):
        raise MlError("durable job projection omitted job_id")
    _journal(["project", "job-status", job_id, "running", "--json"], data_dir=data_dir)
    return job_id


def launch_input_generation(
    *,
    data_dir: Path,
    project_id: str,
    experiment_id: str,
    input_bundle_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Generate one verified snapshot-bound input bundle under an opaque server path."""
    input_bundle_id = _safe_id(input_bundle_id, "input_bundle_id")
    output = _ml_root(data_dir) / "inputs" / input_bundle_id
    if output.exists():
        raise MlError("input_bundle_id is already published")
    safe_request: dict[str, object] = {
        "action": "export-input",
        "project_id": project_id,
        "experiment_id": experiment_id,
        "input_bundle_id": input_bundle_id,
    }
    job_id = _create_job(
        data_dir=data_dir,
        kind=_JOB_KIND["export-input"],
        request=safe_request,
        project_id=project_id,
        experiment_id=experiment_id,
    )
    _start_job(
        job_id,
        "export-input",
        [
            "ml",
            "export-input",
            project_id,
            experiment_id,
            str(output),
            "--json",
        ],
        data_dir=data_dir,
        timeout_seconds=timeout_seconds,
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "action": "export-input",
        "project_id": project_id,
        "experiment_id": experiment_id,
        "input_bundle_id": input_bundle_id,
    }


def _current_experiment(project_id: str, *, data_dir: Path) -> str:
    project = _object(
        _run_json(
            ["project", "show", project_id, "--lineage-limit", "1", "--json"],
            data_dir=data_dir,
        ),
        "project",
    )
    experiment_id = project.get("current_experiment_id")
    if not isinstance(experiment_id, str):
        raise MlError("project has no current immutable experiment")
    return experiment_id


def launch_experiment_generation(
    *,
    data_dir: Path,
    project_id: str,
    experiment_id: str | None,
    timeout_seconds: int,
) -> dict[str, Any]:
    """One-click input export plus immutable exchange preparation for a project experiment."""
    resolved_experiment = experiment_id or _current_experiment(project_id, data_dir=data_dir)
    input_bundle_id = new_input_id()
    exchange_id = new_exchange_id()
    input_dir = _ml_root(data_dir) / "inputs" / input_bundle_id
    exchange_dir = _ml_root(data_dir) / "exchanges" / exchange_id
    project = _worker_project()
    lock = project / "uv.lock"
    if project.is_symlink() or not project.is_dir() or lock.is_symlink() or not lock.is_file():
        raise MlError("isolated worker project/lock is unavailable")
    safe_request: dict[str, object] = {
        "action": "generate-experiment",
        "project_id": project_id,
        "experiment_id": resolved_experiment,
        "input_bundle_id": input_bundle_id,
        "exchange_id": exchange_id,
    }
    job_id = _create_job(
        data_dir=data_dir,
        kind=_JOB_KIND["generate-experiment"],
        request=safe_request,
        project_id=project_id,
        experiment_id=resolved_experiment,
    )
    export_timeout = min(timeout_seconds, 3600)
    prepare_timeout = min(timeout_seconds, 600)
    steps = [
        (
            "export-input",
            [
                "ml",
                "export-input",
                project_id,
                resolved_experiment,
                str(input_dir),
                "--json",
            ],
            export_timeout,
        ),
        (
            "prepare",
            [
                "ml",
                "prepare",
                str(input_dir / "spec.json"),
                str(input_dir / "panel.parquet"),
                str(exchange_dir),
                "--worker-lock",
                str(lock),
                "--json",
            ],
            prepare_timeout,
        ),
    ]
    _start_pipeline(job_id, steps, data_dir=data_dir)
    return {
        "job_id": job_id,
        "status": "queued",
        "action": "generate-experiment",
        "project_id": project_id,
        "experiment_id": resolved_experiment,
        "input_bundle_id": input_bundle_id,
        "exchange_id": exchange_id,
    }


def launch_action(
    action: MlAction,
    *,
    data_dir: Path,
    exchange_id: str,
    input_bundle_id: str | None = None,
    project_id: str | None,
    experiment_id: str | None,
    mode: Literal["fake", "real"] = "real",
    no_sync: bool = False,
    timeout_seconds: int = 7200,
    starting_cash: float = 1_000_000.0,
    periods_per_year: int = 252,
) -> dict[str, Any]:
    """Launch one allowlisted ML CLI action and return its durable journal identity."""
    exchange_id = _safe_id(exchange_id, "exchange_id")
    safe_request: dict[str, object] = {"action": action, "exchange_id": exchange_id}
    ml_root = _ml_root(data_dir)
    exchange = ml_root / "exchanges" / exchange_id
    if action == "prepare":
        if input_bundle_id is None:
            raise MlError("prepare requires input_bundle_id")
        bundle = _resource_dir(data_dir, "inputs", input_bundle_id, "input_bundle_id")
        summary = _input_summary(input_bundle_id, bundle)
        if not summary["ready"]:
            raise MlError("input bundle requires regular spec.json and panel.parquet")
        if exchange.exists():
            raise MlError("exchange_id is already published")
        project = _worker_project()
        lock = project / "uv.lock"
        if project.is_symlink() or not lock.is_file() or lock.is_symlink():
            raise MlError("isolated worker lock is unavailable")
        args = [
            "ml",
            "prepare",
            str(bundle / "spec.json"),
            str(bundle / "panel.parquet"),
            str(exchange),
            "--worker-lock",
            str(lock),
            "--json",
        ]
        safe_request["input_bundle_id"] = input_bundle_id
        timeout_seconds = min(timeout_seconds, 600)
    else:
        exchange = _exchange_dir(exchange_id, data_dir=data_dir)
        if action == "train":
            args = ["ml", "train", str(exchange), "--mode", mode]
            if no_sync:
                args.append("--no-sync")
            args.extend(["--timeout-seconds", str(timeout_seconds), "--json"])
            safe_request.update(
                {"mode": mode, "no_sync": no_sync, "timeout_seconds": timeout_seconds}
            )
        elif action == "import":
            args = ["ml", "import", str(exchange), "--json"]
            timeout_seconds = min(timeout_seconds, 600)
        elif action == "prepare-replay":
            args = [
                "ml",
                "prepare-replay",
                str(exchange),
                str(exchange / "replay_signals.parquet"),
                "--json",
            ]
            timeout_seconds = min(timeout_seconds, 600)
        elif action == "replay":
            args = [
                "ml",
                "replay",
                str(exchange),
                "--starting-cash",
                str(starting_cash),
                "--periods-per-year",
                str(periods_per_year),
                "--json",
            ]
            safe_request.update(
                {"starting_cash": starting_cash, "periods_per_year": periods_per_year}
            )
        else:  # pragma: no cover - static MlAction + strict REST enums guard this
            raise MlError(f"unsupported ML action {action!r}")

    job_id = _create_job(
        data_dir=data_dir,
        kind=_JOB_KIND[action],
        request=safe_request,
        project_id=project_id,
        experiment_id=experiment_id,
    )
    _start_job(
        job_id,
        action,
        args,
        data_dir=data_dir,
        timeout_seconds=timeout_seconds,
    )
    return {
        "job_id": job_id,
        "status": "queued",
        "action": action,
        "exchange_id": exchange_id,
    }


def new_exchange_id() -> str:
    return uuid.uuid4().hex


def new_input_id() -> str:
    return uuid.uuid4().hex


__all__ = [
    "MlBusyError",
    "MlError",
    "MlNotFoundError",
    "evaluate_exchange",
    "exchange_detail",
    "exchange_result",
    "exchange_tearsheet",
    "input_bundle",
    "launch_action",
    "launch_experiment_generation",
    "launch_input_generation",
    "list_exchanges",
    "list_experiments",
    "list_input_bundles",
    "new_exchange_id",
    "new_input_id",
    "readiness",
    "replay_tearsheet",
    "service_status",
]
