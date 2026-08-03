"""CLI-owned frozen-snapshot producer for the isolated Qlib input contract."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import polars as pl

from alpha_cli.control_store import ControlStore
from alpha_cli.ml_contract import MIN_ALIGNED_SESSIONS, MIN_SYMBOLS, PANEL_COLUMNS
from alpha_cli.ml_input import _draft_spec, _folds, export_project_input
from alpha_data.snapshot import create_snapshot, snapshot_manifest_hash
from alpha_data.store import ParquetStore


def _project_snapshot(tmp_path: Path) -> tuple[str, str, list[str]]:
    symbols = [f"S{index:02d}" for index in range(MIN_SYMBOLS)]
    sessions = [
        datetime(2020, 1, 2, tzinfo=UTC) + timedelta(days=index)
        for index in range(MIN_ALIGNED_SESSIONS)
    ]
    store = ParquetStore(tmp_path / "store")
    for symbol_index, symbol in enumerate(symbols):
        prices = [100.0 + symbol_index + index * 0.01 for index in range(len(sessions))]
        store.write_bars(
            symbol,
            pl.DataFrame(
                {
                    "ts": sessions,
                    "open": prices,
                    "high": [price + 1.0 for price in prices],
                    "low": [price - 1.0 for price in prices],
                    "close": [price + 0.25 for price in prices],
                    "volume": [1_000_000.0 + symbol_index] * len(sessions),
                }
            ),
        )
    create_snapshot(
        store,
        tmp_path / "snapshots",
        "ml-frozen",
        symbols,
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    control = ControlStore(tmp_path)
    project = control.create_project(
        name="Cross-sectional starter",
        hypothesis="Relative winners persist one session.",
        falsification_criterion="Reject if locked OOS excess return is non-positive.",
    )
    version = control.create_strategy_version(
        str(project["project_id"]),
        strategy_name="qlib_alpha158_lgbm",
        source_fingerprint="git:test",
        definition={"decision": "close_t", "fill": "open_t_plus_1"},
        parameter_space={},
    )
    experiment = control.create_experiment_spec(
        str(project["project_id"]),
        strategy_version_id=str(version["version_id"]),
        snapshot_id="ml-frozen",
        universe=symbols,
        split_policy={"train": 504, "test": 63, "purge": 5, "embargo": 5},
        costs={"fee_bps": 1.0, "slippage_bps": 2.0},
        seeds={"master": 7},
        stage_config={"ml": {"validation_sessions": 120}},
    )
    return str(project["project_id"]), str(experiment["experiment_id"]), symbols


def test_export_project_input_is_snapshot_bound_aligned_and_worker_validated(
    tmp_path: Path,
) -> None:
    project_id, experiment_id, symbols = _project_snapshot(tmp_path)
    output = tmp_path / "control" / "ml" / "inputs" / ("a" * 32)

    summary = export_project_input(
        data_dir=tmp_path,
        project_id=project_id,
        experiment_id=experiment_id,
        output_dir=output,
    )

    panel = pl.read_parquet(output / "panel.parquet")
    spec = json.loads((output / "spec.json").read_text(encoding="utf-8"))
    assert panel.columns == PANEL_COLUMNS
    assert panel.height == MIN_SYMBOLS * MIN_ALIGNED_SESSIONS
    assert panel.equals(panel.sort(["session_ts", "symbol"]))
    assert (
        panel.get_column("available_at") - panel.get_column("session_ts")
    ).unique().to_list() == [timedelta(hours=23)]
    assert spec["universe"] == symbols
    assert spec["snapshot_hash"] == snapshot_manifest_hash(tmp_path / "snapshots" / "ml-frozen")
    assert spec["universe_membership"] == "current_membership"
    assert "survivorship" in spec["survivorship_warning"].lower()
    assert spec["label_recipe"]["decision"] == "close_t"
    assert spec["label_recipe"]["fill"] == "open_t_plus_1"
    assert len(spec["folds"]) >= 1
    assert summary["input_bundle_id"] == "a" * 32
    assert summary["sessions"] == MIN_ALIGNED_SESSIONS
    assert summary["symbols"] == MIN_SYMBOLS
    assert summary["worker_contract_validated"] is True


def test_zero_configured_split_buffers_resolve_to_the_label_horizon() -> None:
    sessions = [
        datetime(2020, 1, 2, tzinfo=UTC) + timedelta(days=index)
        for index in range(MIN_ALIGNED_SESSIONS)
    ]
    draft = _draft_spec(
        experiment={
            "universe": [f"S{index:02d}" for index in range(MIN_SYMBOLS)],
            "split_policy": {
                "train": 504,
                "test": 63,
                "purge": 0,
                "embargo": 0,
            },
            "stage_config": {"ml": {"validation_sessions": 120}},
            "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
            "seeds": {"master": 7},
        },
        sessions=sessions,
        snapshot_hash="a" * 64,
        worker_lock_hash="b" * 64,
    )

    fold = cast(list[dict[str, Any]], draft["folds"])[0]
    positions = {session.isoformat(): index for index, session in enumerate(sessions)}
    assert draft["purge_sessions"] == 1
    assert draft["embargo_sessions"] == 1
    assert positions[fold["validation_start"]] - positions[fold["train_end"]] - 1 == 1
    assert positions[fold["test_start"]] - positions[fold["validation_end"]] - 1 == 1


def test_fold_generator_never_declares_the_terminal_session_as_a_target() -> None:
    sessions = [datetime(2020, 1, 2, tzinfo=UTC) + timedelta(days=index) for index in range(761)]

    folds = _folds(
        sessions,
        train_sessions=504,
        validation_sessions=120,
        test_sessions=63,
        purge_sessions=5,
        embargo_sessions=5,
    )

    positions = {session.isoformat(): index for index, session in enumerate(sessions)}
    assert len(folds) == 2
    assert all(positions[str(fold["test_end"])] <= len(sessions) - 2 for fold in folds)
    assert positions[str(folds[-1]["test_end"])] == len(sessions) - 2
