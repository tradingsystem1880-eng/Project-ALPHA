"""Isolated worker tests for deterministic offline output and dependency failures."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import polars as pl
import pytest

from alpha_qlib_worker.contract import (
    MIN_ALIGNED_SESSIONS,
    MIN_SYMBOLS,
    PANEL_COLUMNS,
    canonical_json_bytes,
    compute_config_hash,
    sha256_file,
    validate_request,
)
from alpha_qlib_worker.fake import run_fake
from alpha_qlib_worker.real import WorkerDependencyError, require_real_dependencies


def _exchange(path: Path) -> Path:
    symbols = [f"S{i:02d}" for i in range(MIN_SYMBOLS)]
    sessions = [
        datetime(2023, 1, 2, tzinfo=UTC) + timedelta(days=i) for i in range(MIN_ALIGNED_SESSIONS)
    ]
    rows = []
    for session_index, session in enumerate(sessions):
        for symbol_index, symbol in enumerate(symbols):
            price = 100.0 + session_index * 0.01 + symbol_index * 0.1
            rows.append(
                {
                    "symbol": symbol,
                    "session_ts": session,
                    "available_at": session + timedelta(hours=23),
                    "open": price,
                    "high": price + 1,
                    "low": price - 1,
                    "close": price + 0.25,
                    "volume": 1_000_000.0,
                }
            )
    path.mkdir()
    panel_path = path / "panel.parquet"
    pl.DataFrame(rows).select(PANEL_COLUMNS).write_parquet(panel_path)
    request = {
        "schema_version": 1,
        "snapshot_hash": "a" * 64,
        "universe": symbols,
        "universe_membership": "point_in_time",
        "survivorship_warning": None,
        "feature_recipe": {"name": "alpha158", "version": 1, "parameters": {}},
        "label_recipe": {
            "name": "next_session_open_to_open",
            "decision": "close_t",
            "fill": "open_t_plus_1",
            "horizon_sessions": 1,
        },
        "model": {"name": "lightgbm", "parameters": {}},
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
        "worker_lock_hash": sha256_file(Path(__file__).parents[1] / "uv.lock"),
        "panel": {
            "path": "panel.parquet",
            "sha256": sha256_file(panel_path),
            "rows": len(rows),
        },
    }
    request["config_hash"] = compute_config_hash(request)
    (path / "request.json").write_bytes(canonical_json_bytes(request))
    return path


def test_fake_worker_is_byte_reproducible_and_sorted(tmp_path: Path) -> None:
    first = _exchange(tmp_path / "first")
    second = tmp_path / "second"
    shutil.copytree(first, second)
    worker_lock = Path(__file__).parents[1] / "uv.lock"

    result_a = run_fake(first, worker_lock_path=worker_lock)
    result_b = run_fake(second, worker_lock_path=worker_lock)

    assert result_a == result_b
    assert sha256_file(first / "predictions.parquet") == sha256_file(second / "predictions.parquet")
    assert (first / "result.json").read_bytes() == (second / "result.json").read_bytes()
    frame = pl.read_parquet(first / "predictions.parquet")
    assert frame.height > 0
    assert frame.equals(frame.sort(["fold", "split", "target_ts", "symbol", "origin_ts"]))
    assert frame.get_column("score").is_finite().all()


def test_fake_worker_refuses_overwrite_and_corrupt_request(tmp_path: Path) -> None:
    exchange = _exchange(tmp_path / "exchange")
    worker_lock = Path(__file__).parents[1] / "uv.lock"
    run_fake(exchange, worker_lock_path=worker_lock)
    with pytest.raises(RuntimeError, match="already exists"):
        run_fake(exchange, worker_lock_path=worker_lock)

    corrupt = _exchange(tmp_path / "corrupt")
    request = json.loads((corrupt / "request.json").read_text())
    request["panel"]["sha256"] = "d" * 64
    request["config_hash"] = compute_config_hash(request)
    (corrupt / "request.json").write_bytes(canonical_json_bytes(request))
    with pytest.raises(RuntimeError, match="panel hash"):
        validate_request(corrupt)

    wrong_lock = _exchange(tmp_path / "wrong-lock")
    request = json.loads((wrong_lock / "request.json").read_text())
    request["worker_lock_hash"] = "d" * 64
    request["config_hash"] = compute_config_hash(request)
    (wrong_lock / "request.json").write_bytes(canonical_json_bytes(request))
    with pytest.raises(RuntimeError, match="executing worker lock"):
        run_fake(wrong_lock, worker_lock_path=worker_lock)


@pytest.mark.parametrize(
    ("boundary", "message"),
    [("train-validation", "purge_sessions"), ("validation-test", "embargo_sessions")],
)
def test_worker_contract_requires_label_horizon_gap_when_buffer_is_zero(
    tmp_path: Path, boundary: str, message: str
) -> None:
    exchange = _exchange(tmp_path / boundary)
    request = json.loads((exchange / "request.json").read_text())
    sessions = (
        pl.read_parquet(exchange / "panel.parquet")
        .get_column("session_ts")
        .unique(maintain_order=True)
        .to_list()
    )
    if boundary == "train-validation":
        request["purge_sessions"] = 0
        request["folds"][0]["validation_start"] = sessions[504].isoformat()
    else:
        request["embargo_sessions"] = 0
        request["folds"][0]["test_start"] = sessions[629].isoformat()
    request["config_hash"] = compute_config_hash(request)
    (exchange / "request.json").write_bytes(canonical_json_bytes(request))

    with pytest.raises(RuntimeError, match=message):
        validate_request(exchange)


def test_worker_contract_rejects_a_terminal_session_test_target(tmp_path: Path) -> None:
    exchange = _exchange(tmp_path / "terminal-target")
    request = json.loads((exchange / "request.json").read_text())
    sessions = (
        pl.read_parquet(exchange / "panel.parquet")
        .get_column("session_ts")
        .unique(maintain_order=True)
        .to_list()
    )
    request["folds"][0]["test_end"] = sessions[-1].isoformat()
    request["config_hash"] = compute_config_hash(request)
    (exchange / "request.json").write_bytes(canonical_json_bytes(request))

    with pytest.raises(RuntimeError, match="following aligned open"):
        validate_request(exchange)


def test_real_worker_dependency_failure_is_actionable() -> None:
    def missing(name: str) -> ModuleType:
        raise ModuleNotFoundError(name)

    with pytest.raises(WorkerDependencyError, match="Qlib and LightGBM are unavailable"):
        require_real_dependencies(import_module=missing)
