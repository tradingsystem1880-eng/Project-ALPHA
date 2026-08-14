"""Governed crypto-data catalog, storage, estimation, and identity commands."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    CryptoRawReceiptV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.ingestion import ingest_provider_pages, ingest_provider_payload
from alpha_data.crypto.providers.binance import (
    archive_url,
    fetch_binance_archive,
    fetch_binance_checksum,
    parse_binance_archive_zip,
    verify_archive_checksum,
)
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
from alpha_data.crypto.providers.coingecko import (
    coingecko_demo_request,
    fetch_coingecko_demo,
    parse_asset_catalog,
    parse_market_universe,
)
from alpha_data.crypto.providers.coinmetrics import (
    REVIEWED_COMMUNITY_METRICS,
    coinmetrics_community_url,
    fetch_coinmetrics_community,
    parse_asset_metrics,
)
from alpha_data.crypto.providers.geckoterminal import (
    fetch_geckoterminal_public,
    geckoterminal_public_url,
    parse_pool_ohlcv,
    parse_pool_trades,
    parse_top_pools,
)
from alpha_data.crypto.research import (
    CryptoResearchEligibilityV1,
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
    next_cursor: Callable[[bytes], str | None] | None = None
    page_limit: int | None = None


@dataclass(frozen=True)
class _FetchedAcquisition:
    plan: _AcquisitionPlan
    payload: bytes
    provider_schema: str
    parser_version: str
    logical_name: str
    upstream_checksum: str | None = None
    expected_cadence_seconds: int | None = None
    period_start_timestamps: bool = False


def _open_interest_frame(payload: bytes) -> pl.DataFrame:
    return parse_open_interest(payload)[0]


def _open_interest_cursor(payload: bytes) -> str | None:
    return parse_open_interest(payload)[1]


def _long_short_frame(payload: bytes, *, category: Literal["linear", "inverse"]) -> pl.DataFrame:
    if category not in {"linear", "inverse"}:
        raise DataError("Bybit ratio category must be linear or inverse")
    return parse_long_short_ratio(payload, category=category)[0]


def _long_short_cursor(
    payload: bytes, *, category: Literal["linear", "inverse"]
) -> str | None:
    return parse_long_short_ratio(payload, category=category)[1]


def _iso_milliseconds(value: str, *, label: str) -> int:
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError(f"Bybit {label} must be an ISO-8601 timestamp") from exc
    if instant.tzinfo is None:
        raise DataError(f"Bybit {label} must include a timezone")
    return int(instant.astimezone(UTC).timestamp() * 1_000)


def _bybit_range(
    start: str | None, end: str | None, *, fetched_at: datetime
) -> tuple[int, int] | None:
    if (start is None) != (end is None):
        raise DataError("Bybit --start and --end must be supplied together")
    if start is None or end is None:
        return None
    start_ms = _iso_milliseconds(start, label="start")
    end_ms = _iso_milliseconds(end, label="end")
    if end_ms <= start_ms:
        raise DataError("Bybit end must be later than start")
    if end_ms > int(fetched_at.timestamp() * 1_000):
        raise DataError("Bybit end exceeds the acquisition knowledge time")
    return start_ms, end_ms


def _instrument_frame(payload: bytes, *, fetched_at_ms: int, base: str, quote: str) -> pl.DataFrame:
    frame = parse_instruments(payload, category="option", fetched_at_ms=fetched_at_ms)[0]
    selected = frame.filter((pl.col("base_coin") == base) & (pl.col("quote_coin") == quote))
    if selected.is_empty():
        raise DataError("Bybit option page has no contracts for the requested base and quote")
    return selected


def _instrument_cursor(payload: bytes, *, fetched_at_ms: int) -> str | None:
    return parse_instruments(payload, category="option", fetched_at_ms=fetched_at_ms)[1]


def _option_symbol_assets(symbol: str) -> tuple[str, str]:
    parts = symbol.split("-")
    if len(parts) == 4 and parts[0] and parts[3] in {"C", "P"}:
        return parts[0], "USD"
    if len(parts) == 5 and parts[0] and parts[3] in {"C", "P"} and parts[4]:
        return parts[0], parts[4]
    raise DataError("Bybit option symbol cannot establish exact base and quote identity")


def _option_quote_frame(
    payload: bytes, *, fetched_at_ms: int, base: str, quote: str
) -> pl.DataFrame:
    frame = parse_option_tickers(payload, fetched_at_ms=fetched_at_ms)[0]
    identities = [_option_symbol_assets(symbol) for symbol in frame["symbol"].to_list()]
    selected = frame.filter(
        pl.Series([identity == (base, quote) for identity in identities], dtype=pl.Boolean)
    )
    if selected.is_empty():
        raise DataError("Bybit option page has no contracts for the requested base and quote")
    return selected


def _asset_catalog_frame(payload: bytes, *, fetched_at: datetime) -> pl.DataFrame:
    return parse_asset_catalog(payload).with_columns(pl.lit(fetched_at).alias("fetched_at"))


def _top_pools_frame(payload: bytes, *, network: str, fetched_at: datetime) -> pl.DataFrame:
    return parse_top_pools(payload, network=network).with_columns(
        pl.lit(fetched_at).alias("fetched_at")
    )


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


def _verified_snapshot(
    snapshot_id: str,
    *,
    required_families: tuple[CryptoFamily, ...],
    purpose: CryptoResearchPurpose,
) -> tuple[CryptoSnapshotV1, dict[str, CryptoQualityReportV1], CryptoResearchEligibilityV1]:
    snapshot = _read_snapshot(snapshot_id)
    store = _bulk_store()
    by_membership = {
        (manifest.get("artifact_key"), manifest.get("artifact_sha256")): manifest
        for manifest in store.inventory()
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
        required_families=required_families,
        purpose=purpose,
    )
    return snapshot, reports, projection


def crypto_snapshot_registration(snapshot_id: str, *, symbol: str) -> dict[str, object]:
    """Reverify and project one immutable crypto snapshot for research-only registration."""
    clean_symbol = symbol.strip().upper()
    if not clean_symbol or not clean_symbol.replace("-", "").isalnum():
        raise DataError("crypto snapshot registration symbol is invalid")
    snapshot, reports, projection = _verified_snapshot(
        snapshot_id, required_families=(), purpose="research"
    )
    if not projection.eligible:
        raise DataError(
            f"crypto snapshot is not research eligible: {', '.join(projection.blockers)}"
        )
    if not any(
        member.dataset.base_asset == clean_symbol or member.dataset.instrument == clean_symbol
        for member in snapshot.members
    ):
        raise DataError("crypto snapshot does not contain the requested asset identity")
    starts = [report.observed_start for report in reports.values()]
    ends = [report.observed_end for report in reports.values()]
    if any(value is None for value in starts) or any(value is None for value in ends):
        raise DataError("crypto snapshot has no complete observed range for registration")
    frequencies = {member.dataset.frequency for member in snapshot.members}
    bar_minutes = None
    if len(frequencies) == 1:
        bar_minutes = {"1m": 1, "5m": 5, "1h": 60, "1d": 1_440}.get(
            next(iter(frequencies))
        )
    snapshot_path = _snapshot_root() / f"{snapshot.snapshot_id}.json"
    return {
        "dataset_kind": "snapshot",
        "instrument": clean_symbol,
        "provider": "crypto-data-house",
        "start_ts": min(cast(datetime, value) for value in starts).isoformat(),
        "end_ts": max(cast(datetime, value) for value in ends).isoformat(),
        "bar_duration_minutes": bar_minutes,
        "origin": {
            "snapshot_id": snapshot.snapshot_id,
            "manifest_sha256": hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),
            "snapshot_schema": "CryptoSnapshotV1",
        },
    }


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
                "cache_bytes": 0,
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
                "cache_bytes": 0,
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
            "cache_bytes": store.cache_size(),
            "next_action": "Estimate one bounded dataset acquisition.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("storage-inventory")
def storage_inventory(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Inventory immutable artifacts and removable cache without exposing private paths."""
    try:
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
        inventory = store.inventory()
        counts: dict[str, int] = {}
        artifact_bytes: dict[str, int] = {}
        for manifest in inventory:
            kind = str(manifest.get("artifact_kind", "unknown"))
            counts[kind] = counts.get(kind, 0) + 1
            size = manifest.get("artifact_bytes")
            if isinstance(size, int) and not isinstance(size, bool):
                artifact_bytes[kind] = artifact_bytes.get(kind, 0) + size
        snapshots = (
            tuple(sorted(_snapshot_root().glob("*.json")))
            if _snapshot_root().exists()
            else ()
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "manifest_count": len(inventory),
            "snapshot_count": len(snapshots),
            "counts_by_kind": counts,
            "bytes_by_kind": artifact_bytes,
            "cache_bytes": store.cache_size(),
            "staging_count": len(tuple(store.staging_root.glob("*/staging.json"))),
            "private_paths_exposed": False,
            "next_action": "Run storage-verify before relying on frozen snapshots.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("storage-verify")
def storage_verify(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Re-hash every manifest artifact and rederive every frozen snapshot membership."""
    try:
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
        inventory = store.inventory()
        snapshot_count = 0
        eligible_count = 0
        if _snapshot_root().exists():
            for path in sorted(_snapshot_root().glob("*.json")):
                snapshot, _, projection = _verified_snapshot(
                    path.stem, required_families=(), purpose="research"
                )
                snapshot_count += 1
                eligible_count += int(projection.eligible and snapshot.snapshot_id == path.stem)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "state": "verified",
            "manifest_count": len(inventory),
            "snapshot_count": snapshot_count,
            "research_eligible_snapshot_count": eligible_count,
            "cache_bytes": store.cache_size(),
            "private_paths_exposed": False,
            "next_action": "Continue with one bounded acquisition or exact snapshot selection.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("cache-clean")
def cache_clean(
    confirm: bool = typer.Option(False, "--confirm", help="confirm disposable cache deletion"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Delete only the explicitly disposable external cache; immutable data is untouched."""
    if not confirm:
        raise typer.BadParameter("--confirm is required to delete the removable cache")
    try:
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
        removed = store.clean_cache()
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "state": "cleaned",
            "removed_bytes": removed,
            "immutable_artifacts_removed": 0,
            "private_paths_exposed": False,
            "next_action": "Run storage-inventory to confirm current capacity.",
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
    start: str | None,
    end: str | None,
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
    next_cursor: Callable[[bytes], str | None] | None = None
    page_limit: int | None = None
    bounded_range = _bybit_range(start, end, fetched_at=fetched_at)

    if family == "funding":
        endpoint = "funding"
        params = {"category": category, "symbol": symbol, "limit": 200}
        parser = parse_funding_history
        units = "dimensionless_rate"
        dataset_frequency = "funding_interval"
        page_limit = 200
    elif family == "open_interest":
        endpoint = "open_interest"
        params = {
            "category": category,
            "symbol": symbol,
            "intervalTime": frequency,
            "limit": 200,
        }
        parser = _open_interest_frame
        next_cursor = _open_interest_cursor
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
        next_cursor = partial(_long_short_cursor, category=category_value)
        units = "dimensionless_ratio"
    elif family in _BYBIT_PRICE_FAMILIES:
        endpoint, price_family = _BYBIT_PRICE_FAMILIES[family]
        interval = {"1h": "60", "1d": "D", "5m": "5", "1m": "1"}.get(frequency)
        if interval is None:
            raise DataError("Bybit price-bar frequency must be 1m, 5m, 1h, or 1d")
        params = {"category": category, "symbol": symbol, "interval": interval, "limit": 1_000}
        parser = partial(parse_price_klines, family=price_family)
        units = "quote_price"
        page_limit = 1_000
    elif family == "option_instruments":
        endpoint = "instruments"
        params = {"category": "option", "baseCoin": base_value, "limit": 1_000}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(
            _instrument_frame,
            fetched_at_ms=fetched_at_ms,
            base=base_value,
            quote=quote_value,
        )
        observed_column = "fetched_at"
        key_columns = ("symbol",)
        market_type = "option"
        dataset_frequency = "catalog_snapshot"
        next_cursor = partial(_instrument_cursor, fetched_at_ms=fetched_at_ms)
    elif family == "option_quotes":
        endpoint = "option_tickers"
        params = {"category": "option", "baseCoin": base_value}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(
            _option_quote_frame,
            fetched_at_ms=fetched_at_ms,
            base=base_value,
            quote=quote_value,
        )
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

    if bounded_range is not None:
        if family in {"option_instruments", "option_quotes"}:
            raise DataError(f"Bybit {family} is a point-in-time snapshot and rejects a time range")
        start_ms, end_ms = bounded_range
        if family in _BYBIT_PRICE_FAMILIES:
            params.update({"start": start_ms, "end": end_ms})
        else:
            params.update({"startTime": start_ms, "endTime": end_ms})
        if family == "historical_volatility" and end_ms - start_ms > 30 * 86_400_000:
            raise DataError("Bybit historical volatility windows cannot exceed 30 days")

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
        next_cursor=next_cursor,
        page_limit=page_limit,
    )


def _fetch_bybit_pages(
    plan: _AcquisitionPlan, *, follow_cursors: bool
) -> tuple[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]], ...]:
    pages: list[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]]] = []
    params = dict(plan.params)
    seen_cursors: set[str] = set()
    for page_number in range(1, 101):
        payload = fetch_bybit_public(plan.endpoint, params)
        next_cursor = plan.next_cursor(payload) if plan.next_cursor is not None else None
        request = tuple((key, str(value)) for key, value in sorted(params.items()))
        pagination = (f"page={page_number}", f"next_cursor={next_cursor or 'terminal'}")
        pages.append((payload, request, pagination))
        if next_cursor is None or not follow_cursors:
            if (
                plan.page_limit is not None
                and {"startTime", "start"} & params.keys()
                and plan.parser(payload).height >= plan.page_limit
            ):
                raise DataError(
                    "Bybit bounded window fills one provider page; narrow the range to avoid "
                    "silently truncated evidence"
                )
            return tuple(pages)
        if next_cursor in seen_cursors:
            raise DataError("Bybit pagination cursor repeated")
        seen_cursors.add(next_cursor)
        params["cursor"] = next_cursor
    raise DataError("Bybit acquisition exceeded the 100-page safety limit")


def _fetch_non_bybit(
    provider: str,
    family: CryptoFamily,
    instrument: str,
    *,
    base: str,
    quote: str,
    category: str,
    frequency: str,
    period: str | None,
    network: str | None,
    pool_address: str | None,
    metrics: str | None,
    start: str | None,
    end: str | None,
    fetched_at: datetime,
) -> _FetchedAcquisition:
    base_value, quote_value = base.strip().upper(), quote.strip().upper()
    instrument_value = instrument.strip()
    if not base_value.isalnum() or not quote_value.isalnum() or not instrument_value:
        raise DataError("crypto acquisition identity is invalid")
    keys: tuple[str, ...]

    if provider == "binance":
        if family != "market_bars":
            raise DataError("this Binance acquisition accepts market_bars archives")
        if category not in {"spot", "linear", "inverse"}:
            raise DataError("Binance category must be spot, linear, or inverse")
        if period is None:
            raise DataError("Binance archive acquisition requires --period YYYY-MM")
        market = {"spot": "spot", "linear": "um", "inverse": "cm"}[category]
        url = archive_url(
            cast(Literal["spot", "um", "cm"], market),
            "klines",
            instrument_value.upper(),
            frequency,
            period,
        )
        payload = fetch_binance_archive(url)
        checksum = fetch_binance_checksum(f"{url}.CHECKSUM")
        verify_archive_checksum(payload, checksum)
        cadence_seconds = {"1d": 86_400, "1h": 3_600, "5m": 300, "1m": 60}.get(frequency)
        if cadence_seconds is None:
            raise DataError("Binance kline frequency must be 1m, 5m, 1h, or 1d")
        plan = _AcquisitionPlan(
            endpoint="monthly_archive",
            params={
                "market": market,
                "family": "klines",
                "symbol": instrument_value.upper(),
                "interval": frequency,
                "period": period,
            },
            dataset=CryptoDatasetIdentityV1(
                provider="binance",
                venue="binance",
                market_type=cast(CryptoMarketType, category),
                family="market_bars",
                instrument=instrument_value.upper(),
                base_asset=base_value,
                quote_asset=quote_value,
                frequency=frequency,
                units="provider_native_ohlcv",
                timestamp_convention="interval_start_utc",
            ),
            parser=parse_binance_archive_zip,
            observed_column="open_time",
            key_columns=("open_time",),
        )
        return _FetchedAcquisition(
            plan=plan,
            payload=payload,
            provider_schema="binance-public-archive-v1",
            parser_version="binance-archive-v1",
            logical_name=f"{family}.zip",
            upstream_checksum=hashlib.sha256(payload).hexdigest(),
            expected_cadence_seconds=cadence_seconds,
            period_start_timestamps=True,
        )

    if provider == "coingecko":
        api_key = os.environ.get("ALPHA_COINGECKO_API_KEY", "")
        if not api_key:
            raise DataError("CoinGecko Demo key requires scoped process injection")
        if family == "market_reference":
            params: dict[str, str | int | bool] = {
                "vs_currency": quote_value.lower(),
                "ids": instrument_value,
                "order": "market_cap_desc",
                "per_page": 1,
                "page": 1,
                "sparkline": False,
            }
            request = coingecko_demo_request("markets", params, api_key=api_key)
            payload = fetch_coingecko_demo(request)
            parser = partial(
                parse_market_universe,
                vs_currency=quote_value,
                fetched_at=fetched_at,
            )
            observed_column = "observed_at"
            keys = ("coingecko_id", "quote_asset")
            endpoint = "markets"
            frequency_value = "point_in_time_reference"
        elif family == "asset_metadata":
            params = {"include_platform": True}
            request = coingecko_demo_request("asset_catalog", params, api_key=api_key)
            payload = fetch_coingecko_demo(request)
            parser = partial(_asset_catalog_frame, fetched_at=fetched_at)
            observed_column = "fetched_at"
            keys = ("coingecko_id", "network", "contract_address")
            endpoint = "asset_catalog"
            frequency_value = "catalog_snapshot"
        else:
            raise DataError(f"CoinGecko is not authoritative for {family}")
        plan = _AcquisitionPlan(
            endpoint=endpoint,
            params={
                key: int(value) if isinstance(value, bool) else value
                for key, value in params.items()
            },
            dataset=CryptoDatasetIdentityV1(
                provider="coingecko",
                venue="coingecko",
                market_type="reference",
                family=family,
                instrument=instrument_value,
                base_asset=base_value,
                quote_asset=quote_value if family == "market_reference" else None,
                frequency=frequency_value,
                units="reference_only",
                timestamp_convention="provider_observation_utc",
            ),
            parser=parser,
            observed_column=observed_column,
            key_columns=keys,
            availability_column="fetched_at",
        )
        return _FetchedAcquisition(
            plan=plan,
            payload=payload,
            provider_schema="coingecko-demo-v3",
            parser_version="coingecko-reference-v1",
            logical_name=f"{family}.json",
        )

    if provider == "geckoterminal":
        if network is None:
            raise DataError("GeckoTerminal acquisition requires --network")
        if family == "dex_pools":
            params_gt: dict[str, str | int | bool] = {"page": 1}
            url = geckoterminal_public_url("top_pools", network=network, params=params_gt)
            payload = fetch_geckoterminal_public(url)
            parser = partial(_top_pools_frame, network=network, fetched_at=fetched_at)
            observed_column = "fetched_at"
            keys = ("network", "pool_address")
            endpoint = "top_pools"
            frequency_value = "daily_catalog"
        elif family in {"dex_ohlcv", "dex_transactions"}:
            if pool_address is None:
                raise DataError("pool data acquisition requires --pool-address")
            if family == "dex_ohlcv":
                timeframe = {"1d": "day", "1h": "hour", "1m": "minute"}.get(frequency)
                if timeframe is None:
                    raise DataError("GeckoTerminal OHLCV frequency must be 1m, 1h, or 1d")
                params_gt = {"aggregate": 1, "limit": 1_000, "currency": "usd"}
                url = geckoterminal_public_url(
                    "ohlcv",
                    network=network,
                    pool_address=pool_address,
                    timeframe=timeframe,
                    params=params_gt,
                )
                parser = partial(parse_pool_ohlcv, network=network, pool_address=pool_address)
                keys = ("network", "pool_address", "timestamp")
                endpoint = "ohlcv"
            else:
                params_gt = {}
                url = geckoterminal_public_url(
                    "trades", network=network, pool_address=pool_address, params=params_gt
                )
                parser = partial(parse_pool_trades, network=network, pool_address=pool_address)
                keys = ("network", "pool_address", "tx_hash")
                endpoint = "trades"
            payload = fetch_geckoterminal_public(url)
            observed_column = "timestamp"
            frequency_value = frequency
        else:
            raise DataError(f"GeckoTerminal is not authoritative for {family}")
        plan = _AcquisitionPlan(
            endpoint=endpoint,
            params={
                key: int(value) if isinstance(value, bool) else value
                for key, value in params_gt.items()
            },
            dataset=CryptoDatasetIdentityV1(
                provider="geckoterminal",
                venue=network,
                market_type="dex",
                family=family,
                instrument=pool_address or network,
                base_asset=base_value if pool_address else None,
                quote_asset=quote_value if pool_address else None,
                frequency=frequency_value,
                units="provider_native_dex",
                timestamp_convention="provider_observation_utc",
            ),
            parser=parser,
            observed_column=observed_column,
            key_columns=keys,
        )
        return _FetchedAcquisition(
            plan=plan,
            payload=payload,
            provider_schema="geckoterminal-v2",
            parser_version="geckoterminal-public-v1",
            logical_name=f"{family}.json",
        )

    if provider == "coinmetrics":
        if family != "onchain_metrics":
            raise DataError(f"Coin Metrics Community is not authoritative for {family}")
        selected_metrics = tuple(
            item.strip() for item in (metrics or "").split(",") if item.strip()
        )
        if not selected_metrics or any(
            item not in REVIEWED_COMMUNITY_METRICS for item in selected_metrics
        ):
            raise DataError("Coin Metrics requires reviewed --metrics values")
        if not start or not end:
            raise DataError("Coin Metrics acquisition requires --start and --end")
        params_cm: dict[str, str | int] = {
            "assets": instrument_value.lower(),
            "metrics": ",".join(selected_metrics),
            "frequency": frequency,
            "start_time": start,
            "end_time": end,
            "page_size": 10_000,
        }
        url = coinmetrics_community_url("asset_metrics", params_cm)
        payload = fetch_coinmetrics_community(url)
        plan = _AcquisitionPlan(
            endpoint="asset_metrics",
            params=params_cm,
            dataset=CryptoDatasetIdentityV1(
                provider="coinmetrics",
                venue="coinmetrics-community",
                market_type="network",
                family="onchain_metrics",
                instrument=instrument_value.lower(),
                base_asset=base_value,
                quote_asset=None,
                frequency=frequency,
                units="metric_native",
                timestamp_convention="provider_observation_utc",
            ),
            parser=partial(
                parse_asset_metrics,
                assets=(instrument_value.lower(),),
                metrics=selected_metrics,
            ),
            observed_column="timestamp",
            key_columns=("asset", "timestamp", "metric"),
        )
        return _FetchedAcquisition(
            plan=plan,
            payload=payload,
            provider_schema="coinmetrics-community-v4",
            parser_version="coinmetrics-community-v1",
            logical_name="onchain_metrics.json",
        )

    raise DataError(f"unsupported crypto acquisition provider {provider!r}")


@crypto_data_app.command("acquire")
def acquire(
    provider: str,
    family: str,
    instrument: str,
    base: str = typer.Option(..., help="exact base asset"),
    quote: str = typer.Option(..., help="exact quote asset; USD, USDT, and USDC stay distinct"),
    category: str = typer.Option("linear", help="spot, linear, or inverse market"),
    frequency: str = typer.Option("1h", help="provider-native bounded frequency"),
    period: str | None = typer.Option(None, help="Binance monthly archive period YYYY-MM"),
    network: str | None = typer.Option(None, help="reviewed GeckoTerminal network id"),
    pool_address: str | None = typer.Option(None, help="exact DEX pool address"),
    metrics: str | None = typer.Option(None, help="comma-separated reviewed Coin Metrics metrics"),
    start: str | None = typer.Option(None, help="provider-native bounded start time"),
    end: str | None = typer.Option(None, help="provider-native bounded end time"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Acquire one bounded public provider page; this grants no research or order authority."""
    dataset_family = _family(family)
    fetched_at = _now()
    try:
        if provider == "bybit":
            plan = _bybit_plan(
                dataset_family,
                instrument,
                base=base,
                quote=quote,
                category=category,
                frequency=frequency,
                start=start,
                end=end,
                fetched_at=fetched_at,
            )
            pages = _fetch_bybit_pages(
                plan,
                follow_cursors=(start is not None or dataset_family == "option_instruments"),
            )
            fetched = None
        else:
            fetched = _fetch_non_bybit(
                provider,
                dataset_family,
                instrument,
                base=base,
                quote=quote,
                category=category,
                frequency=frequency,
                period=period,
                network=network,
                pool_address=pool_address,
                metrics=metrics,
                start=start,
                end=end,
                fetched_at=fetched_at,
            )
            plan = fetched.plan
        if provider == "bybit" and len(pages) > 1:
            paged_result = ingest_provider_pages(
                _bulk_store(),
                dataset=plan.dataset,
                pages=pages,
                fetched_at=fetched_at,
                provider_schema="bybit-v5",
                parser_version="bybit-public-v1",
                logical_name=f"{dataset_family}.json",
                parser=plan.parser,
                observed_column=plan.observed_column,
                key_columns=plan.key_columns,
                availability_column=plan.availability_column,
            )
            quality = paged_result.quality
            normalized_manifest = paged_result.normalized_manifest
            raw_manifests = paged_result.raw_manifests
        else:
            if provider == "bybit":
                payload, request, pagination = pages[0]
                provider_schema = "bybit-v5"
                parser_version = "bybit-public-v1"
                logical_name = f"{dataset_family}.json"
                upstream_checksum = None
                expected_cadence_seconds = None
                period_start_timestamps = False
            else:
                assert fetched is not None
                payload = fetched.payload
                request = tuple(
                    (key, str(value)) for key, value in sorted(plan.params.items())
                )
                pagination = ()
                provider_schema = fetched.provider_schema
                parser_version = fetched.parser_version
                logical_name = fetched.logical_name
                upstream_checksum = fetched.upstream_checksum
                expected_cadence_seconds = fetched.expected_cadence_seconds
                period_start_timestamps = fetched.period_start_timestamps
            single_result = ingest_provider_payload(
                _bulk_store(),
                dataset=plan.dataset,
                payload=payload,
                request=request,
                fetched_at=fetched_at,
                provider_schema=provider_schema,
                parser_version=parser_version,
                logical_name=logical_name,
                parser=plan.parser,
                observed_column=plan.observed_column,
                key_columns=plan.key_columns,
                pagination=pagination,
                availability_column=plan.availability_column,
                upstream_checksum=upstream_checksum,
                expected_cadence=(
                    timedelta(seconds=expected_cadence_seconds)
                    if expected_cadence_seconds is not None
                    else None
                ),
                period_start_timestamps=period_start_timestamps,
            )
            quality = single_result.quality
            normalized_manifest = single_result.normalized_manifest
            raw_manifests = (single_result.raw_manifest,)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    next_action = (
        "Create or extend a frozen crypto snapshot."
        if quality.state == "qualified"
        else "Review the quality blockers before using this dataset."
    )
    _emit(
        {
            "provider": provider,
            "family": dataset_family,
            "instrument": plan.dataset.instrument,
            "state": quality.state,
            "failures": list(quality.failures),
            "warnings": list(quality.warnings),
            "raw_manifest_id": raw_manifests[0]["manifest_id"],
            "raw_manifest_ids": [item["manifest_id"] for item in raw_manifests],
            "raw_page_count": len(raw_manifests),
            "normalized_manifest_id": normalized_manifest["manifest_id"],
            "artifact_sha256": normalized_manifest["artifact_sha256"],
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


def _coverage_row(
    manifest: dict[str, object], *, store: CryptoBulkStore | None = None
) -> dict[str, object]:
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    manifest_id = manifest.get("manifest_id")
    if not isinstance(manifest_id, str):
        raise DataError("crypto normalized manifest id is invalid")
    fetched_at: str | None = None
    input_manifest_ids = manifest.get("input_manifest_ids")
    if store is not None and isinstance(input_manifest_ids, list) and input_manifest_ids:
        receipt_times: set[str] = set()
        for input_manifest_id in input_manifest_ids:
            raw_manifest = store.verify_manifest(input_manifest_id)
            raw_receipt = raw_manifest.get("receipt")
            if raw_receipt is None:
                receipt_times.clear()
                break
            receipt_times.add(CryptoRawReceiptV1.from_dict(raw_receipt).fetched_at.isoformat())
        if len(receipt_times) == 1:
            fetched_at = receipt_times.pop()
    return {
        "manifest_id": manifest_id,
        "provider": dataset.provider,
        "venue": dataset.venue,
        "market_type": dataset.market_type,
        "family": dataset.family,
        "instrument": dataset.instrument,
        "base_asset": dataset.base_asset,
        "quote_asset": dataset.quote_asset,
        "frequency": dataset.frequency,
        "units": dataset.units,
        "timestamp_convention": dataset.timestamp_convention,
        "state": quality.state,
        "failures": list(quality.failures),
        "warnings": list(quality.warnings),
        "observed_start": quality.observed_start.isoformat() if quality.observed_start else None,
        "observed_end": quality.observed_end.isoformat() if quality.observed_end else None,
        "row_count": quality.row_count,
        "artifact_sha256": quality.dataset_sha256,
        "method_version": quality.method_version,
        "fetched_at": fetched_at,
    }


@crypto_data_app.command("coverage")
def coverage(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Show exact normalized family coverage and qualification without provider probes."""
    try:
        store = _bulk_store()
        items = [
            _coverage_row(manifest, store=store)
            for manifest in store.inventory()
            if manifest.get("artifact_kind") == "normalized"
        ]
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    items.sort(
        key=lambda row: (str(row["family"]), str(row["instrument"]), str(row["manifest_id"]))
    )
    _emit(
        {
            "items": items,
            "count": len(items),
            "canonical_next_action": (
                "Select qualified families for a snapshot."
                if any(item["state"] == "qualified" for item in items)
                else "Acquire and qualify one bounded dataset."
            ),
            "automatic_fallback": False,
            "execution_authority": False,
        },
        json_out=json_out,
    )


@crypto_data_app.command("quality")
def quality(
    manifest_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Reverify and display one normalized artifact's mechanical quality report."""
    try:
        manifest = _bulk_store().verify_manifest(manifest_id)
        if manifest.get("artifact_kind") != "normalized":
            raise DataError("crypto quality requires a normalized manifest")
        row = _coverage_row(manifest, store=_bulk_store())
        report = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "manifest_id": manifest_id,
            "dataset": {
                key: row[key]
                for key in (
                    "provider",
                    "venue",
                    "market_type",
                    "family",
                    "instrument",
                    "base_asset",
                    "quote_asset",
                    "frequency",
                    "units",
                    "timestamp_convention",
                )
            },
            "quality": report.to_dict(),
            "next_action": (
                "Select this dataset for a frozen snapshot."
                if report.state == "qualified"
                else "Resolve the reported failures or warnings; do not substitute another venue."
            ),
        },
        json_out=json_out,
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
        snapshot, _, projection = _verified_snapshot(
            snapshot_id,
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


__all__ = ["crypto_data_app", "crypto_snapshot_registration"]
