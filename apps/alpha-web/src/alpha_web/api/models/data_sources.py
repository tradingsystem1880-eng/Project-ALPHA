"""Data sources, providers and Kronos."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from ._base import StrictModel


class CredentialStatus(StrictModel):
    name: str
    present: bool


class ProviderOption(StrictModel):
    label: str
    choices: list[str]
    default: str


class ProviderDefinition(StrictModel):
    id: str
    label: str
    capabilities: list[str]
    network_required: bool
    credential_env: list[CredentialStatus]
    options: dict[str, ProviderOption]
    limitations: list[str]
    asset_classes: list[str]
    timeframes: list[str]
    research_authority: bool
    paper_execution: bool
    budget_tier: str
    installed: bool
    configured: bool
    configuration_state: Literal[
        "not_installed",
        "optional_disabled",
        "needs_process_injection",
        "process_injected_unverified",
        "available_without_credentials",
    ]
    verification_state: Literal[
        "verified",
        "unverified",
        "authentication_failed",
        "entitlement_denied",
        "rate_limited",
        "connectivity_failed",
        "schema_drift",
        "optional_disabled",
    ]
    verified_at: str | None
    last_receipt_id: str | None
    granted_capabilities: list[str]
    recovery_action: str


class ProviderCheckReceipt(StrictModel):
    schema_version: Literal[1]
    provider_id: str
    verification_state: Literal[
        "verified",
        "unverified",
        "authentication_failed",
        "entitlement_denied",
        "rate_limited",
        "connectivity_failed",
        "schema_drift",
        "optional_disabled",
    ]
    checked_at: str
    granted_capabilities: list[str]
    recovery_action: str
    details: dict[str, object]
    receipt_id: str
    content_sha256: str


class KronosCacheStatus(StrictModel):
    configured: bool
    path: str | None
    exists: bool
    local_only: bool


class Symbols(StrictModel):
    symbols: list[str]


class DataSnapshotRow(StrictModel):
    snapshot_id: str | None
    created_at: str | None
    source: str | None
    adapter_version: str | None
    parser_version: str | None
    symbols: list[str]
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class DataSnapshots(StrictModel):
    snapshots: list[DataSnapshotRow]


class DataSourceStatus(StrictModel):
    symbol: str
    provenance: dict[str, Any] | None
    promotion_pending: bool
    candidates: list[str]
    quarantined: list[str]


class FirstBar(StrictModel):
    symbol: str
    exchange: str
    first_bar_ts: str
    timeframe: str


class Ticker(StrictModel):
    """A displayed public last-trade quote; never stored, never a data authority."""

    symbol: str
    exchange: str
    last: float
    ts: str
