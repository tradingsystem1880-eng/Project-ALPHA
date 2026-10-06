"""The local spot search distinguishes verified venue listings from acquired bars."""

import json
from datetime import UTC, datetime
from typing import cast

import polars as pl
import pytest
from typer.testing import CliRunner

from alpha_cli import crypto_data_cmds
from alpha_cli.main import app
from alpha_data.crypto.contracts import CryptoDatasetIdentityV1, CryptoQualityReportV1


def test_market_catalog_search_uses_latest_qualified_spot_membership_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 9, 30, tzinfo=UTC)
    dataset = CryptoDatasetIdentityV1(
        provider="binance",
        venue="binance",
        market_type="spot",
        family="market_membership",
        instrument="spot",
        base_asset=None,
        quote_asset=None,
        frequency="catalog_snapshot",
        units="provider_native_market_identity",
        timestamp_convention="provider_observation_utc",
    )
    quality = CryptoQualityReportV1(
        dataset_sha256="a" * 64,
        method_version="crypto-quality-v1",
        state="qualified",
        failures=(),
        warnings=(),
        observed_start=now,
        observed_end=now,
        row_count=4,
        correction_lineage=(),
    )
    manifest = {
        "artifact_kind": "normalized",
        "manifest_id": "b" * 64,
        "dataset": dataset.to_dict(),
        "quality": quality.to_dict(),
    }

    class Store:
        def metadata_inventory(self) -> tuple[dict[str, object], ...]:
            return (cast(dict[str, object], manifest),)

    monkeypatch.setattr(crypto_data_cmds, "_bulk_store", lambda: Store())
    monkeypatch.setattr(
        crypto_data_cmds,
        "_qualified_normalized_frame",
        lambda *_args, **_kwargs: (
            pl.DataFrame(
                {
                    "symbol": ["AAVEBTC", "BTCARS", "BTCUSDT", "ETHUSDT"],
                    "base_asset": ["AAVE", "BTC", "BTC", "ETH"],
                    "quote_asset": ["BTC", "ARS", "USDT", "USDT"],
                    "status": ["TRADING", "TRADING", "TRADING", "TRADING"],
                }
            ),
            quality,
        ),
    )

    result = CliRunner().invoke(
        app,
        ["crypto-data", "market-catalog", "--query", "btc", "--limit", "1", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["state"] == "available"
    assert payload["total_matches"] == 3
    assert payload["markets"] == [
        {
            "pair": "BTC/USDT",
            "provider_symbol": "BTCUSDT",
            "base_asset": "BTC",
            "quote_asset": "USDT",
            "status": "TRADING",
        }
    ]
