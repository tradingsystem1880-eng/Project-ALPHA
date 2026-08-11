"""The adapter seam: every data source returns raw bars + corporate actions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal, Protocol

import polars as pl

from alpha_core import CorporateAction, DataError

type AssetClass = Literal["stock", "etf", "crypto", "future"]
type Timeframe = Literal["1D"]
type PriceBasis = Literal["raw"]


@dataclass(frozen=True)
class DatasetIdentity:
    """Stable identity for one provider-qualified daily dataset."""

    symbol: str
    provider: str
    provider_symbol: str
    venue: str
    asset_class: AssetClass
    timeframe: Timeframe
    calendar: str
    currency: str
    price_basis: PriceBasis

    def __post_init__(self) -> None:
        strings = (
            self.symbol,
            self.provider,
            self.provider_symbol,
            self.venue,
            self.asset_class,
            self.timeframe,
            self.calendar,
            self.currency,
            self.price_basis,
        )
        if any(not isinstance(value, str) or not value.strip() for value in strings):
            raise DataError("dataset identity values must be non-empty strings")
        if self.asset_class not in {"stock", "etf", "crypto", "future"}:
            raise DataError(f"unsupported asset class {self.asset_class!r}")
        if self.timeframe != "1D":
            raise DataError(f"unsupported timeframe {self.timeframe!r}; ALPHA is daily-only")
        if self.price_basis != "raw":
            raise DataError("canonical datasets must use raw prices")

    def to_dict(self) -> dict[str, str]:
        return {
            "asset_class": self.asset_class,
            "calendar": self.calendar,
            "currency": self.currency,
            "price_basis": self.price_basis,
            "provider": self.provider,
            "provider_symbol": self.provider_symbol,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "venue": self.venue,
        }

    @classmethod
    def from_dict(cls, value: object) -> DatasetIdentity:
        fields = {
            "asset_class",
            "calendar",
            "currency",
            "price_basis",
            "provider",
            "provider_symbol",
            "symbol",
            "timeframe",
            "venue",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise DataError("invalid dataset identity")
        if any(not isinstance(value[name], str) for name in fields):
            raise DataError("dataset identity fields must be strings")
        return cls(
            symbol=value["symbol"],
            provider=value["provider"],
            provider_symbol=value["provider_symbol"],
            venue=value["venue"],
            asset_class=value["asset_class"],
            timeframe=value["timeframe"],
            calendar=value["calendar"],
            currency=value["currency"],
            price_basis=value["price_basis"],
        )


@dataclass(frozen=True)
class FetchReceipt:
    """Redacted, content-bound record of a provider response."""

    receipt_id: str
    requested_start: date
    requested_end: date
    fetched_at: datetime
    adapter_version: str
    parser_version: str
    response_sha256: str
    response_bytes: int
    row_count: int
    action_count: int
    request_metadata: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.requested_start, date)
            or isinstance(self.requested_start, datetime)
            or not isinstance(self.requested_end, date)
            or isinstance(self.requested_end, datetime)
            or not isinstance(self.fetched_at, datetime)
        ):
            raise DataError("receipt dates must use date/date/timezone-aware datetime values")
        string_values = (
            self.receipt_id,
            self.adapter_version,
            self.parser_version,
            self.response_sha256,
        )
        if any(not isinstance(value, str) for value in string_values):
            raise DataError("receipt identifiers and versions must be strings")
        counts = (self.response_bytes, self.row_count, self.action_count)
        if any(not isinstance(value, int) or isinstance(value, bool) for value in counts):
            raise DataError("receipt counts must be integers")
        if self.requested_end < self.requested_start:
            raise DataError("receipt requested_end precedes requested_start")
        if self.fetched_at.tzinfo is None or self.fetched_at.utcoffset() is None:
            raise DataError("receipt fetched_at must be timezone-aware")
        if len(self.response_sha256) != 64 or any(
            char not in "0123456789abcdef" for char in self.response_sha256
        ):
            raise DataError("receipt response_sha256 must be lowercase SHA-256")
        if len(self.receipt_id) != 32 or any(
            char not in "0123456789abcdef" for char in self.receipt_id
        ):
            raise DataError("receipt_id must be 32 lowercase hex characters")
        if self.response_bytes < 0 or self.row_count < 0 or self.action_count < 0:
            raise DataError("receipt counts must be non-negative")
        if not self.adapter_version.strip() or not self.parser_version.strip():
            raise DataError("receipt versions must be non-empty")
        if not isinstance(self.request_metadata, tuple) or any(
            not isinstance(item, tuple)
            or len(item) != 2
            or not isinstance(item[0], str)
            or not item[0].strip()
            or not isinstance(item[1], str)
            for item in self.request_metadata
        ):
            raise DataError("receipt request metadata must contain non-empty string keys")

    @classmethod
    def create(
        cls,
        *,
        identity: DatasetIdentity,
        requested_start: date,
        requested_end: date,
        fetched_at: datetime,
        adapter_version: str,
        parser_version: str,
        response_sha256: str,
        response_bytes: int,
        row_count: int,
        action_count: int,
        request_metadata: dict[str, str],
    ) -> FetchReceipt:
        seed = json.dumps(
            {
                "dataset": identity.to_dict(),
                "fetched_at": fetched_at.isoformat(),
                "requested_end": requested_end.isoformat(),
                "requested_start": requested_start.isoformat(),
                "response_sha256": response_sha256,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return cls(
            receipt_id=hashlib.sha256(seed).hexdigest()[:32],
            requested_start=requested_start,
            requested_end=requested_end,
            fetched_at=fetched_at,
            adapter_version=adapter_version,
            parser_version=parser_version,
            response_sha256=response_sha256,
            response_bytes=response_bytes,
            row_count=row_count,
            action_count=action_count,
            request_metadata=tuple(sorted(request_metadata.items())),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "action_count": self.action_count,
            "adapter_version": self.adapter_version,
            "fetched_at": self.fetched_at.isoformat(),
            "parser_version": self.parser_version,
            "receipt_id": self.receipt_id,
            "request_metadata": dict(self.request_metadata),
            "requested_end": self.requested_end.isoformat(),
            "requested_start": self.requested_start.isoformat(),
            "response_bytes": self.response_bytes,
            "response_sha256": self.response_sha256,
            "row_count": self.row_count,
        }

    @classmethod
    def from_dict(cls, value: object) -> FetchReceipt:
        fields = {
            "action_count",
            "adapter_version",
            "fetched_at",
            "parser_version",
            "receipt_id",
            "request_metadata",
            "requested_end",
            "requested_start",
            "response_bytes",
            "response_sha256",
            "row_count",
        }
        if not isinstance(value, dict) or set(value) != fields:
            raise DataError("invalid fetch receipt")
        metadata = value["request_metadata"]
        if not isinstance(metadata, dict) or any(
            not isinstance(key, str) or not isinstance(item, str) for key, item in metadata.items()
        ):
            raise DataError("invalid fetch receipt request metadata")
        string_fields = {
            "adapter_version",
            "fetched_at",
            "parser_version",
            "receipt_id",
            "requested_end",
            "requested_start",
            "response_sha256",
        }
        count_fields = {"action_count", "response_bytes", "row_count"}
        if any(not isinstance(value[name], str) for name in string_fields) or any(
            not isinstance(value[name], int) or isinstance(value[name], bool)
            for name in count_fields
        ):
            raise DataError("invalid fetch receipt field types")
        try:
            return cls(
                receipt_id=value["receipt_id"],
                requested_start=date.fromisoformat(value["requested_start"]),
                requested_end=date.fromisoformat(value["requested_end"]),
                fetched_at=datetime.fromisoformat(value["fetched_at"]),
                adapter_version=value["adapter_version"],
                parser_version=value["parser_version"],
                response_sha256=value["response_sha256"],
                response_bytes=value["response_bytes"],
                row_count=value["row_count"],
                action_count=value["action_count"],
                request_metadata=tuple(sorted(metadata.items())),
            )
        except (TypeError, ValueError) as exc:
            raise DataError("invalid fetch receipt values") from exc


@dataclass(frozen=True)
class FetchResult:
    """Raw (unadjusted) bars plus the corporate actions for one symbol."""

    symbol: str
    bars: pl.DataFrame  # schema: ts, open, high, low, close, volume
    actions: list[CorporateAction]
    identity: DatasetIdentity | None = None
    receipt: FetchReceipt | None = None
    raw_response: bytes | None = None


class DataAdapter(Protocol):
    """A source of raw market data. `name`/`version` feed snapshot provenance."""

    name: str
    version: str
    parser_version: str

    def fetch(self, symbol: str, start: date, end: date) -> FetchResult: ...
