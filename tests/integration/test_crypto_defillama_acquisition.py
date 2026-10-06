from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from alpha_cli import crypto_data_cmds
from alpha_core import DataError


def test_defillama_acquisition_plan_pins_provider_and_input_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched_at = datetime(2026, 10, 2, tzinfo=UTC)
    payload = json.dumps(
        {"tvl": [{"date": 1_756_684_800, "totalLiquidityUSD": 1_000_000}]}
    ).encode()
    monkeypatch.setattr(crypto_data_cmds, "fetch_defillama_public", lambda _url: payload)

    fetched = crypto_data_cmds._fetch_non_bybit(
        "defillama",
        "protocol_tvl",
        "aave",
        Path("/tmp"),
        base="AAVE",
        quote="USD",
        category="spot",
        frequency="1d",
        period=None,
        network=None,
        pool_address=None,
        metrics=None,
        start=None,
        end=None,
        fetched_at=fetched_at,
    )

    assert isinstance(fetched, crypto_data_cmds._FetchedAcquisition)
    assert fetched.plan.dataset.provider == "defillama"
    assert fetched.plan.dataset.family == "protocol_tvl"
    assert fetched.plan.dataset.instrument == "aave"
    assert fetched.plan.availability_column == "fetched_at"
    frame = fetched.plan.parser(fetched.payload)
    assert frame.item(0, "fetched_at") == fetched_at
    assert frame.item(0, "tvl_usd") == 1_000_000


def test_defillama_rejects_a_family_it_does_not_authorize() -> None:
    with pytest.raises(DataError, match="not authoritative"):
        crypto_data_cmds._fetch_defillama(
            "market_bars",
            "BTCUSDT",
            fetched_at=datetime(2026, 10, 2, tzinfo=UTC),
        )


def test_stablecoin_acquisition_preserves_native_supply_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(crypto_data_cmds, "fetch_defillama_public", lambda _url: b"{}")
    fetched = crypto_data_cmds._fetch_defillama(
        "stablecoin_supply", "1", fetched_at=datetime(2026, 10, 2, tzinfo=UTC)
    )
    assert fetched.plan.dataset.units == "native_usd_pegged_token_units"
    assert fetched.plan.dataset.quote_asset is None


def test_pool_uuid_case_does_not_split_dataset_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto_data_cmds, "fetch_defillama_public", lambda _url: b"{}")
    ident = "DB678DF9-3281-4BC2-A8BB-01160FFD6D48"
    fetched = crypto_data_cmds._fetch_defillama(
        "yield_history", ident, fetched_at=datetime(2026, 10, 2, tzinfo=UTC)
    )
    assert fetched.plan.dataset.instrument == ident.lower()
