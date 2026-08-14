"""Point-in-time crypto identity resolution without ticker-based joins."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

import polars as pl

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

    def __init__(
        self,
        identities: tuple[CryptoAssetIdentityV1, ...],
        *,
        source_manifest_ids: tuple[str, ...] = (),
        version: str | None = None,
    ) -> None:
        self._identities = tuple(
            sorted(
                identities,
                key=lambda item: (
                    item.network,
                    not item.native_asset,
                    item.contract_address or "",
                    item.coingecko_id,
                    item.valid_from,
                ),
            )
        )
        for index, left in enumerate(self._identities):
            key = (left.network, left.contract_address, left.native_asset)
            for right in self._identities[index + 1 :]:
                if key != (right.network, right.contract_address, right.native_asset):
                    continue
                left_end = left.valid_to or datetime.max.replace(tzinfo=UTC)
                right_end = right.valid_to or datetime.max.replace(tzinfo=UTC)
                if left.valid_from <= right_end and right.valid_from <= left_end:
                    raise DataError("crypto identity lifecycle intervals overlap")
        if len(set(source_manifest_ids)) != len(source_manifest_ids) or any(
            len(item) != 64 or any(char not in "0123456789abcdef" for char in item)
            for item in source_manifest_ids
        ):
            raise DataError("crypto asset-master source manifest identity is invalid")
        self._source_manifest_ids = tuple(source_manifest_ids)
        body = {
            "identities": [identity.to_dict() for identity in self._identities],
            "source_manifest_ids": list(self._source_manifest_ids),
        }
        derived = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        if version is not None and version != derived:
            raise DataError("crypto asset-master version does not match its identities")
        self._version = version or derived

    @property
    def version(self) -> str:
        return self._version

    @property
    def identities(self) -> tuple[CryptoAssetIdentityV1, ...]:
        return self._identities

    @property
    def source_manifest_ids(self) -> tuple[str, ...]:
        return self._source_manifest_ids

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "asset_master_version": self.version,
            "source_manifest_ids": list(self._source_manifest_ids),
            "identities": [identity.to_dict() for identity in self._identities],
        }

    @classmethod
    def from_dict(cls, value: object) -> AssetMaster:
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise DataError("invalid crypto asset-master artifact")
        version = value.get("asset_master_version")
        raw_identities = value.get("identities")
        source_manifest_ids = value.get("source_manifest_ids")
        if (
            not isinstance(version, str)
            or not isinstance(raw_identities, list)
            or not isinstance(source_manifest_ids, list)
            or any(not isinstance(item, str) for item in source_manifest_ids)
        ):
            raise DataError("invalid crypto asset-master artifact")
        identities: list[CryptoAssetIdentityV1] = []
        for raw in raw_identities:
            if not isinstance(raw, dict):
                raise DataError("invalid crypto asset-master identity")
            try:
                provider_symbols = raw["provider_symbols"]
                migration_lineage = raw["migration_lineage"]
                valid_from = raw["valid_from"]
                valid_to = raw["valid_to"]
                if (
                    raw.get("schema_version") != 1
                    or not isinstance(provider_symbols, list)
                    or not isinstance(migration_lineage, list)
                    or not isinstance(valid_from, str)
                    or (valid_to is not None and not isinstance(valid_to, str))
                ):
                    raise DataError("invalid crypto asset-master identity")
                pairs = tuple(
                    (item[0], item[1])
                    for item in provider_symbols
                    if isinstance(item, list) and len(item) == 2
                )
                if len(pairs) != len(provider_symbols) or any(
                    not isinstance(item, str) for item in migration_lineage
                ):
                    raise DataError("invalid crypto asset-master identity")
                identities.append(
                    CryptoAssetIdentityV1(
                        coingecko_id=raw["coingecko_id"],
                        network=raw["network"],
                        contract_address=raw["contract_address"],
                        native_asset=raw["native_asset"],
                        provider_symbols=pairs,
                        valid_from=datetime.fromisoformat(valid_from.replace("Z", "+00:00")),
                        valid_to=datetime.fromisoformat(valid_to.replace("Z", "+00:00"))
                        if valid_to is not None
                        else None,
                        migration_lineage=tuple(migration_lineage),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise DataError("invalid crypto asset-master identity") from exc
        return cls(
            tuple(identities),
            source_manifest_ids=tuple(source_manifest_ids),
            version=version,
        )

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


def build_cross_provider_asset_master(
    *,
    coingecko_catalog: pl.DataFrame,
    geckoterminal_pools: tuple[pl.DataFrame, ...],
    observed_at: datetime,
    source_manifest_ids: tuple[str, ...] = (),
) -> AssetMaster:
    """Build exact contract identities only where reviewed provider contracts intersect."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise DataError("crypto asset-master observation time must be timezone-aware")
    cg_required = {"coingecko_id", "network", "contract_address"}
    pool_required = {"network", "base_token_address", "quote_token_address"}
    if not cg_required.issubset(coingecko_catalog.columns) or not geckoterminal_pools:
        raise DataError("crypto asset-master source schema is invalid")
    tracked: set[tuple[str, str]] = set()
    for pools in geckoterminal_pools:
        if not pool_required.issubset(pools.columns):
            raise DataError("crypto asset-master pool schema is invalid")
        for row in pools.iter_rows(named=True):
            network = canonical_network("geckoterminal", str(row["network"]))
            for field in ("base_token_address", "quote_token_address"):
                contract = str(row[field]).strip().lower()
                if not contract:
                    raise DataError("crypto asset-master pool contract is invalid")
                tracked.add((network, contract))

    matches: dict[tuple[str, str], list[str]] = {}
    for row in coingecko_catalog.iter_rows(named=True):
        network = canonical_network("coingecko", str(row["network"]))
        contract = str(row["contract_address"]).strip().lower()
        key = (network, contract)
        if key in tracked:
            matches.setdefault(key, []).append(str(row["coingecko_id"]))
    identities = list(AssetMaster.with_reviewed_native_assets().identities)
    for (network, contract), coin_ids in sorted(matches.items()):
        unique_ids = sorted(set(coin_ids))
        if len(unique_ids) != 1:
            raise DataError("crypto contract identity is ambiguous across CoinGecko records")
        identities.append(
            CryptoAssetIdentityV1(
                coingecko_id=unique_ids[0],
                network=network,
                contract_address=contract,
                native_asset=False,
                provider_symbols=(
                    ("coingecko", unique_ids[0]),
                    ("geckoterminal", contract),
                ),
                valid_from=observed_at.astimezone(UTC),
                valid_to=None,
                migration_lineage=(),
            )
        )
    return AssetMaster(tuple(identities), source_manifest_ids=source_manifest_ids)


__all__ = ["AssetMaster", "build_cross_provider_asset_master", "canonical_network"]
