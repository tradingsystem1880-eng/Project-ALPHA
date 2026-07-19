"""Provider control plane: capability, configuration, and historical-adapter registry.

This module is the CLI-owned source of truth for providers exposed to operators and the
Workstation.  It reports only credential *names* and whether a non-empty value is present; secret
values never enter a ``ProviderDefinition`` or its JSON projection.
"""

from __future__ import annotations

import importlib.util
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from alpha_data.adapters.base import DataAdapter
from alpha_data.adapters.ccxt_adapter import SUPPORTED_CCXT_EXCHANGES, CCXTAdapter
from alpha_data.adapters.stooq_adapter import StooqAdapter
from alpha_data.adapters.yfinance_adapter import YFinanceAdapter

HistoricalAdapterFactory = Callable[..., DataAdapter]
ModuleAvailable = Callable[[str], bool]


@dataclass(frozen=True)
class CredentialStatus:
    """A redacted credential requirement: environment-variable name and presence only."""

    name: str
    present: bool

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "present": self.present}


@dataclass(frozen=True)
class ProviderOption:
    """A finite provider-specific option suitable for a dynamic UI selector."""

    label: str
    choices: tuple[str, ...]
    default: str

    def to_dict(self) -> dict[str, object]:
        return {"label": self.label, "choices": list(self.choices), "default": self.default}


@dataclass(frozen=True)
class ProviderDefinition:
    """One provider's local availability, configuration, capabilities, and limitations."""

    id: str
    label: str
    capabilities: tuple[str, ...]
    network_required: bool
    credential_env: tuple[CredentialStatus, ...]
    options: Mapping[str, ProviderOption]
    limitations: tuple[str, ...]
    installed: bool
    configured: bool
    historical_adapter_factory: HistoricalAdapterFactory | None = field(
        default=None, repr=False, compare=False
    )

    def to_dict(self) -> dict[str, object]:
        """Return the stable redacted projection used by CLI and Workstation consumers."""
        return {
            "id": self.id,
            "label": self.label,
            "capabilities": list(self.capabilities),
            "network_required": self.network_required,
            "credential_env": [credential.to_dict() for credential in self.credential_env],
            "options": {name: option.to_dict() for name, option in self.options.items()},
            "limitations": list(self.limitations),
            "installed": self.installed,
            "configured": self.configured,
        }


def _module_available(module: str) -> bool:
    try:
        return importlib.util.find_spec(module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def _credentials(
    names: tuple[str, ...], environ: Mapping[str, str]
) -> tuple[CredentialStatus, ...]:
    return tuple(
        CredentialStatus(name=name, present=bool(environ.get(name, "").strip())) for name in names
    )


def _definition(
    *,
    provider_id: str,
    label: str,
    capabilities: tuple[str, ...],
    module: str,
    network_required: bool,
    credential_names: tuple[str, ...],
    options: Mapping[str, ProviderOption],
    limitations: tuple[str, ...],
    factory: HistoricalAdapterFactory | None,
    environ: Mapping[str, str],
    module_available: ModuleAvailable,
) -> ProviderDefinition:
    installed = module_available(module)
    credentials = _credentials(credential_names, environ)
    return ProviderDefinition(
        id=provider_id,
        label=label,
        capabilities=capabilities,
        network_required=network_required,
        credential_env=credentials,
        options=options,
        limitations=limitations,
        installed=installed,
        configured=installed and all(credential.present for credential in credentials),
        historical_adapter_factory=factory,
    )


def provider_definitions(
    *,
    environ: Mapping[str, str] | None = None,
    module_available: ModuleAvailable = _module_available,
) -> tuple[ProviderDefinition, ...]:
    """Build the registry against current local packages and environment configuration."""
    env = os.environ if environ is None else environ
    providers = (
        _definition(
            provider_id="yfinance",
            label="Yahoo Finance (yfinance)",
            capabilities=("historical_bars", "corporate_actions"),
            module="yfinance",
            network_required=True,
            credential_names=(),
            options={},
            limitations=(
                "Unofficial public endpoint; availability and throttling are vendor-controlled.",
                "Daily history only in ALPHA; raw prices are reconstructed from adjusted rows.",
            ),
            factory=YFinanceAdapter,
            environ=env,
            module_available=module_available,
        ),
        _definition(
            provider_id="ccxt",
            label="CCXT Historical Crypto",
            capabilities=("historical_bars",),
            module="ccxt",
            network_required=True,
            credential_names=(),
            options={
                "exchange": ProviderOption(
                    label="Exchange",
                    choices=SUPPORTED_CCXT_EXCHANGES,
                    default="coinbase",
                )
            },
            limitations=(
                "Public daily OHLCV only; exchange retention and rate limits vary.",
                "No corporate actions; the current incomplete UTC candle is excluded.",
            ),
            factory=CCXTAdapter,
            environ=env,
            module_available=module_available,
        ),
        _definition(
            provider_id="stooq",
            label="Stooq",
            capabilities=("historical_bars",),
            module="alpha_data.adapters.stooq_adapter",
            network_required=True,
            credential_names=(),
            options={},
            limitations=(
                "Provider-adjusted prices with no separate corporate-action history.",
                "The public CSV endpoint can be blocked by anti-bot or per-IP gates.",
            ),
            factory=StooqAdapter,
            environ=env,
            module_available=module_available,
        ),
        _definition(
            provider_id="finnhub",
            label="Finnhub",
            capabilities=("live_quote", "news"),
            module="finnhub",
            network_required=True,
            credential_names=("ALPHA_FINNHUB_API_KEY",),
            options={},
            limitations=("Free API-key tier is subject to provider rate limits.",),
            factory=None,
            environ=env,
            module_available=module_available,
        ),
        _definition(
            provider_id="binance",
            label="Binance Live Data (NautilusTrader)",
            capabilities=("live_bars", "live_quotes", "sandbox_paper"),
            module="nautilus_trader.adapters.binance",
            network_required=True,
            credential_names=(),
            options={},
            limitations=(
                "Public Binance market data only; ALPHA never constructs Binance execution.",
                "Paper orders route exclusively to local Nautilus sandbox execution.",
            ),
            factory=None,
            environ=env,
            module_available=module_available,
        ),
    )
    ids = [provider.id for provider in providers]
    if len(ids) != len(set(ids)):
        raise RuntimeError(f"duplicate provider ids: {ids}")
    return providers


def providers_with_capability(
    capability: str, providers: Sequence[ProviderDefinition] | None = None
) -> tuple[ProviderDefinition, ...]:
    """Filter providers by an exact capability identifier, preserving registry order."""
    source = provider_definitions() if providers is None else providers
    return tuple(provider for provider in source if capability in provider.capabilities)


def historical_adapter_factories() -> dict[str, HistoricalAdapterFactory]:
    """Return the data-command adapter choices derived solely from the provider registry."""
    return {
        provider.id: provider.historical_adapter_factory
        for provider in providers_with_capability("historical_bars")
        if provider.historical_adapter_factory is not None
    }


def provider_catalog() -> list[dict[str, Any]]:
    """Redacted JSON-ready provider catalog."""
    return [provider.to_dict() for provider in provider_definitions()]


def provider_option_choices(provider_id: str, option_name: str) -> tuple[str, ...]:
    """Resolve a finite option from the registry; fail loud on an internal unknown option."""
    provider = next((item for item in provider_definitions() if item.id == provider_id), None)
    if provider is None or option_name not in provider.options:
        raise RuntimeError(f"unknown provider option {provider_id}.{option_name}")
    return provider.options[option_name].choices
