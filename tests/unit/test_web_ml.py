"""Safe, bounded projections for the isolated ML worker boundary."""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path
from typing import Any, cast

import polars as pl
import pytest

from alpha_cli.artifact_contract import artifact_contract
from alpha_cli.control_store import ControlStore
from alpha_web import _ml

EXCHANGE_ID = "a" * 32
INPUT_ID = "b" * 32


def _request() -> dict[str, Any]:
    universe = [f"S{index:02d}" for index in range(20)]
    return {
        "schema_version": 1,
        "snapshot_hash": "c" * 64,
        "universe": universe,
        "universe_membership": "current_membership",
        "survivorship_warning": "Current membership is survivorship-biased.",
        "feature_recipe": {"name": "alpha158", "version": 1, "parameters": {}},
        "label_recipe": {
            "name": "next_session_open_to_open",
            "decision": "close_t",
            "fill": "open_t_plus_1",
            "horizon_sessions": 1,
        },
        "model": {"name": "lightgbm", "parameters": {"num_leaves": 31}},
        "portfolio": {
            "selection": "top_quintile",
            "weighting": "equal",
            "long_only": True,
        },
        "costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
        "folds": [
            {
                "fold": 0,
                "train_start": "2023-01-02T21:00:00+00:00",
                "train_end": "2024-05-19T21:00:00+00:00",
                "validation_start": "2024-05-25T21:00:00+00:00",
                "validation_end": "2024-09-21T21:00:00+00:00",
                "test_start": "2024-09-27T21:00:00+00:00",
                "test_end": "2025-01-26T21:00:00+00:00",
            }
        ],
        "purge_sessions": 5,
        "embargo_sessions": 5,
        "seed": 7,
        "worker_lock_hash": "d" * 64,
        "panel": {"path": "panel.parquet", "sha256": "e" * 64, "rows": 15120},
        "config_hash": "f" * 64,
    }


def _diagnostics() -> dict[str, Any]:
    return {
        "authority": "qlib_diagnostic_only",
        "versions": {"worker": "1.0.0", "pyqlib": "0.9.7", "lightgbm": "4.6.0"},
        "feature_recipe": {
            "name": "Alpha158-style",
            "feature_count": 158,
            "names": ["KMID", "KLEN"],
            "vwap_source": "causal_typical_price_proxy_not_vendor_vwap",
        },
        "label_recipe": {
            "name": "next_session_open_to_open",
            "definition": "open[target+1] / open[target] - 1",
            "decision": "close_t",
            "entry": "open_t_plus_1",
        },
        "score_distribution": {
            "min": -1.0,
            "max": 1.0,
            "mean": 0.0,
            "std": 0.5,
            "q05": -0.8,
            "q25": -0.25,
            "q50": 0.0,
            "q75": 0.25,
            "q95": 0.8,
        },
        "folds": [
            {
                "fold": 0,
                "fit_count": 1,
                "train_rows": 10000,
                "validation_rows": 2400,
                "test_rows": 2500,
                "best_iteration": 42,
                "model_hash": "1" * 64,
                "normalization": {
                    "method": "train_only_median_then_zscore",
                    "statistics_hash": "2" * 64,
                    "all_missing_train_features": 0,
                },
                "training_history": {
                    "train": {"l2": [0.3, 0.2, 0.1]},
                    "valid": {"l2": [0.4, 0.3, 0.25]},
                },
                "boundaries": _request()["folds"][0] | {},
            }
        ],
        "feature_importance": [
            {"feature": "KMID", "mean_gain": 10.0, "mean_split_count": 4.0},
            {"feature": "KLEN", "mean_gain": 5.0, "mean_split_count": 2.0},
        ],
        "signal_analysis": {
            "authority": "qlib_diagnostic_only",
            "ic": {
                "mean": 0.05,
                "rank_mean": 0.07,
                "by_target": [
                    {
                        "target_ts": "2024-09-27T21:00:00+00:00",
                        "ic": 0.04,
                        "rank_ic": 0.06,
                        "sample_count": 20,
                    },
                    {
                        "target_ts": "2024-09-28T21:00:00+00:00",
                        "ic": 0.05,
                        "rank_ic": 0.08,
                        "sample_count": 20,
                    },
                ],
            },
            "quantile_returns": [
                {"quantile": index, "mean_return": index / 1000, "observations": 100}
                for index in range(1, 6)
            ],
            "portfolio": {
                "selection": "long_only_top_quintile_equal_weight",
                "declared_costs": {"fee_bps": 1.0, "slippage_bps": 2.0},
                "periods": 2,
                "gross_total_return": 0.03,
                "costed_total_return": 0.02,
                "benchmark_total_return": 0.01,
                "costed_excess_total_return": 0.01,
                "mean_turnover": 0.8,
                "timeline": [
                    {
                        "target_ts": f"2024-09-{27 + index}T21:00:00+00:00",
                        "gross_return": 0.01 + index / 100,
                        "costed_return": 0.009 + index / 100,
                        "benchmark_return": 0.005,
                        "excess_return": 0.004 + index / 100,
                        "turnover": 1.0 - index / 2,
                        "gross_equity": 1.01 + index / 100,
                        "costed_equity": 1.009 + index / 100,
                        "benchmark_equity": 1.005 + index / 100,
                    }
                    for index in range(2)
                ],
            },
        },
        "portfolio_replay": {
            "status": "pending_canonical_alpha_engine_replay",
            "reason": "canonical replay required",
            "selection": _request()["portfolio"],
            "costs": _request()["costs"],
        },
        "counterfactual_refit": False,
        "label": "OOS prediction contract validated — canonical ALPHA replay pending",
    }


def _write_exchange(data_dir: Path) -> Path:
    exchange = data_dir / "control" / "ml" / "exchanges" / EXCHANGE_ID
    exchange.mkdir(parents=True)
    request = _request()
    (exchange / "request.json").write_text(json.dumps(request), encoding="utf-8")
    result = {
        "schema_version": 1,
        "status": "succeeded",
        "request_sha256": hashlib.sha256((exchange / "request.json").read_bytes()).hexdigest(),
        "snapshot_hash": request["snapshot_hash"],
        "config_hash": request["config_hash"],
        "worker_lock_hash": request["worker_lock_hash"],
        "seed": request["seed"],
        "worker": {"kind": "qlib", "implementation_version": "1.0.0"},
        "predictions": {"path": "predictions.parquet", "sha256": "3" * 64, "rows": 2500},
        "diagnostics": _diagnostics(),
        "diagnostic_only": True,
        "counterfactual_refit": False,
    }
    (exchange / "result.json").write_text(json.dumps(result), encoding="utf-8")
    return exchange


def test_exchange_projection_omits_raw_paths_and_bounds_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_exchange(tmp_path)
    monkeypatch.setattr(
        _ml,
        "_run_json",
        lambda args, **kwargs: (
            {"status": "validated"}
            if args[:2] == ["ml", "import"]
            else {"diagnostics": _diagnostics()}
        ),
    )

    detail = _ml.exchange_detail(EXCHANGE_ID, data_dir=tmp_path)
    tear = _ml.exchange_tearsheet(
        EXCHANGE_ID,
        data_dir=tmp_path,
        feature_limit=1,
        timeline_limit=1,
        timeline_offset=1,
        history_limit=2,
    )

    assert detail["status"] == "trained"
    assert detail["contract"]["panel_rows"] == 15120
    assert "path" not in json.dumps(detail).lower()
    assert len(tear["feature_importance"]) == 1
    assert tear["feature_importance_truncated"] is True
    assert tear["ic"]["by_target"][0]["target_ts"].startswith("2024-09-28")
    assert tear["portfolio"]["timeline"][0]["target_ts"].startswith("2024-09-28")
    assert tear["timeline_has_more"] is False
    assert tear["folds"][0]["training_history"]["train"]["l2"] == [0.3, 0.1]


def test_frontend_service_status_is_honest_when_panel_producer_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        _ml,
        "readiness",
        lambda **_: {
            "isolation_ready": True,
            "worker_environment_present": True,
            "heavy_job_limit": 1,
            "heavy_job_busy": False,
        },
    )
    monkeypatch.setattr(
        _ml,
        "_heavy_capacity",
        lambda **_: {"busy": False, "active_jobs": [], "limit": 1},
    )
    monkeypatch.setattr(
        _ml,
        "_catalog_commands",
        lambda **_: [{"id": "ml prepare"}, {"id": "ml train"}],
    )

    status = _ml.service_status(data_dir=tmp_path)

    assert status["available"] is True
    assert status["worker_ready"] is False
    assert "producer" in str(status["message"])


def test_existing_exchanges_project_to_frontend_ml_experiments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_exchange(tmp_path)
    monkeypatch.setattr(
        _ml,
        "_durable_jobs",
        lambda **_: [
            {
                "kind": "ml_prepare",
                "status": "succeeded",
                "project_id": "project-1",
                "result_run_id": None,
                "request": {"exchange_id": EXCHANGE_ID},
            },
            {
                "kind": "ml_replay",
                "status": "succeeded",
                "project_id": "project-1",
                "result_run_id": "0123456789abcdef",
                "request": {"exchange_id": EXCHANGE_ID},
            },
        ],
    )

    page = _ml.list_experiments(data_dir=tmp_path, project_id="project-1", limit=10, offset=0)

    item = page["items"][0]
    assert item["experiment_id"] == EXCHANGE_ID
    assert item["universe_size"] == 20
    assert item["aligned_sessions"] == 756
    assert item["metrics"] == {
        "ic": 0.05,
        "rank_ic": 0.07,
        "turnover": 0.8,
        "costed_return": 0.02,
    }
    assert item["replay_run_id"] == "0123456789abcdef"


def test_qlib_suite_projects_managed_exchange_and_canonical_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_exchange(tmp_path)
    monkeypatch.setattr(
        _ml,
        "_durable_jobs",
        lambda **_: [
            {
                "kind": "suite:qlib",
                "status": "succeeded",
                "project_id": "project-1",
                "result_run_id": "0123456789abcdef",
                "request": {
                    "action": "qlib",
                    "governance": {"managed_resource_id": EXCHANGE_ID},
                },
            }
        ],
    )

    page = _ml.list_experiments(data_dir=tmp_path, project_id="project-1", limit=10, offset=0)

    item = page["items"][0]
    assert item["experiment_id"] == EXCHANGE_ID
    assert item["project_id"] == "project-1"
    assert item["replay_run_id"] == "0123456789abcdef"


def test_exchange_ids_and_input_bundles_are_traversal_safe(tmp_path: Path) -> None:
    with pytest.raises(_ml.MlNotFoundError, match="invalid exchange_id"):
        _ml.exchange_detail("../secret", data_dir=tmp_path)

    input_dir = tmp_path / "control" / "ml" / "inputs" / INPUT_ID
    input_dir.mkdir(parents=True)
    (input_dir / "spec.json").write_text("{}", encoding="utf-8")
    (input_dir / "panel.parquet").write_bytes(b"PAR1")
    assert _ml.input_bundle(INPUT_ID, data_dir=tmp_path)["ready"] is True

    symlink = tmp_path / "control" / "ml" / "inputs" / ("c" * 32)
    symlink.symlink_to(input_dir, target_is_directory=True)
    with pytest.raises(_ml.MlNotFoundError, match="regular directory"):
        _ml.input_bundle("c" * 32, data_dir=tmp_path)


def test_exchange_projection_rejects_duplicate_or_nonfinite_control_json(tmp_path: Path) -> None:
    exchange = tmp_path / "control" / "ml" / "exchanges" / EXCHANGE_ID
    exchange.mkdir(parents=True)
    (exchange / "request.json").write_text('{"schema_version":1,"schema_version":2}')
    with pytest.raises(_ml.MlError, match="duplicate key"):
        _ml.exchange_detail(EXCHANGE_ID, data_dir=tmp_path)

    (exchange / "request.json").write_text('{"schema_version":NaN}')
    with pytest.raises(_ml.MlError, match="non-finite"):
        _ml.exchange_detail(EXCHANGE_ID, data_dir=tmp_path)


def test_canonical_replay_tearsheet_reads_only_declared_ml_artifacts(tmp_path: Path) -> None:
    run_id = "0123456789abcdef"
    rdir = tmp_path / "runs" / run_id
    rdir.mkdir(parents=True)
    manifest = {
        "schema_version": 3,
        "run_id": run_id,
        "run_identity_version": 3,
        "artifact_contract_version": 3,
        "execution_fingerprint": "1" * 64,
        "strategy_fingerprint": None,
        "source_fingerprint": "2" * 64,
        "command": "ml_replay",
        "authority": "alpha_canonical_execution_and_validation",
        "label": "OOS replay validated — model not recomputed under counterfactual",
        "config_hash": "f" * 64,
        "snapshot_hash": "c" * 64,
        "worker_lock_hash": "d" * 64,
        "universe": [f"S{index:02d}" for index in range(20)],
        "universe_membership": "point_in_time",
        "survivorship_warning": None,
        "metrics": {"total_return": 0.02, "sharpe": 1.1},
        "validation": {"promotion_eligible": False, "counterfactual_refit": False},
    }
    pl.DataFrame(
        {
            "fold": [0, 0],
            "target_ts": [
                "2024-09-27T21:00:00+00:00",
                "2024-09-28T21:00:00+00:00",
            ],
            "exit_ts": [
                "2024-09-28T21:00:00+00:00",
                "2024-09-29T21:00:00+00:00",
            ],
            "gross_return": [0.01, 0.02],
            "net_return": [0.009, 0.019],
            "benchmark_return": [0.005, 0.006],
            "excess_return": [0.004, 0.013],
            "turnover": [1.0, 0.5],
            "fees": [10.0, 5.0],
            "slippage_cost": [20.0, 10.0],
        }
    ).with_columns(
        pl.col("target_ts").str.to_datetime(time_zone="UTC"),
        pl.col("exit_ts").str.to_datetime(time_zone="UTC"),
    ).write_parquet(rdir / "ml_periods.parquet")
    pl.DataFrame(
        {
            "fold": [0],
            "train_start": ["2023-01-02T21:00:00+00:00"],
            "train_end": ["2024-05-19T21:00:00+00:00"],
            "validation_start": ["2024-05-25T21:00:00+00:00"],
            "validation_end": ["2024-09-21T21:00:00+00:00"],
            "test_start": ["2024-09-27T21:00:00+00:00"],
            "test_end": ["2025-01-26T21:00:00+00:00"],
        }
    ).with_columns(
        [
            pl.col(name).str.to_datetime(time_zone="UTC")
            for name in (
                "train_start",
                "train_end",
                "validation_start",
                "validation_end",
                "test_start",
                "test_end",
            )
        ]
    ).write_parquet(rdir / "folds.parquet")
    pl.DataFrame({"selected": [True, False, True]}).write_parquet(rdir / "ml_signals.parquet")
    pl.DataFrame({"score": [0.1, 0.2, 0.3]}).write_parquet(rdir / "ml_predictions.parquet")
    manifest["artifacts"] = artifact_contract(rdir)
    artifacts = cast(dict[str, dict[str, object]], manifest["artifacts"])
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    body = _ml.replay_tearsheet(run_id, data_dir=tmp_path, limit=1, offset=1)

    assert body["authority"] == "alpha_canonical_execution_and_validation"
    assert body["promotion_eligible"] is False
    assert body["selected_signals"] == 2
    assert body["periods"][0]["net_return"] == 0.019
    assert body["periods_total"] == 2
    assert (
        body["artifact_provenance"]["ml_periods.parquet"]
        == artifacts["ml_periods.parquet"]["sha256"]
    )


def test_launch_action_journals_safe_ids_not_internal_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    input_dir = tmp_path / "control" / "ml" / "inputs" / INPUT_ID
    input_dir.mkdir(parents=True)
    (input_dir / "spec.json").write_text("{}", encoding="utf-8")
    (input_dir / "panel.parquet").write_bytes(b"PAR1")
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "pyproject.toml").write_text("[project]\nname='worker'\n", encoding="utf-8")
    (worker / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_json(args: list[str], *, data_dir: Path) -> object:
        del data_dir
        calls.append(args)
        if args[:2] == ["project", "job-list"]:
            return []
        if args[:2] == ["project", "job-create"]:
            return {"job_id": "00000000-0000-4000-8000-000000000001", "status": "queued"}
        return {"job_id": "00000000-0000-4000-8000-000000000001", "status": args[3]}

    monkeypatch.setattr(_ml, "_run_json", fake_json)
    monkeypatch.setattr(_ml, "_worker_project", lambda: worker)
    monkeypatch.setattr(_ml, "_start_job", lambda *args, **kwargs: None)

    accepted = _ml.launch_action(
        "prepare",
        data_dir=tmp_path,
        input_bundle_id=INPUT_ID,
        exchange_id=EXCHANGE_ID,
        project_id=None,
        experiment_id=None,
    )

    assert accepted["job_id"].endswith("0001")
    created = next(args for args in calls if args[:2] == ["project", "job-create"])
    request = json.loads(created[created.index("--request-json") + 1])
    assert request == {
        "action": "prepare",
        "exchange_id": EXCHANGE_ID,
        "input_bundle_id": INPUT_ID,
    }
    assert str(tmp_path) not in json.dumps(request)
    assert accepted["exchange_id"] == EXCHANGE_ID


def test_completed_worker_job_records_progress_before_terminal_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        _ml,
        "_run_process",
        lambda *args, **kwargs: (
            0,
            '{"status":"validated","rows":20,"config_hash":"' + "a" * 64 + '"}\n',
            "",
        ),
    )

    def journal(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        return {"status": "ok"}

    monkeypatch.setattr(_ml, "_journal", journal)

    _ml._execute_job(
        "00000000-0000-4000-8000-000000000001",
        "import",
        ["ml", "import", "/internal/exchange", "--json"],
        data_dir=tmp_path,
        timeout_seconds=600,
    )

    assert calls[0][1:4] == ["job-event", "00000000-0000-4000-8000-000000000001", "progress"]
    assert calls[1][1:5] == [
        "job-status",
        "00000000-0000-4000-8000-000000000001",
        "succeeded",
        "--json",
    ]


def test_silent_ml_child_heartbeats_and_heartbeat_failure_aborts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "55555555-5555-4555-8555-555555555555"
    calls: list[list[str]] = []

    def journal(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            return {"job_id": job_id, "cancel_requested": False}
        return {"status": "ok"}

    monkeypatch.setattr(_ml, "_journal", journal)
    monkeypatch.setattr(_ml, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.02)
    monkeypatch.setattr(
        _ml,
        "_command",
        lambda args: [
            sys.executable,
            "-c",
            'import time; time.sleep(0.15); print(\'{"status":"validated","rows":20}\')',
        ],
    )

    _ml._execute_job(job_id, "import", ["ml", "import"], data_dir=tmp_path, timeout_seconds=2)

    heartbeats = [args for args in calls if args[1:4] == ["job-event", job_id, "heartbeat"]]
    assert len(heartbeats) >= 2
    assert calls[-2][3] == "progress"
    assert calls[-1][3] == "succeeded"

    calls.clear()

    def failing_journal(args: list[str], **kwargs: object) -> dict[str, object]:
        del kwargs
        calls.append(args)
        if args[1:4] == ["job-event", job_id, "heartbeat"]:
            raise RuntimeError("heartbeat CLI unavailable")
        return {"status": "ok"}

    monkeypatch.setattr(_ml, "_journal", failing_journal)
    monkeypatch.setattr(
        _ml,
        "_command",
        lambda args: [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    started = time.monotonic()

    _ml._execute_job(job_id, "train", ["ml", "train"], data_dir=tmp_path, timeout_seconds=60)

    assert time.monotonic() - started < 2
    failed = [args for args in calls if args[1:4] == ["job-status", job_id, "failed"]]
    assert len(failed) == 1
    assert not any(args[1:4] == ["job-status", job_id, "succeeded"] for args in calls)


def test_silent_ml_child_honours_audited_cancellation_and_releases_capacity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id = "88888888-8888-4888-8888-888888888888"
    store = ControlStore(tmp_path)
    store.create_job(kind="ml_train", request={"test": "cancel"}, job_id=job_id)
    store.set_job_status(job_id, "running")
    monkeypatch.setattr(_ml, "_DURABLE_HEARTBEAT_INTERVAL_S", 0.03)
    monkeypatch.setattr(
        _ml,
        "_command",
        lambda args: [sys.executable, "-c", "import time; time.sleep(30)"],
    )
    worker = threading.Thread(
        target=_ml._execute_job,
        args=(job_id, "train", ["ml", "train"]),
        kwargs={"data_dir": tmp_path, "timeout_seconds": 60},
    )
    worker.start()
    time.sleep(0.05)
    assert worker.is_alive()
    store.request_job_cancellation(job_id, actor="owner", reason="stop test worker")
    worker.join(timeout=5)

    assert not worker.is_alive(), "cancelled ML process was not reaped"
    row = store.get_job(job_id)
    assert row["status"] == "cancelled"
    assert store.heavyweight_job_capacity()["active_count"] == 0
    terminal_events = cast(list[dict[str, Any]], row["events"])
    transitions = [
        event["payload"].get("to") for event in terminal_events if event["event_type"] == "status"
    ]
    assert transitions[-1] == "cancelled"
    assert "failed" not in transitions
    assert "succeeded" not in transitions
    terminal_sequence = row["last_sequence"]
    time.sleep(0.1)
    assert store.get_job(job_id)["last_sequence"] == terminal_sequence


def test_input_generation_uses_cli_owned_snapshot_producer_and_opaque_journal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    def journal(args: list[str], **kwargs: object) -> dict[str, str]:
        del kwargs
        calls.append(args)
        return {"job_id": "00000000-0000-4000-8000-000000000002", "status": "queued"}

    started: list[list[str]] = []
    monkeypatch.setattr(_ml, "_journal", journal)
    monkeypatch.setattr(
        _ml,
        "_start_job",
        lambda job_id, action, args, **kwargs: started.append(args),
    )

    accepted = _ml.launch_input_generation(
        data_dir=tmp_path,
        project_id="project-1",
        experiment_id="ex_" + "a" * 64,
        input_bundle_id=INPUT_ID,
        timeout_seconds=600,
    )

    create = calls[0]
    request = json.loads(create[create.index("--request-json") + 1])
    assert request == {
        "action": "export-input",
        "experiment_id": "ex_" + "a" * 64,
        "input_bundle_id": INPUT_ID,
        "project_id": "project-1",
    }
    assert started[0][:4] == [
        "ml",
        "export-input",
        "project-1",
        "ex_" + "a" * 64,
    ]
    assert accepted["input_bundle_id"] == INPUT_ID
    assert str(tmp_path) not in json.dumps(request)


def test_one_click_experiment_generation_exports_then_prepares(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(
        _ml,
        "_run_json",
        lambda args, **kwargs: {
            "current_experiment_id": "ex_" + "a" * 64,
        },
    )

    def journal(args: list[str], **kwargs: object) -> dict[str, str]:
        del kwargs
        calls.append(args)
        return {"job_id": "00000000-0000-4000-8000-000000000003", "status": "queued"}

    monkeypatch.setattr(_ml, "_journal", journal)
    pipelines: list[list[tuple[str, list[str], int]]] = []

    def start_pipeline(
        job_id: str, steps: list[tuple[str, list[str], int]], **kwargs: object
    ) -> None:
        del job_id, kwargs
        pipelines.append(steps)

    monkeypatch.setattr(_ml, "_start_pipeline", start_pipeline)
    worker = tmp_path / "worker"
    worker.mkdir()
    (worker / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    monkeypatch.setattr(_ml, "_worker_project", lambda: worker)

    accepted = _ml.launch_experiment_generation(
        data_dir=tmp_path,
        project_id="project-1",
        experiment_id=None,
        timeout_seconds=1200,
    )

    assert accepted["action"] == "generate-experiment"
    assert accepted["exchange_id"]
    assert [step[0] for step in pipelines[0]] == ["export-input", "prepare"]
    safe_request = json.loads(calls[0][calls[0].index("--request-json") + 1])
    assert str(tmp_path) not in json.dumps(safe_request)


def test_generation_pipeline_journals_each_step_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process_calls: list[list[str]] = []
    journal_calls: list[list[str]] = []

    def run_process(args: list[str], **kwargs: object) -> tuple[int, str, str]:
        del kwargs
        process_calls.append(args)
        return 0, json.dumps({"status": "ok", "rows": 15120}) + "\n", ""

    def journal(args: list[str], **kwargs: object) -> dict[str, str]:
        del kwargs
        journal_calls.append(args)
        return {"status": "ok"}

    monkeypatch.setattr(_ml, "_run_process", run_process)
    monkeypatch.setattr(_ml, "_journal", journal)
    steps = [
        ("export-input", ["ml", "export-input", "project", "experiment", "opaque"], 600),
        ("prepare", ["ml", "prepare", "spec", "panel", "exchange"], 600),
    ]

    _ml._execute_pipeline(
        "00000000-0000-4000-8000-000000000004",
        steps,
        data_dir=tmp_path,
    )

    assert len(process_calls) == 2
    assert [call[3] for call in journal_calls] == ["progress", "progress", "succeeded"]
