"""Deterministic equal-weight percentile-rank ensemble behavior."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import polars as pl
import pytest

from alpha_qlib_worker.rank_ensemble import rank_ensemble_v1


def _member(scores: list[float], *, model_hash: str) -> pl.DataFrame:
    target = datetime(2026, 1, 6, tzinfo=UTC)
    origin = target - timedelta(days=1)
    return pl.DataFrame(
        {
            "symbol": ["A", "B", "C", "D"],
            "origin_ts": [origin] * 4,
            "available_at": [origin + timedelta(hours=23)] * 4,
            "target_ts": [target] * 4,
            "score": scores,
            "fold": [0] * 4,
            "split": ["test"] * 4,
            "model_hash": [model_hash] * 4,
            "config_hash": ["c" * 64] * 4,
            "worker_lock_hash": ["w" * 64] * 4,
            "seed": [7] * 4,
        }
    )


def test_rank_ensemble_averages_member_percentiles_and_publishes_disagreement() -> None:
    lightgbm = _member([4.0, 3.0, 2.0, 1.0], model_hash="l" * 64)
    ridge = _member([1.0, 2.0, 4.0, 3.0], model_hash="r" * 64)
    predictions, diagnostics = rank_ensemble_v1(lightgbm, ridge)
    assert predictions.columns == lightgbm.columns
    assert predictions.get_column("score").to_list() == pytest.approx([0.5, 0.5, 2 / 3, 1 / 3])
    assert diagnostics.get_column("ensemble_score").to_list() == pytest.approx(
        predictions.get_column("score").to_list()
    )
    assert diagnostics.get_column("disagreement").to_list() == pytest.approx(
        [1.0, 1 / 3, 2 / 3, 2 / 3]
    )
    assert predictions.get_column("model_hash").n_unique() == 1
    assert predictions.get_column("model_hash")[0] not in {"l" * 64, "r" * 64}


def test_rank_ensemble_is_order_invariant_and_ties_use_average_rank() -> None:
    lightgbm = _member([1.0, 1.0, 3.0, 4.0], model_hash="l" * 64)
    ridge = _member([4.0, 3.0, 2.0, 1.0], model_hash="r" * 64)
    expected = rank_ensemble_v1(lightgbm, ridge)
    observed = rank_ensemble_v1(lightgbm.reverse(), ridge.reverse())
    assert observed[0].equals(expected[0])
    assert observed[1].equals(expected[1])
    tied = expected[1].filter(pl.col("symbol").is_in(["A", "B"]))
    assert tied.get_column("lightgbm_rank").n_unique() == 1


def test_rank_ensemble_rejects_member_key_or_lineage_drift() -> None:
    lightgbm = _member([4.0, 3.0, 2.0, 1.0], model_hash="l" * 64)
    ridge = _member([1.0, 2.0, 4.0, 3.0], model_hash="r" * 64)
    with pytest.raises(RuntimeError, match="keys"):
        rank_ensemble_v1(lightgbm, ridge.filter(pl.col("symbol") != "D"))
    with pytest.raises(RuntimeError, match="lineage"):
        rank_ensemble_v1(
            lightgbm,
            ridge.with_columns(pl.lit("d" * 64).alias("config_hash")),
        )
