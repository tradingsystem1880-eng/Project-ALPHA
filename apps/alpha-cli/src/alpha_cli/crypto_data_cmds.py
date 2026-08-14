"""Governed crypto-data catalog, storage, estimation, and identity commands."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Final

import typer

from alpha_core import DataError
from alpha_core.config import AlphaSettings
from alpha_data.crypto.asset_master import AssetMaster
from alpha_data.crypto.contracts import FAMILY_AUTHORITIES, CryptoFamily
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


__all__ = ["crypto_data_app"]
