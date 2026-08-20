"""Compose the registered crowding events into the sandbox-only two-leg candidate."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from alpha_core import DataError
from alpha_data.crypto.contracts import (
    CryptoFamily,
    CryptoQualityReportV1,
    CryptoSnapshotMemberV1,
    CryptoSnapshotV1,
)
from alpha_research import (
    CryptoCrowdingObservationV1,
    registered_crypto_crowding_plan,
    select_registered_crypto_crowding_events,
)
from alpha_strategies.hedged_basis import HedgedBasisObservationV1

_SHA256 = re.compile(r"[0-9a-f]{64}")
_CROWDING_FAMILIES: tuple[CryptoFamily, ...] = (
    "funding",
    "open_interest",
    "premium_bars",
    "mark_bars",
    "index_bars",
    "derivative_bars",
    "instrument_catalog",
    "long_short_ratio",
)


def _utc(value: object, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DataError(f"hedged basis Binance {label} timestamp is invalid")
    return value.astimezone(UTC)


def _spot_closes(frame: pl.DataFrame) -> dict[datetime, tuple[datetime, float]]:
    required = {"open_time", "close_time", "close"}
    if (
        not isinstance(frame, pl.DataFrame)
        or frame.is_empty()
        or not required.issubset(frame.columns)
    ):
        raise DataError("hedged basis Binance spot frame is invalid")
    result: dict[datetime, tuple[datetime, float]] = {}
    for open_time, close_time, close in frame.select(
        "open_time", "close_time", "close"
    ).iter_rows():
        key = _utc(open_time, "open")
        available_at = _utc(close_time, "close")
        if key in result:
            raise DataError("hedged basis Binance spot timestamps are duplicated")
        if (
            isinstance(close, bool)
            or not isinstance(close, int | float)
            or not math.isfinite(close)
            or close <= 0.0
            or available_at <= key
        ):
            raise DataError("hedged basis Binance spot close is invalid")
        result[key] = (available_at, float(close))
    return result


def _exact_spot(
    closes: dict[datetime, tuple[datetime, float]],
    *,
    open_time: datetime,
    required_by: datetime,
) -> tuple[datetime, float]:
    try:
        available_at, value = closes[open_time]
    except KeyError as exc:
        raise DataError(
            f"hedged basis missing exact Binance spot close for {open_time.isoformat()}"
        ) from exc
    if available_at > required_by:
        raise DataError("hedged basis Binance spot close is not causally available")
    return available_at, value


def compose_hedged_basis_observations(
    crowding: tuple[CryptoCrowdingObservationV1, ...],
    binance_spot: pl.DataFrame,
    *,
    bybit_snapshot_sha256: str,
    binance_spot_sha256: str,
) -> tuple[HedgedBasisObservationV1, ...]:
    """Bind registered events to exact Binance hourly closes without venue substitution."""
    if (
        _SHA256.fullmatch(bybit_snapshot_sha256) is None
        or _SHA256.fullmatch(binance_spot_sha256) is None
    ):
        raise DataError("hedged basis input hashes are invalid")
    events = select_registered_crypto_crowding_events(crowding)
    closes = _spot_closes(binance_spot)
    plan = registered_crypto_crowding_plan()
    rows: list[HedgedBasisObservationV1] = []
    for event in events:
        source = crowding[event.observation_index]
        entry_available_at, entry_spot = _exact_spot(
            closes,
            open_time=source.funding_time,
            required_by=source.entry_time,
        )
        exit_open = source.exit_time - timedelta(hours=1)
        exit_available_at, exit_spot = _exact_spot(
            closes,
            open_time=exit_open,
            required_by=source.exit_time,
        )
        rows.append(
            HedgedBasisObservationV1.create(
                event_time=source.funding_time,
                event_available_at=max(
                    source.funding_available_at,
                    source.open_interest_available_at,
                    source.premium_available_at,
                    source.diagnostics_available_at,
                ),
                entry_time=source.entry_time,
                entry_available_at=max(source.entry_available_at, entry_available_at),
                exit_time=source.exit_time,
                exit_available_at=max(source.exit_available_at, exit_available_at),
                bybit_perp_entry=source.entry_mark,
                bybit_perp_exit=source.exit_mark,
                binance_spot_entry=entry_spot,
                binance_spot_exit=exit_spot,
                funding_rate=source.funding_rate,
                funding_available_at=source.funding_available_at,
                perp_quantity_btc=-1.0,
                spot_quantity_btc=1.0,
                input_sha256=(
                    ("binance_spot", binance_spot_sha256),
                    ("bybit_linear", bybit_snapshot_sha256),
                ),
                event_operator_fingerprint=plan.operator_fingerprint,
                correction_lineage=source.correction_lineage,
            )
        )
    return tuple(rows)


def _member_digest(members: tuple[CryptoSnapshotMemberV1, ...]) -> str:
    payload = json.dumps(
        [member.to_dict() for member in members],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def load_hedged_basis_observations(
    snapshot: CryptoSnapshotV1,
    quality_reports: Mapping[str, CryptoQualityReportV1],
    *,
    bulk_root: Path,
) -> tuple[HedgedBasisObservationV1, ...]:
    """Load one exact qualified nine-family candidate bundle from verified external bytes."""
    from alpha_cli.research_crypto_data import load_crypto_crowding_observations

    by_family = {member.dataset.family: member for member in snapshot.members}
    expected = {*_CROWDING_FAMILIES, "market_bars"}
    if set(by_family) != expected or len(by_family) != len(snapshot.members):
        raise DataError("hedged basis snapshot is not the exact registered nine-family bundle")
    spot = by_family["market_bars"]
    dataset = spot.dataset
    if (
        dataset.provider != "binance"
        or dataset.venue != "binance"
        or dataset.market_type != "spot"
        or dataset.instrument != "BTCUSDT"
        or dataset.base_asset != "BTC"
        or dataset.quote_asset != "USDT"
        or dataset.frequency != "1h"
        or dataset.units != "provider_native_ohlcv"
        or dataset.timestamp_convention != "interval_start_utc"
    ):
        raise DataError("hedged basis Binance spot dataset identity is invalid")
    for member in snapshot.members:
        report = quality_reports.get(member.artifact_sha256)
        if (
            report is None
            or report.dataset_sha256 != member.artifact_sha256
            or report.method_version not in snapshot.qualification_versions
            or report.state != "qualified"
            or report.failures
            or report.warnings
        ):
            raise DataError("hedged basis snapshot has an unqualified member")
        if report.correction_lineage:
            raise DataError(
                "hedged basis snapshot corrections lack row-level availability timestamps"
            )
    bybit_members = tuple(by_family[family] for family in _CROWDING_FAMILIES)
    bybit_snapshot = CryptoSnapshotV1.create(
        members=bybit_members,
        asset_master_version=snapshot.asset_master_version,
        qualification_versions=snapshot.qualification_versions,
    )
    crowding = load_crypto_crowding_observations(
        bybit_snapshot,
        quality_reports,
        bulk_root=bulk_root,
    )
    try:
        spot_frame = pl.read_parquet(bulk_root / spot.artifact_key)
    except (OSError, pl.exceptions.PolarsError) as exc:
        raise DataError("hedged basis Binance spot member is unreadable") from exc
    return compose_hedged_basis_observations(
        crowding,
        spot_frame,
        bybit_snapshot_sha256=_member_digest(bybit_members),
        binance_spot_sha256=spot.artifact_sha256,
    )


__all__ = ["compose_hedged_basis_observations", "load_hedged_basis_observations"]
