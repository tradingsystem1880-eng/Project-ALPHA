"""``alpha forecast run --as-of`` is PIT-safe: poisoning bars after the as-of date must not
change the forecast artifacts, and poisoning a bar inside the window must (discriminating
power). Uses the fake model, whose output is a pure function of the window + seed."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_core import Bar
from tests.fixtures.forecast_fixtures import daily_bars, store_bars

pytestmark = pytest.mark.bias_guard

runner = CliRunner()


def _spike(bar: Bar) -> Bar:
    spiked = bar.close * 9.9
    return Bar(
        symbol=bar.symbol,
        ts=bar.ts,
        open=bar.open,
        high=max(bar.high, spiked),
        low=bar.low,
        close=spiked,
        volume=bar.volume,
    )


def _run_and_read(tmp_path: Path, as_of: str) -> tuple[str, bytes]:
    result = runner.invoke(
        app,
        [
            "forecast",
            "run",
            "SPY",
            "--model",
            "fake",
            "--context",
            "8",
            "--horizon",
            "4",
            "--samples",
            "6",
            "--as-of",
            as_of,
        ],
    )
    assert result.exit_code == 0, result.output
    (rdir,) = sorted(p for p in (tmp_path / "forecast").iterdir() if p.is_dir())
    manifest = json.loads((rdir / "manifest.json").read_text())
    return manifest["run_id"], (rdir / "quantiles.parquet").read_bytes()


def test_future_poison_does_not_change_as_of_forecast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    clean = daily_bars(40, start=date(2026, 1, 5))
    as_of = clean[24].ts.date().isoformat()

    store_bars(tmp_path, clean)
    run_a, quantiles_a = _run_and_read(tmp_path, as_of)

    poisoned = clean[:25] + [_spike(b) for b in clean[25:]]  # poison strictly after as-of
    store_bars(tmp_path, poisoned)
    run_b, quantiles_b = _run_and_read(tmp_path, as_of)

    assert run_a == run_b
    assert quantiles_a == quantiles_b


def test_in_window_poison_changes_forecast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    clean = daily_bars(40, start=date(2026, 1, 5))
    as_of = clean[24].ts.date().isoformat()

    store_bars(tmp_path, clean)
    _, quantiles_a = _run_and_read(tmp_path, as_of)

    poisoned = clean[:24] + [_spike(clean[24])] + clean[25:]  # poison the as-of bar itself
    store_bars(tmp_path, poisoned)
    _, quantiles_b = _run_and_read(tmp_path, as_of)

    assert quantiles_a != quantiles_b  # otherwise this guard has no discriminating power
