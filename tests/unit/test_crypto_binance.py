from __future__ import annotations

import hashlib
import io
import json
import urllib.error
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
    fetch_binance_checksum,
    fetch_binance_public_api,
    parse_binance_aggregate_trades,
    parse_binance_archive_zip,
    parse_binance_book_snapshot,
    parse_binance_exchange_info,
    parse_binance_klines,
    parse_binance_trades,
    point_in_time_liquid_markets,
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
                    "contractSize": 100,
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
    assert inverse_frame["contract_size"].to_list() == [100.0]
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
        (b"1704067200000,nope,2,0.5,1.5,10,1704153599999,15,2,4,6\n", "archive_csv", "numeric"),
        (b"1704067200000,1,0.5,2,1.5,10,1704153599999,15,2,4,6\n", "archive_csv", "OHLC"),
        (b"1704067200000,1,2,0.5,1.5,-1,1704153599999,15,2,4,6\n", "archive_csv", "non-negative"),
        (b"", "archive_csv", "empty"),
    ]
    for payload, source, message in failures:
        with pytest.raises(DataError, match=message):
            parse_binance_klines(payload, source=source)  # type: ignore[arg-type]

    row = b"1704067200000,1,2,0.5,1.5,10,1704153599999,15,2,4,6\n"
    duplicated = row + row
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


@pytest.mark.bias_guard
def test_liquid_markets_rank_within_one_exact_unit_scope() -> None:
    as_of = datetime(2026, 1, 3, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "session": [
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 2, tzinfo=UTC),
                datetime(2026, 1, 3, tzinfo=UTC),
            ],
            "category": ["inverse", "inverse", "inverse"],
            "symbol": ["BTCUSD_PERP", "ETHUSD_PERP", "FUTUREUSD_PERP"],
            "base_asset": ["BTC", "ETH", "FUTURE"],
            "quote_asset": ["USD", "USD", "USD"],
            "base_volume": [10.0, 50.0, 1_000_000.0],
            "quote_volume": [0.1, 1.0, 1_000_000.0],
            "contract_size": [100.0, 10.0, 100.0],
        }
    )

    selected = point_in_time_liquid_markets(
        frame,
        as_of=as_of,
        category="inverse",
        quote_asset="USD",
        limit=2,
    )

    assert selected.select("rank", "symbol", "liquidity_score").rows() == [
        (1, "BTCUSD_PERP", 1_000.0),
        (2, "ETHUSD_PERP", 500.0),
    ]
    assert selected["liquidity_units"].unique().to_list() == ["USD_contract_notional"]


def test_liquid_markets_reject_cross_quote_or_incomplete_contract_units() -> None:
    as_of = datetime(2026, 1, 3, tzinfo=UTC)
    frame = pl.DataFrame(
        {
            "session": [datetime(2026, 1, 2, tzinfo=UTC)],
            "category": ["inverse"],
            "symbol": ["BTCUSD_PERP"],
            "base_asset": ["BTC"],
            "quote_asset": ["USD"],
            "base_volume": [10.0],
            "quote_volume": [0.1],
            "contract_size": [None],
        }
    )
    with pytest.raises(DataError, match="contract size"):
        point_in_time_liquid_markets(
            frame, as_of=as_of, category="inverse", quote_asset="USD", limit=1
        )
    with pytest.raises(DataError, match="scope"):
        point_in_time_liquid_markets(
            frame, as_of=as_of, category="inverse", quote_asset="USDT", limit=1
        )


@pytest.mark.parametrize(
    ("url", "timeout", "message"),
    (
        ("https://attacker.invalid/data.zip", 30, "host"),
        ("https://data.binance.vision/data/file.zip", 0, "timeout"),
        ("https://data.binance.vision/data/file.zip", 121, "timeout"),
    ),
)
def test_archive_fetch_rejects_unbounded_inputs(url: str, timeout: int, message: str) -> None:
    with pytest.raises(DataError, match=message):
        fetch_binance_archive(url, timeout_seconds=timeout)


def test_archive_and_checksum_fetch_validate_redirect_mime_and_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = "https://data.binance.vision/data/file.zip"
    checksum = f"{archive}.CHECKSUM"
    response: _ArchiveResponse

    def urlopen(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        assert timeout == 30
        return response

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    response = _ArchiveResponse(
        [b"zip"], status=200, headers={"Content-Type": "application/zip"}, url=archive
    )
    assert fetch_binance_archive(archive, timeout_seconds=30) == b"zip"
    response = _ArchiveResponse(
        [b"digest file\n"], status=200, headers={"Content-Type": "text/plain"}, url=checksum
    )
    assert fetch_binance_checksum(checksum) == b"digest file\n"
    response = _ArchiveResponse(
        [b"digest file\n"], status=200, headers={"Content-Type": "application/zip"}, url=checksum
    )
    assert fetch_binance_checksum(checksum) == b"digest file\n"

    response = _ArchiveResponse(
        [b"zip"], status=200, headers={"Content-Type": "text/html"}, url=archive
    )
    with pytest.raises(DataError, match="MIME"):
        fetch_binance_archive(archive, timeout_seconds=30)
    response = _ArchiveResponse(
        [b"zip"],
        status=200,
        headers={"Content-Type": "application/zip"},
        url="https://attacker.invalid/file.zip",
    )
    with pytest.raises(DataError, match="redirect"):
        fetch_binance_archive(archive, timeout_seconds=30)
    response = _ArchiveResponse(
        [b"x" * 4097], status=200, headers={"Content-Type": "text/plain"}, url=checksum
    )
    with pytest.raises(DataError, match="byte limit"):
        fetch_binance_checksum(checksum)

    def failed(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", failed)
    with pytest.raises(DataError, match="request failed"):
        fetch_binance_checksum(checksum)


def test_public_api_fetch_validates_boundary_and_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = binance_public_api_url("spot", "depth", {"symbol": "BTCUSDT", "limit": 1})
    response: _ArchiveResponse

    def urlopen(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        assert timeout == 30
        return response

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    response = _ArchiveResponse(
        [b"{}"], status=200, headers={"Content-Type": "application/json; charset=utf-8"}, url=url
    )
    assert fetch_binance_public_api(url) == b"{}"
    response = _ArchiveResponse([b"{}"], status=200, headers={"Content-Type": "text/html"}, url=url)
    with pytest.raises(DataError, match="MIME"):
        fetch_binance_public_api(url)
    response = _ArchiveResponse(
        [b"{}"],
        status=200,
        headers={"Content-Type": "application/json"},
        url="https://attacker.invalid/data",
    )
    with pytest.raises(DataError, match="redirect"):
        fetch_binance_public_api(url)
    with pytest.raises(DataError, match="timeout"):
        fetch_binance_public_api(url, timeout_seconds=0)
    with pytest.raises(DataError, match="host"):
        fetch_binance_public_api("https://attacker.invalid/data")


def test_binance_parsers_reject_malformed_native_rows() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    trade_failures = (
        (b"", "empty"),
        (b"1,2,3\n", "six or seven"),
        (b"x,2,3,6,1704067200000,true\n", "numeric"),
        (b"1,2,3,6,1704067200000,maybe\n", "boolean"),
        (b"1,0,3,6,1704067200000,true\n", "bounds"),
        (
            b"1,2,3,6,1704067200000,true\n1,2,3,6,1704067200001,true\n",
            "duplicate",
        ),
    )
    for payload, message in trade_failures:
        with pytest.raises(DataError, match=message):
            parse_binance_trades(payload)

    aggregate_failures = (
        (b"", "empty"),
        (b"1,2,3\n", "seven or eight"),
        (b"1,2,3,9,8,1704067200000,true\n", "inverted"),
        (b"x,2,3,8,9,1704067200000,true\n", "numeric"),
        (b"1,-2,3,8,9,1704067200000,true\n", "bounds"),
        (
            b"1,2,3,8,9,1704067200000,true\n1,2,3,8,9,1704067200001,true\n",
            "duplicate",
        ),
    )
    for payload, message in aggregate_failures:
        with pytest.raises(DataError, match=message):
            parse_binance_aggregate_trades(payload)

    book_failures = (
        (b"not-json", "malformed"),
        (b"[]", "object"),
        (b'{"lastUpdateId":1,"bids":"bad","asks":[]}', "bids"),
        (b'{"lastUpdateId":1,"bids":[["1"]],"asks":[["2","1"]]}', "level"),
        (
            b'{"lastUpdateId":1,"bids":[["2","1"],["2","1"]],"asks":[["3","1"]]}',
            "duplicate",
        ),
        (
            b'{"lastUpdateId":1,"bids":[["1","1"],["2","1"]],"asks":[["3","1"]]}',
            "descending",
        ),
        (
            b'{"lastUpdateId":1,"bids":[["1","1"]],"asks":[["3","1"],["2","1"]]}',
            "ascending",
        ),
    )
    for payload, message in book_failures:
        with pytest.raises(DataError, match=message):
            parse_binance_book_snapshot(payload, symbol="BTCUSDT", category="spot", fetched_at=now)
    with pytest.raises(DataError, match="identity"):
        parse_binance_book_snapshot(b"{}", symbol="../BTC", category="spot", fetched_at=now)
    with pytest.raises(DataError, match="timezone"):
        parse_binance_book_snapshot(
            b"{}", symbol="BTCUSDT", category="spot", fetched_at=datetime(2026, 8, 15)
        )


def test_exchange_info_and_archive_zip_reject_unsafe_provider_shapes() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    with pytest.raises(DataError, match="category"):
        parse_binance_exchange_info(b"{}", category="bad", fetched_at=now)  # type: ignore[arg-type]
    with pytest.raises(DataError, match="timezone"):
        parse_binance_exchange_info(b"{}", category="spot", fetched_at=datetime(2026, 8, 15))
    for payload, message in (
        (b"not-json", "malformed"),
        (b'{"symbols":[1]}', "symbol"),
        (
            b'{"symbols":[{"symbol":"BTCUSDT","status":"TRADING","baseAsset":"BTC",'
            b'"quoteAsset":"USDT","isSpotTradingAllowed":"yes"}]}',
            "permission",
        ),
        (
            b'{"symbols":[{"symbol":"BTCUSDT","status":"TRADING","baseAsset":"BTC",'
            b'"quoteAsset":"USDT","isSpotTradingAllowed":false}]}',
            "no active",
        ),
    ):
        with pytest.raises(DataError, match=message):
            parse_binance_exchange_info(payload, category="spot", fetched_at=now)

    with pytest.raises(DataError, match="compressed"):
        parse_binance_archive_zip(b"")
    with pytest.raises(DataError, match="malformed"):
        parse_binance_archive_zip(b"not-a-zip")
    multiple = io.BytesIO()
    with zipfile.ZipFile(multiple, "w") as archive:
        archive.writestr("one.csv", b"1")
        archive.writestr("two.csv", b"2")
    with pytest.raises(DataError, match="exactly one"):
        parse_binance_archive_zip(multiple.getvalue())


def test_closed_binance_url_contract_rejects_unsupported_combinations() -> None:
    with pytest.raises(DataError, match="family"):
        archive_url("spot", "depth", "BTCUSDT", "", "2026-07")
    with pytest.raises(DataError, match="interval"):
        archive_url("spot", "trades", "BTCUSDT", "1d", "2026-07")
    with pytest.raises(DataError, match="interval"):
        archive_url("spot", "klines", "BTCUSDT", "../1d", "2026-07")
    with pytest.raises(DataError, match="endpoint"):
        binance_public_api_url("spot", "bad", {})  # type: ignore[arg-type]
    with pytest.raises(DataError, match="does not accept"):
        binance_public_api_url("spot", "exchangeInfo", {"limit": 1})
    with pytest.raises(DataError, match="symbol"):
        binance_public_api_url("spot", "depth", {"symbol": "../BTC", "limit": 1})
    with pytest.raises(DataError, match="interval"):
        binance_public_api_url(
            "spot", "klines", {"symbol": "BTCUSDT", "interval": "2h", "limit": 1}
        )
    with pytest.raises(DataError, match="time range"):
        binance_public_api_url(
            "spot",
            "klines",
            {"symbol": "BTCUSDT", "interval": "1h", "limit": 1, "startTime": -1},
        )


def test_resumable_archive_rejects_corrupt_cache_and_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    expected = hashlib.sha256(b"good").hexdigest()
    staging = tmp_path / "staging"
    cache = tmp_path / "cache" / "downloads" / f"{expected}.zip"
    cache.parent.mkdir(parents=True)
    cache.write_bytes(b"bad")
    with pytest.raises(DataError, match="checksum identity"):
        fetch_binance_archive(url, staging, expected)
    cache.unlink()

    def interrupted(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", interrupted)
    with pytest.raises(DataError, match="rerun to resume"):
        fetch_binance_archive(url, staging, expected)
    metadata = next(staging.rglob("download.json"))
    metadata.write_text("not-json", encoding="utf-8")
    with pytest.raises(DataError, match="metadata is unreadable"):
        fetch_binance_archive(url, staging, expected)
    metadata.write_text("{}", encoding="utf-8")
    with pytest.raises(DataError, match="does not match"):
        fetch_binance_archive(url, staging, expected)


def test_resumable_archive_rejects_symlinked_storage_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    payload = b"good"
    expected = hashlib.sha256(payload).hexdigest()

    def urlopen(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        return _ArchiveResponse(
            [payload],
            status=200,
            headers={"Content-Type": "application/zip", "Content-Length": str(len(payload))},
            url=url,
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    outside_staging = tmp_path / "outside-staging"
    outside_staging.mkdir()
    staging = tmp_path / "staging"
    staging.symlink_to(outside_staging, target_is_directory=True)
    with pytest.raises(DataError, match="staging path is unsafe"):
        fetch_binance_archive(url, staging, expected)

    staging.unlink()
    staging.mkdir()
    outside_cache = tmp_path / "outside-cache"
    outside_cache.mkdir()
    (tmp_path / "cache").symlink_to(outside_cache, target_is_directory=True)
    with pytest.raises(DataError, match="cache path is unsafe"):
        fetch_binance_archive(url, staging, expected)


def test_resumable_archive_rejects_symlinked_resume_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    expected = hashlib.sha256(b"good").hexdigest()

    def offline(*_args: object, **_kwargs: object) -> object:
        raise OSError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    staging = tmp_path / "staging"
    with pytest.raises(DataError, match="rerun to resume"):
        fetch_binance_archive(url, staging, expected)
    metadata = next(staging.rglob("download.json"))
    metadata.unlink()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    metadata.symlink_to(outside)
    with pytest.raises(DataError, match="metadata path is unsafe"):
        fetch_binance_archive(url, staging, expected)


@pytest.mark.parametrize(
    ("status", "headers", "response_url", "message"),
    (
        (200, {"Content-Type": "text/html"}, None, "MIME"),
        (
            200,
            {"Content-Type": "application/zip", "Content-Encoding": "gzip"},
            None,
            "encoding",
        ),
        (201, {"Content-Type": "application/zip"}, None, "status"),
        (200, {"Content-Type": "application/zip", "Content-Length": "bad"}, None, "length"),
        (200, {"Content-Type": "application/zip", "Content-Length": "-1"}, None, "length"),
        (200, {"Content-Type": "application/zip"}, "https://attacker.invalid/file", "redirect"),
    ),
)
def test_resumable_initial_response_is_strictly_validated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: int,
    headers: dict[str, str],
    response_url: str | None,
    message: str,
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    expected = hashlib.sha256(b"good").hexdigest()

    def urlopen(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        return _ArchiveResponse([b"good"], status=status, headers=headers, url=response_url or url)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(DataError, match=message):
        fetch_binance_archive(url, tmp_path / "staging", expected)


@pytest.mark.parametrize(
    ("headers", "message"),
    (
        (
            {
                "Content-Type": "application/zip",
                "Content-Length": "3",
                "Content-Range": "invalid",
            },
            "range is invalid",
        ),
        (
            {
                "Content-Type": "application/zip",
                "Content-Length": "3",
                "Content-Range": "bytes 3-2/6",
            },
            "range is incomplete",
        ),
        (
            {
                "Content-Type": "application/zip",
                "Content-Length": "2",
                "Content-Range": "bytes 3-5/6",
            },
            "length is inconsistent",
        ),
    ),
)
def test_resumable_range_metadata_is_strictly_validated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    headers: dict[str, str],
    message: str,
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    expected = hashlib.sha256(b"abcdef").hexdigest()
    calls = 0

    def urlopen(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _ArchiveResponse(
                [b"abc", OSError("offline")],
                status=200,
                headers={"Content-Type": "application/zip", "Content-Length": "6"},
                url=url,
            )
        return _ArchiveResponse([b"def"], status=206, headers=headers, url=url)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    staging = tmp_path / "staging"
    with pytest.raises(DataError, match="rerun to resume"):
        fetch_binance_archive(url, staging, expected)
    with pytest.raises(DataError, match=message):
        fetch_binance_archive(url, staging, expected)


def test_resumable_archive_quarantines_checksum_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    expected = hashlib.sha256(b"expected").hexdigest()

    def urlopen(_request: urllib.request.Request, *, timeout: int) -> _ArchiveResponse:
        return _ArchiveResponse(
            [b"actual"],
            status=200,
            headers={"Content-Type": "application/zip", "Content-Length": "6"},
            url=url,
        )

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(DataError, match="checksum does not match"):
        fetch_binance_archive(url, tmp_path / "staging", expected)
    assert tuple((tmp_path / "staging" / "downloads").glob("*.corrupt-*"))


def test_liquidity_selection_rejects_invalid_contracts() -> None:
    now = datetime(2026, 1, 3, tzinfo=UTC)
    with pytest.raises(DataError, match="schema"):
        point_in_time_liquid_universe(pl.DataFrame({"bad": [1]}), as_of=now, limit=1)
    frame = pl.DataFrame(
        {
            "session": [datetime(2026, 1, 2, tzinfo=UTC)],
            "symbol": ["BTCUSDT"],
            "quote_volume": [1.0],
        }
    )
    with pytest.raises(DataError, match="timezone"):
        point_in_time_liquid_universe(frame, as_of=datetime(2026, 1, 3), limit=1)
    with pytest.raises(DataError, match="limit"):
        point_in_time_liquid_universe(frame, as_of=now, limit=0)
    with pytest.raises(DataError, match="before as_of"):
        point_in_time_liquid_universe(frame, as_of=datetime(2026, 1, 1, tzinfo=UTC), limit=1)
    duplicated = pl.concat([frame, frame])
    with pytest.raises(DataError, match="duplicate"):
        point_in_time_liquid_universe(duplicated, as_of=now, limit=2)

    market = frame.with_columns(
        pl.lit("spot").alias("category"),
        pl.lit("BTC").alias("base_asset"),
        pl.lit("USDT").alias("quote_asset"),
        pl.lit(1.0).alias("base_volume"),
        pl.lit(None).alias("contract_size"),
    )
    for kwargs, message in (
        ({"category": "bad", "quote_asset": "USDT", "limit": 1}, "category"),
        ({"category": "spot", "quote_asset": "../USD", "limit": 1}, "quote asset"),
        ({"category": "spot", "quote_asset": "USDT", "limit": 0}, "limit"),
    ):
        with pytest.raises(DataError, match=message):
            point_in_time_liquid_markets(market, as_of=now, **kwargs)  # type: ignore[arg-type]
    invalid_volume = market.with_columns(pl.lit(float("nan")).alias("quote_volume"))
    with pytest.raises(DataError, match="volume"):
        point_in_time_liquid_markets(
            invalid_volume, as_of=now, category="spot", quote_asset="USDT", limit=1
        )


def test_remaining_binance_parser_edges_are_explicit() -> None:
    now = datetime(2026, 8, 15, tzinfo=UTC)
    assert parse_binance_trades(b"1,2,3,6,1704067200000,false\n")["buyer_is_maker"][0] is False
    with pytest.raises(DataError, match="supported range"):
        parse_binance_klines(
            b"999999999999999999999,1,2,0.5,1.5,1,2,1,1,1,1\n", source="archive_csv"
        )
    with pytest.raises(DataError, match="unsupported value"):
        parse_binance_klines(b"[{}]", source="rest_json")
    with pytest.raises(DataError, match="unsupported Binance kline source"):
        parse_binance_klines(b"", source="bad")  # type: ignore[arg-type]
    with pytest.raises(DataError, match="malformed"):
        parse_binance_trades(b"\xff")
    with pytest.raises(DataError, match="malformed"):
        parse_binance_aggregate_trades(b"\xff")
    with pytest.raises(DataError, match="level"):
        parse_binance_book_snapshot(
            b'{"lastUpdateId":1,"bids":[["bad","1"]],"asks":[["2","1"]]}',
            symbol="BTCUSDT",
            category="spot",
            fetched_at=now,
        )
    with pytest.raises(DataError, match="timestamp"):
        parse_binance_book_snapshot(
            b'{"lastUpdateId":1,"E":true,"bids":[["1","1"]],"asks":[["2","1"]]}',
            symbol="BTCUSDT",
            category="spot",
            fetched_at=now,
        )
    malformed_contracts = (
        (
            b'{"symbols":[{"symbol":"bad/symbol","status":"TRADING","baseAsset":"BTC",'
            b'"quoteAsset":"USDT","isSpotTradingAllowed":true}]}',
            "symbol",
            "spot",
        ),
        (
            b'{"symbols":[{"symbol":"BTCUSDT","status":"TRADING","baseAsset":"BTC",'
            b'"quoteAsset":"USDT","contractType":"bad/type"}]}',
            "contract type",
            "linear",
        ),
        (
            b'{"symbols":[{"symbol":"BTCUSD_PERP","contractStatus":"TRADING",'
            b'"baseAsset":"BTC","quoteAsset":"USD","contractType":"PERPETUAL",'
            b'"contractSize":true}]}',
            "contract size",
            "inverse",
        ),
        (
            b'{"symbols":[{"symbol":"BTCUSD_PERP","contractStatus":"TRADING",'
            b'"baseAsset":"BTC","quoteAsset":"USD","contractType":"PERPETUAL",'
            b'"contractSize":"bad"}]}',
            "contract size",
            "inverse",
        ),
        (
            b'{"symbols":[{"symbol":"BTCUSD_PERP","contractStatus":"TRADING",'
            b'"baseAsset":"BTC","quoteAsset":"USD","contractType":"PERPETUAL",'
            b'"contractSize":-1}]}',
            "contract size",
            "inverse",
        ),
    )
    for payload, message, category in malformed_contracts:
        with pytest.raises(DataError, match=message):
            parse_binance_exchange_info(
                payload,
                category=category,  # type: ignore[arg-type]
                fetched_at=now,
            )

    one = io.BytesIO()
    with zipfile.ZipFile(one, "w") as archive:
        archive.writestr("one.csv", b"1,2,3,4,5,6\n")
    with pytest.raises(DataError, match="family"):
        parse_binance_archive_zip(one.getvalue(), family="bad")  # type: ignore[arg-type]


def test_remaining_binance_fetch_and_liquidity_edges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = "https://data.binance.vision/data/file.zip"
    with pytest.raises(DataError, match="identify a ZIP"):
        fetch_binance_archive("https://data.binance.vision/data/file")
    with pytest.raises(DataError, match="resumability"):
        fetch_binance_archive(url, tmp_path / "staging")
    with pytest.raises(DataError, match="checksum URL"):
        fetch_binance_checksum(url)
    with pytest.raises(DataError, match="host"):
        fetch_binance_checksum("https://attacker.invalid/file.zip.CHECKSUM")
    with pytest.raises(DataError, match="timeout"):
        fetch_binance_checksum(f"{url}.CHECKSUM", timeout_seconds=0)
    with pytest.raises(DataError, match="expected checksum"):
        fetch_binance_archive(url, tmp_path / "staging", "bad")

    expected = hashlib.sha256(b"good").hexdigest()
    cache = tmp_path / "cache" / "downloads" / f"{expected}.zip"
    cache.mkdir(parents=True)
    with pytest.raises(DataError, match="cache path is unsafe"):
        fetch_binance_archive(url, tmp_path / "staging", expected)

    def offline(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(urllib.request, "urlopen", offline)
    public_url = binance_public_api_url("spot", "depth", {"symbol": "BTCUSDT", "limit": 1})
    with pytest.raises(DataError, match="request failed"):
        fetch_binance_public_api(public_url)

    market = pl.DataFrame(
        {
            "session": [datetime(2026, 1, 2, tzinfo=UTC)] * 2,
            "category": ["spot"] * 2,
            "symbol": ["BTCUSDT"] * 2,
            "base_asset": ["BTC"] * 2,
            "quote_asset": ["USDT"] * 2,
            "base_volume": [1.0] * 2,
            "quote_volume": [2.0] * 2,
            "contract_size": [None] * 2,
        }
    )
    with pytest.raises(DataError, match="duplicate"):
        point_in_time_liquid_markets(
            market,
            as_of=datetime(2026, 1, 3, tzinfo=UTC),
            category="spot",
            quote_asset="USDT",
            limit=2,
        )
    with pytest.raises(DataError, match="schema"):
        point_in_time_liquid_markets(
            pl.DataFrame({"bad": [1]}),
            as_of=datetime(2026, 1, 3, tzinfo=UTC),
            category="spot",
            quote_asset="USDT",
            limit=1,
        )
    with pytest.raises(DataError, match="timezone"):
        point_in_time_liquid_markets(
            market.head(1),
            as_of=datetime(2026, 1, 3),
            category="spot",
            quote_asset="USDT",
            limit=1,
        )


def test_seconds_resolution_timestamp_fails_loud() -> None:
    payload = b"1704067200,42000,43000,41000,42500,12.5,1704153599,531250,42,6.1,259250,0\n"

    with pytest.raises(DataError, match="outside the supported range"):
        parse_binance_klines(payload, source="archive_csv")
