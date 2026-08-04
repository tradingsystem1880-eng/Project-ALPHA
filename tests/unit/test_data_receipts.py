"""Fail-closed validation for provider identity and immutable fetch receipts."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from typing import Any, cast

import pytest

from alpha_core import DataError
from alpha_data.adapters.base import DatasetIdentity, FetchReceipt


def _identity() -> DatasetIdentity:
    return DatasetIdentity(
        symbol="SPY",
        provider="tiingo",
        provider_symbol="SPY",
        venue="ARCX",
        asset_class="etf",
        timeframe="1D",
        calendar="XNYS",
        currency="USD",
        price_basis="raw",
    )


def _receipt() -> FetchReceipt:
    return FetchReceipt.create(
        identity=_identity(),
        requested_start=date(2026, 8, 3),
        requested_end=date(2026, 8, 3),
        fetched_at=datetime(2026, 8, 3, 22, tzinfo=UTC),
        adapter_version="1",
        parser_version="1",
        response_sha256="a" * 64,
        response_bytes=10,
        row_count=1,
        action_count=0,
        request_metadata={"endpoint": "/daily/SPY"},
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("symbol", ""),
        ("asset_class", "option"),
        ("timeframe", "1H"),
        ("price_basis", "adjusted"),
    ],
)
def test_dataset_identity_rejects_unsupported_or_empty_values(field: str, value: str) -> None:
    values = _identity().__dict__ | {field: value}
    with pytest.raises(DataError):
        DatasetIdentity(**values)


def test_dataset_identity_reader_requires_exact_string_schema() -> None:
    raw = _identity().to_dict()
    assert DatasetIdentity.from_dict(raw) == _identity()
    with pytest.raises(DataError, match="invalid dataset identity"):
        DatasetIdentity.from_dict({"symbol": "SPY"})
    raw["symbol"] = 123  # type: ignore[assignment]
    with pytest.raises(DataError, match="fields must be strings"):
        DatasetIdentity.from_dict(raw)


def test_dataset_identity_constructor_normalizes_invalid_runtime_types() -> None:
    raw = _identity().__dict__
    raw["symbol"] = 123
    with pytest.raises(DataError, match="non-empty strings"):
        DatasetIdentity(**raw)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"requested_end": date(2026, 8, 2)}, "precedes"),
        ({"fetched_at": datetime(2026, 8, 3)}, "timezone-aware"),
        ({"response_sha256": "BAD"}, "response_sha256"),
        ({"receipt_id": "BAD"}, "receipt_id"),
        ({"response_bytes": -1}, "non-negative"),
        ({"adapter_version": ""}, "versions"),
        ({"request_metadata": (("", "value"),)}, "metadata"),
    ],
)
def test_fetch_receipt_rejects_invalid_authority_fields(
    changes: dict[str, object], match: str
) -> None:
    with pytest.raises(DataError, match=match):
        replace(_receipt(), **cast(Any, changes))


def test_fetch_receipt_reader_rejects_invalid_schema_metadata_and_values() -> None:
    raw = _receipt().to_dict()
    assert FetchReceipt.from_dict(raw) == _receipt()
    with pytest.raises(DataError, match="invalid fetch receipt"):
        FetchReceipt.from_dict({"receipt_id": "bad"})
    raw["request_metadata"] = []
    with pytest.raises(DataError, match="request metadata"):
        FetchReceipt.from_dict(raw)
    raw = _receipt().to_dict()
    raw["requested_start"] = "not-a-date"
    with pytest.raises(DataError, match="receipt values"):
        FetchReceipt.from_dict(raw)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("receipt_id", None),
        ("requested_start", None),
        ("adapter_version", 1),
        ("response_bytes", True),
        ("row_count", "1"),
        ("action_count", 0.0),
    ],
)
def test_fetch_receipt_reader_requires_exact_scalar_types(field: str, value: object) -> None:
    raw = _receipt().to_dict()
    raw[field] = value
    with pytest.raises(DataError, match="receipt field types"):
        FetchReceipt.from_dict(raw)


def test_fetch_receipt_constructor_normalizes_invalid_metadata_key_type() -> None:
    with pytest.raises(DataError, match="request metadata"):
        replace(_receipt(), request_metadata=((1, "value"),))  # type: ignore[arg-type]
