from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.store import ParquetStore

SCHEMA = ["ts", "open", "high", "low", "close", "volume"]


def _frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "ts": [datetime(2024, 1, 2, tzinfo=UTC), datetime(2024, 1, 3, tzinfo=UTC)],
            "open": [10.0, 10.5],
            "high": [11.0, 11.5],
            "low": [9.5, 10.0],
            "close": [10.5, 11.0],
            "volume": [100.0, 120.0],
        }
    )


def test_write_then_read_round_trips(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("BTCUSD", _frame())
    out = store.read_bars("BTCUSD")
    assert out.columns == SCHEMA
    assert out.height == 2
    assert out["close"].to_list() == [10.5, 11.0]


def test_read_missing_symbol_raises(tmp_path: Path) -> None:
    with pytest.raises(DataError):
        ParquetStore(tmp_path).read_bars("NOPE")


def test_slash_and_underscore_symbols_do_not_collide(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("BTC/USD", _frame())
    store.write_bars("BTC_USD", _frame().with_columns(pl.col("close") + 1000.0))
    assert store.read_bars("BTC/USD")["close"].to_list() == [10.5, 11.0]
    assert store.read_bars("BTC_USD")["close"].to_list() == [1010.5, 1011.0]


def test_list_symbols_reconstructs_slash_symbols(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", _frame())
    store.write_bars("BTC/USD", _frame())
    assert store.list_symbols() == ["AAPL", "BTC/USD"]  # sorted; slash subdir reconstructed


def test_list_symbols_empty_when_no_bars(tmp_path: Path) -> None:
    assert ParquetStore(tmp_path).list_symbols() == []
