"""The Qlib panel producer must never carry sessions from the sealed holdout window."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl
import pytest

from alpha_cli import _runner
from alpha_cli.ml_contract import MIN_ALIGNED_SESSIONS, MIN_SYMBOLS
from alpha_cli.ml_input import _aligned_panel
from alpha_data.snapshot import create_snapshot
from alpha_data.store import ParquetStore

pytestmark = pytest.mark.bias_guard


def _snapshot(root: Path, snapshot_id: str, *, poison_future: bool) -> list[str]:
    symbols = [f"S{index:02d}" for index in range(MIN_SYMBOLS)]
    sessions = [
        datetime(2020, 1, 2, tzinfo=UTC) + timedelta(days=index)
        for index in range(MIN_ALIGNED_SESSIONS + 8)
    ]
    store = ParquetStore(root / "store")
    for symbol_index, symbol in enumerate(symbols):
        prices = [
            100.0 + symbol_index + index * 0.01
            if not poison_future or index < MIN_ALIGNED_SESSIONS
            else 10_000.0 + symbol_index + index
            for index in range(len(sessions))
        ]
        store.write_bars(
            symbol,
            pl.DataFrame(
                {
                    "ts": sessions,
                    "open": prices,
                    "high": [price + 1.0 for price in prices],
                    "low": [price - 1.0 for price in prices],
                    "close": [price + 0.25 for price in prices],
                    "volume": [1_000_000.0] * len(sessions),
                }
            ),
        )
    create_snapshot(
        store,
        root / "snapshots",
        snapshot_id,
        symbols,
        source="fixture",
        adapter_version="1",
        parser_version="1",
        created_at=datetime(2026, 7, 19, tzinfo=UTC),
    )
    return symbols


def test_post_cutoff_mutation_cannot_enter_qlib_panel(tmp_path: Path) -> None:
    clean_root = tmp_path / "clean"
    poison_root = tmp_path / "poison"
    symbols = _snapshot(clean_root, "clean", poison_future=False)
    _snapshot(poison_root, "poison", poison_future=True)
    cutoff = _runner.parse_as_of(
        (datetime(2020, 1, 2, tzinfo=UTC) + timedelta(days=MIN_ALIGNED_SESSIONS - 1))
        .date()
        .isoformat()
    )

    clean, clean_sessions = _aligned_panel(
        data_dir=clean_root,
        snapshot_id="clean",
        universe=symbols,
        as_of=cutoff,
    )
    poisoned, poisoned_sessions = _aligned_panel(
        data_dir=poison_root,
        snapshot_id="poison",
        universe=symbols,
        as_of=cutoff,
    )

    assert clean_sessions == poisoned_sessions
    assert len(clean_sessions) == MIN_ALIGNED_SESSIONS
    assert clean.equals(poisoned)
    assert cutoff is not None
    max_available = clean.get_column("available_at").max()
    assert isinstance(max_available, datetime)
    assert max_available <= cutoff
