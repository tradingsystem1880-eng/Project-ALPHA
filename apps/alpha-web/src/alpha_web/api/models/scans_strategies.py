"""Scans and strategy definitions."""

from __future__ import annotations

from typing import Literal

from ._base import StrictModel


class ScanUniverse(StrictModel):
    kind: Literal["stored", "list"]
    symbols: list[str] | None = None


class ScanRecord(StrictModel):
    name: str
    rules: str
    universe: ScanUniverse
    checked_at: str | None


class ScanSummary(StrictModel):
    name: str
    rules: str | None = None
    universe: ScanUniverse | None = None
    checked_at: str | None = None
    error: str | None = None


class ScanList(StrictModel):
    scans: list[ScanSummary]
    authority: Literal["none"]


class ScanSaveRequest(StrictModel):
    name: str
    rules: str
    symbols: list[str] | None = None


class ScanRunRequest(StrictModel):
    as_of: str | None = None


class ScanRow(StrictModel):
    symbol: str
    signal: int
    bar_ts: float
    bar_date: str
    close: float
    values: dict[str, float]


class ScanSkipped(StrictModel):
    symbol: str
    reason: str


class ScanRunResult(StrictModel):
    scan: str
    rules: str
    rules_sha256: str
    as_of: str | None
    universe_as_of: str
    universe: ScanUniverse
    rows: list[ScanRow]
    skipped: list[ScanSkipped]
    authority: Literal["none"]


class ScanAlert(StrictModel):
    ts: str
    scan: str
    symbol: str
    previous: int | None
    signal: int
    bar_date: str
    close: float


class ScanCheck(StrictModel):
    scan: str
    checked_at: str
    rows: int
    skipped: int
    alerts: list[ScanAlert]
    authority: Literal["none"]


class ScanCheckResult(StrictModel):
    checks: list[ScanCheck]
    alerts: list[ScanAlert]
    authority: Literal["none"]


class ScanAlerts(StrictModel):
    alerts: list[ScanAlert]
    authority: Literal["none"]


class ScanDeleted(StrictModel):
    name: str
    deleted: bool


class ParamDefinition(StrictModel):
    name: str
    type: str
    default: float
    min: float | None
    max: float | None
    min_exclusive: bool
    max_exclusive: bool
    help: str


class StrategyDefinition(StrictModel):
    name: str
    params: list[ParamDefinition]
    has_tier1_surrogate: bool
    supports_live_paper: bool
