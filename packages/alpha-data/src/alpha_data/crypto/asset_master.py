"""Point-in-time crypto identity resolution without ticker-based joins."""

from __future__ import annotations

from datetime import UTC, datetime

from alpha_core import DataError

from .contracts import CryptoAssetIdentityV1

_NETWORKS = {
    ("coingecko", "ethereum"): "ethereum",
    ("geckoterminal", "eth"): "ethereum",
    ("coingecko", "solana"): "solana",
    ("geckoterminal", "solana"): "solana",
    ("coingecko", "base"): "base",
    ("geckoterminal", "base"): "base",
    ("coingecko", "binance-smart-chain"): "bnb-smart-chain",
    ("geckoterminal", "bsc"): "bnb-smart-chain",
    ("coingecko", "arbitrum-one"): "arbitrum",
    ("geckoterminal", "arbitrum"): "arbitrum",
}


def canonical_network(provider: str, network: str) -> str:
    """Map one provider-native network ID through the reviewed closed mapping."""
    result = _NETWORKS.get((provider.strip().lower(), network.strip().lower()))
    if result is None:
        raise DataError("crypto provider network mapping is unavailable")
    return result


def _active(identity: CryptoAssetIdentityV1, as_of: datetime) -> bool:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise DataError("crypto identity lookup time must be timezone-aware")
    instant = as_of.astimezone(UTC)
    return identity.valid_from <= instant and (
        identity.valid_to is None or instant <= identity.valid_to
    )


class AssetMaster:
    """Immutable identity set resolved only by reviewed native or contract identity."""

    def __init__(self, identities: tuple[CryptoAssetIdentityV1, ...]) -> None:
        self._identities = tuple(identities)
        for index, left in enumerate(self._identities):
            key = (left.network, left.contract_address, left.native_asset)
            for right in self._identities[index + 1 :]:
                if key != (right.network, right.contract_address, right.native_asset):
                    continue
                left_end = left.valid_to or datetime.max.replace(tzinfo=UTC)
                right_end = right.valid_to or datetime.max.replace(tzinfo=UTC)
                if left.valid_from <= right_end and right.valid_from <= left_end:
                    raise DataError("crypto identity lifecycle intervals overlap")

    @classmethod
    def with_reviewed_native_assets(cls) -> AssetMaster:
        return cls(
            (
                CryptoAssetIdentityV1(
                    coingecko_id="bitcoin",
                    network="bitcoin",
                    contract_address=None,
                    native_asset=True,
                    provider_symbols=(
                        ("coingecko", "bitcoin"),
                        ("coinmetrics", "btc"),
                        ("binance", "BTC"),
                        ("bybit", "BTC"),
                    ),
                    valid_from=datetime(2009, 1, 3, tzinfo=UTC),
                    valid_to=None,
                    migration_lineage=(),
                ),
                CryptoAssetIdentityV1(
                    coingecko_id="ethereum",
                    network="ethereum",
                    contract_address=None,
                    native_asset=True,
                    provider_symbols=(
                        ("coingecko", "ethereum"),
                        ("coinmetrics", "eth"),
                        ("binance", "ETH"),
                        ("bybit", "ETH"),
                    ),
                    valid_from=datetime(2015, 7, 30, tzinfo=UTC),
                    valid_to=None,
                    migration_lineage=(),
                ),
            )
        )

    def _one(self, matches: list[CryptoAssetIdentityV1]) -> CryptoAssetIdentityV1:
        if not matches:
            raise DataError("crypto asset identity is unavailable at the requested time")
        if len(matches) != 1:
            raise DataError("crypto asset identity is ambiguous")
        return matches[0]

    def resolve_contract(
        self, *, network: str, contract_address: str, as_of: datetime
    ) -> CryptoAssetIdentityV1:
        network_key = network.strip().lower()
        contract_key = contract_address.strip().lower()
        if not network_key or not contract_key:
            raise DataError("crypto contract lookup requires network and contract address")
        return self._one(
            [
                item
                for item in self._identities
                if not item.native_asset
                and item.network == network_key
                and item.contract_address == contract_key
                and _active(item, as_of)
            ]
        )

    def resolve_native(self, *, network: str, as_of: datetime) -> CryptoAssetIdentityV1:
        network_key = network.strip().lower()
        return self._one(
            [
                item
                for item in self._identities
                if item.native_asset and item.network == network_key and _active(item, as_of)
            ]
        )

    def resolve_ticker(self, ticker: str, *, as_of: datetime) -> CryptoAssetIdentityV1:
        del ticker, as_of
        raise DataError("ticker-only crypto identity joins are prohibited")


__all__ = ["AssetMaster", "canonical_network"]
