"""Offline prepare -> fake worker -> import/evaluate exchange flow."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_cli.ml_contract import MIN_ALIGNED_SESSIONS, MIN_SYMBOLS, PANEL_COLUMNS


def _write_inputs(
    tmp_path: Path, *, worker_lock_hash: str, rank_ensemble: bool = False
) -> tuple[Path, Path]:
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
    panel = tmp_path / "panel-source.parquet"
    pl.DataFrame(rows).select(PANEL_COLUMNS).write_parquet(panel)
    spec: dict[str, object] = {
        "schema_version": 2 if rank_ensemble else 1,
        "snapshot_hash": "a" * 64,
        "universe": symbols,
        "universe_membership": "current_membership",
        "survivorship_warning": "Current membership is survivorship-biased and remains advisory.",
        "feature_recipe": {"name": "alpha158", "version": 1, "parameters": {}},
        "label_recipe": {
            "name": "next_session_open_to_open",
            "decision": "close_t",
            "fill": "open_t_plus_1",
            "horizon_sessions": 1,
        },
        "model": {
            "name": "rank_ensemble_v1" if rank_ensemble else "lightgbm",
            "parameters": {},
        },
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
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    return spec_path, panel


def test_offline_ml_cli_round_trip(tmp_path: Path) -> None:
    repo = Path(__file__).parents[2]
    worker_lock = repo / "workers/qlib/uv.lock"
    worker_lock_hash = hashlib.sha256(worker_lock.read_bytes()).hexdigest()
    spec, panel = _write_inputs(tmp_path, worker_lock_hash=worker_lock_hash)
    exchange = tmp_path / "exchange"
    runner = CliRunner()

    prepared = runner.invoke(
        app,
        [
            "ml",
            "prepare",
            str(spec),
            str(panel),
            str(exchange),
            "--worker-lock",
            str(worker_lock),
            "--json",
        ],
    )
    assert prepared.exit_code == 0, prepared.output
    assert json.loads(prepared.output)["config_hash"]

    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "workers/qlib/src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alpha_qlib_worker",
            "fake",
            str(exchange),
            "--worker-lock",
            str(worker_lock),
        ],
        cwd=repo,
        env=env,
        check=True,
    )

    imported = runner.invoke(app, ["ml", "import", str(exchange), "--json"])
    evaluated = runner.invoke(app, ["ml", "evaluate", str(exchange), "--json"])
    replay_path = tmp_path / "replay_signals.parquet"
    replay = runner.invoke(
        app,
        ["ml", "prepare-replay", str(exchange), str(replay_path), "--json"],
    )
    data_dir = tmp_path / "alpha-data"
    canonical = runner.invoke(
        app,
        ["ml", "replay", str(exchange), "--json"],
        env={"ALPHA_DATA_DIR": str(data_dir)},
    )
    assert imported.exit_code == 0, imported.output
    assert evaluated.exit_code == 0, evaluated.output
    assert replay.exit_code == 0, replay.output
    assert canonical.exit_code == 0, canonical.output
    assert json.loads(imported.output)["status"] == "validated"
    evaluation = json.loads(evaluated.output)
    assert evaluation["authority"] == "diagnostic_only"
    assert "ALPHA replay" in evaluation["next_required_step"]
    replay_summary = json.loads(replay.output)
    assert replay_summary["authority"] == "signal_handoff_only"
    assert pl.read_parquet(replay_path).filter(pl.col("selected")).height > 0
    canonical_summary = json.loads(canonical.output)
    assert canonical_summary["authority"] == "alpha_canonical_execution_and_validation"
    assert canonical_summary["validation"]["counterfactual_refit"] is False
    assert canonical_summary["validation"]["promotion_eligible"] is False
    run_dir = data_dir / "runs" / canonical_summary["run_id"]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert manifest["run_identity_version"] == 3
    assert manifest["artifact_contract_version"] == 3
    assert {
        "decision_trace.parquet",
        "orders.parquet",
        "fills.parquet",
        "ml_predictions.parquet",
        "ml_signals.parquet",
        "ml_periods.parquet",
        "folds.parquet",
    } <= set(manifest["artifacts"])
    before = (run_dir / "manifest.json").read_bytes()
    repeated = runner.invoke(
        app,
        ["ml", "replay", str(exchange), "--json"],
        env={"ALPHA_DATA_DIR": str(data_dir)},
    )
    assert repeated.exit_code == 0, repeated.output
    assert (run_dir / "manifest.json").read_bytes() == before


def test_ml_cli_fails_cleanly_on_invalid_bundle(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["ml", "import", str(tmp_path), "--json"])
    assert result.exit_code != 0
    assert "request.json" in result.output
    assert "Traceback" not in result.output


def test_rank_ensemble_replay_publishes_diagnostics_and_cost_sensitivity(
    tmp_path: Path,
) -> None:
    repo = Path(__file__).parents[2]
    worker_lock = repo / "workers/qlib/uv.lock"
    spec, panel = _write_inputs(
        tmp_path,
        worker_lock_hash=hashlib.sha256(worker_lock.read_bytes()).hexdigest(),
        rank_ensemble=True,
    )
    exchange = tmp_path / "ensemble-exchange"
    runner = CliRunner()
    prepared = runner.invoke(
        app,
        [
            "ml",
            "prepare",
            str(spec),
            str(panel),
            str(exchange),
            "--worker-lock",
            str(worker_lock),
            "--json",
        ],
    )
    assert prepared.exit_code == 0, prepared.output
    env = dict(os.environ)
    env["PYTHONPATH"] = str(repo / "workers/qlib/src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "alpha_qlib_worker",
            "fake",
            str(exchange),
            "--worker-lock",
            str(worker_lock),
        ],
        cwd=repo,
        env=env,
        check=True,
    )
    data_dir = tmp_path / "ensemble-data"
    replay = runner.invoke(
        app,
        ["ml", "replay", str(exchange), "--json"],
        env={"ALPHA_DATA_DIR": str(data_dir)},
    )
    assert replay.exit_code == 0, replay.output
    summary = json.loads(replay.output)
    run_dir = data_dir / "runs" / summary["run_id"]
    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert {
        "ensemble_diagnostics.parquet",
        "ml_cost_sensitivity.parquet",
    } <= set(manifest["artifacts"])
    sensitivity = pl.read_parquet(run_dir / "ml_cost_sensitivity.parquet")
    assert sensitivity.get_column("cost_multiplier").to_list() == [0.0, 0.5, 1.0, 2.0]
    assert sensitivity.get_column("total_return").is_finite().all()
    returns = sensitivity.get_column("total_return").to_list()
    assert returns == sorted(returns, reverse=True)
