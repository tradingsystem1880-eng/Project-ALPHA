"""Causality and reproducibility guards for the real isolated worker."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pandas as pd
import polars as pl

from alpha_qlib_worker.contract import (
    canonical_json_bytes,
    compute_config_hash,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.features import alpha158_feature_names, alpha158_features
from alpha_qlib_worker.real import _sample_table, run_real

from .test_fake_worker import _exchange


def test_alpha158_features_are_causal_and_match_the_official_shape(tmp_path: Path) -> None:
    exchange = _exchange(tmp_path / "exchange")
    panel = pl.read_parquet(exchange / "panel.parquet")
    cutoff = panel.get_column("session_ts").unique(maintain_order=True)[120]
    poisoned = panel.with_columns(
        pl.when(pl.col("session_ts") > cutoff)
        .then(pl.col("close") * 7.0)
        .otherwise(pl.col("close"))
        .alias("close")
    )

    observed = alpha158_features(panel)
    altered = alpha158_features(poisoned)

    assert len(alpha158_feature_names()) == 158
    assert list(observed.columns) == list(alpha158_feature_names())
    pd.testing.assert_frame_equal(
        observed.loc[observed.index.get_level_values("datetime") <= cutoff],
        altered.loc[altered.index.get_level_values("datetime") <= cutoff],
        check_exact=True,
    )


def test_real_worker_trains_each_fold_and_is_byte_reproducible(tmp_path: Path) -> None:
    first = _exchange(tmp_path / "first")
    request = json.loads((first / "request.json").read_text(encoding="utf-8"))
    request["model"]["parameters"] = {
        "early_stopping_rounds": 3,
        "learning_rate": 0.1,
        "num_boost_round": 8,
        "num_leaves": 15,
        "num_threads": 1,
    }
    from alpha_qlib_worker.contract import canonical_json_bytes, compute_config_hash

    request["config_hash"] = compute_config_hash(request)
    (first / "request.json").write_bytes(canonical_json_bytes(request))
    second = tmp_path / "second"
    shutil.copytree(first, second)
    future_poison = tmp_path / "future-poison"
    shutil.copytree(first, future_poison)
    poison_panel = pl.read_parquet(future_poison / "panel.parquet")
    cutoff = poison_panel.get_column("session_ts").unique(maintain_order=True)[680]
    poison_panel = poison_panel.with_columns(
        [
            pl.when(pl.col("session_ts") > cutoff)
            .then(pl.col(column) * 7.0)
            .otherwise(pl.col(column))
            .alias(column)
            for column in ("open", "high", "low", "close")
        ]
    )
    poison_panel.write_parquet(future_poison / "panel.parquet")
    poison_request = json.loads((future_poison / "request.json").read_text(encoding="utf-8"))
    poison_request["panel"]["sha256"] = sha256_file(future_poison / "panel.parquet")
    poison_request["config_hash"] = compute_config_hash(poison_request)
    (future_poison / "request.json").write_bytes(canonical_json_bytes(poison_request))
    lock = Path(__file__).parents[1] / "uv.lock"

    result_a = run_real(first, worker_lock_path=lock)
    result_b = run_real(second, worker_lock_path=lock)
    run_real(future_poison, worker_lock_path=lock)

    assert result_a == result_b
    assert result_a["worker"]["kind"] == "qlib"
    assert result_a["diagnostics"]["feature_recipe"]["feature_count"] == 158
    assert result_a["diagnostics"]["folds"][0]["fit_count"] == 1
    signal_analysis = result_a["diagnostics"]["signal_analysis"]
    assert signal_analysis["authority"] == "qlib_diagnostic_only"
    assert len(signal_analysis["quantile_returns"]) == 5
    assert signal_analysis["portfolio"]["periods"] > 0
    assert (
        signal_analysis["portfolio"]["costed_total_return"]
        <= signal_analysis["portfolio"]["gross_total_return"]
    )
    assert sha256_file(first / "predictions.parquet") == sha256_file(second / "predictions.parquet")
    predictions = pl.read_parquet(first / "predictions.parquet")
    assert predictions.get_column("score").is_finite().all()
    assert predictions.get_column("model_hash").n_unique() == 1
    assert predictions.get_column("split").unique().to_list() == ["test"]
    sessions = (
        pl.read_parquet(first / "panel.parquet")
        .get_column("session_ts")
        .unique(maintain_order=True)
        .to_list()
    )
    positions = {session: index for index, session in enumerate(sessions)}
    assert predictions.get_column("target_ts").max() == sessions[-2]
    assert all(
        positions[target] + 1 < len(sessions)
        for target in predictions.get_column("target_ts").unique().to_list()
    )
    poison_predictions = pl.read_parquet(future_poison / "predictions.parquet")
    comparison_columns = ["symbol", "origin_ts", "target_ts", "score", "model_hash"]
    assert (
        predictions.filter(pl.col("target_ts") <= cutoff)
        .select(comparison_columns)
        .equals(poison_predictions.filter(pl.col("target_ts") <= cutoff).select(comparison_columns))
    )


def test_label_horizon_gap_blocks_validation_open_from_train_labels(tmp_path: Path) -> None:
    exchange = _exchange(tmp_path / "exchange")
    request_path = exchange / "request.json"
    payload = json.loads(request_path.read_text(encoding="utf-8"))
    sessions = (
        pl.read_parquet(exchange / "panel.parquet")
        .get_column("session_ts")
        .unique(maintain_order=True)
        .to_list()
    )
    payload["purge_sessions"] = 0
    payload["embargo_sessions"] = 0
    payload["folds"][0].update(
        {
            "validation_start": sessions[505].isoformat(),
            "validation_end": sessions[624].isoformat(),
            "test_start": sessions[626].isoformat(),
        }
    )
    payload["config_hash"] = compute_config_hash(payload)
    request_path.write_bytes(canonical_json_bytes(payload))
    request = validate_request(exchange)
    feature_index = pd.MultiIndex.from_product(
        [request.sessions, request.universe], names=["datetime", "instrument"]
    )
    features = pd.DataFrame({"feature": 1.0}, index=feature_index)

    observed = _sample_table(request, features)
    validation_start = request.folds[0]["validation_start"]
    poisoned_panel = request.panel.with_columns(
        pl.when(pl.col("session_ts") == validation_start)
        .then(pl.col("open") * 7.0)
        .otherwise(pl.col("open"))
        .alias("open")
    )
    poisoned = _sample_table(
        replace(request, panel=poisoned_panel),
        features,
    )
    train_end = request.folds[0]["train_end"]
    comparison_columns = ["datetime", "instrument", "target_ts", "label"]
    pd.testing.assert_frame_equal(
        observed.loc[observed["target_ts"] <= train_end, comparison_columns].reset_index(drop=True),
        poisoned.loc[poisoned["target_ts"] <= train_end, comparison_columns].reset_index(drop=True),
        check_exact=True,
    )
    assert observed["target_ts"].max() == request.sessions[-2]
