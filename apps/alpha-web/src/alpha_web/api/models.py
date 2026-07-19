"""Strict response contracts for the workstation's stable JSON API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunListItem(StrictModel):
    run_id: str
    kind: str
    command: str | None
    label: str | None
    symbol: str | None
    symbols: list[str] | None
    passed: bool | None
    verdict: str | None
    mtime: float


class RunList(StrictModel):
    total: int
    items: list[RunListItem]


class RunDetail(StrictModel):
    run_id: str
    kind: str
    mtime: float
    manifest: dict[str, Any]
    has_equity: bool
    has_trades: bool
    has_tearsheet: bool
    has_forecast: bool
    has_nulls: bool
    has_trials: bool
    has_forecast_paths: bool
    has_propfirm_paths: bool
    has_origins: bool


class EquitySeries(StrictModel):
    ts: list[float]
    equity: list[float]
    drawdown: list[float]


class ForecastSeries(StrictModel):
    history_ts: list[float]
    history: list[float]
    forecast_ts: list[float]
    forecast: list[float]
    p10: list[float]
    q25: list[float]
    q75: list[float]
    p90: list[float]
    mean: list[float]


class ForecastPath(StrictModel):
    sample: int
    closes: list[float]


class ForecastPaths(StrictModel):
    samples: list[ForecastPath]
    ts: list[float]


class NullTier(StrictModel):
    tier: str
    statistics: list[float]


class NullTiers(StrictModel):
    tiers: list[NullTier]


class OptimTrial(StrictModel):
    trial: int
    returns: list[float]


class OptimTrials(StrictModel):
    trials: list[OptimTrial]


class PropfirmPathColumns(StrictModel):
    passed: list[bool]
    busted: list[bool]
    days_to_pass: list[float | None]
    payout: list[float]


class PropfirmPaths(StrictModel):
    paths: PropfirmPathColumns


class ForecastOrigins(StrictModel):
    origin_ts: list[float]
    pre_cutoff: list[bool]
    crps: list[float]
    crps_rw: list[float]
    crps_bootstrap: list[float]
    realized_end_return: list[float]
    median_end_return: list[float]
    hit: list[bool]
    cover50: list[bool]
    cover80: list[bool]
    cover90: list[bool]


class Candle(StrictModel):
    t: float
    o: float
    h: float
    low: float = Field(alias="l", serialization_alias="l")
    c: float
    v: float


class Candles(StrictModel):
    symbol: str
    snapshot_id: str | None
    bars: list[Candle]


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
    installed: bool
    configured: bool


class SystemDataDirectory(StrictModel):
    path: str
    exists: bool
    readable: bool
    writable: bool
    free_bytes: int


class SystemCounts(StrictModel):
    symbols: int
    snapshots: int


class NautilusStatus(StrictModel):
    pinned_version: str
    installed_version: str | None
    matches_pin: bool


class KronosCacheStatus(StrictModel):
    configured: bool
    path: str | None
    exists: bool
    local_only: bool


class SystemStatus(StrictModel):
    data_dir: SystemDataDirectory
    counts: SystemCounts
    nautilus: NautilusStatus
    kronos_cache: KronosCacheStatus
    paper_enabled: bool


class CommandOption(StrictModel):
    name: str
    flag: str | None
    type: str
    default: str | int | float | bool | list[str] | None
    required: bool
    multiple: bool
    help: str
    choices: list[str] | None


class CommandArgument(StrictModel):
    name: str
    type: str
    required: bool
    nargs: int


class CommandDefinition(StrictModel):
    id: str
    run_type: str | None
    args: list[CommandArgument]
    options: list[CommandOption]


class Symbols(StrictModel):
    symbols: list[str]


class JobStatus(StrictModel):
    job_id: str
    status: str
    session_id: str | None


class JobSummary(StrictModel):
    job_id: str
    command: str
    kind: str | None
    status: str
    created_at: float
    run_id: str | None
    session_id: str | None
    returncode: int | None
    n_lines: int


class JobDetail(JobSummary):
    lines: list[str]


type JsonScalar = str | int | float | bool | None


class PaperSession(StrictModel):
    schema_version: int
    session_id: str
    status: Literal["starting", "running", "stopping", "completed", "cancelled", "failed"]
    provider: str
    sandbox: Literal[True]
    symbol: str
    instrument_id: str
    strategy: str
    strategy_params: dict[str, JsonScalar]
    snapshot_id: str
    pid: int | None
    heartbeat_at: str
    started_at: str
    ended_at: str | None
    last_sequence: int
    terminal_error: str | None
    stale: bool


class PaperEvent(StrictModel):
    schema_version: int
    session_id: str
    sequence: int
    event_type: Literal[
        "lifecycle", "order", "fill", "rejection", "position", "reconciliation_warning"
    ]
    recorded_at: str
    ts_event_ns: int | None
    payload: dict[str, JsonScalar]


class WorkspaceMeta(StrictModel):
    slug: str
    name: str
    updated: float | None


class WorkspaceSaved(StrictModel):
    slug: str
    name: str


class WorkspaceLinkedContext(StrictModel):
    symbol: str | None = None
    start: str | None = None
    end: str | None = None
    runId: str | None = None


class WorkspaceDocument(StrictModel):
    name: str
    linked_context: WorkspaceLinkedContext
    dockview: dict[str, Any]
    updated: float | None = None


class Deleted(StrictModel):
    deleted: str


class RiskScenario(StrictModel):
    name: str
    sharpe: float | None
    annual_vol: float
    max_drawdown: float
    value_at_risk: float
    expected_shortfall: float
    total_return: float


class RiskReport(StrictModel):
    run_id: str
    confidence: float
    scenarios: list[RiskScenario]


class ScreenerQuote(StrictModel):
    symbol: str
    current: float
    change: float
    percent_change: float
    high: float
    low: float
    open: float
    prev_close: float


class ScreenerNewsItem(StrictModel):
    headline: str
    source: str
    url: str
    datetime: int
    summary: str


class ScreenerNews(StrictModel):
    symbol: str
    items: list[ScreenerNewsItem]


class ResearchRow(StrictModel):
    strategy: str
    total_return: float | None
    final_equity: float | None = None
    n_trades: int | None = None
    error: str | None


class ResearchReport(StrictModel):
    symbol: str
    n_bars: int
    ranked: list[ResearchRow]


class OptionGreeks(StrictModel):
    spot: float
    strike: float
    rate: float
    vol: float
    days: float
    kind: str
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    implied_vol: float | None = None
    market_price: float | None = None


class OptionCurvePoint(StrictModel):
    spot: float
    price: float
    delta: float
    gamma: float
    vega: float
    theta: float


class OptionCurve(StrictModel):
    strike: float
    vol: float
    days: float
    rate: float
    kind: str
    points: list[OptionCurvePoint] = Field(min_length=2)
