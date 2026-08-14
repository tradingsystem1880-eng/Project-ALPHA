"""Governed crypto-data catalog, storage, estimation, and identity commands."""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from functools import partial
from pathlib import Path
from typing import Annotated, Final, Literal, cast

import polars as pl
import typer

from alpha_cli.control_store import ControlStore, research_case_revision
from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.adapters.ccxt_adapter import CCXTAdapter, parse_ccxt_ohlcv
from alpha_data.crypto.asset_master import AssetMaster, build_cross_provider_asset_master
from alpha_data.crypto.capabilities import project_provider_capabilities
from alpha_data.crypto.contracts import (
    FAMILY_AUTHORITIES,
    CryptoAcquisitionScopeV1,
    CryptoDatasetIdentityV1,
    CryptoFamily,
    CryptoMarketType,
    CryptoQualityReportV1,
    CryptoRawReceiptV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_data.crypto.features import (
    CryptoFeatureArtifactV1,
    QualifiedCryptoFrame,
    basis_features,
    feature_frame_bytes,
    funding_features,
    liquidity_features,
    onchain_features,
    open_interest_features,
    volatility_surface_features,
)
from alpha_data.crypto.ingestion import ingest_provider_pages, ingest_provider_payload
from alpha_data.crypto.profiles import (
    CoverageCadence,
    CryptoCoverageProfileV1,
    CryptoCoverageTaskV1,
    active_option_markets,
    build_default_coverage_tasks,
)
from alpha_data.crypto.providers.binance import (
    archive_checksum_sha256,
    archive_url,
    binance_public_api_url,
    fetch_binance_archive,
    fetch_binance_checksum,
    fetch_binance_public_api,
    parse_binance_archive_zip,
    parse_binance_book_snapshot,
    parse_binance_exchange_info,
    parse_binance_klines,
    point_in_time_liquid_markets,
    reconcile_archive_tail,
    verify_archive_checksum,
)
from alpha_data.crypto.providers.bybit import (
    BybitCategory,
    PriceFamily,
    fetch_bybit_public,
    parse_funding_history,
    parse_historical_volatility,
    parse_instruments,
    parse_long_short_ratio,
    parse_open_interest,
    parse_option_tickers,
    parse_orderbook_snapshot,
    parse_price_klines,
    parse_recent_trades,
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
from alpha_data.crypto.quality import compare_market_observations
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
    "market_membership": 256,
    "instrument_catalog": 256,
    "derivative_bars": 160,
    "derivative_trades": 160,
    "derivative_book_snapshots": 1_600,
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
_OBSERVATIONS_PER_DAY: Final = {
    "1d": 1,
    "4h": 6,
    "1h": 24,
    "30m": 48,
    "15m": 96,
    "5m": 288,
    "1m": 1_440,
    "tick": 100_000,
}
_NATIVE_NETWORKS: Final = {"BTC": "bitcoin", "ETH": "ethereum"}
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_BYBIT_PRICE_FAMILIES: Final[dict[CryptoFamily, tuple[str, PriceFamily]]] = {
    "derivative_bars": ("trade_kline", "trade"),
    "mark_bars": ("mark_kline", "mark"),
    "index_bars": ("index_kline", "index"),
    "premium_bars": ("premium_kline", "premium"),
}
_CASE_BOUND_EVENT_FAMILIES: Final = frozenset({"derivative_trades", "derivative_book_snapshots"})


class _LegacyUnscopedEventError(DataError):
    """Historical bytes are valid but cannot qualify as governed research evidence."""


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
    parser_at: Callable[[datetime], Callable[[bytes], pl.DataFrame]] | None = None


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


@dataclass(frozen=True)
class _FetchedPagedAcquisition:
    plan: _AcquisitionPlan
    pages: tuple[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]], ...]
    page_parsers: tuple[Callable[[bytes], pl.DataFrame], ...]
    upstream_checksums: tuple[str | None, ...]
    combine_frames: Callable[[tuple[pl.DataFrame, ...]], pl.DataFrame] | None
    provider_schema: str
    parser_version: str
    logical_name: str
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


def _long_short_cursor(payload: bytes, *, category: Literal["linear", "inverse"]) -> str | None:
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


def _catalog_frame(payload: bytes, *, category: BybitCategory, fetched_at_ms: int) -> pl.DataFrame:
    return parse_instruments(payload, category=category, fetched_at_ms=fetched_at_ms)[0]


def _catalog_cursor(payload: bytes, *, category: BybitCategory, fetched_at_ms: int) -> str | None:
    return parse_instruments(payload, category=category, fetched_at_ms=fetched_at_ms)[1]


def _catalog_parser_at(
    completed_at: datetime, *, category: BybitCategory
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        _catalog_frame,
        category=category,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
    )


def _recent_trades_parser_at(completed_at: datetime) -> Callable[[bytes], pl.DataFrame]:
    return partial(parse_recent_trades, fetched_at_ms=int(completed_at.timestamp() * 1_000))


def _orderbook_parser_at(
    completed_at: datetime, *, category: BybitCategory
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        parse_orderbook_snapshot,
        category=category,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
    )


def _option_instrument_parser_at(
    completed_at: datetime, *, base: str, quote: str
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        _instrument_frame,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
        base=base,
        quote=quote,
    )


def _option_quote_parser_at(
    completed_at: datetime, *, base: str, quote: str
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        _option_quote_frame,
        fetched_at_ms=int(completed_at.timestamp() * 1_000),
        base=base,
        quote=quote,
    )


def _binance_book_parser_at(
    completed_at: datetime,
    *,
    symbol: str,
    category: Literal["spot", "linear", "inverse"],
) -> Callable[[bytes], pl.DataFrame]:
    return partial(
        parse_binance_book_snapshot,
        symbol=symbol,
        category=category,
        fetched_at=completed_at,
    )


def _binance_membership_parser_at(
    completed_at: datetime,
    *,
    category: Literal["spot", "linear", "inverse"],
) -> Callable[[bytes], pl.DataFrame]:
    return partial(parse_binance_exchange_info, category=category, fetched_at=completed_at)


def _market_reference_parser_at(
    completed_at: datetime, *, quote: str
) -> Callable[[bytes], pl.DataFrame]:
    return partial(parse_market_universe, vs_currency=quote, fetched_at=completed_at)


def _asset_catalog_parser_at(completed_at: datetime) -> Callable[[bytes], pl.DataFrame]:
    return partial(_asset_catalog_frame, fetched_at=completed_at)


def _top_pools_parser_at(
    completed_at: datetime, *, network: str
) -> Callable[[bytes], pl.DataFrame]:
    return partial(_top_pools_frame, network=network, fetched_at=completed_at)


def _ccxt_comparison_payload(frame: pl.DataFrame) -> bytes:
    required = ("ts", "open", "high", "low", "close", "volume")
    if any(column not in frame.columns for column in required) or frame.is_empty():
        raise DataError("CCXT comparison output is empty or malformed")
    rows: list[list[float | int]] = []
    for row in frame.select(required).iter_rows(named=True):
        timestamp = row["ts"]
        if not isinstance(timestamp, datetime):
            raise DataError("CCXT comparison timestamp is invalid")
        rows.append(
            [
                int(timestamp.timestamp() * 1_000),
                float(cast(float, row["open"])),
                float(cast(float, row["high"])),
                float(cast(float, row["low"])),
                float(cast(float, row["close"])),
                float(cast(float, row["volume"])),
            ]
        )
    return json.dumps(rows, separators=(",", ":"), allow_nan=False).encode()


def _parse_ccxt_comparison(payload: bytes, *, symbol: str) -> pl.DataFrame:
    try:
        raw = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DataError("CCXT comparison payload is invalid") from exc
    if not isinstance(raw, list) or any(not isinstance(row, list) for row in raw):
        raise DataError("CCXT comparison payload is invalid")
    return parse_ccxt_ohlcv(raw, symbol).bars.rename({"ts": "timestamp"})


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


def _control_store() -> ControlStore:
    return ControlStore(AlphaSettings().data_dir)


def _acquisition_scope(
    family: CryptoFamily,
    *,
    case_id: str | None,
    expected_case_revision: str | None,
    reason: str | None,
    captured_at: datetime,
) -> CryptoAcquisitionScopeV1 | None:
    supplied = any(value is not None for value in (case_id, expected_case_revision, reason))
    if family not in _CASE_BOUND_EVENT_FAMILIES:
        if supplied:
            raise DataError("research-case scope is only valid for derivative event capture")
        return None
    if not case_id or not expected_case_revision or not reason:
        raise DataError(
            "derivative trades and books require --case-id, --expected-case-revision, and --reason"
        )
    current = _control_store().research_case_summary(case_id)
    revision = research_case_revision(current)
    if revision != expected_case_revision:
        raise DataError("research case changed before derivative event capture; refresh and retry")
    return CryptoAcquisitionScopeV1(
        project_id=case_id,
        case_revision=revision,
        reason=reason,
        captured_at=captured_at,
    )


def _snapshot_root() -> Path:
    return AlphaSettings().data_dir / "crypto" / "snapshots"


def _asset_master_root() -> Path:
    return AlphaSettings().data_dir / "crypto" / "asset-masters"


def _coverage_profile_root() -> Path:
    return AlphaSettings().data_dir / "crypto" / "coverage-profiles"


def _coverage_batch_root() -> Path:
    return AlphaSettings().data_dir / "crypto" / "coverage-batches"


def _write_coverage_profile(profile: CryptoCoverageProfileV1) -> None:
    root = _coverage_profile_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{profile.profile_id}.json"
    rendered = json.dumps(profile.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise DataError("crypto coverage-profile identity collision")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)


def _read_coverage_profile(profile_id: str) -> CryptoCoverageProfileV1:
    if _SHA256.fullmatch(profile_id) is None:
        raise DataError("crypto coverage-profile id is invalid")
    try:
        raw = json.loads(
            (_coverage_profile_root() / f"{profile_id}.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("crypto coverage profile is unavailable or corrupt") from exc
    return CryptoCoverageProfileV1.from_dict(raw)


def _write_asset_master(master: AssetMaster) -> None:
    root = _asset_master_root()
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{master.version}.json"
    rendered = json.dumps(master.to_dict(), sort_keys=True, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise DataError("crypto asset-master identity collision")
        return
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(rendered, encoding="utf-8")
    os.replace(temporary, path)


def _read_asset_master(version: str) -> AssetMaster:
    if _SHA256.fullmatch(version) is None:
        raise DataError("crypto asset-master version is invalid")
    try:
        raw = json.loads((_asset_master_root() / f"{version}.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("crypto asset-master is unavailable or corrupt") from exc
    return AssetMaster.from_dict(raw)


def _stable_resource_revision_lineage(
    store: CryptoBulkStore,
    *,
    dataset: CryptoDatasetIdentityV1,
    request: tuple[tuple[str, str], ...],
    response_sha256: str,
) -> tuple[str, ...]:
    """Find prior bytes for the same stable provider resource without trusting filenames."""
    prior: set[str] = set()
    for manifest in store.inventory():
        if manifest.get("artifact_kind") != "raw" or "receipt" not in manifest:
            continue
        receipt = CryptoRawReceiptV1.from_dict(manifest["receipt"])
        if (
            receipt.dataset == dataset
            and receipt.request == request
            and receipt.response_sha256 != response_sha256
        ):
            prior.add(receipt.response_sha256)
    return tuple(sorted(prior))


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
    if snapshot.asset_master_version != "reviewed-native-v1":
        master = _read_asset_master(snapshot.asset_master_version)
        if master.version != snapshot.asset_master_version:
            raise DataError("crypto snapshot asset-master identity is mismatched")
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
        _manifest_acquisition_scope(manifest, member.dataset)
        reports[member.artifact_sha256] = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports=reports,
        required_families=required_families,
        purpose=purpose,
    )
    return snapshot, reports, projection


def _integrity_verified_snapshot(snapshot_id: str) -> tuple[CryptoSnapshotV1, bool]:
    """Verify historical bytes and identity without promoting legacy scope into evidence."""
    snapshot = _read_snapshot(snapshot_id)
    if snapshot.asset_master_version != "reviewed-native-v1":
        master = _read_asset_master(snapshot.asset_master_version)
        if master.version != snapshot.asset_master_version:
            raise DataError("crypto snapshot asset-master identity is mismatched")
    store = _bulk_store()
    by_membership = {
        (manifest.get("artifact_key"), manifest.get("artifact_sha256")): manifest
        for manifest in store.inventory()
        if manifest.get("artifact_kind") == "normalized"
    }
    scope_eligible = True
    reports: dict[str, CryptoQualityReportV1] = {}
    for member in snapshot.members:
        manifest = by_membership.get((member.artifact_key, member.artifact_sha256))
        if manifest is None or manifest.get("dataset") != member.dataset.to_dict():
            raise DataError("crypto snapshot member manifest is missing or mismatched")
        try:
            _manifest_acquisition_scope(manifest, member.dataset)
        except _LegacyUnscopedEventError:
            scope_eligible = False
        reports[member.artifact_sha256] = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    projection = assess_crypto_snapshot(
        snapshot,
        quality_reports=reports,
        required_families=(),
        purpose="research",
    )
    return snapshot, scope_eligible and projection.eligible


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
        bar_minutes = {"1m": 1, "5m": 5, "1h": 60, "1d": 1_440}.get(next(iter(frequencies)))
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


@crypto_data_app.command("capabilities")
def capabilities(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """Project support, receipt verification, and qualification without probing providers."""
    try:
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
        projected = project_provider_capabilities(store.inventory())
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    verified = sum(item.verification_state == "receipt_verified" for item in projected)
    qualified = sum(item.qualification_state == "qualified" for item in projected)
    _emit(
        {
            "items": [item.to_dict() for item in projected],
            "count": len(projected),
            "receipt_verified_count": verified,
            "qualified_count": qualified,
            "provider_probe_performed": False,
            "automatic_fallback": False,
            "execution_authority": False,
            "canonical_next_action": (
                "Inspect qualified coverage and freeze an exact snapshot."
                if qualified
                else "Acquire and qualify one bounded provider-native dataset."
            ),
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
            tuple(sorted(_snapshot_root().glob("*.json"))) if _snapshot_root().exists() else ()
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
            "staging_count": len(tuple(store.staging_root.rglob("staging.json")))
            + len(tuple(store.staging_root.rglob("download.json"))),
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
        asset_master_count = 0
        if _asset_master_root().exists():
            for path in sorted(_asset_master_root().glob("*.json")):
                master = _read_asset_master(path.stem)
                if master.version != path.stem:
                    raise DataError("crypto asset-master filename identity is mismatched")
                asset_master_count += 1
        if _snapshot_root().exists():
            for path in sorted(_snapshot_root().glob("*.json")):
                snapshot, eligible = _integrity_verified_snapshot(path.stem)
                snapshot_count += 1
                eligible_count += int(eligible and snapshot.snapshot_id == path.stem)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "state": "verified",
            "manifest_count": len(inventory),
            "snapshot_count": snapshot_count,
            "research_eligible_snapshot_count": eligible_count,
            "asset_master_count": asset_master_count,
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


@crypto_data_app.command("asset-contract")
def asset_contract(
    network: str,
    contract_address: str,
    asset_master_version: str = typer.Option(..., help="exact frozen asset-master version"),
    as_of: str = typer.Option(..., help="point-in-time ISO-8601 timestamp"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Resolve one contract by exact network and address; ticker lookup is unavailable."""
    try:
        instant = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        identity = _read_asset_master(asset_master_version).resolve_contract(
            network=network,
            contract_address=contract_address,
            as_of=instant,
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
    diagnostic_spot = family == "comparison_bars" and category == "spot"
    if FAMILY_AUTHORITIES[family] != "bybit" and not diagnostic_spot:
        raise DataError(f"{family} is not a Bybit-authoritative dataset family")
    if diagnostic_spot:
        pass
    elif family == "instrument_catalog":
        if category not in {"spot", "linear", "inverse", "option"}:
            raise DataError(
                "Bybit instrument catalog category must be spot, linear, inverse, or option"
            )
    elif family in {"derivative_trades", "derivative_book_snapshots"}:
        if category not in {"linear", "inverse", "option"}:
            raise DataError("Bybit derivative event category must be linear, inverse, or option")
    elif family in {"option_instruments", "option_quotes", "historical_volatility"}:
        if category != "option":
            raise DataError(f"Bybit {family} requires the option category")
    elif category not in {"linear", "inverse"}:
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
    dataset_instrument = symbol
    dataset_base: str | None = base_value
    dataset_quote: str | None = quote_value
    timestamp_convention = "provider_event_utc"
    next_cursor: Callable[[bytes], str | None] | None = None
    page_limit: int | None = None
    parser_at: Callable[[datetime], Callable[[bytes], pl.DataFrame]] | None = None
    bounded_range = _bybit_range(start, end, fetched_at=fetched_at)

    if family == "comparison_bars":
        endpoint = "trade_kline"
        interval = {"1h": "60", "1d": "D", "5m": "5", "1m": "1"}.get(frequency)
        if interval is None:
            raise DataError("Bybit spot comparison frequency must be 1m, 5m, 1h, or 1d")
        params = {"category": "spot", "symbol": symbol, "interval": interval, "limit": 1_000}
        parser = partial(parse_price_klines, family="trade")
        units = "quote_per_base_and_base_volume"
        page_limit = 1_000
    elif family == "instrument_catalog":
        endpoint = "instruments"
        params = {"category": category}
        if category != "spot":
            params["limit"] = 1_000
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        catalog_category = cast(BybitCategory, category)
        parser = partial(
            _catalog_frame,
            category=catalog_category,
            fetched_at_ms=fetched_at_ms,
        )
        parser_at = partial(_catalog_parser_at, category=catalog_category)
        observed_column = "fetched_at"
        key_columns = ("symbol",)
        dataset_frequency = "catalog_snapshot"
        dataset_instrument = category
        dataset_base = None
        dataset_quote = None
        timestamp_convention = "fetch_knowledge_utc"
        if category != "spot":
            next_cursor = partial(
                _catalog_cursor,
                category=catalog_category,
                fetched_at_ms=fetched_at_ms,
            )
    elif family == "derivative_trades":
        endpoint = "recent_trades"
        params = {"category": category, "symbol": symbol, "limit": 1_000}
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(parse_recent_trades, fetched_at_ms=fetched_at_ms)
        parser_at = _recent_trades_parser_at
        key_columns = ("timestamp", "trade_id")
        availability_column = "available_at"
        units = "provider_native_price_quantity"
        dataset_frequency = "recent_trade_snapshot"
    elif family == "derivative_book_snapshots":
        endpoint = "orderbook"
        params = {
            "category": category,
            "symbol": symbol,
            "limit": 25 if category == "option" else 1_000,
        }
        fetched_at_ms = int(fetched_at.timestamp() * 1_000)
        parser = partial(
            parse_orderbook_snapshot,
            category=cast(BybitCategory, category),
            fetched_at_ms=fetched_at_ms,
        )
        parser_at = partial(_orderbook_parser_at, category=cast(BybitCategory, category))
        observed_column = "observed_at"
        key_columns = ("observed_at", "side", "level")
        availability_column = "available_at"
        units = "provider_native_price_quantity"
        dataset_frequency = "point_in_time_book"
        timestamp_convention = "provider_generation_utc"
    elif family == "funding":
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
        parser_at = partial(_option_instrument_parser_at, base=base_value, quote=quote_value)
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
        parser_at = partial(_option_quote_parser_at, base=base_value, quote=quote_value)
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
        if family in {
            "instrument_catalog",
            "derivative_trades",
            "derivative_book_snapshots",
            "option_instruments",
            "option_quotes",
        }:
            raise DataError(f"Bybit {family} is a point-in-time snapshot and rejects a time range")
        start_ms, end_ms = bounded_range
        if family in _BYBIT_PRICE_FAMILIES or family == "comparison_bars":
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
            instrument=dataset_instrument,
            base_asset=dataset_base,
            quote_asset=dataset_quote,
            frequency=dataset_frequency,
            units=units,
            timestamp_convention=timestamp_convention,
        ),
        parser=parser,
        observed_column=observed_column,
        key_columns=key_columns,
        availability_column=availability_column,
        next_cursor=next_cursor,
        page_limit=page_limit,
        parser_at=parser_at,
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


def _binance_range(
    start: str | None, end: str | None, *, fetched_at: datetime
) -> tuple[int, int] | None:
    if (start is None) != (end is None):
        raise DataError("Binance --start and --end must be supplied together")
    if start is None or end is None:
        return None
    try:
        start_at = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DataError("Binance start and end must be ISO-8601 timestamps") from exc
    if (
        start_at.tzinfo is None
        or start_at.utcoffset() is None
        or end_at.tzinfo is None
        or end_at.utcoffset() is None
    ):
        raise DataError("Binance start and end must include a timezone")
    start_ms = int(start_at.astimezone(UTC).timestamp() * 1_000)
    end_ms = int(end_at.astimezone(UTC).timestamp() * 1_000)
    if end_ms <= start_ms:
        raise DataError("Binance end must be later than start")
    if end_ms > int(fetched_at.timestamp() * 1_000):
        raise DataError("Binance end exceeds the acquisition knowledge time")
    return start_ms, end_ms


def _fetch_binance_tail_pages(
    *,
    category: Literal["spot", "linear", "inverse"],
    symbol: str,
    frequency: str,
    start_ms: int,
    end_ms: int,
) -> tuple[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]], ...]:
    cadence_ms = {"1d": 86_400_000, "1h": 3_600_000, "5m": 300_000, "1m": 60_000}.get(frequency)
    if cadence_ms is None:
        raise DataError("Binance REST-tail frequency must be 1m, 5m, 1h, or 1d")
    pages: list[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]]] = []
    next_start = start_ms
    for page_number in range(1, 101):
        params: dict[str, str | int] = {
            "symbol": symbol,
            "interval": frequency,
            "limit": 1_000,
            "startTime": next_start,
            "endTime": end_ms,
        }
        payload = fetch_binance_public_api(binance_public_api_url(category, "klines", params))
        frame = parse_binance_klines(payload, source="rest_json")
        last_open = frame["open_time"][-1]
        assert isinstance(last_open, datetime)
        last_ms = int(last_open.timestamp() * 1_000)
        if last_ms < next_start:
            raise DataError("Binance REST tail did not advance its requested range")
        following = last_ms + cadence_ms
        terminal = frame.height < 1_000 or following > end_ms
        request = tuple((key, str(value)) for key, value in sorted(params.items()))
        pages.append(
            (
                payload,
                request,
                (f"page={page_number}", f"next_start={following if not terminal else 'terminal'}"),
            )
        )
        if terminal:
            return tuple(pages)
        if following <= next_start:
            raise DataError("Binance REST-tail pagination did not advance")
        next_start = following
    raise DataError("Binance REST-tail acquisition exceeded the 100-page safety limit")


def _combine_binance_archive_tail(frames: tuple[pl.DataFrame, ...]) -> pl.DataFrame:
    if not frames:
        raise DataError("Binance archive/tail combination is empty")
    combined = frames[0]
    for tail in frames[1:]:
        combined = reconcile_archive_tail(combined, tail)
    return combined


def _fetch_non_bybit(
    provider: str,
    family: CryptoFamily,
    instrument: str,
    staging_root: Path,
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
) -> _FetchedAcquisition | _FetchedPagedAcquisition:
    base_value, quote_value = base.strip().upper(), quote.strip().upper()
    instrument_value = instrument.strip()
    if not base_value.isalnum() or not quote_value.isalnum() or not instrument_value:
        raise DataError("crypto acquisition identity is invalid")
    keys: tuple[str, ...]
    parser_at: Callable[[datetime], Callable[[bytes], pl.DataFrame]] | None

    if provider == "ccxt:coinbase":
        if family != "comparison_bars":
            raise DataError("ccxt:coinbase is diagnostic authority only for comparison_bars")
        cadence_seconds = {"1m": 60, "5m": 300, "1h": 3_600, "1d": 86_400}.get(frequency)
        if category != "spot" or cadence_seconds is None:
            raise DataError("ccxt:coinbase comparison supports exact 1m, 5m, 1h, or 1d spot bars")
        if any(value is not None for value in (period, network, pool_address, metrics)):
            raise DataError("ccxt:coinbase comparison received an unsupported provider option")
        if start is None or end is None:
            raise DataError("ccxt:coinbase comparison requires --start and --end")
        symbol = instrument_value.upper()
        if symbol != f"{base_value}/{quote_value}":
            raise DataError("ccxt:coinbase instrument must exactly match BASE/QUOTE")
        try:
            start_at = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end_at = datetime.fromisoformat(end.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DataError("ccxt:coinbase start and end must be ISO-8601 timestamps") from exc
        if start_at.tzinfo is None and len(start) == 10:
            start_at = start_at.replace(tzinfo=UTC)
        if end_at.tzinfo is None and len(end) == 10:
            end_at = end_at.replace(tzinfo=UTC)
        if (
            start_at.tzinfo is None
            or start_at.utcoffset() is None
            or end_at.tzinfo is None
            or end_at.utcoffset() is None
        ):
            raise DataError("ccxt:coinbase intraday bounds must include a timezone")
        start_at = start_at.astimezone(UTC)
        end_at = end_at.astimezone(UTC)
        current_interval = int(fetched_at.timestamp()) // cadence_seconds * cadence_seconds
        if end_at < start_at or int(end_at.timestamp()) >= current_interval:
            raise DataError(
                "ccxt:coinbase range must end before the current incomplete UTC interval"
            )
        result = CCXTAdapter(exchange="coinbase").fetch_timeframe(
            symbol, start_at, end_at, timeframe=frequency
        )
        timestamps = result.bars["ts"].to_list() if "ts" in result.bars.columns else []
        if not timestamps or any(
            not isinstance(value, datetime) or not start_at <= value <= end_at
            for value in timestamps
        ):
            raise DataError("ccxt:coinbase returned bars outside the exact requested range")
        payload = _ccxt_comparison_payload(result.bars)
        comparison_params: dict[str, str | int] = {
            "symbol": symbol,
            "timeframe": frequency,
            "start": start,
            "end": end,
        }
        return _FetchedAcquisition(
            plan=_AcquisitionPlan(
                endpoint="ccxt_fetch_ohlcv",
                params=comparison_params,
                dataset=CryptoDatasetIdentityV1(
                    provider="ccxt:coinbase",
                    venue="coinbase",
                    market_type="spot",
                    family="comparison_bars",
                    instrument=symbol,
                    base_asset=base_value,
                    quote_asset=quote_value,
                    frequency=frequency,
                    units="quote_per_base_and_base_volume",
                    timestamp_convention="interval_start_utc",
                ),
                parser=partial(_parse_ccxt_comparison, symbol=symbol),
                observed_column="timestamp",
                key_columns=("timestamp",),
            ),
            payload=payload,
            provider_schema="ccxt-unified-ohlcv-v1",
            parser_version="ccxt-adapter-v2-parser-v1",
            logical_name="comparison_bars.json",
            expected_cadence_seconds=cadence_seconds,
            period_start_timestamps=True,
        )

    if provider == "binance":
        if category not in {"spot", "linear", "inverse"}:
            raise DataError("Binance category must be spot, linear, or inverse")
        category_value = cast(Literal["spot", "linear", "inverse"], category)
        symbol = instrument_value.upper()
        if family == "market_membership":
            if any(value is not None for value in (period, start, end)):
                raise DataError("Binance market membership does not accept a time range")
            membership_params: dict[str, str | int] = {}
            url = binance_public_api_url(category_value, "exchangeInfo", membership_params)
            payload = fetch_binance_public_api(url)
            plan = _AcquisitionPlan(
                endpoint="exchangeInfo",
                params=membership_params,
                dataset=CryptoDatasetIdentityV1(
                    provider="binance",
                    venue="binance",
                    market_type=category_value,
                    family="market_membership",
                    instrument=category_value,
                    base_asset=None,
                    quote_asset=None,
                    frequency="catalog_snapshot",
                    units="provider_native_market_identity",
                    timestamp_convention="provider_observation_utc",
                ),
                parser=partial(
                    parse_binance_exchange_info,
                    category=category_value,
                    fetched_at=fetched_at,
                ),
                observed_column="fetched_at",
                key_columns=("category", "symbol"),
                availability_column="fetched_at",
                parser_at=partial(_binance_membership_parser_at, category=category_value),
            )
            return _FetchedAcquisition(
                plan=plan,
                payload=payload,
                provider_schema="binance-public-exchange-info-v1",
                parser_version="binance-market-membership-v1",
                logical_name="market_membership.json",
            )
        if family == "book_snapshots":
            if period is not None or start is not None or end is not None:
                raise DataError("Binance book snapshots do not accept period or time ranges")
            depth_params: dict[str, str | int] = {"symbol": symbol, "limit": 1_000}
            url = binance_public_api_url(category_value, "depth", depth_params)
            payload = fetch_binance_public_api(url)
            plan = _AcquisitionPlan(
                endpoint="depth",
                params=depth_params,
                dataset=CryptoDatasetIdentityV1(
                    provider="binance",
                    venue="binance",
                    market_type=category_value,
                    family="book_snapshots",
                    instrument=symbol,
                    base_asset=base_value,
                    quote_asset=quote_value,
                    frequency="point_in_time_book",
                    units="provider_native_price_quantity",
                    timestamp_convention="fetch_knowledge_utc",
                ),
                parser=partial(
                    parse_binance_book_snapshot,
                    symbol=symbol,
                    category=category_value,
                    fetched_at=fetched_at,
                ),
                observed_column="observed_at",
                key_columns=("observed_at", "side", "level"),
                availability_column="observed_at",
                parser_at=partial(
                    _binance_book_parser_at,
                    symbol=symbol,
                    category=category_value,
                ),
            )
            return _FetchedAcquisition(
                plan=plan,
                payload=payload,
                provider_schema="binance-public-depth-v1",
                parser_version="binance-book-v1",
                logical_name="book_snapshots.json",
            )
        archive_family_by_dataset: dict[CryptoFamily, Literal["klines", "trades", "aggTrades"]] = {
            "market_bars": "klines",
            "trades": "trades",
            "aggregate_trades": "aggTrades",
        }
        archive_family = archive_family_by_dataset.get(family)
        if archive_family is None:
            raise DataError(
                "this Binance archive acquisition accepts market_bars, trades, or aggregate_trades"
            )
        bounded_range = _binance_range(start, end, fetched_at=fetched_at)
        if family != "market_bars" and bounded_range is not None:
            raise DataError("Binance trade archives do not accept --start or --end")
        if period is not None and re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", period) is None:
            raise DataError("Binance archive acquisition requires --period YYYY-MM")
        if period is None and (family != "market_bars" or bounded_range is None):
            raise DataError(
                "Binance archives require --period YYYY-MM; market_bars may instead use "
                "a bounded --start/--end REST tail"
            )
        market = {"spot": "spot", "linear": "um", "inverse": "cm"}[category]
        interval = frequency if archive_family == "klines" else ""
        archive_payload: bytes | None = None
        archive_params: dict[str, str | int] | None = None
        if period is not None:
            url = archive_url(
                cast(Literal["spot", "um", "cm"], market),
                archive_family,
                symbol,
                interval,
                period,
            )
            checksum = fetch_binance_checksum(f"{url}.CHECKSUM")
            expected_checksum = archive_checksum_sha256(checksum)
            archive_payload = fetch_binance_archive(url, staging_root, expected_checksum)
            verify_archive_checksum(archive_payload, checksum)
            archive_params = {
                "market": market,
                "family": archive_family,
                "symbol": symbol,
                "period": period,
                **({"interval": interval} if interval else {}),
            }
        if family == "market_bars":
            cadence_seconds = {
                "1d": 86_400,
                "1h": 3_600,
                "5m": 300,
                "1m": 60,
            }.get(frequency)
            if cadence_seconds is None:
                raise DataError("Binance kline frequency must be 1m, 5m, 1h, or 1d")
            parser = parse_binance_archive_zip
            observed_column = "open_time"
            keys = ("open_time",)
            frequency_value = frequency
            units = "provider_native_ohlcv"
            timestamp_convention = "interval_start_utc"
        elif family == "trades":
            cadence_seconds = None
            parser = partial(parse_binance_archive_zip, family="trades")
            observed_column = "timestamp"
            keys = ("trade_id",)
            frequency_value = "trade_events"
            units = "provider_native_trade"
            timestamp_convention = "provider_event_utc"
        else:
            cadence_seconds = None
            parser = partial(parse_binance_archive_zip, family="aggTrades")
            observed_column = "timestamp"
            keys = ("aggregate_trade_id",)
            frequency_value = "aggregate_trade_events"
            units = "provider_native_aggregate_trade"
            timestamp_convention = "provider_event_utc"
        plan = _AcquisitionPlan(
            endpoint=(
                "monthly_archive_and_rest_tail"
                if archive_payload is not None and bounded_range is not None
                else "monthly_archive"
                if archive_payload is not None
                else "rest_tail"
            ),
            params=archive_params
            or {
                "symbol": symbol,
                "interval": frequency,
                "startTime": bounded_range[0] if bounded_range is not None else 0,
                "endTime": bounded_range[1] if bounded_range is not None else 0,
            },
            dataset=CryptoDatasetIdentityV1(
                provider="binance",
                venue="binance",
                market_type=cast(CryptoMarketType, category),
                family=family,
                instrument=symbol,
                base_asset=base_value,
                quote_asset=quote_value,
                frequency=frequency_value,
                units=units,
                timestamp_convention=timestamp_convention,
            ),
            parser=parser,
            observed_column=observed_column,
            key_columns=keys,
        )
        if family == "market_bars" and bounded_range is not None:
            tail_pages = _fetch_binance_tail_pages(
                category=category_value,
                symbol=symbol,
                frequency=frequency,
                start_ms=bounded_range[0],
                end_ms=bounded_range[1],
            )
            pages = tail_pages
            page_parsers: tuple[Callable[[bytes], pl.DataFrame], ...] = tuple(
                partial(parse_binance_klines, source="rest_json") for _ in tail_pages
            )
            upstream_checksums: tuple[str | None, ...] = tuple(None for _ in tail_pages)
            if archive_payload is not None:
                assert archive_params is not None
                pages = (
                    (
                        archive_payload,
                        tuple((key, str(value)) for key, value in sorted(archive_params.items())),
                        ("archive",),
                    ),
                    *tail_pages,
                )
                page_parsers = (parse_binance_archive_zip, *page_parsers)
                upstream_checksums = (
                    hashlib.sha256(archive_payload).hexdigest(),
                    *upstream_checksums,
                )
            return _FetchedPagedAcquisition(
                plan=plan,
                pages=pages,
                page_parsers=page_parsers,
                upstream_checksums=upstream_checksums,
                combine_frames=_combine_binance_archive_tail,
                provider_schema="binance-public-archive-rest-v1"
                if archive_payload is not None
                else "binance-public-rest-v1",
                parser_version="binance-archive-rest-v1",
                logical_name="market_bars.bin",
                expected_cadence_seconds=cadence_seconds,
                period_start_timestamps=True,
            )
        assert archive_payload is not None
        return _FetchedAcquisition(
            plan=plan,
            payload=archive_payload,
            provider_schema="binance-public-archive-v1",
            parser_version="binance-archive-v1",
            logical_name=f"{family}.zip",
            upstream_checksum=hashlib.sha256(archive_payload).hexdigest(),
            expected_cadence_seconds=cadence_seconds,
            period_start_timestamps=family == "market_bars",
        )

    if provider == "coingecko":
        api_key = os.environ.get("ALPHA_COINGECKO_API_KEY", "")
        if not api_key:
            raise DataError("CoinGecko Demo key requires scoped process injection")
        if family == "market_reference":
            params: dict[str, str | int | bool] = {
                "vs_currency": quote_value.lower(),
                "order": "market_cap_desc",
                "per_page": 250 if instrument_value == "all" else 1,
                "page": 1,
                "sparkline": False,
            }
            if instrument_value != "all":
                params["ids"] = instrument_value
            parser = partial(
                parse_market_universe,
                vs_currency=quote_value,
                fetched_at=fetched_at,
            )
            parser_at = partial(_market_reference_parser_at, quote=quote_value)
            observed_column = "observed_at"
            keys = ("coingecko_id", "quote_asset")
            endpoint = "markets"
            frequency_value = "point_in_time_reference"
            if instrument_value != "all":
                request = coingecko_demo_request("markets", params, api_key=api_key)
                payload = fetch_coingecko_demo(request)
        elif family == "asset_metadata":
            params = {"include_platform": True}
            request = coingecko_demo_request("asset_catalog", params, api_key=api_key)
            payload = fetch_coingecko_demo(request)
            parser = partial(_asset_catalog_frame, fetched_at=fetched_at)
            parser_at = _asset_catalog_parser_at
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
                base_asset=(
                    None if family == "asset_metadata" or instrument_value == "all" else base_value
                ),
                quote_asset=quote_value if family == "market_reference" else None,
                frequency=frequency_value,
                units="reference_only",
                timestamp_convention="provider_observation_utc",
            ),
            parser=parser,
            observed_column=observed_column,
            key_columns=keys,
            availability_column="fetched_at",
            parser_at=parser_at,
        )
        if family == "market_reference" and instrument_value == "all":
            market_pages: list[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]]] = []
            market_page_parsers: list[Callable[[bytes], pl.DataFrame]] = []
            for page_number in range(1, 101):
                page_params = {**params, "page": page_number}
                request = coingecko_demo_request("markets", page_params, api_key=api_key)
                payload = fetch_coingecko_demo(request)
                page_parser = partial(
                    parse_market_universe,
                    vs_currency=quote_value,
                    fetched_at=fetched_at,
                )
                row_count = page_parser(payload).height
                if row_count == 0:
                    raise DataError("CoinGecko market universe returned an empty page")
                market_pages.append(
                    (
                        payload,
                        tuple((key, str(value)) for key, value in sorted(page_params.items())),
                        (f"page={page_number}",),
                    )
                )
                market_page_parsers.append(page_parser)
                if row_count < 250:
                    return _FetchedPagedAcquisition(
                        plan=plan,
                        pages=tuple(market_pages),
                        page_parsers=tuple(market_page_parsers),
                        upstream_checksums=tuple(None for _ in market_pages),
                        combine_frames=None,
                        provider_schema="coingecko-demo-v3",
                        parser_version="coingecko-reference-v1",
                        logical_name=f"{family}.json",
                    )
            raise DataError("CoinGecko market universe exceeded the 100-page safety limit")
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
            parser = partial(_top_pools_frame, network=network, fetched_at=fetched_at)
            parser_at = partial(_top_pools_parser_at, network=network)
            observed_column = "fetched_at"
            keys = ("network", "pool_address")
            endpoint = "top_pools"
            frequency_value = "daily_catalog"
        elif family in {"dex_ohlcv", "dex_transactions"}:
            parser_at = None
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
                keys = ("network", "pool_address", "trade_id")
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
            parser_at=parser_at,
        )
        if family == "dex_pools":
            pages_gt: list[tuple[bytes, tuple[tuple[str, str], ...], tuple[str, ...]]] = []
            page_parsers_gt: list[Callable[[bytes], pl.DataFrame]] = []
            for page_number in range(1, 6):
                page_params_gt: dict[str, str | int | bool] = {"page": page_number}
                url = geckoterminal_public_url("top_pools", network=network, params=page_params_gt)
                page_payload = fetch_geckoterminal_public(url)
                page_parser_gt = partial(_top_pools_frame, network=network, fetched_at=fetched_at)
                if page_parser_gt(page_payload).height != 20:
                    raise DataError("GeckoTerminal top-100 catalog page is incomplete")
                pages_gt.append(
                    (
                        page_payload,
                        (("page", str(page_number)),),
                        (f"page={page_number}",),
                    )
                )
                page_parsers_gt.append(page_parser_gt)
            return _FetchedPagedAcquisition(
                plan=plan,
                pages=tuple(pages_gt),
                page_parsers=tuple(page_parsers_gt),
                upstream_checksums=tuple(None for _ in pages_gt),
                combine_frames=None,
                provider_schema="geckoterminal-v2",
                parser_version="geckoterminal-public-v1",
                logical_name=f"{family}.json",
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


def _acquire_result(
    provider: str,
    family: str,
    instrument: str,
    base: str = typer.Option(..., help="exact base asset"),
    quote: str = typer.Option(..., help="exact quote asset; USD, USDT, and USDC stay distinct"),
    category: str = typer.Option("linear", help="spot, linear, inverse, or option market"),
    frequency: str = typer.Option("1h", help="provider-native bounded frequency"),
    period: str | None = typer.Option(None, help="Binance monthly archive period YYYY-MM"),
    network: str | None = typer.Option(None, help="reviewed GeckoTerminal network id"),
    pool_address: str | None = typer.Option(None, help="exact DEX pool address"),
    metrics: str | None = typer.Option(None, help="comma-separated reviewed Coin Metrics metrics"),
    start: str | None = typer.Option(None, help="provider-native bounded start time"),
    end: str | None = typer.Option(None, help="provider-native bounded end time"),
    case_id: str | None = typer.Option(None, help="research case for derivative event capture"),
    expected_case_revision: str | None = typer.Option(
        None, help="fresh research-case revision for derivative event capture"
    ),
    reason: str | None = typer.Option(None, help="bounded event-capture reason"),
) -> dict[str, object]:
    """Acquire one bounded public provider page; this grants no research or order authority."""
    dataset_family = _family(family)
    fetched_at = _now()
    try:
        acquisition_scope = _acquisition_scope(
            dataset_family,
            case_id=case_id,
            expected_case_revision=expected_case_revision,
            reason=reason,
            captured_at=fetched_at,
        )
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
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
                follow_cursors=(
                    start is not None
                    or dataset_family in {"instrument_catalog", "option_instruments"}
                ),
            )
            fetched = None
        else:
            fetched = _fetch_non_bybit(
                provider,
                dataset_family,
                instrument,
                store.staging_root,
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
        fetched_at = _now()
        acquisition_scope = _acquisition_scope(
            dataset_family,
            case_id=case_id,
            expected_case_revision=expected_case_revision,
            reason=reason,
            captured_at=fetched_at,
        )
        if plan.parser_at is not None:
            plan = replace(plan, parser=plan.parser_at(fetched_at))
            if isinstance(fetched, _FetchedPagedAcquisition):
                fetched = replace(
                    fetched,
                    page_parsers=tuple(plan.parser for _ in fetched.pages),
                )
        correction_lineage: tuple[str, ...] = ()
        if isinstance(fetched, _FetchedPagedAcquisition):
            if fetched.upstream_checksums and fetched.upstream_checksums[0] is not None:
                archive_payload, archive_request, _ = fetched.pages[0]
                correction_lineage = _stable_resource_revision_lineage(
                    store,
                    dataset=plan.dataset,
                    request=archive_request,
                    response_sha256=hashlib.sha256(archive_payload).hexdigest(),
                )
        elif (
            isinstance(fetched, _FetchedAcquisition)
            and fetched.plan.dataset.provider == "binance"
            and fetched.upstream_checksum is not None
        ):
            archive_request = tuple((key, str(value)) for key, value in sorted(plan.params.items()))
            correction_lineage = _stable_resource_revision_lineage(
                store,
                dataset=plan.dataset,
                request=archive_request,
                response_sha256=hashlib.sha256(fetched.payload).hexdigest(),
            )
        if isinstance(fetched, _FetchedPagedAcquisition):
            paged_result = ingest_provider_pages(
                store,
                dataset=plan.dataset,
                pages=fetched.pages,
                fetched_at=fetched_at,
                provider_schema=fetched.provider_schema,
                parser_version=fetched.parser_version,
                logical_name=fetched.logical_name,
                parser=plan.parser,
                page_parsers=fetched.page_parsers,
                upstream_checksums=fetched.upstream_checksums,
                combine_frames=fetched.combine_frames,
                observed_column=plan.observed_column,
                key_columns=plan.key_columns,
                availability_column=plan.availability_column,
                expected_cadence=(
                    timedelta(seconds=fetched.expected_cadence_seconds)
                    if fetched.expected_cadence_seconds is not None
                    else None
                ),
                period_start_timestamps=fetched.period_start_timestamps,
                correction_lineage=correction_lineage,
                unexplained_revision=bool(correction_lineage),
                acquisition_scope=acquisition_scope,
            )
            quality = paged_result.quality
            normalized_manifest = paged_result.normalized_manifest
            raw_manifests = paged_result.raw_manifests
        elif provider == "bybit" and len(pages) > 1:
            paged_result = ingest_provider_pages(
                store,
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
                acquisition_scope=acquisition_scope,
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
                request = tuple((key, str(value)) for key, value in sorted(plan.params.items()))
                pagination = ()
                provider_schema = fetched.provider_schema
                parser_version = fetched.parser_version
                logical_name = fetched.logical_name
                upstream_checksum = fetched.upstream_checksum
                expected_cadence_seconds = fetched.expected_cadence_seconds
                period_start_timestamps = fetched.period_start_timestamps
            single_result = ingest_provider_payload(
                store,
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
                correction_lineage=correction_lineage,
                unexplained_revision=bool(correction_lineage),
                acquisition_scope=acquisition_scope,
            )
            quality = single_result.quality
            normalized_manifest = single_result.normalized_manifest
            raw_manifests = (single_result.raw_manifest,)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    if quality.state == "qualified":
        next_action = "Create or extend a frozen crypto snapshot."
    elif quality.state == "warning":
        next_action = "Review the quality warnings before selecting stronger evidence."
    else:
        next_action = "Review the quality blockers before using this dataset."
    return {
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
    }


@crypto_data_app.command("acquire")
def acquire(
    provider: str,
    family: str,
    instrument: str,
    base: str = typer.Option(..., help="exact base asset"),
    quote: str = typer.Option(..., help="exact quote asset; USD, USDT, and USDC stay distinct"),
    category: str = typer.Option("linear", help="spot, linear, inverse, or option market"),
    frequency: str = typer.Option("1h", help="provider-native bounded frequency"),
    period: str | None = typer.Option(None, help="Binance monthly archive period YYYY-MM"),
    network: str | None = typer.Option(None, help="reviewed GeckoTerminal network id"),
    pool_address: str | None = typer.Option(None, help="exact DEX pool address"),
    metrics: str | None = typer.Option(None, help="comma-separated reviewed Coin Metrics metrics"),
    start: str | None = typer.Option(None, help="provider-native bounded start time"),
    end: str | None = typer.Option(None, help="provider-native bounded end time"),
    case_id: str | None = typer.Option(None, help="research case for derivative event capture"),
    expected_case_revision: str | None = typer.Option(
        None, help="fresh research-case revision for derivative event capture"
    ),
    reason: str | None = typer.Option(None, help="bounded event-capture reason"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Acquire one bounded public provider page; this grants no research or order authority."""
    result = _acquire_result(
        provider,
        family,
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
        case_id=case_id,
        expected_case_revision=expected_case_revision,
        reason=reason,
    )
    _emit(result, json_out=json_out)


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
    _manifest_acquisition_scope(manifest, dataset)
    return (
        CryptoSnapshotMemberV1(
            dataset=dataset,
            artifact_key=artifact_key,
            artifact_sha256=artifact_hash,
        ),
        quality,
    )


def _manifest_acquisition_scope(
    manifest: dict[str, object], dataset: CryptoDatasetIdentityV1
) -> CryptoAcquisitionScopeV1 | None:
    raw_scope = manifest.get("acquisition_scope")
    if dataset.family in _CASE_BOUND_EVENT_FAMILIES:
        try:
            return CryptoAcquisitionScopeV1.from_dict(raw_scope)
        except DataError as exc:
            raise _LegacyUnscopedEventError(
                "legacy unscoped derivative event data cannot enter governed research evidence"
            ) from exc
    if raw_scope is not None:
        raise DataError("crypto acquisition scope is attached to an unsupported dataset family")
    return None


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


_FEATURE_INPUT_NAMES: Final = {
    "funding": ("funding",),
    "open_interest_change": ("open_interest",),
    "basis": ("mark", "index", "premium"),
    "volatility_surface": ("quotes", "instruments"),
    "liquidity": ("pools",),
    "onchain_change": ("onchain",),
}


def _qualified_feature_source(
    store: CryptoBulkStore, *, name: str, manifest_id: str
) -> QualifiedCryptoFrame:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto feature inputs must be normalized manifests")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    artifact_sha256 = manifest.get("artifact_sha256")
    if not isinstance(artifact_sha256, str):
        raise DataError("crypto feature input artifact hash is invalid")
    return QualifiedCryptoFrame(
        name=name,
        dataset=dataset,
        artifact_sha256=artifact_sha256,
        quality=quality,
        frame=_parquet_frame(store, manifest),
    )


def _create_feature(
    feature_name: str,
    *,
    inputs: tuple[tuple[str, str], ...],
    available_at: datetime,
) -> dict[str, object]:
    expected = _FEATURE_INPUT_NAMES.get(feature_name)
    if expected is None:
        raise DataError("crypto feature name is unsupported")
    if tuple(name for name, _manifest_id in inputs) != expected or len(
        {manifest_id for _name, manifest_id in inputs}
    ) != len(inputs):
        raise DataError(
            f"crypto {feature_name} feature requires ordered inputs: {', '.join(expected)}"
        )
    store = _bulk_store()
    sources = tuple(
        _qualified_feature_source(store, name=name, manifest_id=manifest_id)
        for name, manifest_id in inputs
    )
    if feature_name == "funding":
        frame, artifact = funding_features(sources[0], available_at=available_at)
    elif feature_name == "open_interest_change":
        frame, artifact = open_interest_features(sources[0], available_at=available_at)
    elif feature_name == "basis":
        frame, artifact = basis_features(
            sources[0], sources[1], sources[2], available_at=available_at
        )
    elif feature_name == "volatility_surface":
        frame, artifact = volatility_surface_features(
            sources[0], sources[1], available_at=available_at
        )
    elif feature_name == "liquidity":
        frame, artifact = liquidity_features(sources[0], available_at=available_at)
    else:
        frame, artifact = onchain_features(sources[0], available_at=available_at)
    payload = feature_frame_bytes(frame)
    if hashlib.sha256(payload).hexdigest() != artifact.artifact_sha256:
        raise DataError("crypto feature payload does not match its immutable contract")
    derived = store.publish_derived(
        payload,
        derived_kind="crypto-feature",
        input_manifest_ids=tuple(manifest_id for _name, manifest_id in inputs),
        metadata={
            "feature": artifact.to_dict(),
            "input_manifest_ids_by_name": [list(item) for item in inputs],
            "research_authority": False,
            "execution_authority": False,
        },
    )
    return {
        "manifest_id": derived["manifest_id"],
        "feature_id": artifact.feature_id,
        "feature_name": artifact.feature_name,
        "method_version": artifact.method_version,
        "available_at": artifact.available_at.isoformat(),
        "row_count": artifact.row_count,
        "artifact_sha256": artifact.artifact_sha256,
        "input_count": len(inputs),
        "state": "frozen",
        "research_authority": False,
        "execution_authority": False,
        "next_action": "Bind this feature beside its exact frozen crypto snapshot.",
    }


def _feature_projection(store: CryptoBulkStore, manifest: dict[str, object]) -> dict[str, object]:
    if (
        manifest.get("artifact_kind") != "derived"
        or manifest.get("derived_kind") != "crypto-feature"
        or not isinstance(manifest.get("metadata"), dict)
    ):
        raise DataError("crypto feature manifest is invalid")
    metadata = cast(dict[str, object], manifest["metadata"])
    if (
        metadata.get("research_authority") is not False
        or metadata.get("execution_authority") is not False
        or not isinstance(metadata.get("input_manifest_ids_by_name"), list)
    ):
        raise DataError("crypto feature authority metadata is invalid")
    artifact = CryptoFeatureArtifactV1.from_dict(metadata.get("feature"))
    if manifest.get("artifact_sha256") != artifact.artifact_sha256:
        raise DataError("crypto feature manifest does not match its artifact contract")
    named_inputs = cast(list[object], metadata["input_manifest_ids_by_name"])
    expected_names = _FEATURE_INPUT_NAMES[artifact.feature_name]
    lineage_ids = manifest.get("input_manifest_ids")
    if (
        tuple(name for name, _digest in artifact.input_sha256) != expected_names
        or len(named_inputs) != len(artifact.input_sha256)
        or not isinstance(lineage_ids, list)
        or len(lineage_ids) != len(named_inputs)
    ):
        raise DataError("crypto feature input lineage is incomplete")
    for item, lineage_id, (expected_name, expected_hash) in zip(
        named_inputs, lineage_ids, artifact.input_sha256, strict=True
    ):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or item[0] != expected_name
            or not isinstance(item[1], str)
            or item[1] != lineage_id
            or store.verify_manifest(item[1]).get("artifact_sha256") != expected_hash
        ):
            raise DataError("crypto feature input lineage is invalid")
    manifest_id = manifest.get("manifest_id")
    if not isinstance(manifest_id, str):
        raise DataError("crypto feature manifest id is invalid")
    return {
        "manifest_id": manifest_id,
        "feature_id": artifact.feature_id,
        "feature_name": artifact.feature_name,
        "method_version": artifact.method_version,
        "available_at": artifact.available_at.isoformat(),
        "row_count": artifact.row_count,
        "artifact_sha256": artifact.artifact_sha256,
        "input_count": len(artifact.input_sha256),
        "state": "verified",
        "research_authority": False,
        "execution_authority": False,
    }


@crypto_data_app.command("feature-create")
def feature_create(
    feature_name: str,
    inputs: Annotated[
        list[str] | None,
        typer.Option("--input", help="repeat exact NAME=MANIFEST_ID"),
    ] = None,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Materialize one immutable provenance-bound research feature."""
    parsed: list[tuple[str, str]] = []
    for value in inputs or ():
        if "=" not in value:
            raise typer.BadParameter("feature input must be NAME=MANIFEST_ID")
        name, manifest_id = value.split("=", 1)
        if _SHA256.fullmatch(manifest_id) is None:
            raise typer.BadParameter("feature input manifest id is invalid")
        parsed.append((name, manifest_id))
    expected = _FEATURE_INPUT_NAMES.get(feature_name)
    if expected is None:
        raise typer.BadParameter("crypto feature name is unsupported")
    by_name = dict(parsed)
    if len(by_name) != len(parsed) or set(by_name) != set(expected):
        raise typer.BadParameter(
            f"crypto {feature_name} feature requires inputs: {', '.join(expected)}"
        )
    ordered = tuple((name, by_name[name]) for name in expected)
    try:
        result = _create_feature(feature_name, inputs=ordered, available_at=_now())
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(result, json_out=json_out)


@crypto_data_app.command("features")
def features(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List immutable derived crypto features after full lineage re-verification."""
    try:
        store = _bulk_store()
        items = [
            _feature_projection(store, manifest)
            for manifest in store.inventory()
            if manifest.get("artifact_kind") == "derived"
            and manifest.get("derived_kind") == "crypto-feature"
        ]
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    items.sort(key=lambda item: (str(item["feature_name"]), str(item["manifest_id"])))
    _emit(
        {
            "items": items,
            "count": len(items),
            "research_authority": False,
            "execution_authority": False,
            "next_action": "Create only a feature supported by exact qualified inputs.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("feature-show")
def feature_show(
    manifest_id: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Reverify one immutable derived feature and its exact input lineage."""
    try:
        store = _bulk_store()
        result = _feature_projection(store, store.verify_manifest(manifest_id))
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(result, json_out=json_out)


def _comparison_frame(
    store: CryptoBulkStore, manifest_id: str
) -> tuple[dict[str, object], CryptoDatasetIdentityV1, CryptoQualityReportV1, pl.DataFrame]:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto comparison inputs must be normalized manifests")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    report = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if report.state != "qualified" or report.failures or report.warnings:
        raise DataError("crypto comparison inputs must be exactly qualified")
    artifact_key = manifest.get("artifact_key")
    if not isinstance(artifact_key, str):
        raise DataError("crypto comparison artifact key is invalid")
    try:
        frame = pl.read_parquet(store.bulk_root / artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("crypto comparison artifact is unreadable") from exc
    if "timestamp" not in frame.columns and "open_time" in frame.columns:
        frame = frame.rename({"open_time": "timestamp"})
    return manifest, dataset, report, frame


@crypto_data_app.command("compare")
def compare(
    primary_manifest_id: Annotated[
        str, typer.Option("--primary-manifest-id", help="authoritative market-bars manifest")
    ],
    comparison_manifest_ids: Annotated[
        list[str],
        typer.Option(
            "--comparison-manifest-id",
            help="independent ccxt:coinbase or Bybit spot comparison manifest",
        ),
    ],
    warning_bps: float = typer.Option(100.0, min=0.000001),
    quarantine_bps: float = typer.Option(500.0, min=0.000001),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Persist non-substituting cross-venue close-price divergence diagnostics."""
    if not comparison_manifest_ids or len(set(comparison_manifest_ids)) != len(
        comparison_manifest_ids
    ):
        raise typer.BadParameter("--comparison-manifest-id must contain unique manifests")
    try:
        store = _bulk_store()
        primary_manifest, primary, primary_quality, primary_frame = _comparison_frame(
            store, primary_manifest_id
        )
        if primary.family != "market_bars" or primary.provider != FAMILY_AUTHORITIES["market_bars"]:
            raise DataError("crypto comparison primary must be authoritative Binance market bars")
        comparisons: list[tuple[str, str, pl.DataFrame]] = []
        for manifest_id in comparison_manifest_ids:
            _manifest, dataset, report, frame = _comparison_frame(store, manifest_id)
            if dataset.family != "comparison_bars" or dataset.provider not in {
                "ccxt:coinbase",
                "bybit",
            }:
                raise DataError("crypto comparison source must be Coinbase or Bybit spot bars")
            if dataset.market_type != "spot" or (
                dataset.base_asset,
                dataset.quote_asset,
                dataset.frequency,
            ) != (primary.base_asset, primary.quote_asset, primary.frequency):
                raise DataError(
                    "crypto comparison sources must match exact spot base, quote, and frequency"
                )
            comparisons.append((dataset.provider, report.dataset_sha256, frame))
        diagnostics, summary = compare_market_observations(
            primary=primary_frame,
            primary_provider=primary.provider,
            primary_sha256=primary_quality.dataset_sha256,
            comparisons=tuple(comparisons),
            timestamp_column="timestamp",
            value_column="close",
            warning_bps=warning_bps,
            quarantine_bps=quarantine_bps,
        )
        output = io.BytesIO()
        diagnostics.write_parquet(output, compression="zstd", statistics=True)
        derived = store.publish_derived(
            output.getvalue(),
            derived_kind="market-comparison",
            input_manifest_ids=(primary_manifest_id, *comparison_manifest_ids),
            metadata=summary.to_dict()
            | {
                "primary_provider": primary.provider,
                "automatic_substitution": False,
                "execution_authority": False,
            },
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        summary.to_dict()
        | {
            "manifest_id": derived["manifest_id"],
            "artifact_sha256": derived["artifact_sha256"],
            "automatic_substitution": False,
            "execution_authority": False,
            "next_action": (
                "Review or quarantine the primary dataset; no provider was substituted."
                if summary.state != "qualified"
                else "The exact cross-venue diagnostic is qualified."
            ),
        },
        json_out=json_out,
    )


def _qualified_normalized_frame(
    store: CryptoBulkStore, manifest_id: str, *, family: CryptoFamily
) -> tuple[pl.DataFrame, CryptoQualityReportV1]:
    manifest = store.verify_manifest(manifest_id)
    if manifest.get("artifact_kind") != "normalized":
        raise DataError("crypto asset-master sources must be normalized artifacts")
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality_report = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if dataset.family != family or dataset.provider != FAMILY_AUTHORITIES[family]:
        raise DataError(f"crypto asset-master source is not authoritative {family}")
    if quality_report.state != "qualified":
        raise DataError("crypto asset-master sources must be mechanically qualified")
    artifact_key = manifest.get("artifact_key")
    if not isinstance(artifact_key, str):
        raise DataError("crypto asset-master source artifact key is invalid")
    try:
        frame = pl.read_parquet(store.bulk_root / artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("crypto asset-master source artifact is unreadable") from exc
    return frame, quality_report


def _latest_profile_source(
    store: CryptoBulkStore,
    *,
    provider: str,
    family: CryptoFamily,
    as_of: datetime,
    instrument: str | None = None,
    base_asset: str | None = None,
    quote_asset: str | None = None,
) -> tuple[str, CryptoDatasetIdentityV1, pl.DataFrame]:
    candidates: list[tuple[str, str, CryptoDatasetIdentityV1, dict[str, object]]] = []
    for manifest in store.inventory():
        if manifest.get("artifact_kind") != "normalized":
            continue
        dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
        quality_report = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        if (
            dataset.provider != provider
            or dataset.family != family
            or quality_report.state != "qualified"
            or (instrument is not None and dataset.instrument != instrument)
            or (base_asset is not None and dataset.base_asset != base_asset)
            or (quote_asset is not None and dataset.quote_asset != quote_asset)
        ):
            continue
        row = _coverage_row(manifest, store=store)
        fetched_at = row.get("fetched_at")
        if not isinstance(fetched_at, str):
            continue
        try:
            fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise DataError("crypto coverage-profile source time is invalid") from exc
        if fetched > as_of:
            continue
        manifest_id = manifest.get("manifest_id")
        if not isinstance(manifest_id, str):
            raise DataError("crypto coverage-profile source id is invalid")
        candidates.append((fetched.isoformat(), manifest_id, dataset, manifest))
    if not candidates:
        identity = instrument or f"{base_asset or '*'}:{quote_asset or '*'}"
        raise DataError(f"no qualified {provider} {family} source is available for {identity}")
    _, manifest_id, dataset, manifest = max(candidates, key=lambda item: (item[0], item[1]))
    artifact_key = manifest.get("artifact_key")
    if not isinstance(artifact_key, str):
        raise DataError("crypto coverage-profile source artifact key is invalid")
    try:
        frame = pl.read_parquet(store.bulk_root / artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("crypto coverage-profile source artifact is unreadable") from exc
    return manifest_id, dataset, frame


_DEFAULT_BINANCE_HOURLY_SCOPES: Final = (
    ("spot", "USDT"),
    ("linear", "USDT"),
    ("inverse", "USD"),
)


def _latest_binance_liquidity_sources(
    store: CryptoBulkStore, *, as_of: datetime
) -> tuple[tuple[str, tuple[str, str], pl.DataFrame], ...]:
    candidates: dict[tuple[str, str], list[tuple[date, str, dict[str, object]]]] = {
        scope: [] for scope in _DEFAULT_BINANCE_HOURLY_SCOPES
    }
    for manifest in store.inventory():
        if (
            manifest.get("artifact_kind") != "derived"
            or manifest.get("derived_kind") != "binance-liquidity-membership"
            or not isinstance(manifest.get("metadata"), dict)
        ):
            continue
        metadata = cast(dict[str, object], manifest["metadata"])
        scope = (metadata.get("category"), metadata.get("quote_asset"))
        if scope not in candidates:
            continue
        if (
            metadata.get("schema_version") != 1
            or metadata.get("method_version") != "binance-prior-day-liquidity-v1"
            or metadata.get("execution_authority") is not False
            or not isinstance(metadata.get("session"), str)
        ):
            raise DataError("Binance liquidity-membership metadata is invalid")
        try:
            session = date.fromisoformat(cast(str, metadata["session"]))
        except ValueError as exc:
            raise DataError("Binance liquidity-membership session is invalid") from exc
        if datetime.combine(session + timedelta(days=1), datetime.min.time(), tzinfo=UTC) > as_of:
            continue
        manifest_id = manifest.get("manifest_id")
        if not isinstance(manifest_id, str):
            raise DataError("Binance liquidity-membership manifest id is invalid")
        candidates[scope].append((session, manifest_id, manifest))
    selected: list[tuple[str, tuple[str, str], pl.DataFrame]] = []
    for scope in _DEFAULT_BINANCE_HOURLY_SCOPES:
        if not candidates[scope]:
            continue
        _session, manifest_id, manifest = max(
            candidates[scope], key=lambda item: (item[0], item[1])
        )
        selected.append((manifest_id, scope, _parquet_frame(store, manifest)))
    return tuple(selected)


def _profile_summary(profile: CryptoCoverageProfileV1) -> dict[str, object]:
    providers: dict[str, int] = {}
    cadences: dict[str, int] = {}
    families: dict[str, int] = {}
    for task in profile.tasks:
        providers[task.provider] = providers.get(task.provider, 0) + 1
        cadences[task.cadence] = cadences.get(task.cadence, 0) + 1
        families[task.family] = families.get(task.family, 0) + 1
    return {
        "profile_id": profile.profile_id,
        "as_of": profile.as_of.isoformat(),
        "source_manifest_ids": list(profile.source_manifest_ids),
        "task_count": len(profile.tasks),
        "counts_by_provider": providers,
        "counts_by_cadence": cadences,
        "counts_by_family": families,
        "execution_authority": False,
    }


@crypto_data_app.command("profile-create")
def profile_create(
    as_of: str | None = typer.Option(None, help="point-in-time ISO-8601 membership clock"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze the default coverage tasks from exact qualified Bybit catalogs."""
    try:
        instant = _now() if as_of is None else datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise DataError("crypto coverage-profile as_of must include a timezone")
        instant = instant.astimezone(UTC)
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
        catalog_sources = tuple(
            _latest_profile_source(
                store,
                provider="bybit",
                family="instrument_catalog",
                instrument=category,
                as_of=instant,
            )
            for category in ("linear", "inverse", "option")
        )
        linear, inverse, options = (source[2] for source in catalog_sources)
        option_sources: list[tuple[str, tuple[str, str], pl.DataFrame]] = []
        for base, quote in active_option_markets(options, as_of=instant):
            manifest_id, _dataset, frame = _latest_profile_source(
                store,
                provider="bybit",
                family="option_quotes",
                base_asset=base,
                quote_asset=quote,
                as_of=instant,
            )
            option_sources.append((manifest_id, (base, quote), frame))
        option_oi: dict[tuple[str, str], float] = {}
        for _manifest_id, market, frame in option_sources:
            if "open_interest" not in frame.columns:
                raise DataError("Bybit option quote source has no open-interest observations")
            total = frame.select(pl.col("open_interest").fill_null(0.0).sum()).item()
            if not isinstance(total, int | float) or isinstance(total, bool):
                raise DataError("Bybit aggregate option open interest is invalid")
            option_oi[market] = float(total)
        binance_sources = tuple(
            _latest_profile_source(
                store,
                provider="binance",
                family="market_membership",
                instrument=category,
                as_of=instant,
            )
            for category in ("spot", "linear", "inverse")
        )
        hourly_sources = _latest_binance_liquidity_sources(store, as_of=instant)
        tasks = build_default_coverage_tasks(
            linear_catalog=linear,
            inverse_catalog=inverse,
            option_catalog=options,
            option_open_interest=option_oi,
            as_of=instant,
            binance_memberships=tuple(source[2] for source in binance_sources),
            binance_hourly_memberships=tuple(source[2] for source in hourly_sources),
        )
        profile = CryptoCoverageProfileV1.create(
            as_of=instant,
            source_manifest_ids=tuple(
                [source[0] for source in catalog_sources]
                + [source[0] for source in option_sources]
                + [source[0] for source in binance_sources]
                + [source[0] for source in hourly_sources]
            ),
            tasks=tasks,
        )
        _write_coverage_profile(profile)
    except (ValueError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        _profile_summary(profile)
        | {
            "state": "frozen",
            "binance_hourly_scopes": [list(source[1]) for source in hourly_sources],
            "binance_hourly_missing_scopes": [
                list(scope)
                for scope in _DEFAULT_BINANCE_HOURLY_SCOPES
                if scope not in {source[1] for source in hourly_sources}
            ],
            "next_action": (
                "Acquire the complete prior-day daily scope, then freeze hourly membership."
                if len(hourly_sources) < len(_DEFAULT_BINANCE_HOURLY_SCOPES)
                else "Inspect a bounded task page before running one cadence batch."
            ),
        },
        json_out=json_out,
    )


@crypto_data_app.command("profile-show")
def profile_show(
    profile_id: str,
    offset: int = typer.Option(0, min=0),
    limit: int = typer.Option(50, min=1, max=100),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Inspect a bounded page of one immutable coverage profile."""
    try:
        profile = _read_coverage_profile(profile_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    page = profile.tasks[offset : offset + limit]
    _emit(
        _profile_summary(profile)
        | {
            "offset": offset,
            "limit": limit,
            "items": [task.to_dict() for task in page],
            "has_more": offset + len(page) < len(profile.tasks),
            "next_offset": offset + len(page) if offset + len(page) < len(profile.tasks) else None,
            "next_action": "Run only the intended bounded cadence batch.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("profiles")
def profiles(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List immutable coverage profiles without exposing their full task membership."""
    try:
        root = _coverage_profile_root()
        items = (
            [
                _profile_summary(_read_coverage_profile(path.stem))
                for path in sorted(root.glob("*.json"))
            ]
            if root.exists()
            else []
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "items": items,
            "count": len(items),
            "execution_authority": False,
            "next_action": "Create a fresh profile after catalog membership changes.",
        },
        json_out=json_out,
    )


def _parquet_frame(store: CryptoBulkStore, manifest: dict[str, object]) -> pl.DataFrame:
    artifact_key = manifest.get("artifact_key")
    if not isinstance(artifact_key, str):
        raise DataError("crypto normalized artifact key is invalid")
    try:
        return pl.read_parquet(store.bulk_root / artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("crypto normalized artifact is unreadable") from exc


def _freeze_binance_liquidity(
    profile: CryptoCoverageProfileV1,
    *,
    category: Literal["spot", "linear", "inverse"],
    quote_asset: str,
    session: date,
    limit: int,
) -> dict[str, object]:
    store = _bulk_store()
    store.verify_ready(required_bytes=0)
    for manifest_id in profile.source_manifest_ids:
        store.verify_manifest(manifest_id)
    expected = tuple(
        task
        for task in profile.tasks
        if task.provider == "binance"
        and task.family == "market_bars"
        and task.category == category
        and task.quote_asset == quote_asset
        and task.frequency == "1d"
    )
    if not expected:
        raise DataError("Binance liquidity profile scope has no daily market membership")
    membership_id: str | None = None
    contract_sizes: dict[str, float | None] = {}
    for source_id in profile.source_manifest_ids:
        source = store.verify_manifest(source_id)
        if source.get("artifact_kind") != "normalized":
            continue
        dataset = CryptoDatasetIdentityV1.from_dict(source.get("dataset"))
        if (
            dataset.provider == "binance"
            and dataset.family == "market_membership"
            and dataset.instrument == category
        ):
            if membership_id is not None:
                raise DataError("Binance liquidity profile has duplicate membership sources")
            membership_id = source_id
            membership = _parquet_frame(store, source)
            if not {"symbol", "contract_size"}.issubset(membership.columns):
                raise DataError("Binance liquidity membership lacks contract units")
            contract_sizes = {
                str(row["symbol"]): (
                    float(row["contract_size"]) if row["contract_size"] is not None else None
                )
                for row in membership.select("symbol", "contract_size").iter_rows(named=True)
            }
    if membership_id is None:
        raise DataError("Binance liquidity profile membership source is unavailable")
    session_at = datetime.combine(session, datetime.min.time(), tzinfo=UTC)
    expected_by_symbol = {task.instrument: task for task in expected}
    candidates: dict[str, list[tuple[str, dict[str, object]]]] = {
        symbol: [] for symbol in expected_by_symbol
    }
    for manifest in store.inventory():
        if manifest.get("artifact_kind") != "normalized":
            continue
        dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
        task = expected_by_symbol.get(dataset.instrument)
        if (
            task is None
            or dataset.provider != "binance"
            or dataset.family != "market_bars"
            or dataset.market_type != category
            or dataset.base_asset != task.base_asset
            or dataset.quote_asset != quote_asset
            or dataset.frequency != "1d"
        ):
            continue
        quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        if quality.state != "qualified" or quality.failures or quality.warnings:
            continue
        frame = _parquet_frame(store, manifest)
        if not {"open_time", "base_volume", "quote_volume"}.issubset(frame.columns):
            raise DataError("Binance daily liquidity artifact schema is incomplete")
        row = frame.filter(pl.col("open_time") == session_at)
        if row.height != 1:
            continue
        values = row.select("base_volume", "quote_volume").row(0, named=True)
        candidate_id = manifest.get("manifest_id")
        if not isinstance(candidate_id, str):
            raise DataError("Binance daily liquidity manifest id is invalid")
        candidates[dataset.instrument].append((candidate_id, values))
    missing = tuple(symbol for symbol, items in candidates.items() if not items)
    if missing:
        raise DataError(
            f"Binance liquidity scope is incomplete for {len(missing)} of {len(expected)} markets"
        )
    observations: list[dict[str, object]] = []
    input_ids: list[str] = [membership_id]
    for symbol, task in expected_by_symbol.items():
        items = candidates[symbol]
        distinct = {
            (
                float(cast(float, values["base_volume"])),
                float(cast(float, values["quote_volume"])),
            )
            for _manifest_id, values in items
        }
        if len(distinct) != 1:
            raise DataError("Binance liquidity scope contains conflicting qualified daily bytes")
        selected_id, values = min(items, key=lambda item: item[0])
        input_ids.append(selected_id)
        observations.append(
            {
                "session": session_at,
                "category": category,
                "symbol": symbol,
                "base_asset": task.base_asset,
                "quote_asset": quote_asset,
                "base_volume": float(cast(float, values["base_volume"])),
                "quote_volume": float(cast(float, values["quote_volume"])),
                "contract_size": contract_sizes.get(symbol),
            }
        )
    selected = point_in_time_liquid_markets(
        pl.DataFrame(observations),
        as_of=session_at + timedelta(days=1),
        category=category,
        quote_asset=quote_asset,
        limit=limit,
    )
    output = io.BytesIO()
    selected.write_parquet(output, compression="zstd", statistics=True)
    derived = store.publish_derived(
        output.getvalue(),
        derived_kind="binance-liquidity-membership",
        input_manifest_ids=tuple(input_ids),
        metadata={
            "schema_version": 1,
            "profile_id": profile.profile_id,
            "session": session.isoformat(),
            "category": category,
            "quote_asset": quote_asset,
            "universe_count": len(expected),
            "selected_count": selected.height,
            "limit": limit,
            "method_version": "binance-prior-day-liquidity-v1",
            "execution_authority": False,
        },
    )
    return {
        "manifest_id": derived["manifest_id"],
        "profile_id": profile.profile_id,
        "session": session.isoformat(),
        "category": category,
        "quote_asset": quote_asset,
        "universe_count": len(expected),
        "selected_count": selected.height,
        "state": "frozen",
        "execution_authority": False,
        "next_action": "Create a fresh profile to admit this exact hourly membership.",
    }


@crypto_data_app.command("liquidity-freeze")
def liquidity_freeze(
    profile_id: str,
    category: str = typer.Option(..., help="exact spot, linear, or inverse unit scope"),
    quote_asset: str = typer.Option(..., help="exact quote asset; never cross-ranked"),
    session: str = typer.Option(..., help="complete UTC session YYYY-MM-DD"),
    limit: int = typer.Option(250, min=1, max=250),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze one complete prior-day top-liquidity scope without cross-unit ranking."""
    if category not in {"spot", "linear", "inverse"}:
        raise typer.BadParameter("liquidity category must be spot, linear, or inverse")
    try:
        result = _freeze_binance_liquidity(
            _read_coverage_profile(profile_id),
            category=cast(Literal["spot", "linear", "inverse"], category),
            quote_asset=quote_asset.strip().upper(),
            session=date.fromisoformat(session),
            limit=limit,
        )
    except (ValueError, DataError) as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(result, json_out=json_out)


def _select_one_minute_profile(
    profile: CryptoCoverageProfileV1,
    *,
    case_id: str,
    expected_case_revision: str,
    markets: tuple[str, ...],
    reason: str,
) -> tuple[CryptoCoverageProfileV1, dict[str, object]]:
    if not 1 <= len(markets) <= 50 or len(set(markets)) != len(markets):
        raise DataError("Binance one-minute selection requires 1 to 50 unique markets")
    if not reason.strip() or len(reason.strip()) > 500:
        raise DataError("Binance one-minute selection reason is invalid")
    current = _control_store().research_case_summary(case_id)
    revision = research_case_revision(current)
    if revision != expected_case_revision:
        raise DataError("research case changed before one-minute selection; refresh and retry")
    daily: dict[tuple[str, str], CryptoCoverageTaskV1] = {
        (task.category, task.instrument): task
        for task in profile.tasks
        if task.provider == "binance"
        and task.family == "market_bars"
        and task.frequency == "1d"
        and task.category is not None
    }
    selected: list[CryptoCoverageTaskV1] = []
    selection_rows: list[dict[str, object]] = []
    for market in markets:
        try:
            category, symbol = market.split(":", 1)
        except ValueError as exc:
            raise DataError("Binance one-minute market must be CATEGORY:SYMBOL") from exc
        category, symbol = category.strip().lower(), symbol.strip().upper()
        task = daily.get((category, symbol))
        if task is None:
            raise DataError("Binance one-minute market is outside frozen daily membership")
        one_minute = CryptoCoverageTaskV1(
            provider="binance",
            family="market_bars",
            instrument=task.instrument,
            base_asset=task.base_asset,
            quote_asset=task.quote_asset,
            category=task.category,
            frequency="1m",
            cadence="hourly",
        )
        if one_minute.task_id in {existing.task_id for existing in profile.tasks}:
            raise DataError("Binance one-minute market is already selected in this profile")
        selected.append(one_minute)
        selection_rows.append(
            {
                "category": task.category,
                "symbol": task.instrument,
                "base_asset": task.base_asset,
                "quote_asset": task.quote_asset,
                "task_id": one_minute.task_id,
            }
        )
    store = _bulk_store()
    membership_inputs: list[str] = []
    selected_categories = {task.category for task in selected}
    for source_id in profile.source_manifest_ids:
        manifest = store.verify_manifest(source_id)
        if manifest.get("artifact_kind") != "normalized":
            continue
        dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
        if (
            dataset.provider == "binance"
            and dataset.family == "market_membership"
            and dataset.instrument in selected_categories
        ):
            membership_inputs.append(source_id)
    if len(membership_inputs) != len(selected_categories):
        raise DataError("Binance one-minute selection membership sources are incomplete")
    output = io.BytesIO()
    pl.DataFrame(selection_rows).sort(["category", "symbol"]).write_parquet(
        output, compression="zstd", statistics=True
    )
    receipt = store.publish_derived(
        output.getvalue(),
        derived_kind="binance-research-selection",
        input_manifest_ids=tuple(sorted(membership_inputs)),
        metadata={
            "schema_version": 1,
            "base_profile_id": profile.profile_id,
            "project_id": case_id,
            "case_revision": revision,
            "reason": reason.strip(),
            "selected_count": len(selected),
            "frequency": "1m",
            "acquisition_window": "previous_complete_hour",
            "execution_authority": False,
        },
    )
    if research_case_revision(_control_store().research_case_summary(case_id)) != revision:
        raise DataError("research case changed during one-minute selection; refresh and retry")
    receipt_id = receipt.get("manifest_id")
    if not isinstance(receipt_id, str):
        raise DataError("Binance one-minute selection receipt id is invalid")
    updated = CryptoCoverageProfileV1.create(
        as_of=_now(),
        source_manifest_ids=(*profile.source_manifest_ids, receipt_id),
        tasks=(*profile.tasks, *selected),
    )
    _write_coverage_profile(updated)
    return updated, {
        "profile_id": updated.profile_id,
        "base_profile_id": profile.profile_id,
        "selection_manifest_id": receipt_id,
        "project_id": case_id,
        "case_revision": revision,
        "selected_count": len(selected),
        "frequency": "1m",
        "acquisition_window": "previous_complete_hour",
        "state": "frozen",
        "execution_authority": False,
        "next_action": "Run only the intended bounded hourly profile page.",
    }


@crypto_data_app.command("profile-select-one-minute")
def profile_select_one_minute(
    profile_id: str,
    case_id: str = typer.Option(..., help="existing governed research project"),
    expected_case_revision: str = typer.Option(..., help="fresh research-case revision"),
    markets: Annotated[
        list[str] | None,
        typer.Option("--market", help="repeat CATEGORY:SYMBOL; maximum 50 exact markets"),
    ] = None,
    reason: str = typer.Option(..., help="bounded research purpose for this high-resolution tier"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Bind at most 50 exact one-minute markets to a fresh research-case revision."""
    try:
        _updated, result = _select_one_minute_profile(
            _read_coverage_profile(profile_id),
            case_id=case_id,
            expected_case_revision=expected_case_revision,
            markets=tuple(markets or ()),
            reason=reason,
        )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(result, json_out=json_out)


def _batch_digest(body: dict[str, object]) -> str:
    payload = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _batch_directory(batch_id: str) -> Path:
    if _SHA256.fullmatch(batch_id) is None:
        raise DataError("crypto coverage-batch id is invalid")
    return _coverage_batch_root() / batch_id


def _write_batch_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _create_coverage_batch(
    profile: CryptoCoverageProfileV1,
    *,
    cadence: CoverageCadence,
    offset: int,
    limit: int,
    run_at: datetime,
) -> tuple[str, dict[str, object]]:
    selected = tuple(task for task in profile.tasks if task.cadence == cadence)[
        offset : offset + limit
    ]
    if not selected:
        raise DataError("crypto coverage batch selection is empty")
    body: dict[str, object] = {
        "schema_version": 1,
        "profile_id": profile.profile_id,
        "cadence": cadence,
        "profile_offset": offset,
        "run_at": run_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
        "tasks": [task.to_dict() for task in selected],
        "execution_authority": False,
    }
    batch_id = _batch_digest(body)
    root = _batch_directory(batch_id)
    plan = {**body, "batch_id": batch_id}
    plan_path = root / "plan.json"
    if plan_path.exists():
        if json.loads(plan_path.read_text(encoding="utf-8")) != plan:
            raise DataError("crypto coverage-batch identity collision")
    else:
        _write_batch_json(plan_path, plan)
    checkpoint_path = root / "checkpoint.json"
    if not checkpoint_path.exists():
        _write_batch_json(
            checkpoint_path,
            {
                "schema_version": 1,
                "batch_id": batch_id,
                "next_index": 0,
                "results": [],
                "results_sha256": _batch_digest({"results": []}),
                "state": "running",
                "error": None,
                "updated_at": run_at.astimezone(UTC).isoformat().replace("+00:00", "Z"),
                "execution_authority": False,
            },
        )
    return batch_id, plan


def _read_coverage_batch(batch_id: str) -> tuple[dict[str, object], dict[str, object]]:
    root = _batch_directory(batch_id)
    try:
        plan = json.loads((root / "plan.json").read_text(encoding="utf-8"))
        checkpoint = json.loads((root / "checkpoint.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DataError("crypto coverage batch is unavailable or corrupt") from exc
    if not isinstance(plan, dict) or plan.get("batch_id") != batch_id:
        raise DataError("crypto coverage-batch plan identity is invalid")
    body = {key: value for key, value in plan.items() if key != "batch_id"}
    if (
        set(body)
        != {
            "schema_version",
            "profile_id",
            "cadence",
            "profile_offset",
            "run_at",
            "tasks",
            "execution_authority",
        }
        or body.get("schema_version") != 1
        or body.get("execution_authority") is not False
        or _batch_digest(body) != batch_id
        or not isinstance(body.get("tasks"), list)
    ):
        raise DataError("crypto coverage-batch plan integrity failure")
    tasks = tuple(
        CryptoCoverageTaskV1.from_dict(item) for item in cast(list[object], body["tasks"])
    )
    if not tasks or len(tasks) > 25:
        raise DataError("crypto coverage-batch task membership is invalid")
    if not isinstance(checkpoint, dict) or set(checkpoint) != {
        "schema_version",
        "batch_id",
        "next_index",
        "results",
        "results_sha256",
        "state",
        "error",
        "updated_at",
        "execution_authority",
    }:
        raise DataError("crypto coverage-batch checkpoint is invalid")
    results = checkpoint.get("results")
    next_index = checkpoint.get("next_index")
    if (
        checkpoint.get("schema_version") != 1
        or checkpoint.get("batch_id") != batch_id
        or checkpoint.get("execution_authority") is not False
        or checkpoint.get("state") not in {"running", "failed", "completed"}
        or not isinstance(results, list)
        or checkpoint.get("results_sha256") != _batch_digest({"results": results})
        or not isinstance(next_index, int)
        or isinstance(next_index, bool)
        or next_index != len(results)
        or not 0 <= next_index <= len(tasks)
        or (checkpoint.get("state") == "completed") != (next_index == len(tasks))
        or (checkpoint.get("state") == "failed") != isinstance(checkpoint.get("error"), str)
        or any(
            not isinstance(result, dict)
            or result.get("task_id") != tasks[index].task_id
            or _SHA256.fullmatch(str(result.get("normalized_manifest_id"))) is None
            for index, result in enumerate(results)
        )
    ):
        raise DataError("crypto coverage-batch checkpoint integrity failure")
    return plan, checkpoint


def _run_profile_task(task: CryptoCoverageTaskV1, *, run_at: datetime) -> dict[str, object]:
    start: str | None = None
    end: str | None = None
    if task.provider == "binance" and task.family == "market_bars":
        if task.frequency == "1d":
            end_day = run_at.astimezone(UTC).date()
            start_at = datetime.combine(
                end_day - timedelta(days=1), datetime.min.time(), tzinfo=UTC
            )
            end_at = datetime.combine(end_day, datetime.min.time(), tzinfo=UTC) - timedelta(
                milliseconds=1
            )
        elif task.frequency in {"1h", "1m"}:
            completed_at = run_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
            start_at = completed_at - timedelta(hours=1)
            end_at = completed_at - timedelta(milliseconds=1)
        else:
            raise DataError("Binance profile market-bar frequency is unsupported")
        start, end = start_at.isoformat(), end_at.isoformat()
    if task.provider == "coinmetrics":
        if task.lookback_days is None:
            raise DataError("Coin Metrics coverage task has no lookback")
        end_day = (run_at.astimezone(UTC) - timedelta(days=1)).date()
        start_day = end_day - timedelta(days=task.lookback_days - 1)
        start, end = start_day.isoformat(), end_day.isoformat()
    return _acquire_result(
        task.provider,
        task.family,
        task.instrument,
        base=task.base_asset or "ALL",
        quote=task.quote_asset or "USD",
        category=task.category or "spot",
        frequency=task.frequency,
        period=None,
        network=task.network,
        pool_address=None,
        metrics=",".join(task.metrics) or None,
        start=start,
        end=end,
        case_id=None,
        expected_case_revision=None,
        reason=None,
    )


def _execute_coverage_batch(batch_id: str) -> dict[str, object]:
    plan, checkpoint = _read_coverage_batch(batch_id)
    profile_id = plan.get("profile_id")
    if not isinstance(profile_id, str):
        raise DataError("crypto coverage-batch profile identity is invalid")
    profile = _read_coverage_profile(profile_id)
    store = _bulk_store()
    for manifest_id in profile.source_manifest_ids:
        store.verify_manifest(manifest_id)
    tasks = tuple(
        CryptoCoverageTaskV1.from_dict(item) for item in cast(list[object], plan["tasks"])
    )
    cadence = plan.get("cadence")
    profile_offset = plan.get("profile_offset")
    if (
        cadence not in {"daily", "hourly", "five_minute", "funding_interval"}
        or not isinstance(profile_offset, int)
        or isinstance(profile_offset, bool)
        or profile_offset < 0
        or tasks
        != tuple(task for task in profile.tasks if task.cadence == cadence)[
            profile_offset : profile_offset + len(tasks)
        ]
    ):
        raise DataError("crypto coverage-batch tasks do not match the frozen profile")
    results = list(cast(list[dict[str, object]], checkpoint["results"]))
    if checkpoint["state"] == "completed":
        return {
            "batch_id": batch_id,
            "profile_id": profile_id,
            "state": "completed",
            "completed_count": len(results),
            "results": results,
            "execution_authority": False,
            "next_action": "Create a new bounded batch when the cadence is next due.",
        }
    run_at = datetime.fromisoformat(str(plan["run_at"]).replace("Z", "+00:00"))
    for index in range(len(results), len(tasks)):
        task = tasks[index]
        try:
            acquired = _run_profile_task(task, run_at=run_at)
        except (DataError, typer.BadParameter) as exc:
            _write_batch_json(
                _batch_directory(batch_id) / "checkpoint.json",
                {
                    "schema_version": 1,
                    "batch_id": batch_id,
                    "next_index": index,
                    "results": results,
                    "results_sha256": _batch_digest({"results": results}),
                    "state": "failed",
                    "error": str(exc),
                    "updated_at": _now().isoformat().replace("+00:00", "Z"),
                    "execution_authority": False,
                },
            )
            raise DataError(
                f"crypto coverage batch {batch_id} stopped at task {task.task_id}; "
                "resume after resolving the reported provider or data blocker"
            ) from exc
        results.append({"task_id": task.task_id, **acquired})
        _write_batch_json(
            _batch_directory(batch_id) / "checkpoint.json",
            {
                "schema_version": 1,
                "batch_id": batch_id,
                "next_index": index + 1,
                "results": results,
                "results_sha256": _batch_digest({"results": results}),
                "state": "completed" if index + 1 == len(tasks) else "running",
                "error": None,
                "updated_at": _now().isoformat().replace("+00:00", "Z"),
                "execution_authority": False,
            },
        )
    return {
        "batch_id": batch_id,
        "profile_id": profile_id,
        "state": "completed",
        "completed_count": len(results),
        "results": results,
        "execution_authority": False,
        "next_action": "Create a new bounded batch when the cadence is next due.",
    }


@crypto_data_app.command("profile-run")
def profile_run(
    profile_id: str,
    cadence: str = typer.Option(..., help="daily, hourly, five_minute, or funding_interval"),
    offset: int = typer.Option(0, min=0),
    limit: int = typer.Option(10, min=1, max=25),
    confirm: bool = typer.Option(False, "--confirm", help="confirm this bounded provider batch"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Run and checkpoint one bounded cadence page from an immutable profile."""
    if not confirm:
        raise typer.BadParameter("profile-run requires --confirm before provider requests")
    if cadence not in {"daily", "hourly", "five_minute", "funding_interval"}:
        raise typer.BadParameter("coverage cadence is invalid")
    try:
        profile = _read_coverage_profile(profile_id)
        batch_id, _plan = _create_coverage_batch(
            profile,
            cadence=cast(CoverageCadence, cadence),
            offset=offset,
            limit=limit,
            run_at=_now(),
        )
        result = _execute_coverage_batch(batch_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(result, json_out=json_out)


@crypto_data_app.command("profile-resume")
def profile_resume(
    batch_id: str,
    confirm: bool = typer.Option(False, "--confirm", help="confirm retry of unfinished tasks"),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Resume exactly one failed or interrupted coverage batch."""
    if not confirm:
        raise typer.BadParameter("profile-resume requires --confirm before provider requests")
    try:
        result = _execute_coverage_batch(batch_id)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(result, json_out=json_out)


@crypto_data_app.command("profile-batches")
def profile_batches(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List bounded coverage batch checkpoints without exposing provider bytes."""
    try:
        root = _coverage_batch_root()
        items: list[dict[str, object]] = []
        for path in sorted(root.glob("*/plan.json")) if root.exists() else ():
            plan, checkpoint = _read_coverage_batch(path.parent.name)
            tasks = cast(list[object], plan["tasks"])
            items.append(
                {
                    "batch_id": path.parent.name,
                    "profile_id": plan["profile_id"],
                    "cadence": plan["cadence"],
                    "profile_offset": plan["profile_offset"],
                    "task_count": len(tasks),
                    "completed_count": checkpoint["next_index"],
                    "state": checkpoint["state"],
                    "updated_at": checkpoint["updated_at"],
                    "execution_authority": False,
                }
            )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "items": items,
            "count": len(items),
            "execution_authority": False,
            "next_action": "Resume only a failed batch after resolving its recorded blocker.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("asset-master-create")
def asset_master_create(
    coingecko_manifest_id: Annotated[
        str, typer.Option("--coingecko-manifest-id", help="qualified asset_metadata manifest")
    ],
    geckoterminal_manifest_ids: Annotated[
        list[str],
        typer.Option("--geckoterminal-manifest-id", help="qualified DEX pool catalog manifest"),
    ],
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze exact cross-provider contract identities; ticker joins remain prohibited."""
    if not geckoterminal_manifest_ids or len(set(geckoterminal_manifest_ids)) != len(
        geckoterminal_manifest_ids
    ):
        raise typer.BadParameter("--geckoterminal-manifest-id must contain unique pool catalogs")
    try:
        store = _bulk_store()
        store.verify_ready(required_bytes=0)
        coingecko, quality_report = _qualified_normalized_frame(
            store, coingecko_manifest_id, family="asset_metadata"
        )
        pools = tuple(
            _qualified_normalized_frame(store, manifest_id, family="dex_pools")[0]
            for manifest_id in geckoterminal_manifest_ids
        )
        if quality_report.observed_end is None:
            raise DataError("CoinGecko asset catalog has no observation time")
        master = build_cross_provider_asset_master(
            coingecko_catalog=coingecko,
            geckoterminal_pools=pools,
            observed_at=quality_report.observed_end,
            source_manifest_ids=(coingecko_manifest_id, *geckoterminal_manifest_ids),
        )
        _write_asset_master(master)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "asset_master_version": master.version,
            "identity_count": len(master.identities),
            "contract_identity_count": sum(
                not identity.native_asset for identity in master.identities
            ),
            "source_manifest_ids": list(master.source_manifest_ids),
            "ticker_join_allowed": False,
            "state": "frozen",
            "next_action": "Use this exact asset-master version when freezing a snapshot.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("asset-master-verify")
def asset_master_verify(
    version: str,
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Rederive a frozen asset master's content identity before snapshot use."""
    try:
        master = _read_asset_master(version)
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "asset_master_version": master.version,
            "identity_count": len(master.identities),
            "contract_identity_count": sum(
                not identity.native_asset for identity in master.identities
            ),
            "source_manifest_ids": list(master.source_manifest_ids),
            "ticker_join_allowed": False,
            "state": "verified",
            "next_action": "Freeze a snapshot bound to this exact asset-master version.",
        },
        json_out=json_out,
    )


@crypto_data_app.command("asset-masters")
def asset_masters(json_out: bool = typer.Option(False, "--json", help="emit JSON")) -> None:
    """List verified asset masters without exposing internal paths or requiring opaque input."""
    try:
        items: list[dict[str, object]] = [
            {
                "asset_master_version": "reviewed-native-v1",
                "identity_count": 2,
                "contract_identity_count": 0,
                "builtin": True,
                "state": "verified",
            }
        ]
        if _asset_master_root().exists():
            for path in sorted(_asset_master_root().glob("*.json")):
                master = _read_asset_master(path.stem)
                items.append(
                    {
                        "asset_master_version": master.version,
                        "identity_count": len(master.identities),
                        "contract_identity_count": sum(
                            not identity.native_asset for identity in master.identities
                        ),
                        "builtin": False,
                        "state": "verified",
                    }
                )
    except DataError as exc:
        raise typer.BadParameter(str(exc)) from exc
    _emit(
        {
            "items": items,
            "count": len(items),
            "ticker_join_allowed": False,
            "next_action": (
                "Select a contract-capable asset master when freezing contract data."
                if len(items) > 1
                else "Acquire CoinGecko metadata and a DEX pool catalog to map contract assets."
            ),
        },
        json_out=json_out,
    )


@crypto_data_app.command("snapshot-create")
def snapshot_create(
    manifest_ids: Annotated[
        list[str], typer.Option("--manifest-id", help="normalized manifest id")
    ],
    asset_master_version: str = typer.Option(
        "reviewed-native-v1", help="exact frozen asset-master version"
    ),
    json_out: bool = typer.Option(False, "--json", help="emit JSON"),
) -> None:
    """Freeze exact ordered qualified membership; source and quote identities remain distinct."""
    if not manifest_ids or len(set(manifest_ids)) != len(manifest_ids):
        raise typer.BadParameter("--manifest-id must contain unique normalized manifests")
    try:
        store = _bulk_store()
        if asset_master_version != "reviewed-native-v1":
            _read_asset_master(asset_master_version)
        resolved = tuple(_normalized_member(store, manifest_id) for manifest_id in manifest_ids)
        snapshot = CryptoSnapshotV1.create(
            members=tuple(member for member, _ in resolved),
            asset_master_version=asset_master_version,
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
            "asset_master_version": snapshot.asset_master_version,
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
