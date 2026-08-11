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
    assert {"yfinance", "ccxt", "stooq", "tiingo", "quantpad", "finnhub", "binance", "ibkr"} == set(
        ids
    )
    historical_ids = {
        provider.id for provider in providers_with_capability("historical_bars", providers)
    }
    assert historical_ids == {
        "yfinance",
        "ccxt",
        "stooq",
        "tiingo",
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


def test_tiingo_is_authoritative_daily_equity_provider() -> None:
    tiingo = next(
        provider for provider in provider_definitions(environ={}) if provider.id == "tiingo"
    )
    assert tiingo.asset_classes == ("stock", "etf")
    assert tiingo.timeframes == ("1D",)
    assert tiingo.research_authority is True
    assert tiingo.paper_execution is False
    assert tiingo.budget_tier == "free_500_symbols"
    assert [credential.name for credential in tiingo.credential_env] == ["ALPHA_TIINGO_API_KEY"]


def test_ibkr_is_paper_only_and_never_a_research_authority() -> None:
    ibkr = next(provider for provider in provider_definitions(environ={}) if provider.id == "ibkr")
    assert ibkr.asset_classes == ("stock", "etf", "future")
    assert ibkr.research_authority is False
    assert ibkr.paper_execution is True
    assert "paper_execution" in ibkr.capabilities


def test_quantpad_is_registered_as_research_only_without_canonical_pull_authority() -> None:
    from alpha_cli.providers import historical_adapter_factories, provider_definitions

    definitions = {definition.id: definition for definition in provider_definitions(environ={})}
    quantpad = definitions["quantpad"]
    assert quantpad.research_authority is False
    assert quantpad.paper_execution is False
    assert "QUANTPAD_API_KEY" in {status.name for status in quantpad.credential_env}
    assert any("research" in limitation.casefold() for limitation in quantpad.limitations)
    # Fail-closed pull boundary: quantpad never enters the canonical `data pull` registry;
    # its capability is `research_bars`, structurally outside the historical_bars invariant.
    assert quantpad.capabilities == ("research_bars",)
    assert "quantpad" not in historical_adapter_factories()
