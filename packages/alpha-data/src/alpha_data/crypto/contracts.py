"""Immutable version-1 contracts for provider-native crypto datasets."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, cast

from alpha_core import DataError

type CryptoFamily = Literal[
    "market_bars",
    "trades",
    "aggregate_trades",
    "book_snapshots",
    "market_membership",
    "instrument_catalog",
    "derivative_bars",
    "derivative_trades",
    "derivative_book_snapshots",
    "funding",
    "open_interest",
    "long_short_ratio",
    "mark_bars",
    "index_bars",
    "premium_bars",
    "option_instruments",
    "option_quotes",
    "historical_volatility",
    "asset_metadata",
    "market_reference",
    "onchain_catalog",
    "onchain_metrics",
    "dex_pools",
    "dex_ohlcv",
    "dex_transactions",
    "comparison_bars",
]
type CryptoMarketType = Literal[
    "spot", "linear", "inverse", "option", "dex", "network", "reference"
]
type QualificationState = Literal[
    "unverified", "qualified", "warning", "quarantined", "unavailable"
]

FAMILY_AUTHORITIES: Final[dict[CryptoFamily, str]] = {
    "market_bars": "binance",
    "trades": "binance",
    "aggregate_trades": "binance",
    "book_snapshots": "binance",
    "market_membership": "binance",
    "instrument_catalog": "bybit",
    "derivative_bars": "bybit",
    "derivative_trades": "bybit",
    "derivative_book_snapshots": "bybit",
    "funding": "bybit",
    "open_interest": "bybit",
    "long_short_ratio": "bybit",
    "mark_bars": "bybit",
    "index_bars": "bybit",
    "premium_bars": "bybit",
    "option_instruments": "bybit",
    "option_quotes": "bybit",
    "historical_volatility": "bybit",
    "asset_metadata": "coingecko",
    "market_reference": "coingecko",
    "onchain_catalog": "coinmetrics",
    "onchain_metrics": "coinmetrics",
    "dex_pools": "geckoterminal",
    "dex_ohlcv": "geckoterminal",
    "dex_transactions": "geckoterminal",
    "comparison_bars": "ccxt:coinbase",
}
_HEX = re.compile(r"^[0-9a-f]{64}$")
_CASE_INSENSITIVE_ADDRESS_NETWORKS = frozenset(
    {
        "arbitrum",
        "arbitrum-one",
        "base",
        "binance-smart-chain",
        "bnb-smart-chain",
        "bsc",
        "eth",
        "ethereum",
    }
)
_SECRET_MARKERS = ("api_key", "apikey", "authorization", "password", "secret", "token")


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _text(value: str, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DataError(f"crypto {label} must be a non-empty string")
    return value.strip()


def normalize_crypto_address(network: str, address: str) -> str:
    """Preserve case-sensitive identities while canonicalizing EVM-style addresses."""
    network_key = _text(network, "address network").lower()
    address_value = _text(address, "address")
    return (
        address_value.lower()
        if network_key in _CASE_INSENSITIVE_ADDRESS_NETWORKS
        else address_value
    )


def _sha(value: str, label: str) -> str:
    if not isinstance(value, str) or _HEX.fullmatch(value) is None:
        raise DataError(f"crypto {label} must be lowercase SHA-256")
    return value


def _time(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"crypto {label} must be timezone-aware")
    return value.astimezone(UTC)


def _pairs(value: tuple[tuple[str, str], ...], label: str) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, tuple):
        raise DataError(f"crypto {label} must be an ordered tuple")
    checked: list[tuple[str, str]] = []
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            raise DataError(f"crypto {label} entries must be string pairs")
        checked.append((_text(item[0], f"{label} key"), _text(item[1], f"{label} value")))
    if len({key for key, _ in checked}) != len(checked):
        raise DataError(f"crypto {label} keys must be unique")
    return tuple(checked)


@dataclass(frozen=True)
class CryptoAssetIdentityV1:
    coingecko_id: str
    network: str
    contract_address: str | None
    native_asset: bool
    provider_symbols: tuple[tuple[str, str], ...]
    valid_from: datetime
    valid_to: datetime | None
    migration_lineage: tuple[str, ...]
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "coingecko_id", _text(self.coingecko_id, "CoinGecko id"))
        object.__setattr__(self, "network", _text(self.network, "network").lower())
        if not isinstance(self.native_asset, bool):
            raise DataError("crypto native_asset must be boolean")
        if not self.native_asset and not self.contract_address:
            raise DataError("non-native crypto identity requires a contract address")
        if self.contract_address is not None:
            object.__setattr__(
                self,
                "contract_address",
                normalize_crypto_address(self.network, self.contract_address),
            )
        object.__setattr__(
            self, "provider_symbols", _pairs(self.provider_symbols, "provider symbols")
        )
        object.__setattr__(self, "valid_from", _time(self.valid_from, "valid_from"))
        if self.valid_to is not None:
            object.__setattr__(self, "valid_to", _time(self.valid_to, "valid_to"))
            if self.valid_to < self.valid_from:
                raise DataError("crypto identity valid_to precedes valid_from")
        if not isinstance(self.migration_lineage, tuple) or any(
            not isinstance(item, str) or not item.strip() for item in self.migration_lineage
        ):
            raise DataError("crypto migration lineage must contain non-empty strings")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "coingecko_id": self.coingecko_id,
            "network": self.network,
            "contract_address": self.contract_address,
            "native_asset": self.native_asset,
            "provider_symbols": [list(item) for item in self.provider_symbols],
            "valid_from": self.valid_from.isoformat().replace("+00:00", "Z"),
            "valid_to": self.valid_to.isoformat().replace("+00:00", "Z") if self.valid_to else None,
            "migration_lineage": list(self.migration_lineage),
        }


@dataclass(frozen=True)
class CryptoDatasetIdentityV1:
    provider: str
    venue: str
    market_type: CryptoMarketType
    family: CryptoFamily
    instrument: str
    base_asset: str | None
    quote_asset: str | None
    frequency: str
    units: str
    timestamp_convention: str
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        for name in (
            "provider",
            "venue",
            "instrument",
            "frequency",
            "units",
            "timestamp_convention",
        ):
            object.__setattr__(self, name, _text(cast(str, getattr(self, name)), name))
        if self.family not in FAMILY_AUTHORITIES:
            raise DataError(f"unsupported crypto dataset family {self.family!r}")
        if self.market_type not in {
            "spot",
            "linear",
            "inverse",
            "option",
            "dex",
            "network",
            "reference",
        }:
            raise DataError(f"unsupported crypto market type {self.market_type!r}")
        for name in ("base_asset", "quote_asset"):
            value = cast(str | None, getattr(self, name))
            if value is not None:
                object.__setattr__(self, name, _text(value, name).upper())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "provider": self.provider,
            "venue": self.venue,
            "market_type": self.market_type,
            "family": self.family,
            "instrument": self.instrument,
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "frequency": self.frequency,
            "units": self.units,
            "timestamp_convention": self.timestamp_convention,
        }

    @property
    def content_sha256(self) -> str:
        return _digest(self.to_dict())

    @classmethod
    def from_dict(cls, value: object) -> CryptoDatasetIdentityV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("invalid CryptoDatasetIdentityV1")
        try:
            return cls(
                provider=value["provider"],
                venue=value["venue"],
                market_type=value["market_type"],
                family=value["family"],
                instrument=value["instrument"],
                base_asset=value["base_asset"],
                quote_asset=value["quote_asset"],
                frequency=value["frequency"],
                units=value["units"],
                timestamp_convention=value["timestamp_convention"],
            )
        except (KeyError, TypeError) as exc:
            raise DataError("invalid CryptoDatasetIdentityV1") from exc


@dataclass(frozen=True)
class CryptoAcquisitionScopeV1:
    """Immutable case binding for high-frequency research-event capture."""

    project_id: str
    case_revision: str
    reason: str
    captured_at: datetime
    purpose: Literal["case_bound_event_capture"] = "case_bound_event_capture"
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        _text(self.project_id, "acquisition project id")
        _sha(self.case_revision, "acquisition case revision")
        reason = _text(self.reason, "acquisition reason")
        if len(reason) > 500:
            raise DataError("crypto acquisition reason exceeds 500 characters")
        object.__setattr__(self, "captured_at", _time(self.captured_at, "captured_at"))
        if self.purpose != "case_bound_event_capture":
            raise DataError("invalid crypto acquisition purpose")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "project_id": self.project_id,
            "case_revision": self.case_revision,
            "reason": self.reason,
            "captured_at": self.captured_at.isoformat().replace("+00:00", "Z"),
            "purpose": self.purpose,
        }

    @classmethod
    def from_dict(cls, value: object) -> CryptoAcquisitionScopeV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("invalid CryptoAcquisitionScopeV1")
        try:
            captured_at = value["captured_at"]
            if not isinstance(captured_at, str):
                raise DataError("invalid CryptoAcquisitionScopeV1 captured_at")
            return cls(
                project_id=value["project_id"],
                case_revision=value["case_revision"],
                reason=value["reason"],
                captured_at=datetime.fromisoformat(captured_at.replace("Z", "+00:00")),
                purpose=value["purpose"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError("invalid CryptoAcquisitionScopeV1") from exc


@dataclass(frozen=True)
class CryptoRawReceiptV1:
    receipt_id: str
    dataset: CryptoDatasetIdentityV1
    request: tuple[tuple[str, str], ...]
    fetched_at: datetime
    response_sha256: str
    response_bytes: int
    provider_schema: str
    parser_version: str
    pagination: tuple[str, ...]
    upstream_checksum: str | None
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        _sha(self.receipt_id, "receipt id")
        request = _pairs(self.request, "request")
        if any(
            marker in key.lower().replace("-", "_")
            for key, _ in request
            for marker in _SECRET_MARKERS
        ):
            raise DataError("crypto request metadata contains a secret-bearing key")
        object.__setattr__(self, "request", request)
        object.__setattr__(self, "fetched_at", _time(self.fetched_at, "fetched_at"))
        _sha(self.response_sha256, "response hash")
        if (
            not isinstance(self.response_bytes, int)
            or isinstance(self.response_bytes, bool)
            or self.response_bytes < 0
        ):
            raise DataError("crypto response_bytes must be a non-negative integer")
        _text(self.provider_schema, "provider schema")
        _text(self.parser_version, "parser version")
        if not isinstance(self.pagination, tuple) or any(
            not isinstance(item, str) for item in self.pagination
        ):
            raise DataError("crypto pagination must be an ordered string tuple")
        if self.upstream_checksum is not None:
            _sha(self.upstream_checksum, "upstream checksum")

    @classmethod
    def create(
        cls,
        *,
        dataset: CryptoDatasetIdentityV1,
        request: tuple[tuple[str, str], ...],
        fetched_at: datetime,
        response_sha256: str,
        response_bytes: int,
        provider_schema: str,
        parser_version: str,
        pagination: tuple[str, ...],
        upstream_checksum: str | None,
    ) -> CryptoRawReceiptV1:
        normalized_time = _time(fetched_at, "fetched_at")
        body = {
            "dataset": dataset.to_dict(),
            "request": request,
            "fetched_at": normalized_time.isoformat(),
            "response_sha256": response_sha256,
        }
        return cls(
            receipt_id=_digest(body),
            dataset=dataset,
            request=request,
            fetched_at=normalized_time,
            response_sha256=response_sha256,
            response_bytes=response_bytes,
            provider_schema=provider_schema,
            parser_version=parser_version,
            pagination=pagination,
            upstream_checksum=upstream_checksum,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "receipt_id": self.receipt_id,
            "dataset": self.dataset.to_dict(),
            "request": [list(item) for item in self.request],
            "fetched_at": self.fetched_at.isoformat().replace("+00:00", "Z"),
            "response_sha256": self.response_sha256,
            "response_bytes": self.response_bytes,
            "provider_schema": self.provider_schema,
            "parser_version": self.parser_version,
            "pagination": list(self.pagination),
            "upstream_checksum": self.upstream_checksum,
        }

    @classmethod
    def from_dict(cls, value: object) -> CryptoRawReceiptV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("invalid CryptoRawReceiptV1")
        try:
            request_raw = value["request"]
            pagination_raw = value["pagination"]
            fetched_raw = value["fetched_at"]
            if (
                not isinstance(request_raw, list)
                or not isinstance(pagination_raw, list)
                or not isinstance(fetched_raw, str)
            ):
                raise DataError("invalid CryptoRawReceiptV1")
            request = tuple(
                (item[0], item[1])
                for item in request_raw
                if isinstance(item, list) and len(item) == 2
            )
            if len(request) != len(request_raw):
                raise DataError("invalid CryptoRawReceiptV1")
            receipt = cls(
                receipt_id=value["receipt_id"],
                dataset=CryptoDatasetIdentityV1.from_dict(value["dataset"]),
                request=request,
                fetched_at=datetime.fromisoformat(fetched_raw.replace("Z", "+00:00")),
                response_sha256=value["response_sha256"],
                response_bytes=value["response_bytes"],
                provider_schema=value["provider_schema"],
                parser_version=value["parser_version"],
                pagination=tuple(pagination_raw),
                upstream_checksum=value["upstream_checksum"],
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise DataError("invalid CryptoRawReceiptV1") from exc
        rebuilt = cls.create(
            dataset=receipt.dataset,
            request=receipt.request,
            fetched_at=receipt.fetched_at,
            response_sha256=receipt.response_sha256,
            response_bytes=receipt.response_bytes,
            provider_schema=receipt.provider_schema,
            parser_version=receipt.parser_version,
            pagination=receipt.pagination,
            upstream_checksum=receipt.upstream_checksum,
        )
        if rebuilt.receipt_id != receipt.receipt_id:
            raise DataError("CryptoRawReceiptV1 identity does not match")
        return receipt


@dataclass(frozen=True)
class CryptoQualityReportV1:
    dataset_sha256: str
    method_version: str
    state: QualificationState
    failures: tuple[str, ...]
    warnings: tuple[str, ...]
    observed_start: datetime | None
    observed_end: datetime | None
    row_count: int
    correction_lineage: tuple[str, ...]
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        _sha(self.dataset_sha256, "quality dataset hash")
        _text(self.method_version, "quality method version")
        if self.state not in {"unverified", "qualified", "warning", "quarantined", "unavailable"}:
            raise DataError("invalid crypto qualification state")
        for values, label in (
            (self.failures, "failures"),
            (self.warnings, "warnings"),
            (self.correction_lineage, "correction lineage"),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise DataError(f"crypto quality {label} must contain non-empty strings")
        if self.state == "qualified" and self.failures:
            raise DataError("qualified crypto quality report cannot contain failures")
        if (
            not isinstance(self.row_count, int)
            or isinstance(self.row_count, bool)
            or self.row_count < 0
        ):
            raise DataError("crypto quality row_count must be non-negative")
        if self.observed_start is not None:
            object.__setattr__(self, "observed_start", _time(self.observed_start, "observed_start"))
        if self.observed_end is not None:
            object.__setattr__(self, "observed_end", _time(self.observed_end, "observed_end"))
        if (
            self.observed_start is not None
            and self.observed_end is not None
            and self.observed_end < self.observed_start
        ):
            raise DataError("crypto quality observed_end precedes observed_start")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "dataset_sha256": self.dataset_sha256,
            "method_version": self.method_version,
            "state": self.state,
            "failures": list(self.failures),
            "warnings": list(self.warnings),
            "observed_start": self.observed_start.isoformat() if self.observed_start else None,
            "observed_end": self.observed_end.isoformat() if self.observed_end else None,
            "row_count": self.row_count,
            "correction_lineage": list(self.correction_lineage),
        }

    @classmethod
    def from_dict(cls, value: object) -> CryptoQualityReportV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("invalid CryptoQualityReportV1")

        def optional_time(raw: object) -> datetime | None:
            if raw is None:
                return None
            if not isinstance(raw, str):
                raise DataError("invalid CryptoQualityReportV1 timestamp")
            try:
                return _time(datetime.fromisoformat(raw.replace("Z", "+00:00")), "quality time")
            except ValueError as exc:
                raise DataError("invalid CryptoQualityReportV1 timestamp") from exc

        try:
            failures = value["failures"]
            warnings = value["warnings"]
            lineage = value["correction_lineage"]
            if any(
                not isinstance(items, list) or any(not isinstance(item, str) for item in items)
                for items in (failures, warnings, lineage)
            ):
                raise DataError("invalid CryptoQualityReportV1 lists")
            return cls(
                dataset_sha256=value["dataset_sha256"],
                method_version=value["method_version"],
                state=value["state"],
                failures=tuple(failures),
                warnings=tuple(warnings),
                observed_start=optional_time(value["observed_start"]),
                observed_end=optional_time(value["observed_end"]),
                row_count=value["row_count"],
                correction_lineage=tuple(lineage),
            )
        except (KeyError, TypeError) as exc:
            raise DataError("invalid CryptoQualityReportV1") from exc


@dataclass(frozen=True)
class CryptoSnapshotMemberV1:
    dataset: CryptoDatasetIdentityV1
    artifact_key: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        key = _text(self.artifact_key, "artifact key")
        if key.startswith("/") or ".." in key.split("/"):
            raise DataError("crypto artifact key must be a safe logical path")
        _sha(self.artifact_sha256, "artifact hash")

    def to_dict(self) -> dict[str, object]:
        return {
            "dataset": self.dataset.to_dict(),
            "artifact_key": self.artifact_key,
            "artifact_sha256": self.artifact_sha256,
        }

    @classmethod
    def from_dict(cls, value: object) -> CryptoSnapshotMemberV1:
        if not isinstance(value, dict):
            raise DataError("invalid CryptoSnapshotMemberV1")
        try:
            return cls(
                dataset=CryptoDatasetIdentityV1.from_dict(value["dataset"]),
                artifact_key=value["artifact_key"],
                artifact_sha256=value["artifact_sha256"],
            )
        except (KeyError, TypeError) as exc:
            raise DataError("invalid CryptoSnapshotMemberV1") from exc


@dataclass(frozen=True)
class CryptoSnapshotV1:
    snapshot_id: str
    members: tuple[CryptoSnapshotMemberV1, ...]
    asset_master_version: str
    qualification_versions: tuple[str, ...]
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        _sha(self.snapshot_id, "snapshot id")
        if not isinstance(self.members, tuple) or not self.members:
            raise DataError("crypto snapshot requires ordered membership")
        _text(self.asset_master_version, "asset master version")
        if not isinstance(self.qualification_versions, tuple) or not self.qualification_versions:
            raise DataError("crypto snapshot requires qualification versions")
        expected = self._identity(
            self.members, self.asset_master_version, self.qualification_versions
        )
        if self.snapshot_id != expected:
            raise DataError("crypto snapshot identity does not match membership")

    @staticmethod
    def _identity(
        members: tuple[CryptoSnapshotMemberV1, ...],
        asset_master_version: str,
        qualification_versions: tuple[str, ...],
    ) -> str:
        return _digest(
            {
                "members": [item.to_dict() for item in members],
                "asset_master_version": asset_master_version,
                "qualification_versions": list(qualification_versions),
            }
        )

    @classmethod
    def create(
        cls,
        *,
        members: tuple[CryptoSnapshotMemberV1, ...],
        asset_master_version: str,
        qualification_versions: tuple[str, ...],
    ) -> CryptoSnapshotV1:
        return cls(
            snapshot_id=cls._identity(members, asset_master_version, qualification_versions),
            members=members,
            asset_master_version=asset_master_version,
            qualification_versions=qualification_versions,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "snapshot_id": self.snapshot_id,
            "members": [item.to_dict() for item in self.members],
            "asset_master_version": self.asset_master_version,
            "qualification_versions": list(self.qualification_versions),
        }

    @classmethod
    def from_dict(cls, value: object) -> CryptoSnapshotV1:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("invalid CryptoSnapshotV1")
        try:
            raw_members = value["members"]
            if not isinstance(raw_members, list):
                raise DataError("invalid CryptoSnapshotV1 members")
            return cls(
                snapshot_id=value["snapshot_id"],
                members=tuple(CryptoSnapshotMemberV1.from_dict(item) for item in raw_members),
                asset_master_version=value["asset_master_version"],
                qualification_versions=tuple(value["qualification_versions"]),
            )
        except (KeyError, TypeError) as exc:
            raise DataError("invalid CryptoSnapshotV1") from exc


@dataclass(frozen=True)
class ProviderDatasetCapabilityV1:
    provider: str
    family: CryptoFamily
    authentication: Literal["none", "demo_key"]
    earliest: datetime | None
    latest: datetime | None
    frequencies: tuple[str, ...]
    limits: tuple[str, ...]
    verification_state: str
    qualification_state: QualificationState
    schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        _text(self.provider, "capability provider")
        if self.family not in FAMILY_AUTHORITIES:
            raise DataError("invalid crypto capability family")
        if self.earliest is not None:
            _time(self.earliest, "capability earliest")
        if self.latest is not None:
            _time(self.latest, "capability latest")
        if self.earliest and self.latest and self.latest < self.earliest:
            raise DataError("crypto capability latest precedes earliest")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "provider": self.provider,
            "family": self.family,
            "authentication": self.authentication,
            "earliest": self.earliest.isoformat() if self.earliest else None,
            "latest": self.latest.isoformat() if self.latest else None,
            "frequencies": list(self.frequencies),
            "limits": list(self.limits),
            "verification_state": self.verification_state,
            "qualification_state": self.qualification_state,
        }
