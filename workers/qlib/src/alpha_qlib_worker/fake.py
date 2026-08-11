"""Deterministic, network-free fake worker for CI and contract development."""

from __future__ import annotations

import hashlib
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

import polars as pl

from alpha_qlib_worker import __version__
from alpha_qlib_worker.contract import (
    PREDICTION_COLUMNS,
    WorkerRequest,
    canonical_json_bytes,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.rank_ensemble import rank_ensemble_v1


def _stable_hash(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _score(*, config_hash: str, fold: int, symbol: str, origin: str, seed: int) -> float:
    digest = hashlib.sha256(f"{config_hash}|{fold}|{symbol}|{origin}|{seed}".encode()).digest()
    integer = int.from_bytes(digest[:8], "big")
    return (integer / ((1 << 64) - 1)) * 2.0 - 1.0


def _predictions(request: WorkerRequest) -> pl.DataFrame:
    payload = request.payload
    positions = {session: index for index, session in enumerate(request.sessions)}
    availability = {
        (row[0], row[1]): row[2]
        for row in request.panel.select("symbol", "session_ts", "available_at").iter_rows()
    }
    rows: list[dict[str, Any]] = []
    for fold in request.folds:
        fold_id = fold["fold"]
        model_hash = _stable_hash(
            {
                "kind": "fake",
                "implementation_version": __version__,
                "fold": fold_id,
                "config_hash": payload["config_hash"],
                "seed": payload["seed"],
            }
        )
        targets = [
            session
            for session in request.sessions
            if fold["test_start"] <= session <= fold["test_end"]
            and positions[session] + 1 < len(request.sessions)
        ]
        for target in targets:
            target_index = positions[target]
            if target_index == 0:
                raise RuntimeError("test target has no prior aligned origin session")
            origin = request.sessions[target_index - 1]
            for symbol in request.universe:
                rows.append(
                    {
                        "symbol": symbol,
                        "origin_ts": origin,
                        "available_at": availability[(symbol, origin)],
                        "target_ts": target,
                        "score": _score(
                            config_hash=payload["config_hash"],
                            fold=fold_id,
                            symbol=symbol,
                            origin=origin.isoformat(),
                            seed=payload["seed"],
                        ),
                        "fold": fold_id,
                        "split": "test",
                        "model_hash": model_hash,
                        "config_hash": payload["config_hash"],
                        "worker_lock_hash": payload["worker_lock_hash"],
                        "seed": payload["seed"],
                    }
                )
    frame = pl.DataFrame(
        rows,
        schema={
            "symbol": pl.String,
            "origin_ts": pl.Datetime("us", "UTC"),
            "available_at": pl.Datetime("us", "UTC"),
            "target_ts": pl.Datetime("us", "UTC"),
            "score": pl.Float64,
            "fold": pl.Int64,
            "split": pl.String,
            "model_hash": pl.String,
            "config_hash": pl.String,
            "worker_lock_hash": pl.String,
            "seed": pl.Int64,
        },
    ).select(PREDICTION_COLUMNS)
    return frame.sort(["fold", "split", "target_ts", "symbol", "origin_ts"])


def _ridge_predictions(request: WorkerRequest, lightgbm: pl.DataFrame) -> pl.DataFrame:
    """Deterministic fake ridge member with identical keys and distinct lineage."""
    scores = [
        _score(
            config_hash=request.payload["config_hash"],
            fold=int(row["fold"]),
            symbol=str(row["symbol"]),
            origin=f"ridge|{row['origin_ts'].isoformat()}",
            seed=int(request.payload["seed"]),
        )
        for row in lightgbm.iter_rows(named=True)
    ]
    hashes = {
        fold: _stable_hash(
            {
                "kind": "fake-ridge",
                "recipe": "rank_ensemble_v1",
                "fold": fold,
                "config_hash": request.payload["config_hash"],
                "seed": request.payload["seed"],
                "ridge_alpha": 1.0,
            }
        )
        for fold in lightgbm.get_column("fold").unique().to_list()
    }
    return lightgbm.with_columns(
        pl.Series("score", scores, dtype=pl.Float64),
        pl.col("fold").replace_strict(hashes).alias("model_hash"),
    )


def _publish(path: Path, writer: Callable[[Path], object]) -> None:
    fd, raw_temp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(fd)
    temp = Path(raw_temp)
    try:
        writer(temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def run_fake(exchange_dir: Path, *, worker_lock_path: Path) -> dict[str, Any]:
    """Write deterministic predictions and a result completion record exactly once."""
    exchange_dir = Path(exchange_dir)
    predictions_path = exchange_dir / "predictions.parquet"
    ensemble_path = exchange_dir / "ensemble_diagnostics.parquet"
    result_path = exchange_dir / "result.json"
    if predictions_path.exists() or result_path.exists():
        raise RuntimeError("worker output already exists; refusing to overwrite immutable exchange")
    request = validate_request(exchange_dir)
    worker_lock_path = Path(worker_lock_path)
    if worker_lock_path.is_symlink() or not worker_lock_path.is_file():
        raise RuntimeError(f"worker lock must be a regular file: {worker_lock_path}")
    actual_lock_hash = sha256_file(worker_lock_path)
    if request.payload["worker_lock_hash"] != actual_lock_hash:
        raise RuntimeError(
            "worker_lock_hash does not match the executing worker lock: "
            f"expected {actual_lock_hash}"
        )
    lightgbm = _predictions(request)
    ensemble_diagnostics: pl.DataFrame | None = None
    if request.payload["schema_version"] == 2:
        predictions, ensemble_diagnostics = rank_ensemble_v1(
            lightgbm, _ridge_predictions(request, lightgbm)
        )
    else:
        predictions = lightgbm
    _publish(predictions_path, predictions.write_parquet)
    if ensemble_diagnostics is not None:
        _publish(ensemble_path, ensemble_diagnostics.write_parquet)
    payload = request.payload
    result: dict[str, Any] = {
        "schema_version": payload["schema_version"],
        "status": "succeeded",
        "request_sha256": sha256_file(exchange_dir / "request.json"),
        "snapshot_hash": payload["snapshot_hash"],
        "config_hash": payload["config_hash"],
        "worker_lock_hash": payload["worker_lock_hash"],
        "seed": payload["seed"],
        "worker": {"kind": "fake", "implementation_version": __version__},
        "predictions": {
            "path": "predictions.parquet",
            "sha256": sha256_file(predictions_path),
            "rows": predictions.height,
        },
        "diagnostics": {
            "generator": "sha256_uniform_score",
            "network_access": False,
        },
        "diagnostic_only": True,
        "counterfactual_refit": False,
    }
    if ensemble_diagnostics is not None:
        result["ensemble_diagnostics"] = {
            "schema": "QlibRankEnsembleDiagnosticsV1",
            "schema_version": 1,
            "path": "ensemble_diagnostics.parquet",
            "sha256": sha256_file(ensemble_path),
            "rows": ensemble_diagnostics.height,
        }
    _publish(result_path, lambda path: path.write_bytes(canonical_json_bytes(result)))
    return result
