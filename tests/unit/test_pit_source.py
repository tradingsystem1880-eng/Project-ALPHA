"""PointInTimeSource — the typed point-in-time DataSource the engine consumes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from alpha_core import Bar, DataError
from alpha_core.protocols import DataSource
from alpha_data.source import PointInTimeSource
from alpha_data.store import ParquetStore
from tests.fixtures.pit_fixtures import aapl_4for1_split, aapl_dividend, linear_bars


def _source(tmp_path: Path) -> PointInTimeSource:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2020, 8, 25), 12, first_close=100.0))
    return PointInTimeSource(store, actions={"AAPL": [aapl_4for1_split(), aapl_dividend()]})


def test_source_satisfies_datasource_protocol(tmp_path: Path) -> None:
    assert isinstance(_source(tmp_path), DataSource)  # runtime_checkable structural check


def test_as_of_returns_typed_split_adjusted_bars(tmp_path: Path) -> None:
    bars = _source(tmp_path).as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    assert bars and all(isinstance(b, Bar) for b in bars)
    assert [b.ts for b in bars] == sorted(b.ts for b in bars)  # chronological
    by_date = {b.ts.date(): b for b in bars}
    assert by_date[date(2020, 8, 30)].close == pytest.approx(105.0 / 4)  # pre-ex quartered
    assert by_date[date(2020, 8, 31)].close == pytest.approx(106.0)  # ex day untouched


def test_available_symbols_includes_slash_symbol(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_bars("AAPL", linear_bars("AAPL", date(2024, 1, 1), 3))
    store.write_bars("BTC/USD", linear_bars("BTC/USD", date(2024, 1, 1), 3))
    src = PointInTimeSource(store, actions={})
    assert src.available_symbols() == ["AAPL", "BTC/USD"]


def test_dividends_as_of_passthrough(tmp_path: Path) -> None:
    divs = _source(tmp_path).dividends_as_of("AAPL", datetime(2020, 9, 5, tzinfo=UTC))
    assert len(divs) == 1
    assert divs[0].amount == 0.82


def test_as_of_unknown_symbol_raises(tmp_path: Path) -> None:
    src = PointInTimeSource(ParquetStore(tmp_path), actions={})
    with pytest.raises(DataError):
        src.as_of("NOPE", datetime(2024, 1, 1, tzinfo=UTC))
