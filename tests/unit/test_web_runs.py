"""Web filesystem reads over the run store.

`_runs` indexes the run store the same way the CLI's `report` does (the workstation JSON API is a
thin layer over these readers).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_web import _runs


def _write_run(
    data_dir: Path,
    run_type: str,
    run_id: str,
    manifest: dict[str, object],
    equity: list[float] | None = None,
) -> None:
    rdir = data_dir / run_type / run_id
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if equity is not None:
        ts = [datetime(2020, 1, 1 + i, tzinfo=UTC) for i in range(len(equity))]
        pl.DataFrame({"ts": ts, "equity": equity}).write_parquet(rdir / "equity_curve.parquet")


def test_list_runs_indexes_every_run_type(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "runs",
        "aaaa000000000001",
        {"command": "validate", "symbol": "SPY", "passed": True},
    )
    _write_run(
        tmp_path, "propfirm", "bbbb000000000002", {"command": "propfirm", "source": "symbol:AAPL"}
    )
    runs = {r["run_id"]: r for r in _runs.list_runs(data_dir=tmp_path)}
    assert set(runs) == {"aaaa000000000001", "bbbb000000000002"}
    assert runs["aaaa000000000001"]["command"] == "validate"
    assert runs["aaaa000000000001"]["label"] == "SPY"
    assert runs["aaaa000000000001"]["passed"] is True
    assert runs["bbbb000000000002"]["label"] == "symbol:AAPL"


def test_get_run_returns_manifest_or_fails_loud(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "runs",
        "cccc000000000003",
        {"command": "backtest_run", "run_id": "cccc000000000003"},
    )
    assert _runs.get_run("cccc000000000003", data_dir=tmp_path)["command"] == "backtest_run"
    with pytest.raises(FileNotFoundError):
        _runs.get_run("nope", data_dir=tmp_path)


def test_equity_values_reads_the_parquet(tmp_path: Path) -> None:
    _write_run(
        tmp_path,
        "runs",
        "dddd000000000004",
        {"command": "backtest_run"},
        equity=[100.0, 101.0, 99.5],
    )
    vals = _runs.equity_values("dddd000000000004", data_dir=tmp_path)
    assert vals == [100.0, 101.0, 99.5]


def test_equity_values_is_empty_without_a_curve(tmp_path: Path) -> None:
    _write_run(
        tmp_path, "optim", "eeee000000000005", {"command": "optim_grid"}
    )  # no equity parquet
    assert _runs.equity_values("eeee000000000005", data_dir=tmp_path) == []


def test_tearsheet_file_present_only_when_written(tmp_path: Path) -> None:
    _write_run(tmp_path, "runs", "ffff000000000006", {"command": "validate"})
    assert _runs.tearsheet_file("ffff000000000006", data_dir=tmp_path) is None
    (tmp_path / "runs" / "ffff000000000006" / "tearsheet.html").write_text("<html></html>")
    assert _runs.tearsheet_file("ffff000000000006", data_dir=tmp_path) is not None
