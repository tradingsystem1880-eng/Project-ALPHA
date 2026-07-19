"""Provider registry invariants: one redacted, capability-filterable control plane."""

from __future__ import annotations

import json

import pytest

from alpha_cli.providers import provider_definitions, providers_with_capability
from alpha_core import DataError
from alpha_data.adapters.ccxt_adapter import CCXTAdapter


def test_provider_ids_are_unique_and_historical_sources_come_from_registry() -> None:
    providers = provider_definitions(environ={}, module_available=lambda _: True)
    ids = [provider.id for provider in providers]

    assert len(ids) == len(set(ids))
    assert {"yfinance", "ccxt", "stooq", "finnhub", "binance"} == set(ids)
    historical_ids = {
        provider.id for provider in providers_with_capability("historical_bars", providers)
    }
    assert historical_ids == {
        "yfinance",
        "ccxt",
        "stooq",
    }
    assert all(
        provider.historical_adapter_factory is not None
        for provider in providers_with_capability("historical_bars", providers)
    )


def test_provider_configuration_reports_credential_presence_but_never_values() -> None:
    secret = "do-not-leak-this-secret"
    absent = provider_definitions(environ={}, module_available=lambda _: True)
    present = provider_definitions(
        environ={"ALPHA_FINNHUB_API_KEY": secret}, module_available=lambda _: True
    )

    absent_finnhub = next(provider for provider in absent if provider.id == "finnhub")
    present_finnhub = next(provider for provider in present if provider.id == "finnhub")
    assert absent_finnhub.installed is True and absent_finnhub.configured is False
    assert present_finnhub.configured is True
    assert absent_finnhub.to_dict()["credential_env"] == [
        {"name": "ALPHA_FINNHUB_API_KEY", "present": False}
    ]
    serialized = json.dumps([provider.to_dict() for provider in present])
    assert "ALPHA_FINNHUB_API_KEY" in serialized
    assert secret not in serialized


def test_provider_installation_is_part_of_configuration() -> None:
    providers = provider_definitions(
        environ={"ALPHA_FINNHUB_API_KEY": "present"},
        module_available=lambda module: module != "finnhub",
    )
    finnhub = next(provider for provider in providers if provider.id == "finnhub")

    assert finnhub.installed is False
    assert finnhub.configured is False


def test_ccxt_exchange_option_is_registry_owned() -> None:
    ccxt = next(
        provider
        for provider in provider_definitions(environ={}, module_available=lambda _: True)
        if provider.id == "ccxt"
    )

    exchange = ccxt.options["exchange"]
    assert exchange.label == "Exchange"
    assert exchange.choices == ("coinbase", "binance")
    assert exchange.default == "coinbase"


def test_ccxt_adapter_provenance_is_venue_qualified_and_rejects_other_exchanges() -> None:
    assert CCXTAdapter(exchange="coinbase").name == "ccxt:coinbase"
    assert CCXTAdapter(exchange="binance").name == "ccxt:binance"
    with pytest.raises(DataError, match="unsupported CCXT exchange"):
        CCXTAdapter(exchange="kraken")
