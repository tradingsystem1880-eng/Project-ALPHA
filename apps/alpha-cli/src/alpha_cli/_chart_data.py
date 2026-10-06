"""Read-only discovery and exact verified bulk bars for visualization, never admission."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import polars as pl

from alpha_core import Bar, DataError
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1
from alpha_data.crypto.storage import CryptoBulkStore

_FREQUENCIES = {
    "1m": timedelta(minutes=1),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "6h": timedelta(hours=6),
    "8h": timedelta(hours=8),
    "12h": timedelta(hours=12),
    "1d": timedelta(days=1),
    "3d": timedelta(days=3),
    "1w": timedelta(weeks=1),
}
_TIMEFRAME_LABELS = {
    "1m": "1MIN",
    "5m": "5MIN",
    "15m": "15MIN",
    "30m": "30MIN",
    **{key: key.upper() for key in _FREQUENCIES if key.endswith(("h", "d", "w"))},
}


def _identity(manifest: dict[str, object]) -> tuple[CryptoDatasetIdentityV1, CryptoQualityReportV1]:
    dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
    quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
    if (
        manifest.get("artifact_kind") != "normalized"
        or quality.state != "qualified"
        or quality.dataset_sha256 != manifest.get("artifact_sha256")
        or dataset.provider != manifest.get("provider")
        or dataset.timestamp_convention != "interval_start_utc"
        or dataset.frequency not in _FREQUENCIES
    ):
        raise DataError("dataset is not a qualified supported chart input")
    if not (
        (
            dataset.provider == "binance"
            and dataset.venue == "binance"
            and dataset.units == "provider_native_ohlcv"
            and dataset.family == "market_bars"
            and dataset.market_type == "spot"
        )
        or (
            dataset.provider == "bybit"
            and dataset.venue == "bybit"
            and dataset.units == "quote_price"
            and dataset.family == "derivative_bars"
            and dataset.market_type in {"linear", "inverse", "spot"}
        )
    ):
        raise DataError("dataset family is not supported for OHLCV charts")
    return dataset, quality


def chart_datasets(store: CryptoBulkStore) -> list[dict[str, object]]:
    """Metadata only; selecting a result still requires full artifact/lineage verification."""
    grouped: dict[
        tuple[str, ...],
        list[tuple[dict[str, object], CryptoDatasetIdentityV1, CryptoQualityReportV1]],
    ] = {}
    for manifest in store.metadata_inventory():
        if manifest.get("artifact_kind") != "normalized":
            continue
        dataset = CryptoDatasetIdentityV1.from_dict(manifest.get("dataset"))
        quality = CryptoQualityReportV1.from_dict(manifest.get("quality"))
        if (
            dataset.family not in {"market_bars", "derivative_bars"}
            or quality.state != "qualified"
            or dataset.frequency not in _FREQUENCIES
            or dataset.timestamp_convention != "interval_start_utc"
        ):
            continue
        _identity(manifest)
        identity = (
            dataset.provider,
            dataset.venue,
            dataset.market_type,
            dataset.family,
            dataset.instrument,
            dataset.base_asset or "",
            dataset.quote_asset or "",
            dataset.frequency,
            dataset.units,
            dataset.timestamp_convention,
        )
        grouped.setdefault(identity, []).append((manifest, dataset, quality))
    result: list[dict[str, object]] = []
    for members in grouped.values():
        members.sort(
            key=lambda row: (
                row[2].observed_start.isoformat() if row[2].observed_start else "",
                str(row[0]["manifest_id"]),
            )
        )
        manifest_ids = [str(row[0]["manifest_id"]) for row in members]
        group_id = (
            manifest_ids[0]
            if len(manifest_ids) == 1
            else hashlib.sha256("\n".join(manifest_ids).encode()).hexdigest()
        )
        dataset = members[0][1]
        starts = [row[2].observed_start for row in members if row[2].observed_start]
        ends = [row[2].observed_end for row in members if row[2].observed_end]
        result.append(
            {
                **dataset.to_dict(),
                "manifest_id": group_id,
                "manifest_ids": manifest_ids,
                "manifest_count": len(manifest_ids),
                "start": min(starts).isoformat() if starts else None,
                "end": max(ends).isoformat() if ends else None,
                "row_count": sum(row[2].row_count for row in members),
                "verification": "metadata_only",
            }
        )
    return sorted(
        result,
        key=lambda row: (
            str(row["instrument"]),
            str(row["venue"]),
            str(row["frequency"]),
            str(row["start"]),
            str(row["manifest_id"]),
        ),
    )


def load_chart_dataset(
    store: CryptoBulkStore, manifest_id: str, *, symbol: str, as_of: datetime | None = None
) -> tuple[list[Bar], dict[str, Any]]:
    store.verify_readable()
    available_groups = chart_datasets(store)
    groups = [row for row in available_groups if row["manifest_id"] == manifest_id]
    if not groups:
        # Accept exact artifact IDs from an older open chart tab; new discovery returns a
        # deterministic identity for all compatible archive segments.
        exact = next(
            (
                row
                for row in store.metadata_inventory()
                if row.get("manifest_id") == manifest_id
                and row.get("artifact_kind") == "normalized"
            ),
            None,
        )
        if exact is not None:
            group = next(
                (
                    row
                    for row in available_groups
                    if isinstance(row.get("manifest_ids"), list)
                    and manifest_id in cast(list[str], row["manifest_ids"])
                ),
                None,
            )
            if group is not None:
                groups = [{**group, "manifest_ids": [manifest_id]}]
    if not groups:
        raise DataError("chart dataset group is unavailable")
    group = groups[0]
    raw_manifest_ids = group["manifest_ids"]
    if not isinstance(raw_manifest_ids, list) or not raw_manifest_ids:
        raise DataError("chart dataset group manifest list is invalid")
    manifests = [store.verify_manifest(str(item)) for item in raw_manifest_ids]
    identities = [_identity(item) for item in manifests]
    dataset, _ = identities[0]
    if dataset.instrument != symbol or any(
        identity.to_dict() != dataset.to_dict() for identity, _ in identities
    ):
        raise DataError("chart symbol or identity does not match the selected dataset group")
    time_column, volume_column = (
        ("open_time", "base_volume") if dataset.family == "market_bars" else ("timestamp", "volume")
    )
    frames = []
    required = {time_column, volume_column, "open", "high", "low", "close"}
    for manifest in manifests:
        payload = (store.bulk_root / str(manifest["artifact_key"])).read_bytes()
        if hashlib.sha256(payload).hexdigest() != manifest["artifact_sha256"]:
            raise DataError("chart dataset bytes changed after verification")
        try:
            frame = pl.read_parquet(io.BytesIO(payload))
        except pl.exceptions.PolarsError as exc:
            raise DataError("chart dataset is not readable Parquet") from exc
        _, quality = _identity(manifest)
        if frame.height != quality.row_count:
            raise DataError("chart dataset row count does not match quality metadata")
        if not required <= set(frame.columns):
            raise DataError("chart dataset has an unsupported OHLCV schema")
        if dataset.family == "derivative_bars":
            expected = {
                "category": dataset.market_type,
                "symbol": symbol,
                "family": "trade",
                "volume_unit_rule": "quote_coin"
                if dataset.market_type == "inverse"
                else "base_coin",
            }
            for column, value in expected.items():
                if column not in frame.columns or frame[column].unique().to_list() != [value]:
                    raise DataError("chart dataset market identity does not match its manifest")
        frames.append(frame)
    try:
        frame = pl.concat(frames, how="vertical").sort(time_column)
    except pl.exceptions.PolarsError as exc:
        raise DataError("chart dataset group schemas do not match") from exc
    if frame[time_column].n_unique() != frame.height:
        duplicate_times = (
            frame.group_by(time_column).len().filter(pl.col("len") > 1).select(time_column)
        )
        duplicate_bars = frame.join(duplicate_times, on=time_column, how="inner")
        visible_bar = [time_column, "open", "high", "low", "close", volume_column]
        conflicting = (
            duplicate_bars.select(visible_bar)
            .unique()
            .group_by(time_column)
            .len()
            .filter(pl.col("len") > 1)
        )
        if conflicting.height:
            raise DataError("overlapping chart segments disagree on OHLCV values")
        frame = frame.unique(subset=[time_column], keep="first").sort(time_column)
    cutoff = as_of or datetime.now(UTC)
    period = _FREQUENCIES[dataset.frequency]
    bars = []
    previous: datetime | None = None
    for row in frame.iter_rows(named=True):
        stamp = row[time_column]
        if (
            not isinstance(stamp, datetime)
            or stamp.tzinfo is None
            or stamp.utcoffset() != timedelta(0)
        ):
            raise DataError("chart dataset timestamps must be UTC")
        if previous is not None and stamp <= previous:
            raise DataError("chart timestamps must be unique and increasing")
        previous = stamp
        if stamp + period > cutoff:
            continue
        try:
            bars.append(
                Bar(
                    symbol=symbol,
                    ts=stamp,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row[volume_column],
                )
            )
        except (TypeError, ValueError) as exc:
            raise DataError("chart dataset contains invalid OHLCV") from exc
    provenance = dict(
        source=f"{dataset.provider}:{dataset.family}",
        venue=dataset.venue,
        timeframe=_TIMEFRAME_LABELS[dataset.frequency],
        snapshot_id=None,
        provenance_sha256=manifest_id,
        receipt_id=None,
        knowledge_cutoff=cutoff.isoformat(),
        quality_status="qualified",
        manifest_id=manifest_id,
        market_type=dataset.market_type,
        volume_unit="quote" if dataset.market_type == "inverse" else "base",
        history_kind="reconstructed_from_verified_archive",
    )
    return bars, provenance
