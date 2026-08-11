"""CLI-owned producer for immutable, snapshot-bound Qlib input bundles."""

from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import cast

import polars as pl

from alpha_cli import _runner
from alpha_cli.control_store import ControlStore
from alpha_cli.ml_contract import (
    DECISION_CLOSE_OFFSET,
    MIN_ALIGNED_SESSIONS,
    MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    MIN_SYMBOLS,
    PANEL_COLUMNS,
    MLContractError,
    canonical_json_bytes,
    prepare_exchange,
    sha256_file,
)
from alpha_core import Bar, DataError

_SURVIVORSHIP_WARNING = (
    "Current-membership universe is frozen for this experiment but may contain survivorship "
    "bias; results remain advisory until point-in-time membership is supplied."
)


def _object(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise DataError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _positive_int(value: object, label: str, *, default: int) -> int:
    resolved = default if value is None else value
    if isinstance(resolved, bool) or not isinstance(resolved, int) or resolved < 1:
        raise DataError(f"{label} must be an integer >= 1")
    return resolved


def _nonnegative_int(value: object, label: str, *, default: int) -> int:
    resolved = default if value is None else value
    if isinstance(resolved, bool) or not isinstance(resolved, int) or resolved < 0:
        raise DataError(f"{label} must be an integer >= 0")
    return resolved


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DataError(f"{label} must be a finite number >= 0")
    resolved = float(value)
    if not resolved >= 0.0 or not resolved < float("inf"):
        raise DataError(f"{label} must be a finite number >= 0")
    return resolved


def _experiment(control: ControlStore, project_id: str, experiment_id: str) -> dict[str, object]:
    project = control.get_project(project_id)
    experiments = project.get("experiments")
    if not isinstance(experiments, list):
        raise DataError(f"project {project_id!r} has corrupt experiment projections")
    for candidate in experiments:
        if isinstance(candidate, dict) and candidate.get("experiment_id") == experiment_id:
            return cast(dict[str, object], candidate)
    raise DataError(f"experiment {experiment_id!r} is not linked to project {project_id!r}")


def _aligned_panel(
    *,
    data_dir: Path,
    snapshot_id: str,
    universe: Sequence[str],
    as_of: datetime | None = None,
) -> tuple[pl.DataFrame, tuple[datetime, ...]]:
    series: dict[str, dict[datetime, Bar]] = {}
    aligned: set[datetime] | None = None
    for symbol in universe:
        bars, _ = _runner.load_bars(
            symbol,
            data_dir=data_dir,
            snapshot_id=snapshot_id,
            as_of=as_of,
        )
        lookup = {bar.ts: bar for bar in bars}
        series[symbol] = lookup
        aligned = set(lookup) if aligned is None else aligned.intersection(lookup)
    sessions = tuple(sorted(aligned or ()))
    if len(sessions) < MIN_ALIGNED_SESSIONS:
        raise DataError(
            f"Qlib starter requires at least {MIN_ALIGNED_SESSIONS} fully aligned sessions; "
            f"snapshot {snapshot_id!r} provides {len(sessions)}"
        )
    rows: list[dict[str, object]] = []
    for session in sessions:
        for symbol in universe:
            bar = series[symbol][session]
            rows.append(
                {
                    "symbol": symbol,
                    "session_ts": session,
                    # Daily bars are date keys at 00:00 UTC.  Complete OHLCV is available only at
                    # the canonical close used by the engine's decision event, never at midnight.
                    "available_at": session + DECISION_CLOSE_OFFSET,
                    "open": float(bar.open),
                    "high": float(bar.high),
                    "low": float(bar.low),
                    "close": float(bar.close),
                    "volume": float(bar.volume),
                }
            )
    panel = pl.DataFrame(rows).with_columns(
        pl.col("symbol").cast(pl.String),
        pl.col("session_ts").cast(pl.Datetime("us", "UTC")),
        pl.col("available_at").cast(pl.Datetime("us", "UTC")),
        *(pl.col(name).cast(pl.Float64) for name in ("open", "high", "low", "close", "volume")),
    )
    return panel.select(PANEL_COLUMNS), sessions


def _folds(
    sessions: Sequence[datetime],
    *,
    train_sessions: int,
    validation_sessions: int,
    test_sessions: int,
    purge_sessions: int,
    embargo_sessions: int,
) -> list[dict[str, object]]:
    purge_sessions = max(purge_sessions, MIN_LABEL_BOUNDARY_GAP_SESSIONS)
    embargo_sessions = max(embargo_sessions, MIN_LABEL_BOUNDARY_GAP_SESSIONS)
    train_end = train_sessions - 1
    result: list[dict[str, object]] = []
    while True:
        validation_start = train_end + purge_sessions + 1
        validation_end = validation_start + validation_sessions - 1
        test_start = validation_end + embargo_sessions + 1
        # A target session is evaluable only when the panel also contains the following open used
        # by the next-session open-to-open label.  The final aligned session is therefore context,
        # never a fold target.
        if test_start >= len(sessions) - 1:
            break
        test_end = min(test_start + test_sessions - 1, len(sessions) - 2)
        result.append(
            {
                "fold": len(result),
                "train_start": sessions[0].isoformat(),
                "train_end": sessions[train_end].isoformat(),
                "validation_start": sessions[validation_start].isoformat(),
                "validation_end": sessions[validation_end].isoformat(),
                "test_start": sessions[test_start].isoformat(),
                "test_end": sessions[test_end].isoformat(),
            }
        )
        if test_end == len(sessions) - 2:
            break
        train_end += test_sessions
    if not result:
        required = train_sessions + purge_sessions + validation_sessions + embargo_sessions + 2
        raise DataError(
            f"ML split needs at least {required} aligned sessions for one fold; got {len(sessions)}"
        )
    return result


def _draft_spec(
    *,
    experiment: Mapping[str, object],
    sessions: Sequence[datetime],
    snapshot_hash: str,
    worker_lock_hash: str,
) -> dict[str, object]:
    universe_value = experiment.get("universe")
    if not isinstance(universe_value, list) or not all(
        isinstance(symbol, str) for symbol in universe_value
    ):
        raise DataError("experiment universe must be an array of symbols")
    universe = sorted(cast(list[str], universe_value))
    split = _object(experiment.get("split_policy"), "experiment split_policy")
    stage = _object(experiment.get("stage_config"), "experiment stage_config")
    ml_value = stage.get("ml", {})
    ml = _object(ml_value, "stage_config.ml")
    train_sessions = _positive_int(
        ml.get("train_sessions", split.get("train_sessions", split.get("train"))),
        "ML train_sessions",
        default=504,
    )
    validation_sessions = _positive_int(
        ml.get("validation_sessions", split.get("validation_sessions")),
        "ML validation_sessions",
        default=120,
    )
    test_sessions = _positive_int(
        ml.get("test_sessions", split.get("test_sessions", split.get("test"))),
        "ML test_sessions",
        default=63,
    )
    purge_sessions = max(
        _nonnegative_int(
            ml.get("purge_sessions", split.get("purge_sessions", split.get("purge"))),
            "ML purge_sessions",
            default=5,
        ),
        MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    )
    embargo_sessions = max(
        _nonnegative_int(
            ml.get("embargo_sessions", split.get("embargo_sessions", split.get("embargo"))),
            "ML embargo_sessions",
            default=5,
        ),
        MIN_LABEL_BOUNDARY_GAP_SESSIONS,
    )
    costs = _object(experiment.get("costs"), "experiment costs")
    seeds = _object(experiment.get("seeds"), "experiment seeds")
    seed = _nonnegative_int(seeds.get("ml", seeds.get("master")), "ML seed", default=7)
    membership = ml.get("universe_membership", "current_membership")
    if membership not in {"point_in_time", "current_membership"}:
        raise DataError(
            "stage_config.ml.universe_membership must be point_in_time or current_membership"
        )
    warning: str | None = None if membership == "point_in_time" else _SURVIVORSHIP_WARNING
    model_parameters = _object(ml.get("model_parameters", {}), "ML model_parameters")
    recipe = ml.get("recipe", "lightgbm")
    if recipe not in {"lightgbm", "rank_ensemble_v1"}:
        raise DataError("stage_config.ml.recipe must be lightgbm or rank_ensemble_v1")
    if "ridge_alpha" in ml:
        raise DataError(
            "stage_config.ml.ridge_alpha is not configurable; rank_ensemble_v1 fixes it at 1.0"
        )
    return {
        "schema_version": 1 if recipe == "lightgbm" else 2,
        "snapshot_hash": snapshot_hash,
        "universe": universe,
        "universe_membership": membership,
        "survivorship_warning": warning,
        "feature_recipe": {"name": "alpha158", "version": 1, "parameters": {}},
        "label_recipe": {
            "name": "next_session_open_to_open",
            "decision": "close_t",
            "fill": "open_t_plus_1",
            "horizon_sessions": 1,
        },
        "model": {"name": recipe, "parameters": model_parameters},
        "portfolio": {
            "selection": "top_quintile",
            "weighting": "equal",
            "long_only": True,
        },
        "costs": {
            "fee_bps": _finite_nonnegative(costs.get("fee_bps"), "costs.fee_bps"),
            "slippage_bps": _finite_nonnegative(costs.get("slippage_bps"), "costs.slippage_bps"),
        },
        "folds": _folds(
            sessions,
            train_sessions=train_sessions,
            validation_sessions=validation_sessions,
            test_sessions=test_sessions,
            purge_sessions=purge_sessions,
            embargo_sessions=embargo_sessions,
        ),
        "purge_sessions": purge_sessions,
        "embargo_sessions": embargo_sessions,
        "seed": seed,
        "worker_lock_hash": worker_lock_hash,
    }


def export_project_input(
    *,
    data_dir: Path,
    project_id: str,
    experiment_id: str,
    output_dir: Path,
    worker_project: Path | None = None,
    as_of: datetime | None = None,
) -> dict[str, object]:
    """Publish one immutable Qlib input draft from a verified ALPHA project snapshot."""
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise DataError(f"ML input bundle already exists: {output_dir.name}")
    project = (
        Path(__file__).resolve().parents[4] / "workers" / "qlib"
        if worker_project is None
        else Path(worker_project)
    )
    worker_lock = project / "uv.lock"
    if worker_lock.is_symlink() or not worker_lock.is_file():
        raise DataError("isolated Qlib worker lock is unavailable")
    experiment = _experiment(ControlStore(data_dir), project_id, experiment_id)
    snapshot_id = experiment.get("snapshot_id")
    universe_value = experiment.get("universe")
    if not isinstance(snapshot_id, str) or not snapshot_id:
        raise DataError("experiment has no immutable snapshot id")
    if not isinstance(universe_value, list) or not all(
        isinstance(symbol, str) for symbol in universe_value
    ):
        raise DataError("experiment universe must be an array of symbols")
    universe = sorted(cast(list[str], universe_value))
    if len(universe) < MIN_SYMBOLS:
        raise DataError(f"Qlib starter requires at least {MIN_SYMBOLS} frozen symbols")
    snapshot_hash = _runner.verified_snapshot_hash(data_dir, snapshot_id)
    if snapshot_hash is None:  # pragma: no cover - snapshot_id is required above.
        raise DataError("experiment snapshot hash is unavailable")
    panel, sessions = _aligned_panel(
        data_dir=data_dir,
        snapshot_id=snapshot_id,
        universe=universe,
        as_of=as_of,
    )
    draft = _draft_spec(
        experiment=experiment,
        sessions=sessions,
        snapshot_hash=snapshot_hash,
        worker_lock_hash=sha256_file(worker_lock),
    )

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output_dir.name}.", suffix=".tmp", dir=output_dir.parent)
    )
    validation_dir = staging / ".contract-check"
    try:
        spec_path = staging / "spec.json"
        panel_path = staging / "panel.parquet"
        spec_path.write_bytes(canonical_json_bytes(draft))
        panel.write_parquet(panel_path)
        # Reuse the exact boundary validator that will later prepare the real worker exchange.
        prepare_exchange(
            spec_path,
            panel_path,
            validation_dir,
            worker_lock_path=worker_lock,
        )
        shutil.rmtree(validation_dir)
        os.rename(staging, output_dir)
    except (OSError, MLContractError):
        shutil.rmtree(staging, ignore_errors=True)
        if output_dir.exists():
            raise DataError(f"ML input bundle already exists: {output_dir.name}") from None
        raise
    return {
        "status": "generated",
        "input_bundle_id": output_dir.name,
        "project_id": project_id,
        "experiment_id": experiment_id,
        "snapshot_id": snapshot_id,
        "snapshot_hash": snapshot_hash,
        "symbols": len(universe),
        "sessions": len(sessions),
        "rows": panel.height,
        "folds": len(cast(list[object], draft["folds"])),
        "panel_sha256": sha256_file(output_dir / "panel.parquet"),
        "spec_sha256": sha256_file(output_dir / "spec.json"),
        "worker_contract_validated": True,
    }


__all__ = ["export_project_input"]
