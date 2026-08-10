"""Versioned equal-weight percentile-rank ensemble for isolated worker predictions."""

from __future__ import annotations

import hashlib

import polars as pl

from alpha_qlib_worker.contract import PREDICTION_COLUMNS, canonical_json_bytes

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

_KEYS = ["symbol", "origin_ts", "available_at", "target_ts", "fold", "split"]
_GROUP = ["fold", "split", "target_ts"]
_LINEAGE = ["config_hash", "worker_lock_hash", "seed"]
_SORT = ["fold", "split", "target_ts", "symbol", "origin_ts"]


def _member(frame: pl.DataFrame, name: str) -> pl.DataFrame:
    if frame.columns != PREDICTION_COLUMNS:
        raise RuntimeError(f"{name} member must use canonical prediction columns")
    if frame.is_empty() or frame.select(_KEYS).is_duplicated().any():
        raise RuntimeError(f"{name} member keys must be non-empty and unique")
    if not frame.get_column("score").is_finite().all():
        raise RuntimeError(f"{name} member scores must be finite")
    return frame.sort(_SORT)


def rank_ensemble_v1(
    lightgbm: pl.DataFrame, ridge: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Combine two aligned members by equal-weight cross-sectional percentile rank."""
    left = _member(lightgbm, "lightgbm")
    right = _member(ridge, "ridge")
    if not left.select(_KEYS).equals(right.select(_KEYS)):
        raise RuntimeError("rank_ensemble_v1 member keys must match exactly")
    if not left.select([*_KEYS, *_LINEAGE]).equals(right.select([*_KEYS, *_LINEAGE])):
        raise RuntimeError("rank_ensemble_v1 member lineage must match exactly")
    lightgbm_hashes = left.get_column("model_hash").unique().sort().to_list()
    ridge_hashes = right.get_column("model_hash").unique().sort().to_list()
    ensemble_hash = hashlib.sha256(
        canonical_json_bytes(
            {
                "recipe": "rank_ensemble_v1",
                "weights": {"lightgbm": 0.5, "ridge": 0.5},
                "lightgbm_model_hashes": lightgbm_hashes,
                "ridge_model_hashes": ridge_hashes,
            }
        )
    ).hexdigest()
    diagnostics = (
        left.select(
            *_KEYS,
            pl.col("score").alias("lightgbm_score"),
            pl.col("model_hash").alias("lightgbm_model_hash"),
            *_LINEAGE,
        )
        .with_columns(
            right.get_column("score").alias("ridge_score"),
            right.get_column("model_hash").alias("ridge_model_hash"),
        )
        .with_columns(
            (
                (pl.col("lightgbm_score").rank(method="average").over(_GROUP) - 1.0)
                / (pl.len().over(_GROUP) - 1.0)
            ).alias("lightgbm_rank"),
            (
                (pl.col("ridge_score").rank(method="average").over(_GROUP) - 1.0)
                / (pl.len().over(_GROUP) - 1.0)
            ).alias("ridge_rank"),
        )
        .with_columns(
            ((pl.col("lightgbm_rank") + pl.col("ridge_rank")) / 2.0).alias("ensemble_score"),
            (pl.col("lightgbm_rank") - pl.col("ridge_rank")).abs().alias("disagreement"),
            pl.lit(ensemble_hash).alias("ensemble_model_hash"),
        )
        .select(ENSEMBLE_DIAGNOSTIC_COLUMNS)
        .sort(_SORT)
    )
    if diagnostics.select(pl.len().over(_GROUP).min()).item() < 2:
        raise RuntimeError("rank_ensemble_v1 requires at least two symbols per cross-section")
    predictions = diagnostics.select(
        "symbol",
        "origin_ts",
        "available_at",
        "target_ts",
        pl.col("ensemble_score").alias("score"),
        "fold",
        "split",
        pl.col("ensemble_model_hash").alias("model_hash"),
        "config_hash",
        "worker_lock_hash",
        "seed",
    ).select(PREDICTION_COLUMNS)
    return predictions, diagnostics


__all__ = ["ENSEMBLE_DIAGNOSTIC_COLUMNS", "rank_ensemble_v1"]
