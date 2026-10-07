"""Proposed holdout: platform defects found by the 2026-09-28 agentic benchmark (tools/alpha-eval).

Each test states the behavioural contract and is pinned ``xfail(strict=True)`` because the defect is
open today: the suite stays green, and the fix turns the test into an XPASS that fails strictly, so
whoever fixes it must also remove the marker. Evidence (Layer A probes P02 and P09):
docs/audit/2026-09-28-agentic-benchmark-baseline.md.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli.main import app
from alpha_data.store import ParquetStore

pytestmark = pytest.mark.holdout

_SMALL = [
    "--lookback", "20", "--skip", "1", "--vol-window", "10",
    "--tier1-paths", "50", "--tier2-paths", "8", "--n-resamples", "100", "--max-workers", "1",
]  # fmt: skip


def _frame(closes: np.ndarray) -> pl.DataFrame:
    start = date(2020, 1, 1)
    return pl.DataFrame(
        [
            {
                "ts": datetime.fromordinal(start.toordinal() + i).replace(tzinfo=UTC),
                "open": c,
                "high": c,
                "low": c,
                "close": c,
                "volume": 1e6,
            }
            for i, c in enumerate(closes.tolist())
        ]
    )


@pytest.mark.xfail(strict=True, reason="P09: non-finite bar escapes as a pydantic traceback")
def test_validate_on_non_finite_close_fails_loud_with_a_typed_data_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fail-loud contract: invalid data is a typed usage error (exit 2), never a raw traceback."""
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    rng = np.random.default_rng(0)
    closes = 100.0 * np.cumprod(1.0 + 0.002 + rng.normal(0.0, 0.01, 300))
    closes[150] = float("nan")
    path = tmp_path / "store" / "bars" / "NANX.parquet"
    path.parent.mkdir(parents=True)
    _frame(closes).write_parquet(path)  # raw write: data that bypassed provider ingestion
    result = CliRunner().invoke(
        app, ["validate", "NANX", "--train-size", "100", "--test-size", "40", *_SMALL]
    )
    assert result.exit_code == 2, (result.exit_code, repr(result.exception))


@pytest.mark.xfail(strict=True, reason="P02: denied OOS orders are silent in the manifest")
def test_denied_orders_are_disclosed_in_the_validation_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A strategy whose orders the venue DENIED did not run as specified; the verdict must say so.

    World: uptrend, drawdown, uptrend. After the drawdown a cash-account BUY sized from starting
    capital is denied, so part of the OOS record is an unintended flat position.
    """
    monkeypatch.setenv("ALPHA_DATA_DIR", str(tmp_path))
    rng = np.random.default_rng(0)
    drift = np.r_[np.full(200, 0.004), np.full(80, -0.012), np.full(320, 0.004)]
    closes = 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, 0.01, drift.size))
    ParquetStore(tmp_path / "store").write_bars("DNY", _frame(closes))
    result = CliRunner().invoke(
        app,
        [
            "validate", "DNY", "--rebalance-every", "5", "--train-size", "150",
            "--test-size", "60", "--embargo", "2", "--periods-per-year", "365", *_SMALL,
        ],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    run_dir = next((tmp_path / "runs").iterdir())
    orders = pl.read_parquet(run_dir / "orders.parquet")
    denied = orders.filter(pl.col("status") == "DENIED").height
    manifest = (run_dir / "manifest.json").read_text(encoding="utf-8")
    assert denied == 0 or "denied" in manifest.lower(), (
        f"{denied} DENIED orders, none disclosed in manifest keys {sorted(json.loads(manifest))}"
    )
