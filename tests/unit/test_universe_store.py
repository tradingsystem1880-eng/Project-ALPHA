"""Phase B B3: point-in-time universe type, store round trip, and CSV import."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from alpha_core import DataError, UniverseMembership, members_as_of
from alpha_data.store import ParquetStore
from alpha_data.universe import parse_universe_csv


def _rows() -> list[UniverseMembership]:
    return [
        UniverseMembership(symbol="AAA", effective_from=date(2020, 1, 1)),
        UniverseMembership(
            symbol="DEAD",
            effective_from=date(2020, 1, 1),
            effective_to=date(2022, 6, 1),
            delisting_return=-0.35,
            reason="delisted",
        ),
        UniverseMembership(symbol="NEW", effective_from=date(2023, 3, 15), reason="index_add"),
    ]


def test_members_as_of_is_from_inclusive_and_to_exclusive() -> None:
    rows = _rows()
    assert members_as_of(rows, date(2019, 12, 31)) == []
    assert members_as_of(rows, date(2020, 1, 1)) == ["AAA", "DEAD"]
    assert members_as_of(rows, date(2022, 5, 31)) == ["AAA", "DEAD"]
    assert members_as_of(rows, date(2022, 6, 1)) == ["AAA"]
    assert members_as_of(rows, date(2023, 3, 15)) == ["AAA", "NEW"]


def test_membership_validation_fails_loud() -> None:
    with pytest.raises(ValueError, match="effective_to"):
        UniverseMembership(
            symbol="X", effective_from=date(2021, 1, 1), effective_to=date(2021, 1, 1)
        )
    with pytest.raises(ValueError, match="delisting_return requires"):
        UniverseMembership(symbol="X", effective_from=date(2021, 1, 1), delisting_return=-0.1)
    with pytest.raises(ValueError, match="blank"):
        UniverseMembership(symbol=" ", effective_from=date(2021, 1, 1))


def test_store_round_trip_replaces_wholesale(tmp_path: Path) -> None:
    store = ParquetStore(tmp_path)
    store.write_universe("sp500", _rows())
    assert store.read_universe("sp500") == _rows()
    assert store.list_universes() == ["sp500"]
    store.write_universe("sp500", _rows()[:1])
    assert [m.symbol for m in store.read_universe("sp500")] == ["AAA"]
    with pytest.raises(DataError, match="universe"):
        store.read_universe("missing")


def test_csv_import_parses_the_four_columns_and_rejects_junk() -> None:
    text = (
        "symbol,effective_from,effective_to,delisting_return,reason\n"
        "AAA,2020-01-01,,,\n"
        "DEAD,2020-01-01,2022-06-01,-0.35,delisted\n"
    )
    rows = parse_universe_csv(text)
    assert rows == _rows()[:2]
    with pytest.raises(DataError, match="column"):
        parse_universe_csv("symbol,start\nAAA,2020-01-01\n")
    with pytest.raises(DataError, match="row 2"):
        parse_universe_csv("symbol,effective_from,effective_to,delisting_return,reason\nAAA,x,,,\n")
