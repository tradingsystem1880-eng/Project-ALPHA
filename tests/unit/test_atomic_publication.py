"""Failure and concurrency guards for completion-marker publication."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_cli import _artifacts, _forecast
from alpha_forecast import FakeForecaster
from tests.fixtures.forecast_fixtures import daily_bars


def _temp_files(root: Path) -> list[Path]:
    return [path for path in root.rglob(".*.tmp") if path.is_file()]


def test_run_sidecar_failure_never_publishes_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original: Any = _artifacts.publish  # type: ignore[attr-defined]
    calls = 0

    def fail_second(path: Path, writer: Any) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("disk full")
        original(path, writer)

    monkeypatch.setattr(_artifacts, "publish", fail_second)
    rdir = tmp_path / "runs" / "0123456789abcdef"
    with pytest.raises(OSError, match="disk full"):
        _artifacts.write_run(
            rdir,
            manifest={"run_id": "0123456789abcdef"},
            equity=[(datetime(2026, 1, 1, tzinfo=UTC), 1.0)],
            trades=[],
        )

    assert not (rdir / "manifest.json").exists()
    assert _temp_files(rdir) == []


def test_concurrent_identical_run_writers_publish_one_complete_set(tmp_path: Path) -> None:
    rdir = tmp_path / "runs" / "0123456789abcdef"
    manifest = {"run_id": "0123456789abcdef", "command": "backtest_run"}

    def write() -> None:
        _artifacts.write_run(
            rdir,
            manifest=manifest,
            equity=[(datetime(2026, 1, 1, tzinfo=UTC), 1.0)],
            trades=[],
        )

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: write(), range(8)))

    assert _artifacts.read_manifest(rdir) == manifest
    assert _artifacts.read_equity(rdir)[0][1] == 1.0
    assert (rdir / "trades.parquet").is_file()
    assert _temp_files(rdir) == []


def test_forecast_sidecar_failure_never_publishes_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = daily_bars(8)
    out = _forecast.run_forecast(
        bars,
        forecaster=FakeForecaster(),
        context=5,
        horizon=2,
        sample_count=3,
        temperature=1.0,
        top_p=0.9,
        top_k=0,
        seed=7,
        as_of=None,
        cutoff=date(2025, 1, 1),
    )
    original: Any = _forecast.publish  # type: ignore[attr-defined]

    def fail_history(path: Path, writer: Any) -> None:
        if path.name == "history.parquet":
            raise OSError("disk full")
        original(path, writer)

    monkeypatch.setattr(_forecast, "publish", fail_history)
    rdir = tmp_path / "forecast" / "0123456789abcdef"
    with pytest.raises(OSError, match="disk full"):
        _forecast.write_forecast_run(
            rdir,
            manifest={"run_id": "0123456789abcdef"},
            out=out,
            history=bars,
        )

    assert not (rdir / "manifest.json").exists()
    assert _temp_files(rdir) == []
