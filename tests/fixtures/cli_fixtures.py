"""Offline, deterministic store seeding for the CLI integration tests (no network)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import linear_bars


def seed_store(data_dir: Path, *, symbol: str = "SPY", n: int = 60) -> None:
    """Write a deterministic ``n``-bar uptrend for ``symbol`` into the CLI store.

    The store lives at ``data_dir/store`` (matching the CLI). Long enough (and trending) that the
    small-parameter strategy warms up, trades, and yields
    multiple walk-forward folds — enough to drive the full validate/backtest pipeline offline.
    """
    ParquetStore(data_dir / "store").write_bars(symbol, linear_bars(symbol, date(2020, 1, 1), n))
