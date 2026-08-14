"""Explicit opt-in smoke tests for current public crypto reference interfaces."""

from __future__ import annotations

from urllib.request import Request

import pytest

from alpha_data.crypto.providers.coingecko import fetch_coingecko_demo, parse_asset_catalog
from alpha_data.crypto.providers.coinmetrics import (
    coinmetrics_community_url,
    fetch_coinmetrics_community,
    parse_asset_metric_catalog,
    parse_asset_metrics,
)
from alpha_data.crypto.providers.geckoterminal import (
    fetch_geckoterminal_public,
    geckoterminal_public_url,
    parse_top_pools,
)

pytestmark = pytest.mark.network


def test_public_reference_provider_schemas_remain_parseable() -> None:
    catalog = parse_asset_catalog(
        fetch_coingecko_demo(
            Request(
                "https://api.coingecko.com/api/v3/coins/list?include_platform=true",
                headers={"Accept": "application/json", "User-Agent": "Project-ALPHA/1.0"},
            )
        )
    )
    usdc = catalog.filter(
        (catalog["coingecko_id"] == "usd-coin") & (catalog["network"] == "ethereum")
    )
    assert usdc.height == 1 and usdc.row(0, named=True)["contract_address"]

    pools = parse_top_pools(
        fetch_geckoterminal_public(
            geckoterminal_public_url("top_pools", network="eth", params={"page": 1})
        ),
        network="eth",
    )
    assert pools.height > 0

    metric_catalog = parse_asset_metric_catalog(
        fetch_coinmetrics_community(
            coinmetrics_community_url("catalog", {"assets": "btc,eth", "page_size": 100})
        )
    )
    assert {"btc", "eth"}.issubset(set(metric_catalog["asset"]))
    metrics = tuple(sorted(set(metric_catalog.filter(metric_catalog["asset"] == "btc")["metric"])))
    values = parse_asset_metrics(
        fetch_coinmetrics_community(
            coinmetrics_community_url(
                "asset_metrics",
                {
                    "assets": "btc",
                    "metrics": ",".join(metrics),
                    "frequency": "1d",
                    "start_time": "2026-08-01",
                    "end_time": "2026-08-03",
                    "page_size": 100,
                },
            )
        ),
        assets=("btc",),
        metrics=metrics,
    )
    assert values.height > 0
