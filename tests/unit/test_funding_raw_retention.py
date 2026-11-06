"""Real temporary storage operations, fake provider bytes and explicit fault injection."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from alpha_core import DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoRawReceiptV1
from alpha_data.crypto.funding_ingestion import collect_retained_funding_pages
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.providers.bybit import _result_object, parse_funding_history
from alpha_data.crypto.providers.bybit_funding import FundingPageCollection
from alpha_data.crypto.storage import Capacity, CryptoBulkStore, StagingHandle

NOW = datetime(2026, 9, 1, tzinfo=UTC)
END = int(NOW.timestamp() * 1000)
START = END - 1000
UUID = "758CBD77-1003-3BA3-AD28-1D647F5E2A08"


def store_at(root: Path) -> CryptoBulkStore:
    bulk = root / "bulk"
    bulk.mkdir(exist_ok=True)
    # Fake volume/capacity observations only; production reserve defaults are unchanged.
    return CryptoBulkStore(
        bulk_root=bulk,
        manifest_root=root / "manifests",
        expected_volume_uuid=UUID,
        volume_uuid=lambda _: UUID,
        capacity=lambda _: Capacity(2_000_000_000_000, 1_000_000_000_000),
    )


def dataset() -> CryptoDatasetIdentityV1:
    return CryptoDatasetIdentityV1(
        provider="bybit",
        venue="bybit",
        market_type="linear",
        family="funding",
        instrument="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        frequency="funding_interval",
        units="dimensionless_rate",
        timestamp_convention="provider_event_utc",
    )


def payload(timestamp: int = START, symbol: str = "BTCUSDT") -> bytes:
    return json.dumps(
        {
            "retCode": 0,
            "result": {
                "category": "linear",
                "list": [
                    {
                        "symbol": symbol,
                        "fundingRateTimestamp": str(timestamp),
                        "fundingRate": "-0.0001",
                    }
                ],
            },
        }
    ).encode()


def collect(
    store: CryptoBulkStore, raw: bytes, **options: Any
) -> tuple[FundingPageCollection, tuple[dict[str, object], ...]]:
    return collect_retained_funding_pages(
        store,
        lambda _p, _n: raw,
        dataset=dataset(),
        fetched_at=NOW,
        start_ms=START,
        end_ms=END,
        **options,
    )


def test_exact_raw_is_verified_before_decoder_and_reopens(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from alpha_data.crypto.providers import bybit_funding

    store = store_at(tmp_path)
    raw = payload()

    def checked(body: bytes) -> tuple[dict[str, object], int | None]:
        inventory = store.inventory()
        assert len(inventory) == 1
        assert (store.bulk_root / str(inventory[0]["artifact_key"])).read_bytes() == body == raw
        return _result_object(body)

    monkeypatch.setattr(bybit_funding, "_result_object", checked)
    collection, manifests = collect(store, raw)
    assert collection.stop_reason == "lower_bound_reached"
    assert collection.coverage_complete is False
    reopened = store_at(tmp_path)
    manifest = reopened.verify_manifest(manifests[0]["manifest_id"])
    receipt = CryptoRawReceiptV1.from_dict(manifest["receipt"])
    assert receipt.response_sha256 == hashlib.sha256(raw).hexdigest()
    assert receipt.response_bytes == len(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b"{",
        b"",
        payload(symbol="ETHUSDT"),
        pytest.param(payload(END + 1), marks=pytest.mark.bias_guard),
        b'{"retCode":0,"result":{"category":"linear","list":[]}}',
    ],
)
def test_rejected_or_empty_pages_remain_raw_evidence(tmp_path: Path, raw: bytes) -> None:
    store = store_at(tmp_path)
    if raw == payload(END + 1):
        latest = parse_funding_history(raw)["timestamp"].max()
        assert isinstance(latest, datetime) and latest > NOW  # Leaky control sees canary.
    if b'"list":[]' in raw:
        result, _ = collect(store, raw)
        assert result.stop_reason == "empty_page" and not result.coverage_complete
    else:
        with pytest.raises(DataError):
            collect(store, raw)
    inventory = store.inventory()
    assert len(inventory) == 1 and inventory[0]["artifact_kind"] == "raw"
    assert (store.bulk_root / str(inventory[0]["artifact_key"])).read_bytes() == raw
    assert CryptoRawReceiptV1.from_dict(inventory[0]["receipt"]).response_bytes == len(raw)


def test_duplicate_replay_has_identical_receipt_manifest_and_bytes(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    _, first = collect(store, payload())
    _, second = collect(store, payload())
    assert first == second and len(store.inventory()) == 1


def test_oversize_body_is_not_decoded_or_retained(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    with pytest.raises(DataError, match="byte"):
        collect(store, payload(), max_total_bytes=1)
    assert store.inventory() == ()


def test_supplier_failure_has_no_raw_evidence(tmp_path: Path) -> None:
    store = store_at(tmp_path)

    def failing(_params: dict[str, str | int], _max_bytes: int) -> bytes:
        raise DataError("synthetic callback failure")

    with pytest.raises(DataError, match="callback failure"):
        collect_retained_funding_pages(
            store, failing, dataset=dataset(), fetched_at=NOW, start_ms=START, end_ms=END
        )
    assert store.inventory() == ()


def test_reserve_failure_precedes_supplier_without_lowering_defaults(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    store._capacity = lambda _: Capacity(2_000_000_000_000, 1)

    def prohibited(_params: dict[str, str | int], _max_bytes: int) -> bytes:
        pytest.fail("reserve failure reached supplier")

    with pytest.raises(DataError):
        collect_retained_funding_pages(
            store, prohibited, dataset=dataset(), fetched_at=NOW, start_ms=START, end_ms=END
        )
    assert store.inventory() == ()


@pytest.mark.parametrize("after_manifest", [False, True])
def test_publication_interruption_never_decodes_and_exact_replay_recovers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    after_manifest: bool,
) -> None:
    from alpha_data.crypto.providers import bybit_funding

    store = store_at(tmp_path)
    publish = store._publish_manifest

    def interrupted(body: dict[str, object]) -> dict[str, object]:
        if after_manifest:
            publish(body)
        raise OSError("synthetic publication interruption")

    def prohibited(_raw: bytes) -> tuple[dict[str, object], int | None]:
        pytest.fail("interrupted retention reached decoder")

    with monkeypatch.context() as fault:
        fault.setattr(store, "_publish_manifest", interrupted)
        fault.setattr(bybit_funding, "_result_object", prohibited)
        with pytest.raises(OSError):
            collect(store, payload())
    assert len(store.inventory()) == int(after_manifest)
    assert list((store.bulk_root / "raw").rglob("funding.json"))
    _, manifests = collect(store, payload())
    assert len(store.inventory()) == 1
    assert store.verify_manifest(manifests[0]["manifest_id"])


def test_partial_staging_retains_prefix_and_replay_finishes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = store_at(tmp_path)
    append = store.append_staging

    def interrupted(handle: StagingHandle, body: bytes) -> StagingHandle:
        append(handle, body[:10])
        raise OSError("synthetic partial write")

    with monkeypatch.context() as fault:
        fault.setattr(store, "append_staging", interrupted)
        with pytest.raises(OSError):
            collect(store, payload())
    assert store.inventory() == ()
    staged = list(store.staging_root.glob("*/payload.part"))
    assert len(staged) == 1 and staged[0].read_bytes() == payload()[:10]
    collect(store, payload())
    assert len(store.inventory()) == 1


def test_request_is_frozen_before_supplier_mutates_params(tmp_path: Path) -> None:
    store = store_at(tmp_path)

    def supplied(params: dict[str, str | int], _max_bytes: int) -> bytes:
        params["symbol"] = "MUTATED"
        return payload()

    _, manifests = collect_retained_funding_pages(
        store, supplied, dataset=dataset(), fetched_at=NOW, start_ms=START, end_ms=END
    )
    receipt = CryptoRawReceiptV1.from_dict(manifests[0]["receipt"])
    assert dict(receipt.request)["symbol"] == "BTCUSDT"


def test_valid_first_rejected_second_keeps_both_raw_pages(tmp_path: Path) -> None:
    store = store_at(tmp_path)
    bodies = iter([payload(END), b"{"])
    with pytest.raises(DataError):
        collect_retained_funding_pages(
            store,
            lambda _p, _n: next(bodies),
            dataset=dataset(),
            fetched_at=NOW,
            start_ms=START,
            end_ms=END,
        )
    inventory = store.inventory()
    assert len(inventory) == 2 and all(m["artifact_kind"] == "raw" for m in inventory)
    assert {(store.bulk_root / str(m["artifact_key"])).read_bytes() for m in inventory} == {
        payload(END),
        b"{",
    }


def test_changed_published_bytes_prevent_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = store_at(tmp_path)
    publish = store.publish_staging

    def changed(handle: StagingHandle, **kwargs: Any) -> dict[str, object]:
        manifest = publish(handle, **kwargs)
        (store.bulk_root / str(manifest["artifact_key"])).write_bytes(b"corrupt")
        return manifest

    monkeypatch.setattr(store, "publish_staging", changed)
    with pytest.raises(DataError, match="integrity"):
        collect(store, payload())


def test_invalid_dataset_refuses_before_supplier(tmp_path: Path) -> None:
    store = store_at(tmp_path)

    def prohibited(_params: dict[str, str | int], _max_bytes: int) -> bytes:
        pytest.fail("invalid dataset reached supplier")

    with pytest.raises(DataError, match="identity"):
        collect_retained_funding_pages(
            store,
            prohibited,
            dataset=replace(dataset(), venue="other"),
            fetched_at=NOW,
            start_ms=START,
            end_ms=END,
        )
    assert store.inventory() == ()


def test_readability_failure_after_publication_prevents_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from alpha_data.crypto.providers import bybit_funding

    store = store_at(tmp_path)

    def unreadable() -> Capacity:
        raise DataError("synthetic root lost after publication")

    def prohibited(_raw: bytes) -> tuple[dict[str, object], int | None]:
        pytest.fail("lost root reached decoder")

    with monkeypatch.context() as fault:
        fault.setattr(store, "verify_readable", unreadable)
        fault.setattr(bybit_funding, "_result_object", prohibited)
        with pytest.raises(DataError, match="root lost"):
            collect(store, payload())
    assert len(store.inventory()) == 1


def test_legacy_ingestion_still_refuses_zero_body(tmp_path: Path) -> None:
    with pytest.raises(DataError, match="non-empty"):
        ingest_provider_payload(
            store_at(tmp_path),
            dataset=dataset(),
            payload=b"",
            request=(),
            fetched_at=NOW,
            provider_schema="bybit-v5",
            parser_version="bybit-public-v1",
            logical_name="funding.json",
            parser=lambda _: pytest.fail("decoded"),
            observed_column="timestamp",
            key_columns=("timestamp", "symbol"),
        )
