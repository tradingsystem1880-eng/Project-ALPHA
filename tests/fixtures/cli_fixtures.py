"""Offline, deterministic store seeding for the CLI integration tests (no network).

A *noisy* upward random walk (fixed seed), not a smooth ramp: the validation gauntlet needs OOS
returns with real dispersion (a perfectly smooth trend yields a zero-variance Sharpe), while the
positive drift keeps the momentum strategy reliably long so it trades.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np
import polars as pl

from alpha_data.store import ParquetStore


def _noisy_bars(symbol: str, n: int, *, seed: int, drift: float, sigma: float) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    closes = 100.0 * np.cumprod(1.0 + drift + rng.normal(0.0, sigma, n))
    start = date(2020, 1, 1)
    rows = [
        {
            "ts": datetime.fromordinal(start.toordinal() + i).replace(tzinfo=UTC),
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": 1000.0,
        }
        for i, c in enumerate(closes.tolist())
    ]
    return pl.DataFrame(rows)


def seed_store(
    data_dir: Path,
    *,
    symbol: str = "SPY",
    n: int = 60,
    seed: int = 0,
    drift: float = 0.002,
    sigma: float = 0.01,
) -> None:
    """Write a deterministic ``n``-bar noisy uptrend for ``symbol`` into the CLI store.

    The store lives at ``data_dir/store`` (matching the CLI). ``n`` is large enough for the
    small-parameter strategy to warm up, trade, and produce several walk-forward folds offline.
    """
    df = _noisy_bars(symbol, n, seed=seed, drift=drift, sigma=sigma)
    ParquetStore(data_dir / "store").write_bars(symbol, df)
