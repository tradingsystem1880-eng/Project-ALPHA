from __future__ import annotations

import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest

from alpha_core import DataError
from alpha_data.crypto.providers.binance import (
    archive_url,
    binance_public_api_url,
    fetch_binance_archive,
    fetch_binance_public_api,
    parse_binance_aggregate_trades,
    parse_binance_archive_zip,
    parse_binance_book_snapshot,
    parse_binance_exchange_info,
    parse_binance_klines,
    parse_binance_trades,
    point_in_time_liquid_universe,
    reconcile_archive_tail,
    verify_archive_checksum,
)


def test_exchange_info_parses_active_spot_and_perpetual_membership() -> None:
    fetched_at = datetime(2026, 8, 15, tzinfo=UTC)
    spot = json.dumps(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                },
                {
                    "symbol": "OLDUSDT",
                    "status": "BREAK",
                    "baseAsset": "OLD",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": False,
                },
                {
                    "symbol": "币安人生USDT",
                    "status": "TRADING",
                    "baseAsset": "币安人生",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                },
            ]
        }
    ).encode()
    linear = json.dumps(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "contractType": "PERPETUAL",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "onboardDate": 1_600_000_000_000,
                    "deliveryDate": 4_133_980_800_000,
                },
                {
                    "symbol": "BTCUSDT_260925",
                    "status": "TRADING",
                    "contractType": "CURRENT_QUARTER",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "onboardDate": 1_700_000_000_000,
                    "deliveryDate": 1_790_000_000_000,
                },
            ]
        }
    ).encode()
    inverse = json.dumps(
        {
            "symbols": [
                {
                    "symbol": "BTCUSD_PERP",
                    "contractStatus": "TRADING",
                    "contractType": "PERPETUAL",
                    "baseAsset": "BTC",
                    "quoteAsset": "USD",
                    "onboardDate": 1_600_000_000_000,
                    "deliveryDate": 4_133_980_800_000,
                }
            ]
        }
    ).encode()

    spot_frame = parse_binance_exchange_info(spot, category="spot", fetched_at=fetched_at)
    linear_frame = parse_binance_exchange_info(linear, category="linear", fetched_at=fetched_at)
    inverse_frame = parse_binance_exchange_info(inverse, category="inverse", fetched_at=fetched_at)

    assert spot_frame.select("symbol", "contract_type").rows() == [
        ("BTCUSDT", "SPOT"),
        ("币安人生USDT", "SPOT"),
    ]
    assert linear_frame.select("symbol", "contract_type").rows() == [("BTCUSDT", "PERPETUAL")]
    assert inverse_frame.select("symbol", "contract_type").rows() == [("BTCUSD_PERP", "PERPETUAL")]
    assert spot_frame["fetched_at"].to_list() == [fetched_at, fetched_at]


def test_exchange_info_rejects_duplicate_and_malformed_membership() -> None:
    fetched_at = datetime(2026, 8, 15, tzinfo=UTC)
    duplicate = json.dumps(
        {
            "symbols": [
                {
                    "symbol": "BTCUSDT",
                    "status": "TRADING",
                    "baseAsset": "BTC",
                    "quoteAsset": "USDT",
                    "isSpotTradingAllowed": True,
                }
            ]
            * 2
        }
    ).encode()
    with pytest.raises(DataError, match="duplicate"):
        parse_binance_exchange_info(duplicate, category="spot", fetched_at=fetched_at)
    with pytest.raises(DataError, match="malformed"):
        parse_binance_exchange_info(b"{}", category="spot", fetched_at=fetched_at)


class _ArchiveResponse:
    def __init__(
        self,
        chunks: list[bytes | BaseException],
        *,
        status: int,
        headers: dict[str, str],
        url: str,
    ) -> None:
        self._chunks = iter(chunks)
        self.status = status
        self.headers = headers
        self._url = url

    def __enter__(self) -> _ArchiveResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def geturl(self) -> str:
        return self._url

    def getcode(self) -> int:
        return self.status

    def read(self, _size: int = -1) -> bytes:
        value = next(self._chunks, b"")
        if isinstance(value, BaseException):
            raise value
        return value


def test_exchange_info_has_a_separate_bounded_response_ceiling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"x" * (17 * 1024 * 1024)
    current_url = ""

    def urlopen(request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        assert timeout == 30
        return _ArchiveResponse(
            [payload],
            status=200,
            headers={"Content-Type": "application/json"},
            url=current_url,
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    current_url = binance_public_api_url("spot", "exchangeInfo", {})
    assert fetch_binance_public_api(current_url) == payload

    current_url = binance_public_api_url(
        "spot", "klines", {"symbol": "BTCUSDT", "interval": "1d", "limit": 1}
    )
    with pytest.raises(DataError, match="byte limit"):
        fetch_binance_public_api(current_url)


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


def test_trade_and_aggregate_trade_archives_preserve_native_ids_and_optional_fields() -> None:
    trades = parse_binance_trades(b"51175358,17.8018,5.69,101.292242,1735689600010866,True,True\n")
    assert trades.row(0, named=True) == {
        "trade_id": 51175358,
        "price": 17.8018,
        "quantity": 5.69,
        "quote_quantity": 101.292242,
        "timestamp": datetime(2025, 1, 1, 0, 0, 0, 10866, tzinfo=UTC),
        "buyer_is_maker": True,
        "best_match": True,
    }
    futures = parse_binance_trades(b"28457,4.000001,12,48,1499865549590,true\n")
    assert futures["best_match"][0] is None

    aggregate = parse_binance_aggregate_trades(
        b"26129,0.01633102,4.70443515,27781,27781,1498793709153,true\n"
    )
    assert aggregate.row(0, named=True)["aggregate_trade_id"] == 26129
    assert aggregate.row(0, named=True)["first_trade_id"] == 27781
    assert aggregate.row(0, named=True)["best_match"] is None

    assert "/monthly/trades/BTCUSDT/BTCUSDT-trades-2026-07.zip" in archive_url(
        "spot", "trades", "BTCUSDT", "", "2026-07"
    )
    assert "/monthly/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2026-07.zip" in archive_url(
        "um", "aggTrades", "BTCUSDT", "", "2026-07"
    )


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
    assert "%E5%B8%81%E5%AE%89%E4%BA%BA%E7%94%9FUSDT" in archive_url(
        "spot", "klines", "币安人生USDT", "1d", "2026-07"
    )
    with pytest.raises(DataError, match="market"):
        archive_url("options", "klines", "BTCUSDT", "1d", "2026-07")  # type: ignore[arg-type]


def test_archive_download_resumes_exact_partial_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/file.zip"
    payload = b"abcdef"
    expected = hashlib.sha256(payload).hexdigest()
    requests: list[urllib.request.Request] = []

    def urlopen(request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        assert timeout == 120
        requests.append(request)
        if len(requests) == 1:
            assert request.get_header("Range") is None
            return _ArchiveResponse(
                [b"abc", OSError("connection reset")],
                status=200,
                headers={"Content-Type": "application/zip", "Content-Length": "6"},
                url=url,
            )
        assert request.get_header("Range") == "bytes=3-"
        return _ArchiveResponse(
            [b"def", b""],
            status=206,
            headers={
                "Content-Type": "application/zip",
                "Content-Length": "3",
                "Content-Range": "bytes 3-5/6",
            },
            url=url,
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    staging = tmp_path / "staging"
    with pytest.raises(DataError, match="rerun to resume"):
        fetch_binance_archive(url, staging, expected)
    partial = tuple(staging.rglob("payload.part"))
    assert len(partial) == 1
    assert partial[0].read_bytes() == b"abc"

    assert fetch_binance_archive(url, staging, expected) == payload
    assert [request.get_header("Range") for request in requests] == [None, "bytes=3-"]
    assert not tuple(staging.rglob("payload.part"))
    assert (tmp_path / "cache" / "downloads" / f"{expected}.zip").read_bytes() == payload

    assert fetch_binance_archive(url, staging, expected) == payload
    assert len(requests) == 2


def test_archive_download_rejects_server_that_ignores_resume_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/spot/monthly/klines/BTCUSDT/1d/file.zip"
    payload = b"abcdef"
    expected = hashlib.sha256(payload).hexdigest()
    calls = 0

    def urlopen(request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _ArchiveResponse(
                [b"abc", OSError("connection reset")],
                status=200,
                headers={"Content-Type": "application/zip", "Content-Length": "6"},
                url=url,
            )
        assert request.get_header("Range") == "bytes=3-"
        return _ArchiveResponse(
            [payload],
            status=200,
            headers={"Content-Type": "application/zip", "Content-Length": "6"},
            url=url,
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    staging = tmp_path / "staging"
    with pytest.raises(DataError, match="rerun to resume"):
        fetch_binance_archive(url, staging, expected)
    with pytest.raises(DataError, match="refused the exact resume range"):
        fetch_binance_archive(url, staging, expected)
    assert next(staging.rglob("payload.part")).read_bytes() == b"abc"


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


def test_book_snapshot_preserves_exact_sides_levels_and_knowledge_time() -> None:
    fetched_at = datetime(2026, 8, 14, 19, tzinfo=UTC)
    frame = parse_binance_book_snapshot(
        b'{"lastUpdateId":42,"bids":[["90000","1.5"],["89999","2"]],'
        b'"asks":[["90001","0.5"],["90002","3"]]}',
        symbol="BTCUSDT",
        category="spot",
        fetched_at=fetched_at,
    )

    assert frame.columns == [
        "observed_at",
        "provider_event_time",
        "transaction_time",
        "symbol",
        "category",
        "update_id",
        "side",
        "level",
        "price",
        "quantity",
    ]
    assert frame.height == 4
    assert frame.filter(pl.col("side") == "bid").sort("level")["price"].to_list() == [
        90000.0,
        89999.0,
    ]
    assert frame["observed_at"].unique().to_list() == [fetched_at]


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (b'{"lastUpdateId":1,"bids":[],"asks":[]}', "empty"),
        (b'{"lastUpdateId":1,"bids":[["2","1"]],"asks":[["1","1"]]}', "crossed"),
        (b'{"lastUpdateId":1,"bids":[["1","-1"]],"asks":[["2","1"]]}', "bounds"),
        (b'{"lastUpdateId":"x","bids":[["1","1"]],"asks":[["2","1"]]}', "update"),
    ),
)
def test_book_snapshot_rejects_invalid_provider_state(payload: bytes, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_binance_book_snapshot(
            payload,
            symbol="BTCUSDT",
            category="spot",
            fetched_at=datetime(2026, 8, 14, 19, tzinfo=UTC),
        )


def test_public_api_urls_are_closed_bounded_and_market_specific() -> None:
    spot = binance_public_api_url("spot", "depth", {"symbol": "BTCUSDT", "limit": 1000})
    linear = binance_public_api_url(
        "linear",
        "klines",
        {"symbol": "BTCUSDT", "interval": "1h", "limit": 1000, "startTime": 1},
    )
    inverse = binance_public_api_url("inverse", "depth", {"symbol": "BTCUSD_PERP", "limit": 100})

    assert spot.startswith("https://api.binance.com/api/v3/depth?")
    assert linear.startswith("https://fapi.binance.com/fapi/v1/klines?")
    assert inverse.startswith("https://dapi.binance.com/dapi/v1/depth?")
    with pytest.raises(DataError, match="parameter"):
        binance_public_api_url(
            "spot", "depth", {"symbol": "BTCUSDT", "limit": 100, "apiKey": "secret"}
        )
    with pytest.raises(DataError, match="limit"):
        binance_public_api_url("spot", "depth", {"symbol": "BTCUSDT", "limit": 5000})
    with pytest.raises(DataError, match="range"):
        binance_public_api_url(
            "spot",
            "klines",
            {
                "symbol": "BTCUSDT",
                "interval": "1h",
                "limit": 1000,
                "startTime": 2,
                "endTime": 1,
            },
        )


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
