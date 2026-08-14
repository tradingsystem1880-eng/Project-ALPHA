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
from pathlib import Path
from typing import Any

from alpha_data.adapters.base import DataAdapter
from alpha_data.adapters.ccxt_adapter import SUPPORTED_CCXT_EXCHANGES, CCXTAdapter
from alpha_data.adapters.stooq_adapter import StooqAdapter
from alpha_data.adapters.tiingo_adapter import TiingoAdapter
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
    asset_classes: tuple[str, ...]
    timeframes: tuple[str, ...]
    research_authority: bool
    paper_execution: bool
    budget_tier: str
    installed: bool
    configured: bool
    configuration_state: str
    verification_state: str
    verified_at: str | None
    last_receipt_id: str | None
    granted_capabilities: tuple[str, ...]
    recovery_action: str
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
            "asset_classes": list(self.asset_classes),
            "timeframes": list(self.timeframes),
            "research_authority": self.research_authority,
            "paper_execution": self.paper_execution,
            "budget_tier": self.budget_tier,
            "installed": self.installed,
            "configured": self.configured,
            "configuration_state": self.configuration_state,
            "verification_state": self.verification_state,
            "verified_at": self.verified_at,
            "last_receipt_id": self.last_receipt_id,
            "granted_capabilities": list(self.granted_capabilities),
            "recovery_action": self.recovery_action,
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
    asset_classes: tuple[str, ...],
    timeframes: tuple[str, ...],
    research_authority: bool,
    paper_execution: bool,
    budget_tier: str,
    factory: HistoricalAdapterFactory | None,
    environ: Mapping[str, str],
    module_available: ModuleAvailable,
    verification: Mapping[str, object],
) -> ProviderDefinition:
    installed = module_available(module)
    credentials = _credentials(credential_names, environ)
    configured = installed and all(credential.present for credential in credentials)
    granted = verification["granted_capabilities"]
    if not isinstance(granted, list | tuple):
        raise RuntimeError("provider verification capabilities must be a sequence")
    if not installed:
        configuration_state = "not_installed"
    elif provider_id == "finnhub" and not configured:
        configuration_state = "optional_disabled"
    elif credential_names and not configured:
        configuration_state = "needs_process_injection"
    elif credential_names:
        configuration_state = "process_injected_unverified"
    else:
        configuration_state = "available_without_credentials"
    return ProviderDefinition(
        id=provider_id,
        label=label,
        capabilities=capabilities,
        network_required=network_required,
        credential_env=credentials,
        options=options,
        limitations=limitations,
        asset_classes=asset_classes,
        timeframes=timeframes,
        research_authority=research_authority,
        paper_execution=paper_execution,
        budget_tier=budget_tier,
        installed=installed,
        configured=configured,
        configuration_state=configuration_state,
        verification_state=str(verification["verification_state"]),
        verified_at=(str(verification["verified_at"]) if verification["verified_at"] else None),
        last_receipt_id=(
            str(verification["last_receipt_id"]) if verification["last_receipt_id"] else None
        ),
        granted_capabilities=tuple(str(item) for item in granted),
        recovery_action=str(verification["recovery_action"]),
        historical_adapter_factory=factory,
    )


def provider_definitions(
    *,
    environ: Mapping[str, str] | None = None,
    module_available: ModuleAvailable = _module_available,
    data_dir: Path | None = None,
) -> tuple[ProviderDefinition, ...]:
    """Build the registry against current local packages and environment configuration."""
    env = os.environ if environ is None else environ
    from alpha_cli.provider_readiness import last_check_status

    def verification(provider_id: str) -> Mapping[str, object]:
        if provider_id == "finnhub" and not env.get("ALPHA_FINNHUB_API_KEY", "").strip():
            return {
                "verification_state": "optional_disabled",
                "verified_at": None,
                "last_receipt_id": None,
                "granted_capabilities": [],
                "recovery_action": "No action required unless Finnhub quote/news is wanted.",
            }
        if data_dir is None:
            return {
                "verification_state": "unverified",
                "verified_at": None,
                "last_receipt_id": None,
                "granted_capabilities": [],
                "recovery_action": "Run an explicit provider check from the Readiness Center.",
            }
        return last_check_status(data_dir, provider_id)

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
            asset_classes=("stock", "etf"),
            timeframes=("1D",),
            research_authority=False,
            paper_execution=False,
            budget_tier="free_audit_only",
            factory=YFinanceAdapter,
            environ=env,
            module_available=module_available,
            verification=verification("yfinance"),
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
            asset_classes=("crypto",),
            timeframes=("1D",),
            research_authority=True,
            paper_execution=False,
            budget_tier="free_public",
            factory=CCXTAdapter,
            environ=env,
            module_available=module_available,
            verification=verification("ccxt"),
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
            asset_classes=("stock", "etf"),
            timeframes=("1D",),
            research_authority=False,
            paper_execution=False,
            budget_tier="free_audit_only",
            factory=StooqAdapter,
            environ=env,
            module_available=module_available,
            verification=verification("stooq"),
        ),
        _definition(
            provider_id="quantpad",
            label="QuantPad (research-only)",
            capabilities=("research_bars",),
            module="alpha_data.adapters.quantpad_adapter",
            network_required=True,
            credential_names=("QUANTPAD_API_KEY",),
            options={},
            limitations=(
                "Research scratch data only (ADR-0018): never canonical authority, never a "
                "validation snapshot, never strategy evidence, never paper readiness.",
                "Daily sub-slice; intraday loading waits for the qualified lane (ADR-0023).",
                "Bulk access uses the official REST API only; no scraping, no redistribution.",
            ),
            asset_classes=("stock", "etf", "future"),
            timeframes=("1D",),
            research_authority=False,
            paper_execution=False,
            budget_tier="subscription_research",
            factory=None,
            environ=env,
            module_available=module_available,
            verification=verification("quantpad"),
        ),
        _definition(
            provider_id="tiingo",
            label="Tiingo End-of-Day",
            capabilities=("historical_bars", "corporate_actions"),
            module="alpha_data.adapters.tiingo_adapter",
            network_required=True,
            credential_names=("ALPHA_TIINGO_API_KEY",),
            options={
                "asset_class": ProviderOption(
                    label="Asset class",
                    choices=("stock", "etf"),
                    default="stock",
                )
            },
            limitations=(
                "Internal-use EOD data; the free tier is limited to 500 unique symbols per month.",
                "Daily research only; provider data is never called directly from the browser.",
            ),
            asset_classes=("stock", "etf"),
            timeframes=("1D",),
            research_authority=True,
            paper_execution=False,
            budget_tier="free_500_symbols",
            factory=TiingoAdapter,
            environ=env,
            module_available=module_available,
            verification=verification("tiingo"),
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
            asset_classes=("stock", "etf"),
            timeframes=("quote",),
            research_authority=False,
            paper_execution=False,
            budget_tier="free_optional",
            factory=None,
            environ=env,
            module_available=module_available,
            verification=verification("finnhub"),
        ),
        _definition(
            provider_id="binance",
            label="Binance Native Market Data + Local Sandbox Paper",
            capabilities=(
                "crypto_market_bars",
                "crypto_trades",
                "crypto_aggregate_trades",
                "crypto_book_snapshots",
                "live_bars",
                "live_quotes",
                "sandbox_paper",
            ),
            module="nautilus_trader.adapters.binance",
            network_required=True,
            credential_names=(),
            options={},
            limitations=(
                "Native public archives/REST are the CEX spot/futures history authority; spot, "
                "USD-M, and COIN-M identities remain distinct.",
                "Public Binance market data only; ALPHA never constructs Binance execution.",
                "Paper orders route exclusively to local Nautilus sandbox execution.",
            ),
            asset_classes=("crypto",),
            timeframes=("live", "1D"),
            research_authority=False,
            paper_execution=True,
            budget_tier="free_public",
            factory=None,
            environ=env,
            module_available=module_available,
            verification=verification("binance"),
        ),
        _definition(
            provider_id="ibkr",
            label="Interactive Brokers Paper (NautilusTrader)",
            capabilities=("live_quotes", "paper_execution", "reconciliation"),
            module="nautilus_trader.adapters.interactive_brokers",
            network_required=True,
            credential_names=(
                "TWS_USERNAME",
                "TWS_PASSWORD",
                "ALPHA_IBKR_PAPER_ACCOUNT",
                "ALPHA_IBKR_GATEWAY_IMAGE",
            ),
            options={},
            limitations=(
                "Paper account and port 4002 only; live-capital routing is absent.",
                "CME futures are connectivity probes only and require explicit dated micro "
                "contracts.",
            ),
            asset_classes=("stock", "etf", "future"),
            timeframes=("live",),
            research_authority=False,
            paper_execution=True,
            budget_tier="broker_external",
            factory=None,
            environ=env,
            module_available=module_available,
            verification=verification("ibkr"),
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


def provider_catalog(*, data_dir: Path | None = None) -> list[dict[str, Any]]:
    """Redacted JSON-ready provider catalog."""
    return [provider.to_dict() for provider in provider_definitions(data_dir=data_dir)]


def provider_option_choices(provider_id: str, option_name: str) -> tuple[str, ...]:
    """Resolve a finite option from the registry; fail loud on an internal unknown option."""
    provider = next((item for item in provider_definitions() if item.id == provider_id), None)
    if provider is None or option_name not in provider.options:
        raise RuntimeError(f"unknown provider option {provider_id}.{option_name}")
    return provider.options[option_name].choices
