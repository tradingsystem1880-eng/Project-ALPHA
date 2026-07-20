"""Research ``--as-of`` must make canonical backtest artifacts future-poison invariant."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_core import Bar
from tests.fixtures.forecast_fixtures import daily_bars, store_bars

pytestmark = pytest.mark.bias_guard

_RUN_ID = re.compile(r"-> run ([0-9a-f]{16})")


def _spike(bar: Bar) -> Bar:
    close = bar.close * 7.0
    return Bar(
        symbol=bar.symbol,
        ts=bar.ts,
        open=bar.open,
        high=max(bar.high, close),
        low=bar.low,
        close=close,
        volume=bar.volume,
    )


def _run(tmp_path: Path, as_of: str) -> tuple[str, dict[str, bytes]]:
    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "run",
            "SPY",
            "--lookback",
            "5",
            "--skip",
            "1",
            "--vol-window",
            "3",
            "--rebalance-every",
            "2",
            "--target-vol",
            "0.05",
            "--max-leverage",
            "0.25",
            "--starting-cash",
            "100000",
            "--as-of",
            as_of,
        ],
    )
    assert result.exit_code == 0, result.output
    match = _RUN_ID.search(result.output)
    assert match is not None, result.output
    run_id = match.group(1)
    run_dir = tmp_path / "runs" / run_id
    return run_id, {
        name: (run_dir / name).read_bytes()
        for name in (
            "manifest.json",
            "equity_curve.parquet",
            "decision_trace.parquet",
            "indicator_series.parquet",
        )
    }


def test_post_cutoff_price_mutation_cannot_change_research_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    clean = daily_bars(40, start=date(2020, 1, 2))
    as_of = clean[24].ts.date().isoformat()
    store_bars(tmp_path, clean)
    run_a, artifacts_a = _run(tmp_path, as_of)

    store_bars(tmp_path, clean[:25] + [_spike(bar) for bar in clean[25:]])
    run_b, artifacts_b = _run(tmp_path, as_of)

    assert run_b == run_a
    assert artifacts_b == artifacts_a


def test_cutoff_guard_has_in_window_discriminating_power(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    clean = daily_bars(40, start=date(2020, 1, 2))
    as_of = clean[24].ts.date().isoformat()
    store_bars(tmp_path, clean)
    run_a, _ = _run(tmp_path, as_of)

    store_bars(tmp_path, [*clean[:24], _spike(clean[24]), *clean[25:]])
    run_b, _ = _run(tmp_path, as_of)

    assert run_b != run_a
