"""Frozen daily price comparisons: descriptive evidence, never causal attribution."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import polars as pl
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from alpha_cli import _runner
from alpha_core import Bar, DataError
from alpha_data.snapshot import resolve_snapshot_dir, snapshot_manifest_hash
from alpha_data.source import PointInTimeSource
from alpha_data.store import ParquetStore


class ComparisonSeries(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    snapshot_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
    snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    symbol: str = Field(pattern=r"^[A-Z0-9][A-Z0-9._/-]{0,39}$")
    role: Literal["asset", "market", "sector", "other"]

    @field_validator("symbol")
    @classmethod
    def safe_symbol(cls, value: str) -> str:
        if ".." in value or any(part in {"", "."} for part in value.split("/")):
            raise ValueError("symbol must have safe path components")
        return value


class ComparisonPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    schema_version: Literal[1] = 1
    series: list[ComparisonSeries] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def distinct_series(self) -> ComparisonPlan:
        keys = {(item.snapshot_id, item.symbol) for item in self.series}
        if len(keys) != len(self.series):
            raise ValueError("comparison series must be distinct")
        return self


def _snapshot_hash(snap: Path) -> str:
    """Bound all files the existing verifier will hash, before it reads their payloads."""
    manifest = snap / "manifest.json"
    if any(part.is_symlink() for part in (manifest, *manifest.parents)):
        raise DataError("comparison snapshot cannot be symlinked")
    with manifest.open("rb") as source:
        raw = source.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise DataError("comparison manifest exceeds 1 MiB limit")
    document = json.loads(raw)
    members = document.get("symbols") if isinstance(document, dict) else None
    if not isinstance(members, dict) or len(members) > 128:
        raise DataError("comparison snapshot requires at most 128 members")
    total = 0
    for entry in members.values():
        if not isinstance(entry, dict):
            raise DataError("invalid comparison snapshot member")
        for kind in ("bars", "actions", "provenance"):
            value = entry.get(f"{kind}_file")
            if value is None:
                continue
            if not isinstance(value, str) or not value:
                raise DataError("invalid comparison snapshot file")
            relative = Path(value)
            if relative.is_absolute() or ".." in relative.parts:
                raise DataError("comparison snapshot file escapes its root")
            path = snap / relative
            if any(part.is_symlink() for part in (path, *path.parents)) or not path.is_file():
                raise DataError("comparison snapshot file missing or symlinked")
            size = path.stat().st_size
            if size > (32 * 1024 * 1024 if kind == "bars" else 1024 * 1024):
                raise DataError("comparison snapshot file exceeds size limit")
            total += size
    if total > 128 * 1024 * 1024:
        raise DataError("comparison snapshot exceeds 128 MiB total limit")
    return snapshot_manifest_hash(snap)


def _member_paths(snap: Path, ref: ComparisonSeries, entry: dict[str, Any]) -> None:
    # The PIT reader uses conventional paths, not the manifest's arbitrary path strings.
    for kind, suffix in (("bars", "parquet"), ("actions", "json"), ("provenance", "json")):
        relative = f"{kind}/{ref.symbol}.{suffix}"
        path = snap / relative
        declared = entry.get(f"{kind}_file")
        if declared is not None and declared != relative:
            raise DataError("comparison manifest path does not match reader path")
        if path.exists() != (declared is not None):
            raise DataError("comparison reader path is missing or undeclared")
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise DataError("comparison reader paths cannot be symlinked")
    if (snap / f"bars/{ref.symbol}.parquet").stat().st_size > 32 * 1024 * 1024:
        raise DataError("comparison bars exceed 32 MiB limit")


def _series(
    ref: ComparisonSeries, data_dir: Path, cutoff: datetime
) -> tuple[dict[str, Any], list[Bar]]:
    snap = resolve_snapshot_dir(data_dir / "snapshots", ref.snapshot_id)
    if (
        any(part.is_symlink() for part in (snap, *snap.parents))
        or (snap / "manifest.json").is_symlink()
    ):
        raise DataError("comparison snapshot cannot be symlinked")
    if _snapshot_hash(snap) != ref.snapshot_sha256:
        raise DataError("comparison snapshot hash mismatch")
    manifest = json.loads((snap / "manifest.json").read_text())
    if manifest.get("snapshot_id") != ref.snapshot_id:
        raise DataError("comparison snapshot identity mismatch")
    result: dict[str, Any] = {**ref.model_dump(), "blockers": [], "windows": []}
    entry = manifest["symbols"].get(ref.symbol)
    if entry is None:
        result["blockers"] = ["snapshot_member_missing"]
        result["data_needed"] = (
            f"A new verified snapshot containing {ref.symbol}; do not edit this snapshot."
        )
        return result, []
    _member_paths(snap, ref, entry)
    store = ParquetStore(snap)
    provenance = store.read_provenance(ref.symbol)
    if provenance is None or provenance.get("schema_version") != 2:
        result["blockers"] = ["versioned_provenance_required"]
        result["data_needed"] = (
            "Versioned instrument identity and pull receipt from a supported acquisition, "
            "frozen into a new snapshot."
        )
        return result, []
    if any(
        provenance[k] != manifest.get(k) for k in ("source", "adapter_version", "parser_version")
    ):
        raise DataError("comparison provenance disagrees with snapshot")
    receipt = provenance["receipt"]
    assert isinstance(receipt, dict)  # read_provenance has validated FetchReceipt
    result.update(
        dataset=provenance["dataset"],
        fetch_receipt={
            key: receipt[key]
            for key in (
                "receipt_id",
                "fetched_at",
                "requested_start",
                "requested_end",
                "response_sha256",
            )
        },
        historical_vintage="unverified",
    )
    frame = pl.scan_parquet(snap / f"bars/{ref.symbol}.parquet")
    schema = frame.collect_schema()
    price_fields = {"open", "high", "low", "close", "volume"}
    if set(schema) != {"ts", *price_fields} or any(
        not schema[key].is_numeric() for key in price_fields
    ):
        raise DataError("comparison bars require the numeric daily OHLCV schema")
    timestamp_type = schema["ts"]
    if not isinstance(timestamp_type, pl.Datetime) or timestamp_type.time_zone is None:
        raise DataError("comparison timestamps must be timezone-aware datetimes")
    if frame.select(pl.len()).collect().item() > 50_000:
        raise DataError("comparison bars exceed 50000 row limit")
    # Same PIT seam as load_bars, while permitting sparse inputs to yield explicit blockers.
    bars = PointInTimeSource(store, {ref.symbol: store.read_actions(ref.symbol)}).as_of(
        ref.symbol, cutoff
    )
    timestamps = [bar.ts for bar in bars]
    if timestamps != sorted(set(timestamps)) or any(
        ts.astimezone(UTC).time().isoformat() != "00:00:00" for ts in timestamps
    ):
        raise DataError("comparison requires ordered unique UTC daily session labels")
    return result, bars


def _window(episode: dict[str, Any], bars: list[Bar], cutoff: datetime) -> dict[str, Any]:
    peak, trough = (datetime.fromisoformat(episode[name]) for name in ("peak", "trough"))
    if any(ts.tzinfo is None for ts in (peak, trough)) or not peak < trough <= cutoff:
        raise DataError("comparison episode is outside ordered cutoff bounds")
    if any(ts.astimezone(UTC).time().isoformat() != "00:00:00" for ts in (peak, trough)):
        raise DataError("comparison episodes must use UTC daily session labels")
    selected = {bar.ts: bar for bar in bars if peak <= bar.ts <= trough}
    missing = [
        f"missing_{name}_session:{ts.date()}"
        for name, ts in (("peak", peak), ("trough", trough))
        if ts not in selected
    ]
    result: dict[str, Any] = dict(
        peak=peak.isoformat(),
        trough=trough.isoformat(),
        observed_rows=len(selected),
        schedule_coverage="unverified",
        blockers=missing,
        status="blocked" if missing else "measured",
    )
    if missing:
        result["data_needed"] = (
            "Verified observations on the exact missing endpoint dates; "
            "no forward fill or nearest-date substitution."
        )
    if not missing:
        change = selected[trough].close / selected[peak].close - 1
        if not math.isfinite(change):
            raise DataError("comparison price change must be finite")
        result.update(
            peak_close=selected[peak].close,
            trough_close=selected[trough].close,
            price_change=change,
        )
    return result


def comparison_evidence(
    packet: dict[str, Any], plan: ComparisonPlan, data_dir: Path
) -> dict[str, Any]:
    """Reverify each frozen input and expose exact-endpoint measurements or explicit blockers."""
    plan = ComparisonPlan.model_validate_json(plan.model_dump_json())
    data_dir = data_dir.resolve(strict=True)
    observations = packet["observations"]
    cutoff = _runner.parse_as_of(observations["execution"]["research_cutoff"])
    assert cutoff is not None
    episodes = observations["drawdown_episodes"]
    if len(episodes) > 3:
        raise DataError("comparison supports at most three drawdown episodes")
    results = []
    for ref in plan.series:
        result, bars = _series(ref, data_dir, cutoff)
        if not result["blockers"]:
            result["windows"] = [_window(episode, bars, cutoff) for episode in episodes]
        # Catch changes during the read, in addition to verification before every cached receipt.
        snap = resolve_snapshot_dir(data_dir / "snapshots", ref.snapshot_id)
        if _snapshot_hash(snap) != ref.snapshot_sha256:
            raise DataError("comparison snapshot changed during read")
        results.append(result)
    return dict(
        schema_version=1,
        series=results,
        causal_attribution="not_tested",
        quality_certification="not_established",
        historical_vintage="unverified",
        alignment="exact UTC daily session labels; closes need not be simultaneous",
        price_basis="split-adjusted at run cutoff; excludes dividends, FX, costs and leverage",
        selection="operator-selected proxies; roles do not establish benchmark suitability",
        policy_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
