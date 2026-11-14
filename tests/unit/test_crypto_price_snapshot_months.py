"""Explicit monthly lineage and bounded deterministic daily price reads."""

from collections.abc import Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import NoReturn, cast

import pytest

from alpha_cli.crypto_price_snapshot_query import (
    BinanceDailyPriceSnapshotQueryV1,
    BinanceDailyPriceSnapshotQueryV2,
    query_binance_daily_price_snapshot,
)
from alpha_core import DataError
from alpha_data.crypto.ingestion import CryptoIngestionResultV1
from alpha_data.crypto.storage import CryptoBulkStore
from tests.fixtures.daily_price_months import manifest_ids, month_start, publish_month, snapshot_for
from tests.unit.test_crypto_price_snapshot_query import _store


def query(
    store: CryptoBulkStore,
    results: Sequence[CryptoIngestionResultV1],
    *,
    ids: tuple[str, ...] | list[str] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
) -> BinanceDailyPriceSnapshotQueryV1 | BinanceDailyPriceSnapshotQueryV2:
    start = start or month_start(2020, 1)
    end = end or month_start(2020, len(results) + 1)
    return query_binance_daily_price_snapshot(
        snapshot_for(*results),
        store,
        normalized_manifest_ids=manifest_ids(*results) if ids is None else ids,
        start=start,
        end=end,
        available_by=end,
    )


@pytest.mark.parametrize("count", [3, 36])
def test_months_are_contiguous_equal_single_reads_and_canonical(tmp_path: Path, count: int) -> None:
    store = _store(tmp_path)
    results = [
        publish_month(store, value.year, value.month)
        for value in (month_start(2020, i) for i in range(1, count + 1))
    ]
    result = query(store, results)
    singles = tuple(
        row
        for index, member in enumerate(results)
        for row in query(
            store, [member], start=month_start(2020, index + 1), end=month_start(2020, index + 2)
        ).rows
    )
    assert result.rows == singles
    assert result.to_dict()["schema"] == "BinanceDailyPriceSnapshotQueryV2"
    assert result.to_dict() == query(store, results, ids=manifest_ids(*reversed(results))).to_dict()
    assert [row.open_time for row in result.rows] == [
        month_start(2020, 1) + timedelta(days=index) for index in range(len(result.rows))
    ]
    members = result.to_dict()["members"]
    assert isinstance(members, list)
    assert members[0]["source_receipt_ids"] == [result.source_receipts[0].receipt_id]


@pytest.mark.parametrize(
    "start,end",
    [
        (month_start(2020, 1) + timedelta(days=15), month_start(2020, 3) + timedelta(days=10)),
        (month_start(2020, 1) + timedelta(days=30), month_start(2020, 2)),
        (month_start(2020, 2) + timedelta(days=28), month_start(2020, 3)),
        (month_start(2020, 12) + timedelta(days=30), month_start(2021, 1)),
    ],
)
def test_partial_months_and_exact_boundaries(
    tmp_path: Path, start: datetime, end: datetime
) -> None:
    store = _store(tmp_path)
    results = [
        publish_month(store, value.year, value.month)
        for value in (month_start(2020, i) for i in range(1, 13))
    ]
    chosen = []
    for result in results:
        assert result.quality.observed_start is not None
        assert result.quality.observed_end is not None
        if result.quality.observed_start < end and result.quality.observed_end >= start:
            chosen.append(result)
    selected = query(store, results, ids=manifest_ids(*chosen), start=start, end=end)
    assert len(selected.rows) == (end - start).days
    assert selected.rows[0].open_time == start
    assert selected.rows[-1].available_at == end


@pytest.mark.parametrize("rest", [False, True])
def test_overlapping_members_refused(tmp_path: Path, rest: bool) -> None:
    store = _store(tmp_path)
    first = publish_month(store, 2020, 1)
    second = publish_month(
        store, 2020, 2, start=month_start(2020, 2) - timedelta(days=1), rest=rest
    )
    with pytest.raises(DataError, match="price query members overlap"):
        query(store, [first, second])


def test_rest_capture_covering_archive_month_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = publish_month(store, 2020, 1)
    second = publish_month(store, 2020, 1, rest=True, price=101)
    with pytest.raises(DataError, match="price query members overlap"):
        query(store, [first, second])


@pytest.mark.parametrize(
    "retained,message", [(True, "is not named"), (False, "coverage is incomplete")]
)
def test_missing_month_refused(tmp_path: Path, retained: bool, message: str) -> None:
    store = _store(tmp_path)
    results = [publish_month(store, 2020, month) for month in (1, 2, 3)]
    ids = manifest_ids(results[0], results[2])
    with pytest.raises(DataError, match=message):
        query(
            store,
            results if retained else [results[0], results[2]],
            ids=ids,
            end=month_start(2020, 4),
        )


def test_duplicate_ids_and_two_ids_for_one_member_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    first = publish_month(store, 2020, 1)
    repeat = publish_month(store, 2020, 1, fetched=month_start(2020, 3))
    with pytest.raises(DataError, match="names a normalized manifest more than once"):
        query(store, [first], ids=manifest_ids(first, first))
    with pytest.raises(DataError, match="one member"):
        query(store, [first], ids=manifest_ids(first, repeat))


def test_named_member_outside_range_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    results = [publish_month(store, 2020, month) for month in (1, 2, 3)]
    with pytest.raises(DataError, match="lies outside the requested range"):
        query(store, results, end=month_start(2020, 3))


def test_other_instrument_ignored_unless_named(tmp_path: Path) -> None:
    store = _store(tmp_path)
    btc = [publish_month(store, 2020, month) for month in (1, 2)]
    eth = publish_month(store, 2020, 1, instrument="ETHUSDT")
    assert (
        query(store, [*btc, eth], ids=manifest_ids(*btc), end=month_start(2020, 3)).rows
        == query(store, btc).rows
    )
    with pytest.raises(DataError, match="exact Binance"):
        query(store, [*btc, eth], ids=manifest_ids(*btc, eth))


@pytest.mark.parametrize(
    "change", [{"period": "2020-01-01"}, {"symbol": "ETHUSDT"}, {"extra": "x"}]
)
def test_forged_archive_request_refused(tmp_path: Path, change: dict[str, str]) -> None:
    store = _store(tmp_path)
    request = {
        "family": "klines",
        "interval": "1d",
        "market": "spot",
        "period": "2020-01",
        "symbol": "BTCUSDT",
        **change,
    }
    result = publish_month(store, 2020, 1, request=request)
    with pytest.raises(DataError, match="identity/schema differs"):
        query(store, [result])


def test_candle_outside_receipt_month_refused(tmp_path: Path) -> None:
    store = _store(tmp_path)
    result = publish_month(store, 2020, 1, end=month_start(2020, 2) + timedelta(days=1))
    with pytest.raises(DataError, match="outside pinned raw request bounds"):
        query(store, [result], end=month_start(2020, 2) + timedelta(days=1))


def test_aggregate_raw_size_precedes_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    results = [publish_month(store, 2020, month) for month in (1, 2)]
    metadata = list(store.metadata_inventory())
    from dataclasses import replace

    from alpha_data.crypto.contracts import CryptoRawReceiptV1

    for raw in metadata:
        if raw["artifact_kind"] == "raw":
            receipt = replace(
                CryptoRawReceiptV1.from_dict(raw["receipt"]), response_bytes=5 * 1024 * 1024
            )
            raw.update(
                artifact_bytes=receipt.response_bytes,
                receipt=receipt.to_dict(),
                receipt_id=receipt.receipt_id,
            )
    monkeypatch.setattr(store, "metadata_inventory", lambda: tuple(metadata))

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("payload hashing preceded aggregate raw preflight")

    monkeypatch.setattr(store, "verify_manifest", forbidden)
    with pytest.raises(DataError, match="8 MiB"):
        query(store, results)


def test_aggregate_normalized_size_precedes_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = _store(tmp_path)
    results = [publish_month(store, 2020, month) for month in (1, 2)]
    metadata = list(store.metadata_inventory())
    for item in metadata:
        if item["artifact_kind"] == "normalized":
            item["artifact_bytes"] = 17 * 1024 * 1024
    monkeypatch.setattr(store, "metadata_inventory", lambda: tuple(metadata))

    def forbidden(*args: object, **kwargs: object) -> NoReturn:
        pytest.fail("payload hashing preceded aggregate normalized preflight")

    monkeypatch.setattr(store, "verify_manifest", forbidden)
    monkeypatch.setattr(store, "read_verified_normalized", forbidden)
    with pytest.raises(DataError, match="32 MiB"):
        query(store, results)


def test_document_is_identical_across_stores(tmp_path: Path) -> None:
    documents = []
    for name in ("first", "second"):
        root = tmp_path / name
        root.mkdir()
        store = _store(root)
        documents.append(
            query(store, [publish_month(store, 2020, month) for month in (1, 2, 3)]).to_dict()
        )
    assert documents[0] == documents[1]


@pytest.mark.parametrize("ids", ["a" * 64, (), ["A" * 64], ["bad"], ["a" * 64] * 201])
def test_invalid_manifest_sequence_fails(tmp_path: Path, ids: object) -> None:
    store = _store(tmp_path)
    result = publish_month(store, 2020, 1)
    with pytest.raises(DataError):
        query(store, [result], ids=cast(tuple[str, ...] | list[str], ids))
