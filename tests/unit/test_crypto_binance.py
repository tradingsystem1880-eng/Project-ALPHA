from __future__ import annotations

import hashlib
import io
import zipfile
from datetime import UTC, datetime

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.binance import (
    archive_url,
    parse_binance_archive_zip,
    parse_binance_klines,
    point_in_time_liquid_universe,
    reconcile_archive_tail,
    verify_archive_checksum,
)


def test_archive_parser_preserves_native_kline_fields() -> None:
    payload = b"1704067200000,42000,43000,41000,42500,12.5,1704153599999,531250,42,6.1,259250,0\n"
    frame = parse_binance_klines(payload, source="archive_csv")

    assert frame.columns == [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "base_volume",
        "close_time",
        "quote_volume",
        "trade_count",
        "taker_buy_base_volume",
        "taker_buy_quote_volume",
    ]
    assert frame.row(0, named=True)["quote_volume"] == 531250.0
    assert frame.row(0, named=True)["trade_count"] == 42


def test_archive_zip_allows_one_bounded_flat_csv_member() -> None:
    csv = b"1704067200000,42000,43000,41000,42500,12.5,1704153599999,531250,42,6.1,259250,0\n"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("BTCUSDT-1d-2026-07.csv", csv)

    assert parse_binance_archive_zip(output.getvalue()).equals(
        parse_binance_klines(csv, source="archive_csv")
    )

    bad = io.BytesIO()
    with zipfile.ZipFile(bad, "w") as archive:
        archive.writestr("../private.csv", csv)
    with pytest.raises(DataError, match="member path"):
        parse_binance_archive_zip(bad.getvalue())


def test_parser_detects_post_2025_microsecond_timestamps() -> None:
    payload = b"1735689600000000,90000,91000,89000,90500,1,1735775999999999,90500,10,0.5,45250,0\n"
    frame = parse_binance_klines(payload, source="archive_csv")
    assert frame["open_time"][0] == datetime(2025, 1, 1, tzinfo=UTC)


def test_checksum_and_archive_paths_fail_loud() -> None:
    payload = b"exact archive bytes"
    digest = hashlib.sha256(payload).hexdigest()
    verify_archive_checksum(payload, f"{digest}  BTCUSDT-1d-2026-07.zip\n".encode())
    with pytest.raises(DataError, match="checksum"):
        verify_archive_checksum(payload + b"changed", f"{digest} file\n".encode())

    assert archive_url("spot", "klines", "BTCUSDT", "1d", "2026-07").startswith(
        "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/"
    )
    with pytest.raises(DataError, match="market"):
        archive_url("options", "klines", "BTCUSDT", "1d", "2026-07")  # type: ignore[arg-type]


def test_rest_tail_reconciliation_rejects_revisions_and_deduplicates() -> None:
    archive = pl.DataFrame(
        {
            "open_time": [datetime(2026, 1, 1, tzinfo=UTC)],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "base_volume": [10.0],
            "close_time": [datetime(2026, 1, 2, tzinfo=UTC)],
            "quote_volume": [15.0],
            "trade_count": [2],
            "taker_buy_base_volume": [4.0],
            "taker_buy_quote_volume": [6.0],
        }
    )
    same = archive.vstack(
        archive.with_columns(pl.lit(datetime(2026, 1, 2, tzinfo=UTC)).alias("open_time"))
    )
    merged = reconcile_archive_tail(archive, same)
    assert merged.height == 2

    changed = archive.with_columns(pl.lit(9.0).alias("close"))
    with pytest.raises(DataError, match="overlap"):
        reconcile_archive_tail(archive, changed)


def test_rest_json_parser_and_malformed_rows_fail_loud() -> None:
    rest = b'[[1704067200000,"1","2","0.5","1.5","10",1704153599999,"15",2,"4","6","0"]]'
    assert parse_binance_klines(rest, source="rest_json").height == 1

    failures = [
        (b"{}", "rest_json", "must be a list"),
        (b"not-json", "rest_json", "malformed"),
        (b"1,2,3\n", "archive_csv", "fewer than eleven"),
        (b"x,1,2,0.5,1.5,10,2,15,2,4,6\n", "archive_csv", "timestamp"),
        (b"1,nope,2,0.5,1.5,10,2,15,2,4,6\n", "archive_csv", "numeric"),
        (b"1,1,0.5,2,1.5,10,2,15,2,4,6\n", "archive_csv", "OHLC"),
        (b"1,1,2,0.5,1.5,-1,2,15,2,4,6\n", "archive_csv", "non-negative"),
        (b"", "archive_csv", "empty"),
    ]
    for payload, source, message in failures:
        with pytest.raises(DataError, match=message):
            parse_binance_klines(payload, source=source)  # type: ignore[arg-type]

    duplicated = b"1,1,2,0.5,1.5,10,2,15,2,4,6\n1,1,2,0.5,1.5,10,2,15,2,4,6\n"
    with pytest.raises(DataError, match="duplicate"):
        parse_binance_klines(duplicated, source="archive_csv")


def test_checksum_url_and_reconciliation_validate_contracts() -> None:
    with pytest.raises(DataError, match="sidecar"):
        verify_archive_checksum(b"x", b"not-a-checksum")
    with pytest.raises(DataError, match="symbol"):
        archive_url("spot", "klines", "../BTC", "1d", "2026-07")

    empty = pl.DataFrame({"wrong": [1]})
    with pytest.raises(DataError, match="schema"):
        reconcile_archive_tail(empty, empty)


@pytest.mark.bias_guard
def test_liquid_universe_uses_only_the_prior_available_day() -> None:
    frame = pl.DataFrame(
        {
            "session": [
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 1, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 3, tzinfo=UTC),
            ],
            "symbol": ["AAA", "BBB", "AAA", "BBB", "ZZZ"],
            "quote_volume": [10.0, 20.0, 30.0, 5.0, 1_000_000.0],
        }
    )
    as_of = datetime(2026, 1, 3, tzinfo=UTC)
    selected = point_in_time_liquid_universe(frame, as_of=as_of, limit=1)
    poisoned = frame.with_columns(
        pl.when(pl.col("session") >= as_of)
        .then(pl.lit(9_999_999.0))
        .otherwise(pl.col("quote_volume"))
        .alias("quote_volume")
    )

    assert selected == ("AAA",)
    assert point_in_time_liquid_universe(poisoned, as_of=as_of, limit=1) == selected
