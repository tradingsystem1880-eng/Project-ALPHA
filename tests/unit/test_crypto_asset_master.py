from __future__ import annotations

from datetime import UTC, datetime

import pytest

from alpha_core import DataError
from alpha_data.crypto.asset_master import AssetMaster, canonical_network
from alpha_data.crypto.contracts import CryptoAssetIdentityV1


def _identity(
    coin_id: str,
    network: str,
    contract: str | None,
    *,
    native: bool = False,
    valid_from: datetime = datetime(2020, 1, 1, tzinfo=UTC),
    valid_to: datetime | None = None,
) -> CryptoAssetIdentityV1:
    return CryptoAssetIdentityV1(
        coingecko_id=coin_id,
        network=network,
        contract_address=contract,
        native_asset=native,
        provider_symbols=(("coinmetrics", coin_id),),
        valid_from=valid_from,
        valid_to=valid_to,
        migration_lineage=(),
    )


def test_contract_identity_requires_network_and_contract_not_ticker() -> None:
    usdc = _identity("usd-coin", "ethereum", "0xA0B8")
    master = AssetMaster((usdc,))

    assert (
        master.resolve_contract(
            network="ethereum", contract_address="0xa0b8", as_of=datetime(2024, 1, 1, tzinfo=UTC)
        )
        == usdc
    )
    with pytest.raises(DataError, match="ticker-only"):
        master.resolve_ticker("USDC", as_of=datetime(2024, 1, 1, tzinfo=UTC))


def test_identity_resolution_is_point_in_time_and_ambiguous_overlap_fails() -> None:
    old = _identity(
        "token-v1",
        "ethereum",
        "0x01",
        valid_to=datetime(2022, 12, 31, tzinfo=UTC),
    )
    new = _identity(
        "token-v2",
        "ethereum",
        "0x01",
        valid_from=datetime(2023, 1, 1, tzinfo=UTC),
    )
    master = AssetMaster((old, new))
    assert (
        master.resolve_contract(
            network="ethereum", contract_address="0x01", as_of=datetime(2022, 1, 1, tzinfo=UTC)
        ).coingecko_id
        == "token-v1"
    )
    assert (
        master.resolve_contract(
            network="ethereum", contract_address="0x01", as_of=datetime(2024, 1, 1, tzinfo=UTC)
        ).coingecko_id
        == "token-v2"
    )

    with pytest.raises(DataError, match="overlap"):
        AssetMaster((old, _identity("collision", "ethereum", "0x01")))


def test_reviewed_native_mapping_resolves_btc_and_eth_explicitly() -> None:
    master = AssetMaster.with_reviewed_native_assets()
    instant = datetime(2026, 1, 1, tzinfo=UTC)
    assert master.resolve_native(network="bitcoin", as_of=instant).coingecko_id == "bitcoin"
    assert master.resolve_native(network="ethereum", as_of=instant).coingecko_id == "ethereum"


def test_provider_network_ids_are_explicitly_mapped_not_guessed() -> None:
    assert canonical_network("coingecko", "ethereum") == "ethereum"
    assert canonical_network("geckoterminal", "eth") == "ethereum"
    assert canonical_network("coingecko", "binance-smart-chain") == "bnb-smart-chain"
    with pytest.raises(DataError, match="network mapping"):
        canonical_network("geckoterminal", "new-chain")
