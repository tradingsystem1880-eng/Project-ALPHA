"""Governed crypto-data catalog, storage, estimation, and identity commands."""

from __future__ import annotations

import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Annotated, Final, Literal, cast

import polars as pl
import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto.asset_master import AssetMaster
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoMarketType,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.ingestion import ingest_provider_payload
from alpha_data.crypto.providers.bybit import (
    PriceFamily,
    fetch_bybit_public,
    parse_funding_history,
    parse_historical_volatility,
    parse_instruments,
    parse_long_short_ratio,
    parse_open_interest,
    parse_option_tickers,
    parse_price_klines,
)
from alpha_data.crypto.research import (
    CryptoResearchPurpose,
    assess_crypto_snapshot,
)
from alpha_data.crypto.storage import CryptoBulkStore

crypto_data_app = typer.Typer(
    help="Provider-native crypto acquisition, qualification, snapshots, and storage."
)

_ROW_BYTES: Final[dict[CryptoFamily, int]] = {
    "market_bars": 160,
    "trades": 120,
    "aggregate_trades": 128,
    "book_snapshots": 1_600,
    "funding": 96,
    "open_interest": 112,
    "long_short_ratio": 128,
    "mark_bars": 128,
    "index_bars": 128,
    "premium_bars": 112,
    "option_instruments": 256,
    "option_quotes": 384,
    "historical_volatility": 112,
    "asset_metadata": 1_024,
    "market_reference": 384,
    "onchain_metrics": 128,
    "dex_pools": 512,
    "dex_ohlcv": 176,
    "dex_transactions": 192,
    "comparison_bars": 128,
}
_OBSERVATIONS_PER_DAY: Final = {"1d": 1, "1h": 24, "5m": 288, "1m": 1_440, "tick": 100_000}
_NATIVE_NETWORKS: Final = {"BTC": "bitcoin", "ETH": "ethereum"}
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_BYBIT_PRICE_FAMILIES: Final[dict[CryptoFamily, tuple[str, PriceFamily]]] = {
    "mark_bars": ("mark_kline", "mark"),
    "index_bars": ("index_kline", "index"),
    "premium_bars": ("premium_kline", "premium"),
}


@dataclass(frozen=True)
class _AcquisitionPlan:
    endpoint: str
    params: dict[str, str | int]
    dataset: CryptoDatasetIdentityV1
    parser: Callable[[bytes], pl.DataFrame]
    observed_column: str
    key_columns: tuple[str, ...]
    availability_column: str | None = None


def _open_interest_frame(payload: bytes) -> pl.DataFrame:
    return parse_open_interest(payload)[0]


def _long_short_frame(payload: bytes, *, category: Literal["linear", "inverse"]) -> pl.DataFrame:
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit ratio category must be linear or inverse")
    return parse_long_short_ratio(payload, category=category)[0]


def _instrument_frame(payload: bytes, *, fetched_at_ms: int) -> pl.DataFrame:
    return parse_instruments(payload, category="option", fetched_at_ms=fetched_at_ms)[0]


def _option_quote_frame(payload: bytes, *, fetched_at_ms: int) -> pl.DataFrame:
    return parse_option_tickers(payload, fetched_at_ms=fetched_at_ms)[0]


def _emit(value: object, *, json_out: bool) -> None:
    typer.echo(
        json.dumps(value, sort_keys=True, allow_nan=False)
        if json_out
        else json.dumps(value, sort_keys=True, indent=2, allow_nan=False)
    )


def _family(value: str) -> CryptoFamily:
    if value not in FAMILY_AUTHORITIES:
        raise typer.BadParameter(
            f"unknown crypto dataset family {value!r}; use `alpha crypto-data catalog`"
        )
    return value


def _now() -> datetime:
    return datetime.now(UTC)


def _bulk_store() -> CryptoBulkStore:
    settings = AlphaSettings()
    if not settings.bulk_volume_uuid:
        raise DataError("crypto bulk volume UUID is not configured")
    return CryptoBulkStore(
        bulk_root=settings.bulk_data_dir,
        manifest_root=settings.data_dir / "crypto" / "manifests",
        expected_volume_uuid=settings.bulk_volume_uuid,
    )


def _snapshot_root() -> Path:
    return AlphaSettings().data_dir / "crypto" / "snapshots"


def _write_snapshot(snapshot: CryptoSnapshotV1) -> None:
    root = _snapshot_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{snapshot.snapshot_id}.json"
    rendered = json.dumps(snapshot.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise DataError("crypto snapshot identity collision")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)


def _read_snapshot(snapshot_id: str) -> CryptoSnapshotV1:
    if _SHA256.fullmatch(snapshot_id) is None:
        raise DataError("crypto snapshot id is invalid")
    try:
        raw = json.loads((_snapshot_root() / f"{snapshot_id}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("crypto snapshot is unavailable or corrupt") from exc
    return CryptoSnapshotV1.from_dict(raw)


@crypto_data_app.command("catalog")
def catalog(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List the exact provider authority for every supported dataset family."""
    families = [
        {
            "family": family,
            "provider": provider,
            "role": "diagnostic_comparison"
            if family == "comparison_bars"
            else "primary_acquisition",
        }
        for family, provider in FAMILY_AUTHORITIES.items()
    ]
    _emit(
        {
            "families": families,
            "automatic_fallback": False,
            "execution_authority": False,
            "next_action": "Check storage before estimating or acquiring data.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("estimate")
def estimate(
    family: str,
    instruments: int = typer.Option(1, min=1, max=250),
    days: int = typer.Option(30, min=1, max=3_650),
    frequency: str = typer.Option("1d", help="1d, 1h, 5m, 1m, or tick"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Estimate a bounded acquisition before any network or storage write."""
    dataset_family = _family(family)
    observations = _OBSERVATIONS_PER_DAY.get(frequency)
    if observations is None:
        raise typer.BadParameter("--frequency must be one of 1d, 1h, 5m, 1m, or tick")
    if frequency == "tick" and (
        dataset_family not in {"trades", "aggregate_trades", "book_snapshots"}
        or instruments > 50
        or days > 31
    ):
        raise typer.BadParameter(
            "tick data is permitted only for at most 50 instruments and "
            "31-day bounded research windows"
        )
    if frequency == "1m" and instruments > 50:
        raise typer.BadParameter(
            "one-minute acquisition is capped at 50 research-selected instruments"
        )
    estimated_rows = instruments * days * observations
    estimated_bytes = math.ceil(estimated_rows * _ROW_BYTES[dataset_family] * 1.25)
    _emit(
        {
            "family": dataset_family,
            "provider": FAMILY_AUTHORITIES[dataset_family],
            "instruments": instruments,
            "days": days,
            "frequency": frequency,
            "estimated_rows": estimated_rows,
            "estimated_bytes": estimated_bytes,
            "bounded": True,
            "estimate_only": True,
            "next_action": "Verify storage, then start one bounded acquisition.",
        },
        json_out=json_out,
    )


def _storage_blocker(message: str) -> str:
    if "not mounted" in message:
        return "bulk_volume_not_mounted"
    if "UUID" in message:
        return "bulk_volume_uuid_mismatch"
    if "reserve" in message:
        return "bulk_storage_reserve_blocked"
    if "writable" in message:
        return "bulk_volume_not_writable"
    return "bulk_storage_verification_failed"


@crypto_data_app.command("storage")
def storage(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Verify the configured external volume and immutable inventory without probing providers."""
    settings = AlphaSettings()
    label = settings.bulk_data_dir.name or "bulk"
    if not settings.bulk_volume_uuid:
        _emit(
            {
                "state": "blocked",
                "blocker": "bulk_volume_uuid_not_configured",
                "bulk_root_label": label,
                "manifest_count": 0,
                "next_action": "Configure the reviewed Expansion volume UUID.",
            },
            json_out=json_out,
        )
        return
    store = CryptoBulkStore(
        bulk_root=settings.bulk_data_dir,
        manifest_root=settings.data_dir / "crypto" / "manifests",
        expected_volume_uuid=settings.bulk_volume_uuid,
    )
    try:
        capacity = store.verify_ready(required_bytes=0)
        inventory = store.inventory()
    except DataError as exc:
        _emit(
            {
                "state": "blocked",
                "blocker": _storage_blocker(str(exc)),
                "bulk_root_label": label,
                "manifest_count": 0,
                "next_action": "Reconnect the reviewed Expansion volume and run this check again.",
            },
            json_out=json_out,
        )
        return
    _emit(
        {
            "state": "ready",
            "blocker": None,
            "bulk_root_label": label,
            "free_bytes": capacity.free_bytes,
            "total_bytes": capacity.total_bytes,
            "reserve_fraction": store.reserve_fraction,
            "minimum_free_bytes": store.minimum_free_bytes,
            "manifest_count": len(inventory),
            "next_action": "Estimate one bounded dataset acquisition.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("asset")
def asset(
    symbol: str,
    as_of: str = typer.Option(..., help="point-in-time ISO-8601 timestamp"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Inspect one reviewed native-asset identity and provider-symbol lineage."""
    symbol_key = symbol.strip().upper()
    network = _NATIVE_NETWORKS.get(symbol_key)
    if network is None:
        raise typer.BadParameter(
            "asset has no reviewed native mapping; contract assets require "
            "network plus contract address"
        )
    try:
        instant = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        identity = AssetMaster.with_reviewed_native_assets().resolve_native(
            network=network, as_of=instant
        )
    except (ValueError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(identity.to_dict(), json_out=json_out)


def _bybit_plan(
    family: CryptoFamily,
    instrument: str,
    *,
    base: str,
    quote: str,
    category: str,
    frequency: str,
    fetched_at: datetime,
) -> _AcquisitionPlan:
    if FAMILY_AUTHORITIES[family] != "bybit":
        raise DataError(f"{family} is not a Bybit-authoritative dataset family")
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit derivative category must be linear or inverse")
    category_value = cast(Literal["linear", "inverse"], category)
    market_type = cast(CryptoMarketType, category)
    base_value, quote_value = base.strip().upper(), quote.strip().upper()
    symbol = instrument.strip().upper()
    if (
        not base_value.isalnum()
        or not quote_value.isalnum()
        or not symbol.replace("-", "").isalnum()
    ):
        raise DataError("Bybit instrument, base, or quote identity is invalid")
    endpoint: str
    params: dict[str, str | int]
    parser: Callable[[bytes], pl.DataFrame]
    observed_column = "timestamp"
    key_columns: tuple[str, ...] = ("timestamp", "symbol")
    availability_column: str | None = None
    units = "provider_native"
    dataset_frequency = frequency

    if family == "funding":
        endpoint = "funding"
        params = {"category": category, "symbol": symbol, "limit": 200}
        parser = parse_funding_history
        units = "dimensionless_rate"
        dataset_frequency = "funding_interval"
    elif family == "open_interest":
        endpoint = "open_interest"
        params = {
            "category": category,
            "symbol": symbol,
            "intervalTime": frequency,
            "limit": 200,
        }
        parser = _open_interest_frame
        units = "base_coin_if_linear_quote_coin_if_inverse"
    elif family == "long_short_ratio":
        endpoint = "long_short_ratio"
        params = {
            "category": category,
            "symbol": symbol,
            "period": frequency,
            "limit": 200,
        }
        parser = partial(_long_short_frame, category=category_value)
        units = "dimensionless_ratio"
    elif family in _BYBIT_PRICE_FAMILIES:
        endpoint, price_family = _BYBIT_PRICE_FAMILIES[family]
        interval = {"1h": "60", "1d": "D", "5m": "5", "1m": "1"}.get(frequency)
        if interval is None:
            raise DataError("Bybit price-bar frequency must be 1m, 5m, 1h, or 1d")
        params = {"category": category, "symbol": symbol, "interval": interval, "limit": 1_000}
        parser = partial(parse_price_klines, family=price_family)
        units = "quote_price"
    elif family == "option_instruments":
        endpoint = "instruments"
        params = {"category": "option", "baseCoin": base_value, "limit": 1_000}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(_instrument_frame, fetched_at_ms=fetched_at_ms)
        observed_column = "fetched_at"
        key_columns = ("symbol",)
        market_type = "option"
        dataset_frequency = "catalog_snapshot"
    elif family == "option_quotes":
        endpoint = "option_tickers"
        params = {"category": "option", "baseCoin": base_value}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(_option_quote_frame, fetched_at_ms=fetched_at_ms)
        observed_column = "available_at"
        availability_column = "available_at"
        key_columns = ("available_at", "symbol")
        market_type = "option"
        dataset_frequency = "point_in_time_chain"
    elif family == "historical_volatility":
        endpoint = "historical_volatility"
        params = {"category": "option", "baseCoin": base_value, "quoteCoin": quote_value}
        parser = partial(
            parse_historical_volatility,
            base_coin=base_value,
            quote_coin=cast(Literal["USD", "USDT"], quote_value),
        )
        key_columns = ("timestamp", "period_days")
        market_type = "option"
    else:
        raise DataError(f"Bybit acquisition is not implemented for {family}")

    return _AcquisitionPlan(
        endpoint=endpoint,
        params=params,
        dataset=CryptoDatasetIdentityV1(
            provider="bybit",
            venue="bybit",
            market_type=market_type,
            family=family,
            instrument=symbol,
            base_asset=base_value,
            quote_asset=quote_value,
            frequency=dataset_frequency,
            units=units,
            timestamp_convention="provider_event_utc",
        ),
        parser=parser,
        observed_column=observed_column,
        key_columns=key_columns,
        availability_column=availability_column,
    )


@crypto_data_app.command("acquire")
def acquire(
    provider: str,
    family: str,
    instrument: str,
    base: str = typer.Option(..., help="exact base asset"),
    quote: str = typer.Option(..., help="exact quote asset; USD, USDT, and USDC stay distinct"),
    category: str = typer.Option("linear", help="Bybit linear or inverse market"),
    frequency: str = typer.Option("1h", help="provider-native bounded frequency"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Acquire one bounded public provider page; this grants no research or order authority."""
    if provider != "bybit":
        raise typer.BadParameter("this acquisition slice currently accepts provider 'bybit'")
    dataset_family = _family(family)
    fetched_at = _now()
    try:
        plan = _bybit_plan(
            dataset_family,
            instrument,
            base=base,
            quote=quote,
            category=category,
            frequency=frequency,
            fetched_at=fetched_at,
        )
        payload = fetch_bybit_public(plan.endpoint, plan.params)
        result = ingest_provider_payload(
            _bulk_store(),
            dataset=plan.dataset,
            payload=payload,
            request=tuple((key, str(value)) for key, value in sorted(plan.params.items())),
            fetched_at=fetched_at,
            provider_schema="bybit-v5",
            parser_version="bybit-public-v1",
            logical_name=f"{dataset_family}.json",
            parser=plan.parser,
            observed_column=plan.observed_column,
            key_columns=plan.key_columns,
            availability_column=plan.availability_column,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    next_action = (
        "Create or extend a frozen crypto snapshot."
        if result.quality.state == "qualified"
        else "Review the quality blockers before using this dataset."
    )
    _emit(
        {
            "provider": provider,
            "family": dataset_family,
            "instrument": plan.dataset.instrument,
            "state": result.quality.state,
            "failures": list(result.quality.failures),
            "warnings": list(result.quality.warnings),
            "raw_manifest_id": result.raw_manifest["manifest_id"],
            "normalized_manifest_id": result.normalized_manifest["manifest_id"],
            "artifact_sha256": result.normalized_manifest["artifact_sha256"],
            "next_action": next_action,
            "execution_authority": False,
        },
        json_out=json_out,
    )


def _normalized_member(
    store: CryptoBulkStore, manifest_id: str
) -> tuple[CryptoSnapshotMemberV1, CryptoQualityReportV1]:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto snapshot members must be normalized artifacts")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    artifact_key, artifact_hash = manifest.get("artifact_key"), manifest.get("artifact_sha256")
    if not isinstance(artifact_key, str) or not isinstance(artifact_hash, str):
        raise DataError("crypto normalized manifest membership is invalid")
    if quality.dataset_sha256 != artifact_hash or quality.state != "qualified":
        raise DataError("crypto snapshot creation requires exact qualified artifacts")
    if dataset.provider != FAMILY_AUTHORITIES[dataset.family]:
        raise DataError("crypto normalized manifest has the wrong family authority")
    return (
        CryptoSnapshotMemberV1(
            dataset=dataset,
            artifact_key=artifact_key,
            artifact_sha256=artifact_hash,
        ),
        quality,
    )


@crypto_data_app.command("snapshot-create")
def snapshot_create(
    manifest_ids: Annotated[
        list[str], typer.Option("--manifest-id", help="normalized manifest id")
    ],
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze exact ordered qualified membership; source and quote identities remain distinct."""
    if not manifest_ids or len(set(manifest_ids)) != len(manifest_ids):
        raise typer.BadParameter("--manifest-id must contain unique normalized manifests")
    try:
        store = _bulk_store()
        resolved = tuple(_normalized_member(store, manifest_id) for manifest_id in manifest_ids)
        snapshot = CryptoSnapshotV1.create(
            members=tuple(member for member, _ in resolved),
            asset_master_version="reviewed-native-v1",
            qualification_versions=tuple(
                sorted({quality.method_version for _, quality in resolved})
            ),
        )
        _write_snapshot(snapshot)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "snapshot_id": snapshot.snapshot_id,
            "member_count": len(snapshot.members),
            "families": sorted({member.dataset.family for member in snapshot.members}),
            "providers": sorted({member.dataset.provider for member in snapshot.members}),
            "state": "frozen",
            "next_action": "Verify the snapshot for the exact research purpose.",
            "execution_authority": False,
        },
        json_out=json_out,
    )


@crypto_data_app.command("snapshot-verify")
def snapshot_verify(
    snapshot_id: str,
    required_families: Annotated[
        list[str] | None,
        typer.Option("--required-family", help="family required by the research contract"),
    ] = None,
    purpose: str = typer.Option("research", help="research, validation, or execution_price"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Reverify every external byte and current qualification before research binding."""
    if purpose not in {"research", "validation", "execution_price"}:
        raise typer.BadParameter("--purpose must be research, validation, or execution_price")
    try:
        required = tuple(_family(family) for family in (required_families or []))
        snapshot = _read_snapshot(snapshot_id)
        store = _bulk_store()
        inventory = store.inventory()
        by_membership = {
            (manifest.get("artifact_key"), manifest.get("artifact_sha256")): manifest
            for manifest in inventory
            if manifest.get("artifact_kind") == "normalized"
        }
        reports: dict[str, CryptoQualityReportV1] = {}
        for member in snapshot.members:
            manifest = by_membership.get((member.artifact_key, member.artifact_sha256))
            if manifest is None or manifest.get("dataset") != member.dataset.to_dict():
                raise DataError("crypto snapshot member manifest is missing or mismatched")
            reports[member.artifact_sha256] = CryptoQualityReportV1.from_dict(
                manifest.get("quality")
            )
        projection = assess_crypto_snapshot(
            snapshot,
            quality_reports=reports,
            required_families=required,
            purpose=cast(CryptoResearchPurpose, purpose),
        )
    except (DataError, typer.BadParameter) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "snapshot_id": snapshot.snapshot_id,
            "eligible": projection.eligible,
            "purpose": projection.purpose,
            "qualified_families": list(projection.qualified_families),
            "supplemental_families": list(projection.supplemental_families),
            "blockers": list(projection.blockers),
            "next_action": (
                "Bind this snapshot to the exact research proposal."
                if projection.eligible
                else "Resolve every blocker and create a new snapshot; never edit this one."
            ),
            "execution_authority": False,
        },
        json_out=json_out,
    )


__all__ = ["crypto_data_app"]
